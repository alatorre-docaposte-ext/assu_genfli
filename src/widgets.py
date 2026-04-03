"""
widgets.py — Widgets réutilisables pour assu_genfli.

- CalendarPopup : sélecteur de date en tkinter pur (aucune dépendance externe)
- DateEntry     : champ de date avec bouton calendrier intégré
"""

import calendar
import datetime
import tkinter as tk
from tkinter import ttk

_MONTHS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]
_DAYS_FR = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]


class CalendarPopup:
    """
    Fenêtre Toplevel modale affichant un calendrier mensuel.
    Appelle on_select(date: datetime.date) à la sélection.
    """

    def __init__(
        self,
        parent: tk.Widget,
        initial_date: datetime.date | None = None,
        on_select=None,
    ) -> None:
        self._on_select = on_select
        self._view = (initial_date or datetime.date.today()).replace(day=1)
        self._selected = initial_date or datetime.date.today()

        self._win = tk.Toplevel(parent)
        self._win.title("Choisir une date")
        self._win.resizable(False, False)
        self._win.grab_set()
        self._win.transient(parent)

        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        win = self._win

        # Navigation mois
        nav = ttk.Frame(win)
        nav.pack(fill="x", padx=6, pady=6)
        ttk.Button(nav, text="◀", width=3, command=self._prev).pack(side="left")
        self._month_lbl = ttk.Label(nav, text="", anchor="center", width=22)
        self._month_lbl.pack(side="left", expand=True, fill="x")
        ttk.Button(nav, text="▶", width=3, command=self._next).pack(side="right")

        # Grille (reconstruite à chaque changement de mois)
        self._grid = ttk.Frame(win)
        self._grid.pack(padx=6, pady=(0, 8))

        self._refresh()

    def _refresh(self) -> None:
        for w in self._grid.winfo_children():
            w.destroy()

        self._month_lbl.config(
            text=f"{_MONTHS_FR[self._view.month - 1]} {self._view.year}"
        )

        # En-têtes
        for col, day in enumerate(_DAYS_FR):
            ttk.Label(
                self._grid, text=day, width=4, anchor="center",
                foreground="#0078d4" if col >= 5 else "",
            ).grid(row=0, column=col, padx=1, pady=2)

        today = datetime.date.today()
        for row_idx, week in enumerate(calendar.monthcalendar(self._view.year, self._view.month)):
            for col_idx, day_num in enumerate(week):
                if day_num == 0:
                    tk.Label(self._grid, text="", width=4).grid(
                        row=row_idx + 1, column=col_idx, padx=1, pady=1
                    )
                    continue
                d = datetime.date(self._view.year, self._view.month, day_num)
                is_sel   = (d == self._selected)
                is_today = (d == today)
                is_we    = (col_idx >= 5)

                btn = tk.Button(
                    self._grid,
                    text=str(day_num),
                    width=3,
                    relief="flat",
                    bg="#0078d4" if is_sel else ("#ddeeff" if is_today else "#ffffff"),
                    fg="white" if is_sel else ("#c00000" if is_we else "#1a1a1a"),
                    font=("Segoe UI", 9, "bold") if (is_sel or is_today) else ("Segoe UI", 9),
                    cursor="hand2",
                    command=lambda date=d: self._select(date),
                )
                btn.grid(row=row_idx + 1, column=col_idx, padx=1, pady=1)

        # Bouton Aujourd'hui
        ttk.Button(
            self._grid, text="Aujourd'hui",
            command=lambda: self._select(datetime.date.today()),
        ).grid(row=8, column=0, columnspan=7, sticky="ew", pady=(6, 0))

    def _prev(self) -> None:
        m, y = self._view.month - 1, self._view.year
        if m == 0:
            m, y = 12, y - 1
        self._view = datetime.date(y, m, 1)
        self._refresh()

    def _next(self) -> None:
        m, y = self._view.month + 1, self._view.year
        if m == 13:
            m, y = 1, y + 1
        self._view = datetime.date(y, m, 1)
        self._refresh()

    def _select(self, date: datetime.date) -> None:
        self._selected = date
        self._win.destroy()
        if self._on_select:
            self._on_select(date)


# ---------------------------------------------------------------------------


class DateEntry(ttk.Frame):
    """
    Widget compact : [JJ/MM/AAAA] [📅]
    Expose .get() → datetime.date  et  .set(date) → None
    """

    def __init__(self, parent: tk.Widget, initial: datetime.date | None = None, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._date = initial or datetime.date.today()
        self._var  = tk.StringVar(value=self._date.strftime("%d/%m/%Y"))

        entry = ttk.Entry(self, textvariable=self._var, width=12)
        entry.pack(side="left")
        entry.bind("<FocusOut>", self._on_manual_edit)

        ttk.Button(self, text="📅", width=3, command=self._open_calendar).pack(side="left", padx=(2, 0))

    def get(self) -> datetime.date:
        return self._date

    def set(self, date: datetime.date) -> None:
        self._date = date
        self._var.set(date.strftime("%d/%m/%Y"))

    def _open_calendar(self) -> None:
        CalendarPopup(self, initial_date=self._date, on_select=self.set)

    def _on_manual_edit(self, _event=None) -> None:
        try:
            self._date = datetime.datetime.strptime(self._var.get(), "%d/%m/%Y").date()
        except ValueError:
            self._var.set(self._date.strftime("%d/%m/%Y"))
