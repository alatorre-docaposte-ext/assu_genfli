"""
screen3_delivery.py — Écran 3 : informations de livraison.

Layout (fidèle à la maquette step2.png) :
┌─ Entité émettrice ───┐  ┌─ Entité destinataire ───────────┐
│ Nom (gras)           │  │ Nom (gras)                       │
│ Client / Projet /    │  │ Client / Projet                  │
│ Mode livraison       │  │ Réception par : [____________]   │
│ Livreur : [_______]  │  └──────────────────────────────────┘
└──────────────────────┘
┌─ Fiche de livraison ─────────────────────────────────────────────┐
│ FLI_SGK_EXT_LIV_00198  (titre dynamique)                         │
│ Identifiant FLI : [198]   ┌─ Tags Git ─────────────────────────┐ │
│ Date référence  : [📅]   │ WFD maîtres : [v1.2.68-beta1]      │ │
│ Date livraison  : [📅]   │ Ressources  : [v1.2.78-beta1]      │ │
│                           └────────────────────────────────────┘ │
│ ☑ Livraison en environnement d'intégration                       │
│ ☑ Livraison d'éléments Quadient R15                              │
└──────────────────────────────────────────────────────────────────┘
"""

import datetime
import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from src import git_ops
from src import preferences as prefs_mod
from src import fli_pdf
from src.logger import get_logger
from src.widgets import DateEntry

log = get_logger()


class Screen3Delivery:
    title = "Informations de livraison"

    def __init__(self, parent: ttk.Frame, wizard) -> None:
        self._wizard = wizard
        self._prefs  = wizard.get_prefs()
        self._tag_queue: queue.Queue = queue.Queue()

        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        inner = ttk.Frame(self.frame)
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)
        inner.grid(row=0, column=0, sticky="nsew")

        self._build_emettrice(inner)
        self._build_destinataire(inner)
        self._build_fiche(inner)
        self._build_git_livraison(inner)

    # ------------------------------------------------------------------
    # Panneau entité émettrice
    # ------------------------------------------------------------------

    def _build_emettrice(self, parent: ttk.Frame) -> None:
        lv = prefs_mod.get(self._prefs, "livraison", default={})
        em = lv.get("emettrice", {})

        f = ttk.LabelFrame(parent, text="Informations sur l'entité émettrice", padding=10)
        f.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
        f.columnconfigure(1, weight=1)

        # Nom en gras
        ttk.Label(f, text=em.get("nom", "—"), font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )

        ttk.Label(f, text="Nom du client :").grid(row=1, column=0, sticky="w", pady=1)
        ttk.Label(f, text=em.get("client", "—")).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=1)

        ttk.Label(f, text="Nom du projet :").grid(row=2, column=0, sticky="w", pady=1)
        ttk.Label(f, text=em.get("projet", "—")).grid(row=2, column=1, sticky="w", padx=(6, 0), pady=1)

        ttk.Label(f, text="Mode de livraison :").grid(row=3, column=0, sticky="w", pady=1)
        ttk.Label(f, text=em.get("mode", "—")).grid(row=3, column=1, sticky="w", padx=(6, 0), pady=1)

        # Livreur (pré-rempli depuis préférences livraison puis général.username)
        ttk.Label(f, text="Livreur :").grid(row=5, column=0, sticky="w", padx=(0, 6), pady=4)
        default_livreur = (
            prefs_mod.get(self._prefs, "livraison", "emettrice", "reception_par", default="")
            or prefs_mod.get(self._prefs, "general", "username", default="")
        )
        session_livreur = (
            prefs_mod.get(self._prefs, "session", "emettrice", "livraison", default="")
            or default_livreur
        )
        self._livreur_var = tk.StringVar(value=session_livreur)
        ttk.Entry(f, textvariable=self._livreur_var).grid(row=5, column=1, sticky="ew", pady=4)

    # ------------------------------------------------------------------
    # Panneau entité destinataire
    # ------------------------------------------------------------------

    def _build_destinataire(self, parent: ttk.Frame) -> None:
        lv   = prefs_mod.get(self._prefs, "livraison", default={})
        dest = lv.get("destinataire", {})
        # Nom du projet côté destinataire : vient du projet sélectionné
        project = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        dest_projet = project.get("dest_projet", "—")

        f = ttk.LabelFrame(parent, text="Informations sur l'entité destinataire", padding=10)
        f.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))
        f.columnconfigure(1, weight=1)

        # Nom en gras
        ttk.Label(f, text=dest.get("nom", "—"), font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )

        ttk.Label(f, text="Nom du client :").grid(row=1, column=0, sticky="w", pady=1)
        ttk.Label(f, text=dest.get("client", "—")).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=1)

        ttk.Label(f, text="Nom du projet :").grid(row=2, column=0, sticky="w", pady=1)
        ttk.Label(f, text=dest_projet).grid(row=2, column=1, sticky="w", padx=(6, 0), pady=1)

        # Réception par
        ttk.Label(f, text="Réception par :").grid(row=4, column=0, sticky="e", padx=(0, 6), pady=4)
        default_recep = prefs_mod.get(self._prefs, "livraison", "destinataire", "reception_par", default="")
        session_recep = (
            prefs_mod.get(self._prefs, "session", "delivery", "reception_par", default="")
            or default_recep
        )
        self._reception_var = tk.StringVar(value=session_recep)
        ttk.Entry(f, textvariable=self._reception_var).grid(row=4, column=1, sticky="ew", pady=4)

    # ------------------------------------------------------------------
    # Panneau fiche de livraison
    # ------------------------------------------------------------------

    def _build_fiche(self, parent: ttk.Frame) -> None:
        f = ttk.LabelFrame(parent, text="Informations sur la fiche de livraison", padding=10)
        f.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 8))
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        # --- Titre FLI dynamique ---
        project = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        code    = project.get("code", "XXX").upper()
        last_id = prefs_mod.get(self._prefs, "livraison", "last_fli_id", default=0)
        next_id = last_id + 1

        self._fli_title_var = tk.StringVar()
        ttk.Label(f, textvariable=self._fli_title_var, font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        # --- Colonne gauche : ID + dates ---
        left = ttk.Frame(f)
        left.grid(row=1, column=0, columnspan=2, sticky="nsew")
        left.columnconfigure(1, weight=1)

        ttk.Label(left, text="Identifiant de la FLI :").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=5)
        session_id = prefs_mod.get(self._prefs, "session", "delivery", "fli_id", default="")
        self._fli_id_var = tk.StringVar(value=str(session_id) if session_id else "")
        self._fli_id_var.trace_add("write", lambda *_: self._update_fli_title())
        ttk.Entry(left, textvariable=self._fli_id_var, width=12).grid(row=0, column=1, sticky="w", pady=5)

        today = datetime.date.today()
        session_ref  = prefs_mod.get(self._prefs, "session", "delivery", "date_reference", default=None)
        session_liv  = prefs_mod.get(self._prefs, "session", "delivery", "date_livraison",  default=None)
        date_ref = self._parse_date(session_ref, today)
        date_liv = self._parse_date(session_liv, today)

        ttk.Label(left, text="Date de référence :").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=5)
        self._date_ref = DateEntry(left, initial=date_ref)
        self._date_ref.grid(row=1, column=1, sticky="w", pady=5)

        ttk.Label(left, text="Date de livraison :").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=5)
        self._date_liv = DateEntry(left, initial=date_liv)
        self._date_liv.grid(row=2, column=1, sticky="w", pady=5)

        # --- Checkboxes ---
        chk_frame = ttk.Frame(f)
        chk_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ttk.Label(chk_frame, text="Livraison en environnement d'intégration").pack(anchor="w", pady=(0, 4))

        self._update_fli_title()

    # ------------------------------------------------------------------
    # Fieldset Livraison git
    # ------------------------------------------------------------------

    def _build_git_livraison(self, parent: ttk.Frame) -> None:
        f = ttk.LabelFrame(parent, text="Livraison git", padding=10)
        f.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        f.columnconfigure(1, weight=1)

        session_quadient = prefs_mod.get(self._prefs, "session", "delivery", "quadient_r15", default=True)
        self._quadient_r15_var = tk.BooleanVar(value=session_quadient)
        ttk.Checkbutton(
            f,
            text="Livraison d'éléments Quadient R15",
            variable=self._quadient_r15_var,
            command=self._on_quadient_changed,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(f, text="Message de commit :").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=5)
        ttk.Label(f, textvariable=self._fli_title_var,
                  font=("Segoe UI", 11, "bold"), foreground="#0055cc").grid(row=1, column=1, sticky="w", pady=5)

        # --- Tags Git ---
        tags_frame = ttk.LabelFrame(f, text="Tags Git", padding=8)
        tags_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        tags_frame.columnconfigure(1, weight=1)

        session_tag_wfd  = prefs_mod.get(self._prefs, "session", "delivery", "tag_wfd",       default="")
        session_tag_ress = prefs_mod.get(self._prefs, "session", "delivery", "tag_ressources", default="")
        self._tag_wfd_var  = tk.StringVar(value=session_tag_wfd)
        self._tag_ress_var = tk.StringVar(value=session_tag_ress)

        ttk.Label(tags_frame, text="WFD maîtres :").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=5)
        self._combo_wfd = ttk.Combobox(tags_frame, textvariable=self._tag_wfd_var, state="normal", width=22)
        self._combo_wfd.grid(row=0, column=1, sticky="ew", pady=5)
        self._combo_wfd.bind("<KeyRelease>", lambda e: self._filter_combo(self._combo_wfd, self._tag_wfd_var, "_tags_wfd"))

        ttk.Label(tags_frame, text="Ressources :").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=5)
        self._combo_ress = ttk.Combobox(tags_frame, textvariable=self._tag_ress_var, state="normal", width=22)
        self._combo_ress.grid(row=1, column=1, sticky="ew", pady=5)
        self._combo_ress.bind("<KeyRelease>", lambda e: self._filter_combo(self._combo_ress, self._tag_ress_var, "_tags_ress"))

        self._tags_wfd:  list[str] = []
        self._tags_ress: list[str] = []

        # Désactiver "Livrer" jusqu'à la fin du chargement des tags
        self._wizard.set_next_enabled(False)
        # Charge les tags en arrière-plan
        self._start_tag_loading()

    def _on_quadient_changed(self) -> None:
        pass  # Placeholder pour extensions futures

    # ------------------------------------------------------------------
    # Chargement asynchrone des tags
    # ------------------------------------------------------------------

    def _start_tag_loading(self) -> None:
        project   = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        code      = project.get("code", "").upper()
        wfd_path  = project.get("depot_wfd_local",  "")
        ress_path = project.get("depot_ress_local", "")

        def run() -> None:
            if wfd_path:
                log.info("[screen3] Chargement WFD  cwd=%s", wfd_path)
                all_tags = git_ops.get_tags(wfd_path)
                next_tag = git_ops.get_next_beta1_tag(wfd_path)
                fli      = git_ops.get_last_fli_commit(wfd_path, code) if code else None
                log.info("[screen3] WFD  tags=%d  next_beta1=%r  fli=%s",
                         len(all_tags), next_tag, fli["message"] if fli else "—")
                self._tag_queue.put(("wfd", all_tags, next_tag, fli))
            else:
                log.info("[screen3] WFD  aucun chemin local configuré")
            if ress_path:
                log.info("[screen3] Chargement RESS  cwd=%s", ress_path)
                all_tags = git_ops.get_tags(ress_path)
                next_tag = git_ops.get_next_beta1_tag(ress_path)
                fli      = git_ops.get_last_fli_commit(ress_path, code) if code else None
                log.info("[screen3] RESS  tags=%d  next_beta1=%r  fli=%s",
                         len(all_tags), next_tag, fli["message"] if fli else "—")
                self._tag_queue.put(("ress", all_tags, next_tag, fli))
            else:
                log.info("[screen3] RESS  aucun chemin local configuré")
            self._tag_queue.put(("done", None, None, None))

        threading.Thread(target=run, daemon=True).start()
        self._poll_tags()

    def _poll_tags(self) -> None:
        try:
            while True:
                kind, tags, next_tag, fli = self._tag_queue.get_nowait()
                if kind == "wfd":
                    if tags:
                        self._tags_wfd = tags
                        self._combo_wfd["values"] = tags
                    if next_tag:
                        self._tag_wfd_var.set(next_tag)
                    if fli:
                        self._last_fli_wfd = fli
                elif kind == "ress":
                    if tags:
                        self._tags_ress = tags
                        self._combo_ress["values"] = tags
                    if next_tag:
                        self._tag_ress_var.set(next_tag)
                    if fli:
                        self._last_fli_ress = fli
                elif kind == "done":
                    self._apply_fli_id()
                    self._wizard.set_next_enabled(True)
                    return
        except queue.Empty:
            pass
        self.frame.after(100, self._poll_tags)

    def _apply_fli_id(self) -> None:
        """Choisit le commit FLI le plus récent entre WFD et RESS et pré-remplit l'ID."""
        wfd_fli  = getattr(self, "_last_fli_wfd",  None)
        ress_fli = getattr(self, "_last_fli_ress", None)
        candidates = [f for f in (wfd_fli, ress_fli) if f is not None]
        if not candidates:
            log.info("[screen3] FLI auto-détection : aucun commit FLI trouvé")
            return
        best = max(candidates, key=lambda f: f["date"])
        next_id = best["fli_id"] + 1
        log.info("[screen3] FLI auto-détecté : %s (date=%s) → prochain id=%d",
                 best["message"], best["date"].strftime("%Y-%m-%d %H:%M"), next_id)
        self._fli_id_var.set(str(next_id))
        self._update_fli_title()

    def _filter_combo(self, combo: ttk.Combobox, var: tk.StringVar, tags_attr: str) -> None:
        """Filtre les valeurs de la combobox selon la saisie."""
        typed   = var.get().lower()
        all_tags: list[str] = getattr(self, tags_attr, [])
        filtered = [t for t in all_tags if typed in t.lower()]
        combo["values"] = filtered if filtered else all_tags
        if filtered and not combo.winfo_ismapped():
            combo.event_generate("<Down>")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_fli_title(self, *_) -> None:
        project = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        code = project.get("code", "XXX").upper()
        try:
            fli_id = int(self._fli_id_var.get())
        except ValueError:
            fli_id = 0
        self._fli_title_var.set(f"FLI_{code}_EXT_LIV_{fli_id:05d}")

    @staticmethod
    def _parse_date(value, fallback: datetime.date) -> datetime.date:
        if isinstance(value, datetime.date):
            return value
        if isinstance(value, str):
            try:
                return datetime.datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                pass
        return fallback

    # ------------------------------------------------------------------
    # Hooks wizard
    # ------------------------------------------------------------------

    def on_shown(self) -> None:
        pass

    def on_next(self) -> bool:
        """Valide, sauvegarde et ouvre la fenêtre de confirmation/livraison."""
        try:
            fli_id = int(self._fli_id_var.get())
            if fli_id <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Champ invalide",
                "L'identifiant de la FLI doit être un entier positif.",
                parent=self.frame,
            )
            return False

        delivery = {
            "livreur":         self._livreur_var.get(),
            "reception_par":   self._reception_var.get(),
            "fli_id":          fli_id,
            "date_reference":  self._date_ref.get().strftime("%Y-%m-%d"),
            "date_livraison":  self._date_liv.get().strftime("%Y-%m-%d"),
            "tag_wfd":         self._tag_wfd_var.get(),
            "tag_ressources":  self._tag_ress_var.get(),
            "quadient_r15":    self._quadient_r15_var.get(),
            "commit_message":  self._fli_title_var.get(),
            "fli_title":       self._fli_title_var.get(),
        }
        prefs_mod.set_(self._prefs, "session", "delivery", value=delivery)
        log.info("Livraison configurée : %s — livreur=%s",
                 delivery["fli_title"], delivery["livreur"])

        _DeliveryConfirmDialog(self.frame, self._prefs, delivery)
        return True


# ---------------------------------------------------------------------------
# Fenêtre de confirmation / génération des FLI
# ---------------------------------------------------------------------------

class _DeliveryConfirmDialog:
    """
    Fenêtre modale affichant le résumé de la livraison et permettant
    de générer les PDFs FLI (un par dépôt cible).
    """

    _REPO_TARGETS: dict[str, tuple[str, ...]] = {
        "WFD":    ("WFD", "BOTH"),
        "RESS":   ("RESS", "BOTH"),
        "COMMUN": ("COMMUN",),
    }

    def __init__(self, parent: tk.Misc, prefs: dict, delivery: dict) -> None:
        self._prefs    = prefs
        self._delivery = delivery
        self._log      = get_logger()

        # Fichiers cochés depuis la session
        session_files: list[dict] = prefs_mod.get(prefs, "session", "files", default=[]) or []
        self._checked = [f for f in session_files if f.get("checked")]

        # Fichiers par repo
        self._repo_files: dict[str, list[dict]] = {}
        for repo, targets in self._REPO_TARGETS.items():
            subset = [f for f in self._checked if f.get("cible") in targets]
            if subset:
                self._repo_files[repo] = subset

        project = prefs_mod.get(prefs, "session", "selected_project", default={})
        code    = project.get("code", "XXX").upper()
        fli_id  = delivery.get("fli_id", 0)
        self._fli_ids: dict[str, str] = {
            repo: f"FLI_{code}_EXT_{repo}_LIV_{fli_id:05d}"
            for repo in self._repo_files
        }

        # Dossier de sortie par défaut
        default_out = prefs_mod.get(prefs, "general", "output_dir", default="") or os.path.join(
            os.path.expanduser("~"), "Documents"
        )
        self._out_var = tk.StringVar(value=default_out)

        self._win = tk.Toplevel(parent)
        self._win.title("Confirmation de livraison")
        self._win.grab_set()
        self._win.transient(parent)
        self._win.resizable(True, False)
        self._win.minsize(540, 30)
        self._win.columnconfigure(0, weight=1)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        saved_geom = prefs_mod.get(prefs, "delivery_confirm_dialog", "geometry", default="")
        if saved_geom:
            self._win.geometry(saved_geom)

        self._build()
        self._win.wait_window()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        pad = {"padx": 16, "pady": (6, 0)}

        # --- Titre ---
        ttk.Label(self._win, text="Livraison prête à générer",
                  font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 4))

        # --- Résumé livraison ---
        d = self._delivery
        project = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        summary_lines = [
            ("Projet",           project.get("name", "—")),
            ("FLI (base)",       d.get("fli_title", "—")),
            ("Livreur",          d.get("livreur", "—")),
            ("Date de livraison", d.get("date_livraison", "—")),
            ("Tag WFD",          d.get("tag_wfd", "—") or "—"),
            ("Tag Ressources",   d.get("tag_ressources", "—") or "—"),
        ]
        summary_f = ttk.LabelFrame(self._win, text="Résumé", padding=8)
        summary_f.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 8))
        summary_f.columnconfigure(1, weight=1)
        for i, (lbl, val) in enumerate(summary_lines):
            ttk.Label(summary_f, text=f"{lbl} :", foreground="gray").grid(
                row=i, column=0, sticky="w", padx=(0, 8), pady=1)
            ttk.Label(summary_f, text=val, font=("Segoe UI", 9, "bold")).grid(
                row=i, column=1, sticky="w", pady=1)

        # --- PDFs à générer ---
        pdf_f = ttk.LabelFrame(self._win, text="Fiches de livraison à générer", padding=8)
        pdf_f.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        pdf_f.columnconfigure(1, weight=1)
        if not self._repo_files:
            ttk.Label(pdf_f, text="Aucun fichier sélectionné.",
                      foreground="#cc0000").grid(row=0, column=0, columnspan=2, sticky="w")
        else:
            for i, (repo, files) in enumerate(self._repo_files.items()):
                fli_id_str = self._fli_ids[repo]
                ttk.Label(pdf_f, text=f"{fli_id_str}.pdf",
                          font=("Segoe UI", 9, "bold")).grid(
                    row=i, column=0, sticky="w", pady=2)
                ttk.Label(pdf_f, text=f"{len(files)} fichier(s)",
                          foreground="gray").grid(row=i, column=1, sticky="w", padx=(8, 0))

        # --- Dossier de sortie ---
        out_f = ttk.Frame(self._win, padding=(16, 0, 16, 0))
        out_f.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        out_f.columnconfigure(1, weight=1)
        ttk.Label(out_f, text="Dossier de sortie :").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(out_f, textvariable=self._out_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(out_f, text="Parcourir…", command=self._browse_output).grid(
            row=0, column=2, padx=(6, 0))

        # --- Statut ---
        self._status_var = tk.StringVar(value="")
        self._status_lbl = ttk.Label(self._win, textvariable=self._status_var,
                                     foreground="#006600", wraplength=500)
        self._status_lbl.grid(row=4, column=0, sticky="w", padx=16, pady=(0, 4))

        # --- Boutons ---
        btn_f = ttk.Frame(self._win, padding=(16, 0, 16, 14))
        btn_f.grid(row=5, column=0, sticky="e")
        self._btn_generate = ttk.Button(btn_f, text="Générer les FLI",
                                        command=self._generate,
                                        state="disabled" if not self._repo_files else "normal")
        self._btn_generate.pack(side="left", padx=(0, 6))
        self._btn_open = ttk.Button(btn_f, text="Ouvrir le dossier",
                                    command=self._open_folder, state="disabled")
        self._btn_open.pack(side="left", padx=(0, 6))
        ttk.Button(btn_f, text="Fermer", command=self._on_close).pack(side="left")

    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        prefs_mod.set_(self._prefs, "delivery_confirm_dialog", "geometry",
                       value=self._win.geometry())
        self._win.destroy()

    # ------------------------------------------------------------------

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(
            title="Dossier de sortie pour les PDF",
            initialdir=self._out_var.get() or os.path.expanduser("~"),
            parent=self._win,
        )
        if folder:
            self._out_var.set(folder)
            prefs_mod.set_(self._prefs, "general", "output_dir", value=folder)

    def _generate(self) -> None:
        out_dir = self._out_var.get().strip()
        if not out_dir:
            messagebox.showwarning("Dossier manquant",
                                   "Veuillez sélectionner un dossier de sortie.",
                                   parent=self._win)
            return
        os.makedirs(out_dir, exist_ok=True)

        self._btn_generate.config(state="disabled")
        self._status_var.set("Génération en cours…")
        self._win.update_idletasks()

        context = fli_pdf.build_context(self._prefs, self._delivery)
        generated: list[str] = []
        errors: list[str] = []

        for repo, files in self._repo_files.items():
            fli_id_str = self._fli_ids[repo]
            out_path   = os.path.join(out_dir, f"{fli_id_str}.pdf")
            json_path  = os.path.join(out_dir, f"{fli_id_str}.json")
            try:
                fli_pdf.generate_fli(out_path, repo, fli_id_str, context, files)
                fli_pdf.generate_fli_json(json_path, repo, fli_id_str, context, files)
                generated.append(out_path)
                self._log.info("[fli_pdf] Généré : %s  (%d fichiers)", out_path, len(files))
            except Exception as exc:
                errors.append(f"{repo}: {exc}")
                self._log.error("[fli_pdf] Erreur %s : %s", repo, exc)

        if errors:
            self._status_var.set("⚠ Erreurs : " + " | ".join(errors))
            self._status_lbl.config(foreground="#cc0000")
        else:
            self._status_var.set(f"✓ {len(generated)} PDF(s) générés dans {out_dir}")
            self._status_lbl.config(foreground="#006600")
            self._btn_open.config(state="normal")

        self._btn_generate.config(state="normal")
        self._generated_dir = out_dir

    def _open_folder(self) -> None:
        folder = getattr(self, "_generated_dir", self._out_var.get())
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
