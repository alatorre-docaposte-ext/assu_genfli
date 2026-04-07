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
import tkinter as tk
from tkinter import ttk, messagebox

from src import preferences as prefs_mod
from src.logger import get_logger
from src.widgets import DateEntry

log = get_logger()


class Screen2Delivery:
    title = "Informations de livraison"

    def __init__(self, parent: ttk.Frame, wizard) -> None:
        self._wizard = wizard
        self._prefs  = wizard.get_prefs()

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
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._build_emettrice(inner)
        self._build_destinataire(inner)
        self._build_fiche(inner)

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

        ttk.Label(f, text="Nom du client :", foreground="#555").grid(row=1, column=0, sticky="w", pady=1)
        ttk.Label(f, text=em.get("client", "—"), foreground="#555").grid(row=1, column=1, sticky="w", padx=(6, 0), pady=1)

        ttk.Label(f, text="Nom du projet :", foreground="#555").grid(row=2, column=0, sticky="w", pady=1)
        ttk.Label(f, text=em.get("projet", "—"), foreground="#555").grid(row=2, column=1, sticky="w", padx=(6, 0), pady=1)

        ttk.Label(f, text="Mode de livraison :", foreground="#555").grid(row=3, column=0, sticky="w", pady=1)
        ttk.Label(f, text=em.get("mode", "—"), foreground="#555").grid(row=3, column=1, sticky="w", padx=(6, 0), pady=1)

        # Livreur (pré-rempli depuis préférences livraison puis général.username)
        ttk.Separator(f, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(f, text="Livreur :").grid(row=5, column=0, sticky="e", padx=(0, 6), pady=4)
        default_livreur = (
            prefs_mod.get(self._prefs, "livraison", "emettrice", "reception_par", default="")
            or prefs_mod.get(self._prefs, "general", "username", default="")
        )
        session_livreur = (
            prefs_mod.get(self._prefs, "session", "delivery", "livreur", default="")
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

        ttk.Label(f, text="Nom du client :", foreground="#555").grid(row=1, column=0, sticky="w", pady=1)
        ttk.Label(f, text=dest.get("client", "—"), foreground="#555").grid(row=1, column=1, sticky="w", padx=(6, 0), pady=1)

        ttk.Label(f, text="Nom du projet :", foreground="#555").grid(row=2, column=0, sticky="w", pady=1)
        ttk.Label(f, text=dest_projet, foreground="#555").grid(row=2, column=1, sticky="w", padx=(6, 0), pady=1)

        # Réception par
        ttk.Separator(f, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)
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
        ttk.Entry(right, textvariable=self._tag_wfd_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(right, text="Ressources :").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=6)
        ttk.Entry(right, textvariable=self._tag_ress_var).grid(row=1, column=1, sticky="ew", pady=6)

        # --- Checkboxes ---
        chk_frame = ttk.Frame(f)
        chk_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        ttk.Label(chk_frame, text="Livraison en environnement d'intégration").pack(anchor="w", pady=(0, 4))

        session_quadient = prefs_mod.get(self._prefs, "session", "delivery", "quadient_r15", default=False)
        self._quadient_r15_var = tk.BooleanVar(value=session_quadient)
        ttk.Checkbutton(
            chk_frame,
            text="Livraison d'éléments Quadient R15",
            variable=self._quadient_r15_var,
        ).pack(anchor="w", pady=2)

        self._update_fli_title()

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
