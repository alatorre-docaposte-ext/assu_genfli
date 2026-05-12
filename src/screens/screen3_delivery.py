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
import re
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

    # Regex du format de tag Quadient R15
    _RE_QUADIENT_TAG = re.compile(r"^v1\.2\.")

    def _on_quadient_changed(self) -> None:
        """Filtre les comboboxes selon le flag Quadient R15."""
        self._apply_quadient_filter()

    def _apply_quadient_filter(self) -> None:
        """Restreint (ou restaure) les listes de tags selon la case Quadient R15."""
        quadient = self._quadient_r15_var.get()
        for combo, all_tags_attr, var in (
            (self._combo_wfd,  "_tags_wfd",  self._tag_wfd_var),
            (self._combo_ress, "_tags_ress", self._tag_ress_var),
        ):
            all_tags: list[str] = getattr(self, all_tags_attr, [])
            filtered = (
                [t for t in all_tags if self._RE_QUADIENT_TAG.match(t)]
                if quadient else all_tags
            )
            combo["values"] = filtered
            # Si la valeur courante ne correspond plus au filtre, on la réinitialise
            if quadient and var.get() and not self._RE_QUADIENT_TAG.match(var.get()):
                var.set(filtered[0] if filtered else "")

    # ------------------------------------------------------------------
    # Chargement asynchrone des tags
    # ------------------------------------------------------------------

    def _start_tag_loading(self) -> None:
        project   = prefs_mod.get(self._prefs, "session", "selected_project", default={})
        code      = project.get("code", "").upper()
        wfd_path  = project.get("depot_wfd_local",  "")
        ress_path = project.get("depot_ress_local", "")
        quadient  = self._quadient_r15_var.get()

        def _next_tag(path: str) -> str:
            return (
                git_ops.get_next_quadient_r15_tag(path)
                if quadient else
                git_ops.get_next_beta1_tag(path)
            )

        def run() -> None:
            if wfd_path:
                log.info("[screen3] Chargement WFD  cwd=%s", wfd_path)
                all_tags = git_ops.get_tags(wfd_path)
                next_tag = _next_tag(wfd_path)
                fli      = git_ops.get_last_fli_commit(wfd_path, code) if code else None
                log.info("[screen3] WFD  tags=%d  next=%r  fli=%s",
                         len(all_tags), next_tag, fli["message"] if fli else "—")
                self._tag_queue.put(("wfd", all_tags, next_tag, fli))
            else:
                log.info("[screen3] WFD  aucun chemin local configuré")
            if ress_path:
                log.info("[screen3] Chargement RESS  cwd=%s", ress_path)
                all_tags = git_ops.get_tags(ress_path)
                next_tag = _next_tag(ress_path)
                fli      = git_ops.get_last_fli_commit(ress_path, code) if code else None
                log.info("[screen3] RESS  tags=%d  next=%r  fli=%s",
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
                    self._apply_quadient_filter()
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

        if self._quadient_r15_var.get():
            bad_tags = [
                (label, val)
                for label, val in (
                    ("WFD maîtres",  self._tag_wfd_var.get()),
                    ("Ressources",   self._tag_ress_var.get()),
                )
                if val and not self._RE_QUADIENT_TAG.match(val)
            ]
            if bad_tags:
                details = "\n".join(f"• {lbl} : {val}" for lbl, val in bad_tags)
                messagebox.showwarning(
                    "Tag invalide",
                    "Livraison Quadient R15 : les tags doivent être de la forme v1.2.x\n\n"
                    + details,
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
    Fenêtre modale de livraison :
      1. Génération automatique des PDFs FLI à l'ouverture.
      2. Bouton "Livrer" : copie les fichiers vers les dépôts d'intégration,
         commit avec le message FLI et pose les tags Git.
    Journal en temps réel dans une zone de texte scrollable.
    """

    _REPO_TARGETS: dict[str, tuple[str, ...]] = {
        "WFD":    ("WFD",  "BOTH"),
        "RESS":   ("RESS", "BOTH"),
        "COMMUN": ("COMMUN",),
    }
    _REPO_LOCAL_KEY: dict[str, str] = {
        "WFD":    "depot_wfd_local",
        "RESS":   "depot_ress_local",
        "COMMUN": "depot_commun_local",
    }
    _REPO_REMOTE_KEY: dict[str, str] = {
        "WFD":    "depot_wfd_distant",
        "RESS":   "depot_ress_distant",
        "COMMUN": "depot_commun_distant",
    }
    _REPO_TAG_KEY: dict[str, str] = {
        "WFD":    "tag_wfd",
        "RESS":   "tag_ressources",
        "COMMUN": "tag_ressources",
    }

    def __init__(self, parent: tk.Misc, prefs: dict, delivery: dict) -> None:
        self._prefs    = prefs
        self._delivery = delivery
        self._log      = get_logger()
        self._queue: queue.Queue = queue.Queue()
        self._busy     = False

        session_files: list[dict] = prefs_mod.get(prefs, "session", "files", default=[]) or []
        self._checked = [f for f in session_files if f.get("checked")]

        self._repo_files: dict[str, list[dict]] = {}
        for repo, targets in self._REPO_TARGETS.items():
            subset = [f for f in self._checked if f.get("cible") in targets]
            if subset:
                self._repo_files[repo] = subset

        self._project = prefs_mod.get(prefs, "session", "selected_project", default={})
        code   = self._project.get("code", "XXX").upper()
        fli_id = delivery.get("fli_id", 0)
        self._fli_ids: dict[str, str] = {
            repo: f"FLI_{code}_EXT_{repo}_LIV_{fli_id:05d}"
            for repo in self._repo_files
        }

        default_out = prefs_mod.get(prefs, "general", "output_dir", default="") or os.path.join(
            os.path.expanduser("~"), "Documents"
        )
        self._out_var = tk.StringVar(value=default_out)

        self._win = tk.Toplevel(parent)
        self._win.title("Livraison")
        self._win.grab_set()
        self._win.transient(parent)
        self._win.resizable(True, True)
        self._win.minsize(620, 460)
        self._win.columnconfigure(0, weight=1)
        self._win.rowconfigure(2, weight=1)   # journal extensible
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        saved_geom = prefs_mod.get(prefs, "delivery_confirm_dialog", "geometry", default="")
        if saved_geom:
            self._win.geometry(saved_geom)

        self._build()
        self._win.after(100, self._start_pdf_generation)  # PDF auto
        self._poll()
        self._win.wait_window()

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        d = self._delivery

        # --- Résumé compact (2 colonnes) ---
        summary_f = ttk.LabelFrame(self._win, text="Livraison", padding=8)
        summary_f.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        summary_f.columnconfigure(1, weight=1)
        summary_f.columnconfigure(3, weight=1)
        rows = [
            ("FLI",            d.get("fli_title", "—"),              "Tag WFD",  d.get("tag_wfd",        "—") or "—"),
            ("Livreur",        d.get("livreur",   "—"),              "Tag RESS", d.get("tag_ressources", "—") or "—"),
            ("Date livraison", d.get("date_livraison", "—"),         "Fichiers", str(len(self._checked))),
        ]
        for r, (l1, v1, l2, v2) in enumerate(rows):
            ttk.Label(summary_f, text=f"{l1} :", foreground="gray").grid(
                row=r, column=0, sticky="w", padx=(0, 6), pady=1)
            ttk.Label(summary_f, text=v1, font=("Segoe UI", 9, "bold")).grid(
                row=r, column=1, sticky="w", pady=1)
            ttk.Label(summary_f, text=f"{l2} :", foreground="gray").grid(
                row=r, column=2, sticky="w", padx=(16, 6), pady=1)
            ttk.Label(summary_f, text=v2, font=("Segoe UI", 9, "bold")).grid(
                row=r, column=3, sticky="w", pady=1)

        # --- Dossier de sortie PDF ---
        out_f = ttk.Frame(self._win, padding=(12, 0))
        out_f.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        out_f.columnconfigure(1, weight=1)
        ttk.Label(out_f, text="Dossier PDF :").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(out_f, textvariable=self._out_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(out_f, text="…", width=3, command=self._browse_output).grid(
            row=0, column=2, padx=(4, 0))

        # --- Journal scrollable ---
        log_f = ttk.LabelFrame(self._win, text="Journal", padding=4)
        log_f.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 4))
        log_f.columnconfigure(0, weight=1)
        log_f.rowconfigure(0, weight=1)

        self._log_text = tk.Text(
            log_f, wrap="word", state="disabled",
            bg="#1e1e1e", fg="#d4d4d4",
            font=("Consolas", 9), relief="flat", height=16,
        )
        vsb = ttk.Scrollbar(log_f, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=vsb.set)
        self._log_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._log_text.tag_configure("ok",    foreground="#6dbf6d")
        self._log_text.tag_configure("warn",  foreground="#e0c060")
        self._log_text.tag_configure("error", foreground="#f47777")
        self._log_text.tag_configure("head",  foreground="#569cd6",
                                     font=("Consolas", 9, "bold"))

        # --- Boutons ---
        btn_f = ttk.Frame(self._win, padding=(12, 0, 12, 10))
        btn_f.grid(row=3, column=0, sticky="e")
        self._btn_deliver = ttk.Button(btn_f, text="Livrer",
                                       command=self._deliver, state="disabled")
        self._btn_deliver.pack(side="left", padx=(0, 6))
        self._btn_open = ttk.Button(btn_f, text="Ouvrir PDF",
                                    command=self._open_folder, state="disabled")
        self._btn_open.pack(side="left", padx=(0, 6))
        ttk.Button(btn_f, text="Fermer", command=self._on_close).pack(side="left")

    # ------------------------------------------------------------------
    # Log helper
    # ------------------------------------------------------------------

    def _append_log(self, text: str, tag: str = "") -> None:
        """Ajoute une ligne dans le journal (appelé depuis le thread principal)."""
        if not tag:
            s = text.strip()
            if s.startswith(("✔", "✓")):
                tag = "ok"
            elif s.startswith("✘"):
                tag = "error"
            elif s.startswith(("⚠", "►")):
                tag = "warn"
        self._log_text.configure(state="normal")
        self._log_text.insert("end", text + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Génération automatique des PDFs
    # ------------------------------------------------------------------

    def _start_pdf_generation(self) -> None:
        out_dir = self._out_var.get().strip()
        if not out_dir:
            self._append_log("⚠ Dossier de sortie non défini — PDFs non générés", "warn")
            return

        os.makedirs(out_dir, exist_ok=True)
        self._append_log("Génération des fiches de livraison (PDF)…", "head")

        context = fli_pdf.build_context(self._prefs, self._delivery)

        def run() -> None:
            ok = True
            for repo, files in self._repo_files.items():
                fli_id_str = self._fli_ids[repo]
                out_path   = os.path.join(out_dir, f"{fli_id_str}.pdf")
                json_path  = os.path.join(out_dir, f"{fli_id_str}.json")
                try:
                    fli_pdf.generate_fli(out_path, repo, fli_id_str, context, files)
                    fli_pdf.generate_fli_json(json_path, repo, fli_id_str, context, files)
                    self._queue.put(("log", f"  ✓ {fli_id_str}.pdf  ({len(files)} fichier(s))", "ok"))
                except Exception as exc:
                    self._queue.put(("log", f"  ✘ {fli_id_str}.pdf : {exc}", "error"))
                    ok = False
            self._queue.put(("pdf_done", ok, out_dir))

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------
    # Livraison Git (copie + commit + tag)
    # ------------------------------------------------------------------

    def _deliver(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._btn_deliver.config(state="disabled")

        conn_method = prefs_mod.get(self._prefs, "git", "conn_method", default="SSH")
        dev_root    = self._project.get("depot_dev", "")
        commit_msg  = self._delivery.get("commit_message", self._delivery.get("fli_title", ""))

        self._append_log("", "")
        self._append_log("─" * 56, "head")
        self._append_log("Livraison vers les dépôts d'intégration…", "head")

        def run() -> None:
            had_error = False
            for repo_key, files in self._repo_files.items():
                dest_root  = self._project.get(self._REPO_LOCAL_KEY.get(repo_key, ""), "")
                remote_url = self._project.get(self._REPO_REMOTE_KEY.get(repo_key, ""), "")
                tag        = self._delivery.get(self._REPO_TAG_KEY.get(repo_key, ""), "")

                label = f"[{repo_key}] → {dest_root or '(non configuré)'}"
                self._queue.put(("log", label, "head"))

                if not dest_root:
                    self._queue.put(("log",
                        f"  ⚠ Dépôt {repo_key} non configuré — ignoré", "warn"))
                    continue

                ok = git_ops.copy_and_deliver(
                    src_root       = dev_root,
                    dest_root      = dest_root,
                    files          = files,
                    commit_message = commit_msg,
                    tag            = tag,
                    conn_method    = conn_method,
                    prefs          = self._prefs,
                    on_progress    = lambda msg: self._queue.put(("log", msg, "")),
                    push           = False,
                    remote_url     = remote_url,
                )
                if not ok:
                    had_error = True

            self._queue.put(("deliver_done", not had_error))

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------
    # Polling de la queue (boucle continue)
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        try:
            while True:
                item = self._queue.get_nowait()
                kind = item[0]

                if kind == "log":
                    _, msg, tag = item
                    self._append_log(msg, tag)

                elif kind == "pdf_done":
                    _, success, out_dir = item
                    if success:
                        self._append_log("PDFs générés avec succès.", "ok")
                        self._btn_open.config(state="normal")
                        self._generated_dir = out_dir
                        if self._repo_files:
                            self._btn_deliver.config(state="normal")
                    else:
                        self._append_log("⚠ Certains PDFs ont échoué — livraison désactivée.", "error")

                elif kind == "deliver_done":
                    _, success = item
                    if success:
                        self._append_log("✔ Livraison terminée avec succès.", "ok")
                    else:
                        self._append_log("⚠ Livraison terminée avec des erreurs.", "warn")
                    self._busy = False
                    self._btn_deliver.config(state="normal")

        except queue.Empty:
            pass

        if self._win.winfo_exists():
            self._win.after(50, self._poll)

    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        prefs_mod.set_(self._prefs, "delivery_confirm_dialog", "geometry",
                       value=self._win.geometry())
        self._win.destroy()

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(
            title="Dossier de sortie pour les PDF",
            initialdir=self._out_var.get() or os.path.expanduser("~"),
            parent=self._win,
        )
        if folder:
            self._out_var.set(folder)
            prefs_mod.set_(self._prefs, "general", "output_dir", value=folder)

    def _open_folder(self) -> None:
        folder = getattr(self, "_generated_dir", self._out_var.get())
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
