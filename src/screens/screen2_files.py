"""
screen2_files.py — Écran 2 : sélection des livrables.

Pipeline :
  1. À l'arrivée, calcule le diff Git dans un thread :
       tag courant WFD (screen 2)  vs.  tag n-1 WFD  (trouvé automatiquement)
       tag courant RESS             vs.  tag n-1 RESS
  2. Affiche la liste (Treeview) avec cases à cocher
  3. Permet l'ajout manuel de fichiers
  4. on_next() → sauvegarde la liste sélectionnée dans session["files"]
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

from src import git_ops
from src import preferences as prefs_mod
from src import db as db_mod
from src.logger import get_logger

log = get_logger()

_CHECKED   = "☑"
_UNCHECKED = "☐"

_STATUS_TEXT = {
    "A": "Ajouté",
    "M": "Modifié",
    "D": "Supprimé",
    "R": "Renommé",
    "T": "Type",
    "-": "Manuel",
}


class Screen2Files:
    title = "Sélection des livrables"

    def __init__(self, parent: ttk.Frame, wizard) -> None:
        self._wizard = wizard
        self._prefs  = wizard.get_prefs()
        self._files: list[dict] = []      # {checked, status, path, source}
        self._queue: queue.Queue = queue.Queue()

        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # --- Toolbar ---
        tb = ttk.Frame(self.frame)
        tb.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ttk.Button(tb, text="☑ Tout cocher",    command=self._check_all).pack(side="left", padx=(0, 4))
        ttk.Button(tb, text="☐ Tout décocher",  command=self._uncheck_all).pack(side="left", padx=(0, 4))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Label(tb, text="🔍").pack(side="left", padx=(0, 2))
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._on_filter_change())
        self._filter_entry = ttk.Entry(tb, textvariable=self._filter_var, width=24)
        self._filter_entry.pack(side="left", padx=(0, 4))
        ttk.Button(tb, text="✕", width=2, command=lambda: self._filter_var.set("")).pack(side="left", padx=(0, 6))
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(tb, text="⟳ Recalculer",     command=self._start_diff).pack(side="left")

        self._diff_status_var = tk.StringVar(value="")
        ttk.Label(tb, textvariable=self._diff_status_var, foreground="gray").pack(side="right", padx=4)

        # --- Treeview + scrollbars ---
        tree_frame = ttk.Frame(self.frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            tree_frame,
            columns=("check", "status", "path", "ver_num", "ver_maq", "dest_path", "source", "cible"),
            show="headings",
            selectmode="browse",
        )
        self._tree.heading("check",     text="")
        self._tree.heading("status",    text="Statut",             anchor="center")
        self._tree.heading("path",      text="Fichier (DEV)",       anchor="w")
        self._tree.heading("ver_num",   text="Version",            anchor="center")
        self._tree.heading("ver_maq",   text="Maquette",           anchor="center")
        self._tree.heading("dest_path", text="Destination (intég)",  anchor="w")
        self._tree.heading("source",    text="Dépôt",             anchor="center")
        self._tree.heading("cible",     text="Cible",              anchor="center")

        self._tree.column("check",     width=30,  minwidth=30,  stretch=False, anchor="center")
        self._tree.column("status",    width=95,  minwidth=70,  stretch=False, anchor="center")
        self._tree.column("path",      width=300, minwidth=150, stretch=True,  anchor="w")
        self._tree.column("ver_num",   width=70,  minwidth=60,  stretch=False, anchor="center")
        self._tree.column("ver_maq",   width=75,  minwidth=60,  stretch=False, anchor="center")
        self._tree.column("dest_path", width=260, minwidth=120, stretch=True,  anchor="w")
        self._tree.column("source",    width=60,  minwidth=50,  stretch=False, anchor="center")
        self._tree.column("cible",     width=60,  minwidth=50,  stretch=False, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._tree.bind("<Button-1>", self._on_click)

        # Couleurs par statut
        self._tree.tag_configure("added",    foreground="#007700")
        self._tree.tag_configure("modified", foreground="#0055cc")
        self._tree.tag_configure("deleted",  foreground="#cc0000")
        self._tree.tag_configure("manual",   foreground="#886600")
        self._tree.tag_configure("unchecked",foreground="#aaaaaa")
        # Couleurs cible (fond léger)
        self._tree.tag_configure("cible_WFD",    background="#e8f0ff")
        self._tree.tag_configure("cible_RESS",   background="#e8f5e8")
        self._tree.tag_configure("cible_COMMUN", background="#f3e8ff")
        self._tree.tag_configure("cible_BOTH",   background="#fff3e0")
        self._tree.tag_configure("cible_NONE",   background="#f5f5f5")

        # --- Résumé bas de page ---
        self._summary_var = tk.StringVar(value="Aucun fichier")
        ttk.Label(self.frame, textvariable=self._summary_var, foreground="gray").grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )

        self._wizard.set_next_enabled(False)

    # ------------------------------------------------------------------
    # Hook wizard
    # ------------------------------------------------------------------

    def on_shown(self) -> None:
        session_files = prefs_mod.get(self._prefs, "session", "files", default=None)
        if session_files is not None:
            # Restaurer la liste de session (revenir en arrière)
            self._files = session_files
            self._load_wfd_versions()
            self._update_summary()
        else:
            self._start_diff()

    # ------------------------------------------------------------------
    # Diff Git (thread)
    # ------------------------------------------------------------------

    def _start_diff(self) -> None:
        self._diff_status_var.set("Calcul en cours…")
        self._wizard.set_next_enabled(False)

        # On garde les fichiers ajoutés manuellement
        self._files = [f for f in self._files if f.get("source") == "Manuel"]
        self._refresh_tree()

        project  = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        dev_path = project.get("depot_dev", "")

        if not dev_path:
            self._diff_status_var.set("⚠ Dépôt DEV non configuré pour ce projet")
            self._wizard.set_next_enabled(True)
            return

        def run() -> None:
            source = "DEV"
            # 1. Diff HEAD~1 → HEAD
            self._queue.put(("status", "[DEV] Diff HEAD~1 → HEAD…"))
            diff_paths: set[tuple[str, str]] = set()
            try:
                for change_type, path in git_ops.get_diff_files_head_vs_prev(dev_path):
                    diff_paths.add((change_type, path))
                if not diff_paths:
                    self._queue.put(("warning", "[DEV] Aucun fichier modifié entre HEAD~1 et HEAD"))
            except Exception as exc:
                self._queue.put(("warning", f"[DEV] Diff impossible : {exc}"))

            # 3. Tous les fichiers au HEAD
            self._queue.put(("status", "[DEV] Lecture de tous les fichiers au HEAD…"))
            try:
                all_paths = git_ops.get_all_files_at_head(dev_path)
                diff_path_set = {p for _, p in diff_paths}
                diff_type_map = {p: ct for ct, p in diff_paths}
                for path in all_paths:
                    in_diff = path in diff_path_set
                    ct      = diff_type_map.get(path, "M")
                    self._queue.put(("file", (source, ct, path, in_diff)))
                # Fichiers supprimés (dans le diff mais absents du HEAD)
                for ct, path in diff_paths:
                    if ct == "D":
                        self._queue.put(("file", (source, "D", path, True)))
            except Exception as exc:
                self._queue.put(("warning", f"[DEV] Lecture impossible : {exc}"))

            self._queue.put(("done", None))

        threading.Thread(target=run, daemon=True).start()
        self._poll()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "status":
                    self._diff_status_var.set(payload)
                elif kind == "warning":
                    self._diff_status_var.set(payload)
                    log.warning(payload)
                elif kind == "file":
                    source, change_type, path, checked = payload
                    existing = {f["path"] for f in self._files}
                    if path not in existing:
                        self._files.append({
                            "checked": checked,
                            "in_diff": checked,  # conservé même si checked change plus tard
                            "status":  change_type,
                            "path":    path,
                            "source":  source,
                        })
                    self._refresh_tree()
                elif kind == "done":
                    total = len(self._files)
                    self._diff_status_var.set(f"Diff terminé — {total} fichier(s) trouvé(s)")
                    self._resolve_cibles()
                    if self._auto_update_v_files():
                        # Un amend a été effectué : relancer le diff pour refléter les .v mis à jour
                        self._diff_status_var.set("Fichiers .v mis à jour — recalcul du diff…")
                        self._start_diff()
                        return
                    self._load_wfd_versions()
                    self._update_summary()
                    return
        except queue.Empty:
            pass
        self.frame.after(50, self._poll)

    # ------------------------------------------------------------------
    # Résolution des cibles (DB)
    # ------------------------------------------------------------------

    def _resolve_cibles(self) -> None:
        conn = db_mod.get_db()
        if conn is None:
            return
        project = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        code    = project.get("code", "")
        if not code:
            return
        project_id = db_mod.get_project_id(conn, code)
        if project_id is None:
            return
        paths   = [f["path"] for f in self._files]
        routing = db_mod.resolve_routing_batch(conn, project_id, paths)
        for f in self._files:
            target, dest_path = routing.get(f["path"], ("NONE", f["path"]))
            f["cible"]     = target
            f["dest_path"] = dest_path
            if f["cible"] == "NONE":
                f["checked"] = False
        self._refresh_tree()

    # ------------------------------------------------------------------
    # Versions WFD
    # ------------------------------------------------------------------

    def _load_wfd_versions(self) -> None:
        """Lit les fichiers PARAM/<wfd>.v — DEV en priorité (après amend), sinon RESS."""
        project   = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        dev_root  = project.get("depot_dev", "")
        ress_root = project.get("depot_ress_local", "")
        for f in self._files:
            if f.get("cible") not in ("WFD", "BOTH"):
                continue
            if f.get("ver_num"):  # déjà renseigné (session restaurée)
                continue
            wfd_name = os.path.basename(f.get("dest_path") or f["path"])
            v_num, v_maq = None, None
            if dev_root:
                abs_v, _ = git_ops.find_v_file_path(dev_root, wfd_name)
                if abs_v:
                    v_num, v_maq = git_ops.read_v_file(abs_v)
            if v_num is None and ress_root:
                v_num, v_maq = git_ops.read_wfd_version(ress_root, wfd_name)
            if v_num is not None:
                f["ver_num"] = v_num
                f["ver_maq"] = v_maq or ""
        self._refresh_tree()

    # ------------------------------------------------------------------
    # Mise à jour automatique des fichiers .v
    # ------------------------------------------------------------------

    def _auto_update_v_files(self) -> bool:
        """
        Pour chaque WFD/BOTH présent dans le diff, vérifie si le fichier .v
        correspondant a aussi été modifié (cas 1 : rien à faire) ou non (cas 2).

        Cas 2 : incrémente VERSION_NUM dans le .v du dépôt DEV, recrée
        versions.txt, puis amende le dernier commit DEV avec ces changements.

        Dans tous les cas, si un WFD est dans le diff et que versions.txt
        n'est pas encore dans le diff, il est recréé et inclus dans l'amend.

        Retourne True si un amend a été effectué (le diff doit être relancé).
        """
        project  = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        dev_path = project.get("depot_dev", "")
        if not dev_path:
            return False

        # Chemins des fichiers présents dans le diff DEV (sans les ajouts manuels)
        diff_paths = {
            f["path"]
            for f in self._files
            if f.get("in_diff") and f.get("source") != "Manuel"
        }

        # Fichiers WFD/BOTH dans le diff
        wfd_in_diff = [
            f for f in self._files
            if f.get("in_diff")
            and f.get("source") != "Manuel"
            and f.get("cible") in ("WFD", "BOTH")
        ]

        if not wfd_in_diff:
            return False

        # Passe 1 : identifier les WFDs qui nécessitent un incrément automatique (cas 2)
        needs_increment: list[tuple[dict, str, str]] = []  # (file_dict, abs_v, rel_v)

        for f in wfd_in_diff:
            wfd_name = os.path.basename(f.get("dest_path") or f["path"])
            abs_v, rel_v = git_ops.find_v_file_path(dev_path, wfd_name)
            if abs_v is None:
                log.debug("[screen2] .v introuvable dans DEV pour : %s", wfd_name)
                continue
            if rel_v in diff_paths:
                # Cas 1 : l'utilisateur a déjà mis à jour le .v lui-même
                log.debug("[screen2] .v déjà dans le diff (cas 1) : %s", rel_v)
                continue
            needs_increment.append((f, abs_v, rel_v))

        if not needs_increment:
            return False

        # Confirmation utilisateur avant toute modification
        wfd_lines = "".join(
            f"  • {os.path.basename(f['dest_path'] or f['path'])}  ({rel_v})\n"
            for f, _, rel_v in needs_increment
        )
        confirmed = messagebox.askyesno(
            "Mise à jour automatique des fichiers .v",
            f"Les fichiers WFD suivants ont été modifiés mais leurs fichiers .v "
            f"ne sont pas inclus dans le commit :\n\n"
            f"{wfd_lines}\n"
            f"Le programme va :\n"
            f"  1. Incrémenter VERSION_NUM dans chaque fichier .v\n"
            f"  2. Reconstruire PARAM/versions.txt\n"
            f"  3. Amender le dernier commit DEV avec ces fichiers\n"
            f"  4. Recalculer la liste des livrables\n\n"
            f"Continuer ?",
            parent=self.frame,
        )
        if not confirmed:
            log.info("[screen2] Mise à jour .v annulée par l'utilisateur")
            return False

        # Passe 2 : effectuer les incréments
        to_amend: list[str] = []
        for f, abs_v, rel_v in needs_increment:
            result = git_ops.increment_v_file(abs_v)
            if result is None:
                log.warning("[screen2] Impossible d'incrémenter .v : %s", rel_v)
                continue
            new_ver, ver_maq = result
            log.info("[screen2] .v auto-incrémenté : %s → version %s (maq=%s)",
                     os.path.basename(f.get("dest_path") or f["path"]), new_ver, ver_maq)
            to_amend.append(rel_v)

        # Reconstruire versions.txt
        versions_rel = git_ops.rebuild_versions_txt(dev_path)
        if versions_rel and versions_rel not in diff_paths:
            to_amend.append(versions_rel)

        if not to_amend:
            return False

        # Dédupliquer (ordre stable)
        seen: set[str] = set()
        to_amend = [p for p in to_amend if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]

        self._diff_status_var.set(
            f"Mise à jour des fichiers .v ({len(to_amend)} fichier(s))…"
        )
        if not git_ops.amend_with_files(dev_path, to_amend):
            log.warning("[screen2] amend_with_files échoué — .v non commités")
            messagebox.showerror(
                "Erreur d'amend",
                "La mise à jour des fichiers .v a échoué (git commit --amend).\n"
                "Consultez les logs pour plus de détails.",
                parent=self.frame,
            )
            return False

        log.info("[screen2] Amend effectué avec : %s", to_amend)
        return True

    # ------------------------------------------------------------------
    # Treeview
    # ------------------------------------------------------------------

    def _refresh_tree(self) -> None:
        self._tree.delete(*self._tree.get_children())
        needle = self._filter_var.get().lower() if hasattr(self, "_filter_var") else ""
        # Fichiers cochés en premier, puis non cochés — ordre stable à l'intérieur de chaque groupe
        ordered = sorted(range(len(self._files)), key=lambda i: (not self._files[i]["checked"], self._files[i]["path"]))
        for i in ordered:
            f         = self._files[i]
            dest_path = f.get("dest_path") or f["path"]
            if needle and needle not in f["path"].lower() and needle not in dest_path.lower():
                continue
            label  = _STATUS_TEXT.get(f["status"], f["status"])
            source = f.get("source", "?")
            cible  = f.get("cible", "")
            chk    = "" if cible == "NONE" else (_CHECKED if f["checked"] else _UNCHECKED)

            # Mettre en évidence si le chemin destination diffère du source
            dest_display = dest_path if dest_path != f["path"] else ""

            if not f["checked"]:
                tag = "unchecked"
            elif source == "Manuel":
                tag = "manual"
            else:
                tag = {"A": "added", "M": "modified", "D": "deleted"}.get(f["status"], "modified")

            tags = (tag,)
            if cible in ("WFD", "RESS", "COMMUN", "BOTH", "NONE") and f["checked"]:
                tags = (tag, f"cible_{cible}")

            is_wfd  = cible in ("WFD", "BOTH")
            ver_num = f.get("ver_num", "") if is_wfd else ""
            ver_maq = f.get("ver_maq", "") if is_wfd else ""
            self._tree.insert("", "end", iid=str(i),
                              values=(chk, label, f["path"], ver_num, ver_maq, dest_display, source, cible),
                              tags=tags)

    def _on_click(self, event: tk.Event) -> None:
        if self._tree.identify_region(event.x, event.y) != "cell":
            return
        if self._tree.identify_column(event.x) != "#1":
            return
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        idx = int(iid)
        if self._files[idx].get("cible") == "NONE":
            return  # fichier exclu du routage — non sélectionnable
        self._files[idx]["checked"] = not self._files[idx]["checked"]
        self._refresh_tree()
        self._update_summary()

    def _on_filter_change(self) -> None:
        self._refresh_tree()
        self._update_summary()

    def _update_summary(self) -> None:
        needle   = self._filter_var.get().lower() if hasattr(self, "_filter_var") else ""
        total    = len(self._files)
        selected = sum(1 for f in self._files if f["checked"])
        visible  = sum(1 for f in self._files if not needle or needle in f["path"].lower())
        if needle:
            self._summary_var.set(f"{selected} fichier(s) sélectionné(s) — {visible}/{total} affiché(s)")
        else:
            self._summary_var.set(f"{selected} fichier(s) sélectionné(s) sur {total}")
        self._wizard.set_next_enabled(selected > 0)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _check_all(self) -> None:
        for f in self._files:
            if f.get("cible") != "NONE":
                f["checked"] = True
        self._refresh_tree()
        self._update_summary()

    def _uncheck_all(self) -> None:
        for f in self._files:
            f["checked"] = False
        self._refresh_tree()
        self._update_summary()

    def _add_manual(self) -> None:
        path = simpledialog.askstring(
            "Ajouter un fichier",
            "Chemin du fichier (relatif ou absolu) :",
            parent=self.frame,
        )
        if not path:
            return
        path = path.strip()
        if path in {f["path"] for f in self._files}:
            return
        self._files.append({"checked": True, "status": "-", "path": path, "source": "Manuel"})
        self._refresh_tree()
        self._update_summary()

    # ------------------------------------------------------------------
    # Hook on_next
    # ------------------------------------------------------------------

    def on_next(self) -> bool:
        selected = [f for f in self._files if f["checked"]]
        if not selected:
            return False
        prefs_mod.set_(self._prefs, "session", "files", value=selected)
        log.info(f"Livrables : {len(selected)} fichier(s) sélectionné(s)")
        return True
