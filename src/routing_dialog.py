"""
routing_dialog.py — Dialogue de gestion des règles de routage.

Permet de définir, pour chaque projet, des règles glob qui déterminent
vers quel dépôt cible (WFD | RESS | BOTH | NONE) chaque fichier doit aller.

Priorité d'évaluation :
  1. Surcharge par fichier exact (onglet "Fichiers")
  2. Règles glob dans l'ordre priority DESC (onglet "Règles")
  3. Défaut : NONE
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from src import db as db_mod
from src import preferences as prefs_mod

# Couleurs par cible
_TARGET_COLORS = {
    "WFD":    "#0055cc",
    "RESS":   "#007700",
    "COMMUN": "#6600aa",
    "BOTH":   "#884400",
    "NONE":   "#888888",
}


class RoutingDialog:
    """Fenêtre modale de gestion des règles de routage."""

    def __init__(self, parent: tk.Misc, prefs: dict) -> None:
        self._prefs = prefs
        self._conn  = db_mod.get_db()
        self._project_id: int | None = None

        self._win = tk.Toplevel(parent)
        self._win.title("Règles de routage")
        self._win.grab_set()
        self._win.transient(parent)
        self._win.minsize(660, 420)
        self._win.columnconfigure(0, weight=1)
        self._win.rowconfigure(1, weight=1)

        self._build()
        _geom = prefs_mod.get(self._prefs, "routing_dialog", "geometry", default="")
        if _geom:
            self._win.geometry(_geom)
        self._win.protocol("WM_DELETE_WINDOW", self._close)
        self._win.wait_window()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # --- Sélecteur de projet ---
        top = ttk.Frame(self._win, padding=(10, 8, 10, 4))
        top.grid(row=0, column=0, sticky="ew")

        ttk.Label(top, text="Projet :").pack(side="left", padx=(0, 6))
        projects = prefs_mod.get(self._prefs, "projects", default=[])
        proj_labels = [f"{p.get('code', '?')} — {p.get('name', '?')}" for p in projects]
        self._proj_var = tk.StringVar()
        self._proj_combo = ttk.Combobox(
            top, textvariable=self._proj_var,
            values=proj_labels, state="readonly", width=44,
        )
        self._proj_combo.pack(side="left")
        self._proj_combo.bind("<<ComboboxSelected>>", self._on_project_selected)

        if self._conn is None:
            ttk.Label(top, text="⚠ Aucune base de données configurée",
                      foreground="#cc0000").pack(side="left", padx=(12, 0))

        # --- Notebook Règles / Fichiers ---
        nb = ttk.Notebook(self._win)
        nb.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))

        tab_rules = ttk.Frame(nb)
        tab_files = ttk.Frame(nb)
        nb.add(tab_rules, text="Règles glob")
        nb.add(tab_files, text="Surcharges par fichier")

        self._build_rules_tab(tab_rules)
        self._build_files_tab(tab_files)

        # --- Bouton Fermer ---
        bot = ttk.Frame(self._win, padding=(10, 0, 10, 8))
        bot.grid(row=2, column=0, sticky="e")
        ttk.Button(bot, text="Fermer", command=self._close).pack()

        # Pré-sélectionner le projet courant si disponible
        project = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        code = project.get("code", "")
        if code:
            for i, p in enumerate(projects):
                if p.get("code") == code:
                    self._proj_combo.current(i)
                    self._on_project_selected()
                    break

    def _close(self) -> None:
        prefs_mod.set_(self._prefs, "routing_dialog", "geometry", value=self._win.geometry())
        self._win.destroy()

    # ------------------------------------------------------------------
    # Onglet Règles glob
    # ------------------------------------------------------------------

    def _build_rules_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Treeview
        cols = ("pattern", "target", "strip_prefix", "priority")
        self._rules_tree = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        self._rules_tree.heading("pattern",      text="Motif (glob)")
        self._rules_tree.heading("target",       text="Cible",              anchor="center")
        self._rules_tree.heading("strip_prefix", text="Retirer le préfixe", anchor="w")
        self._rules_tree.heading("priority",     text="Priorité",           anchor="center")
        self._rules_tree.column("pattern",      width=250, stretch=True)
        self._rules_tree.column("target",       width=70,  stretch=False, anchor="center")
        self._rules_tree.column("strip_prefix", width=200, stretch=True,  anchor="w")
        self._rules_tree.column("priority",     width=60,  stretch=False, anchor="center")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._rules_tree.yview)
        self._rules_tree.configure(yscrollcommand=vsb.set)
        self._rules_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        for t, c in _TARGET_COLORS.items():
            self._rules_tree.tag_configure(t, foreground=c)

        self._rules_tree.bind("<Double-1>",         lambda _: self._edit_rule())
        self._rules_tree.bind("<<TreeviewSelect>>", self._on_rule_select)

        # Boutons
        bf = ttk.Frame(parent, padding=(0, 4, 0, 0))
        bf.grid(row=1, column=0, columnspan=2, sticky="ew")

        ttk.Button(bf, text="Ajouter…",  command=self._add_rule).pack(side="left", padx=(0, 4))
        self._btn_rule_edit   = ttk.Button(bf, text="Modifier…",  command=self._edit_rule,   state="disabled")
        self._btn_rule_edit.pack(side="left", padx=4)
        self._btn_rule_delete = ttk.Button(bf, text="Supprimer",  command=self._delete_rule, state="disabled")
        self._btn_rule_delete.pack(side="left", padx=4)

        ttk.Label(bf, text="Double-cliquez pour modifier. Priorité élevée = évaluée en premier.",
                  foreground="gray").pack(side="right")

    # ------------------------------------------------------------------
    # Onglet Surcharges par fichier
    # ------------------------------------------------------------------

    def _build_files_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        cols = ("path", "target", "dest_path")
        self._files_tree = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        self._files_tree.heading("path",      text="Chemin source (exact)")
        self._files_tree.heading("target",    text="Cible",            anchor="center")
        self._files_tree.heading("dest_path", text="Chemin destination", anchor="w")
        self._files_tree.column("path",      width=260, stretch=True)
        self._files_tree.column("target",    width=70,  stretch=False, anchor="center")
        self._files_tree.column("dest_path", width=220, stretch=True,  anchor="w")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._files_tree.yview)
        self._files_tree.configure(yscrollcommand=vsb.set)
        self._files_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        for t, c in _TARGET_COLORS.items():
            self._files_tree.tag_configure(t, foreground=c)

        self._files_tree.bind("<<TreeviewSelect>>", self._on_file_select)

        bf = ttk.Frame(parent, padding=(0, 4, 0, 0))
        bf.grid(row=1, column=0, columnspan=2, sticky="ew")

        ttk.Button(bf, text="Ajouter…", command=self._add_file_route).pack(side="left", padx=(0, 4))
        self._btn_file_delete = ttk.Button(bf, text="Supprimer", command=self._delete_file_route, state="disabled")
        self._btn_file_delete.pack(side="left", padx=4)

        ttk.Label(bf, text="Surcharge absolue — ignorée par les règles glob.",
                  foreground="gray").pack(side="right")

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def _on_project_selected(self, *_) -> None:
        if self._conn is None:
            messagebox.showwarning("Base de données",
                                   "Aucune base de données ouverte.\n"
                                   "Configurez le chemin dans Préférences → DB.",
                                   parent=self._win)
            return
        projects = prefs_mod.get(self._prefs, "projects", default=[])
        idx = self._proj_combo.current()
        if idx < 0 or idx >= len(projects):
            return
        project = projects[idx]
        self._project_id = db_mod.upsert_project(
            self._conn, project.get("code", ""), project.get("name", "")
        )
        self._reload_rules()
        self._reload_files()

    def _reload_rules(self) -> None:
        self._rules_tree.delete(*self._rules_tree.get_children())
        if self._conn is None or self._project_id is None:
            return
        for rule in db_mod.list_rules(self._conn, self._project_id):
            self._rules_tree.insert(
                "", "end", iid=str(rule["id"]),
                values=(rule["pattern"], rule["target"],
                        rule["strip_prefix"] or "", rule["priority"]),
                tags=(rule["target"],),
            )

    def _reload_files(self) -> None:
        self._files_tree.delete(*self._files_tree.get_children())
        if self._conn is None or self._project_id is None:
            return
        for fr in db_mod.list_file_routes(self._conn, self._project_id):
            self._files_tree.insert(
                "", "end", iid=str(fr["id"]),
                values=(fr["path"], fr["target"], fr["dest_path"] or ""),
                tags=(fr["target"],),
            )

    # ------------------------------------------------------------------
    # Actions règles
    # ------------------------------------------------------------------

    def _on_rule_select(self, *_) -> None:
        sel = bool(self._rules_tree.selection())
        self._btn_rule_edit.config(state="normal" if sel else "disabled")
        self._btn_rule_delete.config(state="normal" if sel else "disabled")

    def _add_rule(self) -> None:
        if self._project_id is None:
            messagebox.showwarning("Projet", "Sélectionnez d'abord un projet.", parent=self._win)
            return
        dlg = _RuleDialog(self._win, prefs=self._prefs)
        if dlg.result:
            db_mod.add_rule(self._conn, self._project_id, **dlg.result)
            self._reload_rules()

    def _edit_rule(self) -> None:
        sel = self._rules_tree.selection()
        if not sel:
            return
        vals = self._rules_tree.item(sel[0])["values"]
        dlg = _RuleDialog(self._win, data={
            "pattern":      vals[0],
            "target":       vals[1],
            "strip_prefix": vals[2],
            "priority":     int(vals[3]),
        }, prefs=self._prefs)
        if dlg.result:
            db_mod.update_rule(self._conn, int(sel[0]), **dlg.result)
            self._reload_rules()

    def _delete_rule(self) -> None:
        sel = self._rules_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Supprimer", "Supprimer cette règle ?", parent=self._win):
            return
        db_mod.delete_rule(self._conn, int(sel[0]))
        self._reload_rules()

    # ------------------------------------------------------------------
    # Actions surcharges fichier
    # ------------------------------------------------------------------

    def _on_file_select(self, *_) -> None:
        sel = bool(self._files_tree.selection())
        self._btn_file_delete.config(state="normal" if sel else "disabled")

    def _add_file_route(self) -> None:
        if self._project_id is None:
            messagebox.showwarning("Projet", "Sélectionnez d'abord un projet.", parent=self._win)
            return
        dlg = _FileRouteDialog(self._win, prefs=self._prefs)
        if dlg.result:
            db_mod.set_file_route(self._conn, self._project_id,
                                  dlg.result["path"], dlg.result["target"],
                                  dest_path=dlg.result.get("dest_path", ""))
            self._reload_files()

    def _delete_file_route(self) -> None:
        sel = self._files_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Supprimer", "Supprimer cette surcharge ?", parent=self._win):
            return
        # retrieve path from values then delete
        path = self._files_tree.item(sel[0])["values"][0]
        db_mod.delete_file_route(self._conn, self._project_id, path)
        self._reload_files()


# ---------------------------------------------------------------------------
# Mini-dialogues
# ---------------------------------------------------------------------------

class _RuleDialog:
    """Dialogue Ajouter / Modifier une règle glob."""

    def __init__(self, parent: tk.Misc, data: dict | None = None, prefs: dict | None = None) -> None:
        self.result: dict | None = None
        data = data or {}
        self._prefs = prefs

        self._win = tk.Toplevel(parent)
        self._win.title("Règle de routage")
        self._win.grab_set()
        self._win.transient(parent)
        self._win.resizable(False, False)
        self._win.columnconfigure(1, weight=1)

        ttk.Label(self._win, text="Motif (glob) :").grid(row=0, column=0, sticky="e", padx=(10, 6), pady=8)
        self._pat_var = tk.StringVar(value=data.get("pattern", ""))
        ttk.Entry(self._win, textvariable=self._pat_var, width=40).grid(
            row=0, column=1, columnspan=2, padx=(0, 10), pady=8, sticky="ew"
        )

        ttk.Label(self._win, text="Cible :").grid(row=1, column=0, sticky="e", padx=(10, 6), pady=8)
        self._target_var = tk.StringVar(value=data.get("target", "WFD"))
        ttk.Combobox(self._win, textvariable=self._target_var,
                     values=list(db_mod.TARGETS), state="readonly", width=10,
                     ).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=8)

        ttk.Label(self._win, text="Préfixe à retirer :").grid(row=2, column=0, sticky="e", padx=(10, 6), pady=8)
        self._strip_var = tk.StringVar(value=data.get("strip_prefix", ""))
        ttk.Entry(self._win, textvariable=self._strip_var, width=40).grid(
            row=2, column=1, columnspan=2, padx=(0, 10), pady=8, sticky="ew"
        )
        ttk.Label(self._win, text="Préfixe retiré du chemin DEV pour former le chemin dans le dépôt cible.",
                  foreground="gray").grid(row=3, column=0, columnspan=3,
                                          sticky="w", padx=10, pady=(0, 2))

        ttk.Label(self._win, text="Priorité :").grid(row=4, column=0, sticky="e", padx=(10, 6), pady=8)
        self._prio_var = tk.StringVar(value=str(data.get("priority", 0)))
        ttk.Entry(self._win, textvariable=self._prio_var, width=8).grid(
            row=4, column=1, sticky="w", padx=(0, 10), pady=8
        )

        ttk.Label(self._win, text="Ex. motif : COMMUN/WFD/**   strip : COMMUN/WFD/   cible : COMMUN",
                  foreground="gray").grid(row=5, column=0, columnspan=3,
                                          sticky="w", padx=10, pady=(0, 6))

        bf = ttk.Frame(self._win)
        bf.grid(row=6, column=0, columnspan=3, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(bf, text="OK",      width=10, command=self._ok).pack(side="left", padx=4)
        ttk.Button(bf, text="Annuler", width=10, command=self._close).pack(side="left", padx=4)

        self._win.protocol("WM_DELETE_WINDOW", self._close)
        _geom = prefs_mod.get(prefs, "rule_dialog", "geometry", default="") if prefs else ""
        if _geom:
            self._win.geometry(_geom)

        self._win.wait_window()

    def _close(self) -> None:
        if self._prefs is not None:
            prefs_mod.set_(self._prefs, "rule_dialog", "geometry", value=self._win.geometry())
        self._win.destroy()

    def _ok(self) -> None:
        pattern = self._pat_var.get().strip()
        if not pattern:
            return
        try:
            priority = int(self._prio_var.get())
        except ValueError:
            priority = 0
        self.result = {
            "pattern":      pattern,
            "target":       self._target_var.get(),
            "strip_prefix": self._strip_var.get().strip(),
            "priority":     priority,
        }
        self._close()


class _FileRouteDialog:
    """Dialogue Ajouter une surcharge par fichier."""

    def __init__(self, parent: tk.Misc, data: dict | None = None, prefs: dict | None = None) -> None:
        self.result: dict | None = None
        data = data or {}
        self._prefs = prefs

        self._win = tk.Toplevel(parent)
        self._win.title("Surcharge par fichier")
        self._win.grab_set()
        self._win.transient(parent)
        self._win.resizable(False, False)
        self._win.columnconfigure(1, weight=1)

        ttk.Label(self._win, text="Chemin (exact) :").grid(row=0, column=0, sticky="e", padx=(10, 6), pady=8)
        self._path_var = tk.StringVar(value=data.get("path", ""))
        ttk.Entry(self._win, textvariable=self._path_var, width=40).grid(
            row=0, column=1, padx=(0, 10), pady=8, sticky="ew"
        )

        ttk.Label(self._win, text="Cible :").grid(row=1, column=0, sticky="e", padx=(10, 6), pady=8)
        self._target_var = tk.StringVar(value=data.get("target", "WFD"))
        ttk.Combobox(self._win, textvariable=self._target_var,
                     values=list(db_mod.TARGETS), state="readonly", width=10,
                     ).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=8)

        ttk.Label(self._win, text="Chemin destination :").grid(row=2, column=0, sticky="e", padx=(10, 6), pady=8)
        self._dest_var = tk.StringVar(value=data.get("dest_path", ""))
        ttk.Entry(self._win, textvariable=self._dest_var, width=40).grid(
            row=2, column=1, padx=(0, 10), pady=8, sticky="ew"
        )
        ttk.Label(self._win, text="Chemin dans le dépôt cible (vide = même que source).",
                  foreground="gray").grid(row=3, column=0, columnspan=2,
                                          sticky="w", padx=10, pady=(0, 6))

        bf = ttk.Frame(self._win)
        bf.grid(row=4, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(bf, text="OK",      width=10, command=self._ok).pack(side="left", padx=4)
        ttk.Button(bf, text="Annuler", width=10, command=self._close).pack(side="left", padx=4)

        self._win.protocol("WM_DELETE_WINDOW", self._close)
        _geom = prefs_mod.get(prefs, "file_route_dialog", "geometry", default="") if prefs else ""
        if _geom:
            self._win.geometry(_geom)

        self._win.wait_window()

    def _close(self) -> None:
        if self._prefs is not None:
            prefs_mod.set_(self._prefs, "file_route_dialog", "geometry", value=self._win.geometry())
        self._win.destroy()

    def _ok(self) -> None:
        path = self._path_var.get().strip().replace("\\", "/")
        if not path:
            return
        self.result = {
            "path":      path,
            "target":    self._target_var.get(),
            "dest_path": self._dest_var.get().strip().replace("\\", "/"),
        }
        self._close()
