"""
screen2_delivery.py — Écran 2 : informations de livraison.

Layout (fidèle à la maquette step2.png) :
┌─ Entité émettrice ───┐  ┌─ Entité destinataire ───────────┐
│ Nom (gras)           │  │ Nom (gras)                       │
│ Client / Projet /    │  │ Client / Projet                  │
│ Mode livraison       │  │ Réception par : [____________]   │
│ Livreur : [_______]  │  └──────────────────────────────────┘
└──────────────────────┘
┌─ Fiche de livraison ─────────────────────────────────────────────┐
│ FLI_SGK_EXT_LIV00198  (titre dynamique)                          │
│ Identifiant FLI : [198]   ┌─ Tags Git ─────────────────────────┐ │
│ Date référence  : [📅]   │ WFD maîtres : [v1.2.68-beta1]      │ │
│ Date livraison  : [📅]   │ Ressources  : [v1.2.78-beta1]      │ │
│                           └────────────────────────────────────┘ │
│ ☑ Livraison en environnement d'intégration                       │
│ ☑ Livraison d'éléments Quadient R15                              │
└──────────────────────────────────────────────────────────────────┘
"""

import datetime
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from src import git_ops
from src import preferences as prefs_mod
from src.logger import get_logger
from src.widgets import DateEntry

log = get_logger()


class Screen2Delivery:
    title = "Informations de livraison"

    def __init__(self, parent: ttk.Frame, wizard) -> None:
        self._wizard = wizard
        self._prefs  = wizard.get_prefs()
        self._tag_queue: queue.Queue = queue.Queue()

        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # Zone scrollable
        canvas = tk.Canvas(self.frame, highlightthickness=0)
        vsb    = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.frame.rowconfigure(0, weight=1)

        inner = ttk.Frame(canvas)
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.winfo_exists() and canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        canvas.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._build_emettrice(inner)
        self._build_destinataire(inner)
        self._build_fiche(inner)
        self._build_git_graph(inner)

        # Activer Suivant dès le début (tous les champs ont des valeurs par défaut valides)
        self._wizard.set_next_enabled(True)

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
        f.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
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
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
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

        # --- Colonne droite : Tags Git ---
        right = ttk.LabelFrame(f, text="Tags Git", padding=8)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        session_tag_wfd  = prefs_mod.get(self._prefs, "session", "delivery", "tag_wfd",       default="")
        session_tag_ress = prefs_mod.get(self._prefs, "session", "delivery", "tag_ressources", default="")
        self._tag_wfd_var  = tk.StringVar(value=session_tag_wfd)
        self._tag_ress_var = tk.StringVar(value=session_tag_ress)

        ttk.Label(right, text="WFD maîtres :").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=6)
        self._combo_wfd = ttk.Combobox(right, textvariable=self._tag_wfd_var, state="normal", width=22)
        self._combo_wfd.grid(row=0, column=1, sticky="ew", pady=6)
        self._combo_wfd.bind("<KeyRelease>", lambda e: self._filter_combo(self._combo_wfd, self._tag_wfd_var, "_tags_wfd"))

        ttk.Label(right, text="Ressources :").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=6)
        self._combo_ress = ttk.Combobox(right, textvariable=self._tag_ress_var, state="normal", width=22)
        self._combo_ress.grid(row=1, column=1, sticky="ew", pady=6)
        self._combo_ress.bind("<KeyRelease>", lambda e: self._filter_combo(self._combo_ress, self._tag_ress_var, "_tags_ress"))

        self._tags_wfd:  list[str] = []
        self._tags_ress: list[str] = []

        # Charge les tags en arrière-plan
        self._start_tag_loading()

        # --- Checkboxes ---
        chk_frame = ttk.Frame(f)
        chk_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ttk.Label(chk_frame, text="Livraison en environnement d'intégration").pack(anchor="w", pady=(0, 4))

        session_quadient = prefs_mod.get(self._prefs, "session", "delivery", "quadient_r15", default=True)
        self._quadient_r15_var = tk.BooleanVar(value=session_quadient)
        ttk.Checkbutton(
            chk_frame,
            text="Livraison d'éléments Quadient R15",
            variable=self._quadient_r15_var
        ).pack(anchor="w", pady=2)

        self._update_fli_title()

    # ------------------------------------------------------------------
    # Chargement asynchrone des tags
    # ------------------------------------------------------------------

    def _start_tag_loading(self) -> None:
        project = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        wfd_path  = project.get("depot_wfd_local",  "")
        ress_path = project.get("depot_ress_local", "")

        def run() -> None:
            if wfd_path:
                all_tags  = git_ops.get_tags(wfd_path)
                beta1_tag = git_ops.get_latest_beta1_tag(wfd_path)
                self._tag_queue.put(("wfd", all_tags, beta1_tag))
            if ress_path:
                all_tags  = git_ops.get_tags(ress_path)
                beta1_tag = git_ops.get_latest_beta1_tag(ress_path)
                self._tag_queue.put(("ress", all_tags, beta1_tag))
            self._tag_queue.put(("done", None, None))

        threading.Thread(target=run, daemon=True).start()
        self._poll_tags()

    def _poll_tags(self) -> None:
        try:
            while True:
                kind, tags, beta1_tag = self._tag_queue.get_nowait()
                if kind == "wfd" and tags:
                    self._tags_wfd = tags
                    self._combo_wfd["values"] = tags
                    # Pré-remplir avec le dernier *-beta1 si le champ est vide
                    if not self._tag_wfd_var.get() and beta1_tag:
                        self._tag_wfd_var.set(beta1_tag)
                elif kind == "ress" and tags:
                    self._tags_ress = tags
                    self._combo_ress["values"] = tags
                    if not self._tag_ress_var.get() and beta1_tag:
                        self._tag_ress_var.set(beta1_tag)
                elif kind == "done":
                    return
        except queue.Empty:
            pass
        self.frame.after(100, self._poll_tags)

    def _filter_combo(self, combo: ttk.Combobox, var: tk.StringVar, tags_attr: str) -> None:
        """Filtre les valeurs de la combobox selon la saisie."""
        typed   = var.get().lower()
        all_tags: list[str] = getattr(self, tags_attr, [])
        filtered = [t for t in all_tags if typed in t.lower()]
        combo["values"] = filtered if filtered else all_tags
        if filtered and not combo.winfo_ismapped():
            combo.event_generate("<Down>")

    # ------------------------------------------------------------------
    # Git graph (historique des commits)
    # ------------------------------------------------------------------

    def _build_git_graph(self, parent: ttk.Frame) -> None:
        self._graph_wfd_tree:  ttk.Treeview | None = None
        self._graph_ress_tree: ttk.Treeview | None = None
        self._commits_wfd:  list[dict] = []
        self._commits_ress: list[dict] = []
        self._graph_queue: queue.Queue = queue.Queue()

        lf = ttk.LabelFrame(parent, text="Historique Git", padding=8)
        lf.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)

        project   = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        wfd_path  = project.get("depot_wfd_local",  "")
        ress_path = project.get("depot_ress_local", "")

        self._graph_notebook = ttk.Notebook(lf)
        self._graph_notebook.grid(row=0, column=0, sticky="nsew")

        if wfd_path:
            tab_wfd = ttk.Frame(self._graph_notebook)
            self._graph_notebook.add(tab_wfd, text="WFD maîtres")
            self._graph_wfd_tree = self._build_graph_tree(tab_wfd)

        if ress_path:
            tab_ress = ttk.Frame(self._graph_notebook)
            self._graph_notebook.add(tab_ress, text="Ressources")
            self._graph_ress_tree = self._build_graph_tree(tab_ress)

        if wfd_path or ress_path:
            self._start_graph_loading(wfd_path, ress_path)

    def _build_graph_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        cols = ("tags", "hash", "date", "author", "message")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=9)
        tree.heading("tags",    text="Tags")
        tree.heading("hash",    text="Hash")
        tree.heading("date",    text="Date")
        tree.heading("author",  text="Auteur")
        tree.heading("message", text="Message")
        tree.column("tags",    width=190, stretch=False)
        tree.column("hash",    width=65,  stretch=False)
        tree.column("date",    width=130, stretch=False)
        tree.column("author",  width=110, stretch=False)
        tree.column("message", width=200, stretch=True)

        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        tree.tag_configure("selected_tag", background="#FFF3B0", font=("Segoe UI", 9, "bold"))
        tree.tag_configure("has_tag",      background="#E8F5E9")
        return tree

    def _start_graph_loading(self, wfd_path: str, ress_path: str) -> None:
        def run() -> None:
            if wfd_path:
                commits = git_ops.get_commit_log(wfd_path, max_count=60)
                self._graph_queue.put(("wfd", commits))
            if ress_path:
                commits = git_ops.get_commit_log(ress_path, max_count=60)
                self._graph_queue.put(("ress", commits))
            self._graph_queue.put(("done", None))

        threading.Thread(target=run, daemon=True).start()
        self._poll_graph()

    def _poll_graph(self) -> None:
        try:
            while True:
                kind, commits = self._graph_queue.get_nowait()
                if kind == "wfd":
                    self._commits_wfd = commits
                    if self._graph_wfd_tree:
                        self._fill_graph_tree(self._graph_wfd_tree, commits, self._tag_wfd_var.get())
                elif kind == "ress":
                    self._commits_ress = commits
                    if self._graph_ress_tree:
                        self._fill_graph_tree(self._graph_ress_tree, commits, self._tag_ress_var.get())
                elif kind == "done":
                    if self._graph_wfd_tree:
                        self._tag_wfd_var.trace_add("write", lambda *_: self._refresh_graph_highlights())
                    if self._graph_ress_tree:
                        self._tag_ress_var.trace_add("write", lambda *_: self._refresh_graph_highlights())
                    return
        except queue.Empty:
            pass
        self.frame.after(100, self._poll_graph)

    def _fill_graph_tree(self, tree: ttk.Treeview, commits: list[dict], selected_tag: str) -> None:
        tree.delete(*tree.get_children())
        scroll_to: str | None = None
        for c in commits:
            tag_names = c["tags"]
            tags_str  = "  ".join(sorted(tag_names)) if tag_names else ""
            if selected_tag and selected_tag in tag_names:
                row_tag = "selected_tag"
            elif tag_names:
                row_tag = "has_tag"
            else:
                row_tag = ""
            iid = tree.insert("", "end",
                              values=(tags_str, c["short_hash"], c["date"], c["author"], c["message"]),
                              tags=(row_tag,) if row_tag else ())
            if row_tag == "selected_tag":
                scroll_to = iid
        if scroll_to:
            tree.see(scroll_to)

    def _refresh_graph_highlights(self) -> None:
        if self._commits_wfd and self._graph_wfd_tree:
            self._fill_graph_tree(self._graph_wfd_tree, self._commits_wfd, self._tag_wfd_var.get())
        if self._commits_ress and self._graph_ress_tree:
            self._fill_graph_tree(self._graph_ress_tree, self._commits_ress, self._tag_ress_var.get())

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
        self._fli_title_var.set(f"FLI_{code}_EXT_LIV{fli_id:05d}")

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
        self._wizard.set_next_enabled(True)

    def on_next(self) -> bool:
        """Valide et sauvegarde les données de session."""
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
            "livreur":        self._livreur_var.get(),
            "reception_par":  self._reception_var.get(),
            "fli_id":         fli_id,
            "date_reference": self._date_ref.get().strftime("%Y-%m-%d"),
            "date_livraison": self._date_liv.get().strftime("%Y-%m-%d"),
            "tag_wfd":        self._tag_wfd_var.get(),
            "tag_ressources": self._tag_ress_var.get(),
            "quadient_r15":   self._quadient_r15_var.get(),
            "fli_title":      self._fli_title_var.get(),
        }

        prefs_mod.set_(self._prefs, "session", "delivery", value=delivery)
        log.info(f"Livraison configurée : {delivery['fli_title']} — livreur={delivery['livreur']}")
        return True
