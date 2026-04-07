"""
prefs_dialog.py — Fenêtre de préférences modale à onglets.

Onglets : Général | Projets | Git | SFTP
Boutons  : OK / Annuler / Appliquer
"""

import base64
import copy
import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src import preferences as prefs_mod
from src.project_dialog import ProjectDialog
from src.git_sync_dialog import GitSyncDialog


class PrefsDialog:
    """
    Usage :
        PrefsDialog(root, prefs, on_apply=callback)

    on_apply(prefs) est appelé à chaque "Appliquer" et "OK".
    """

    def __init__(self, parent: tk.Tk, prefs: dict, on_apply=None) -> None:
        self._parent = parent
        self._prefs = prefs                       # référence vivante
        self._working = copy.deepcopy(prefs)      # copie de travail modifiable
        self._on_apply = on_apply

        self._win = tk.Toplevel(parent)
        self._win.title("Préférences")
        self._win.resizable(True, False)
        self._win.grab_set()
        self._win.transient(parent)
        self._win.minsize(550, 0)

        # Restaurer la geometry sauvegardée
        saved_geom = prefs_mod.get(self._prefs, "prefs_dialog", "geometry", default="")
        if saved_geom:
            self._win.geometry(saved_geom)

        self._build()
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._win.wait_window()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        win = self._win
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)

        nb = ttk.Notebook(win)
        nb.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self._tab_general(nb)
        self._tab_projets(nb)
        self._tab_git(nb)
        self._tab_sftp(nb)
        self._tab_livraison(nb)

        # Boutons bas de page
        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=1, column=0, sticky="e", padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="OK",       width=10, command=self._ok).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Annuler",  width=10, command=self._on_close).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Appliquer",width=10, command=self._apply).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # Onglet Général
    # ------------------------------------------------------------------

    def _tab_general(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=15)
        nb.add(f, text="Général")
        f.columnconfigure(1, weight=1)

        # Nom d'utilisateur
        ttk.Label(f, text="Nom d'utilisateur :").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=6)
        self._username_var = tk.StringVar(value=prefs_mod.get(self._working, "general", "username", default=""))
        ttk.Entry(f, textvariable=self._username_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=6)

        # Répertoire de travail
        ttk.Label(f, text="Répertoire de travail :").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=6)
        self._workdir_var = tk.StringVar(value=prefs_mod.get(self._working, "general", "work_dir", default=""))
        ttk.Entry(f, textvariable=self._workdir_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(f, text="Browse...", command=lambda: self._browse_dir(self._workdir_var)).grid(row=1, column=2, padx=(4, 0), pady=6)

        # Fichier de journal
        ttk.Label(f, text="Fichier de journal :").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=6)
        self._logfile_var = tk.StringVar(value=prefs_mod.get(self._working, "general", "log_file", default=""))
        ttk.Entry(f, textvariable=self._logfile_var).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(f, text="Browse...", command=lambda: self._browse_save(
            self._logfile_var, [("Fichiers log", "*.log"), ("Tous", "*.*")]
        )).grid(row=2, column=2, padx=(4, 0), pady=6)

        # Séparateur + Export/Import
        ttk.Separator(f, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(f, text="Paramètres :").grid(row=4, column=0, sticky="e", padx=(0, 8), pady=6)
        pf = ttk.Frame(f)
        pf.grid(row=4, column=1, columnspan=2, sticky="w")
        ttk.Button(pf, text="Exporter...", command=self._export).pack(side="top", anchor="w", pady=2)
        ttk.Button(pf, text="Importer...", command=self._import).pack(side="top", anchor="w", pady=2)

    # ------------------------------------------------------------------
    # Onglet Projets
    # ------------------------------------------------------------------

    def _tab_projets(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=15)
        nb.add(f, text="Projets")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        # Treeview
        self._proj_tree = ttk.Treeview(f, columns=("nom", "code"), show="headings", height=8)
        self._proj_tree.heading("nom",  text="Nom")
        self._proj_tree.heading("code", text="Code")
        self._proj_tree.column("nom",  width=250, stretch=True)
        self._proj_tree.column("code", width=100, stretch=False)
        self._proj_tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(f, orient="vertical", command=self._proj_tree.yview)
        self._proj_tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")

        self._proj_tree.bind("<Double-1>",       lambda _e: self._edit_project())
        self._proj_tree.bind("<<TreeviewSelect>>", self._on_proj_select)

        # Boutons
        bf = ttk.Frame(f)
        bf.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        ttk.Button(bf, text="Ajouter...", command=self._add_project).pack(side="left", padx=(0, 4))
        self._btn_modifier   = ttk.Button(bf, text="Modifier...", command=self._edit_project, state="disabled")
        self._btn_modifier.pack(side="left", padx=4)
        self._btn_supprimer  = ttk.Button(bf, text="Supprimer",  command=self._delete_project, state="disabled")
        self._btn_supprimer.pack(side="right")

        ttk.Label(f, text="Double-cliquez sur un projet pour le modifier.", foreground="gray").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        self._reload_projects()

    # ------------------------------------------------------------------
    # Onglet Git
    # ------------------------------------------------------------------

    def _tab_git(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=15)
        nb.add(f, text="Git")
        f.columnconfigure(1, weight=1)

        # --- Fieldset SSH ---
        ssh_frame = ttk.LabelFrame(f, text="SSH", padding=8)
        ssh_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        ssh_frame.columnconfigure(1, weight=1)

        ttk.Label(ssh_frame, text="Clé SSH :", anchor="e").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=6)
        self._ssh_key_var = tk.StringVar(value=prefs_mod.get(self._working, "git", "ssh_key", default=""))
        ttk.Entry(ssh_frame, textvariable=self._ssh_key_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(ssh_frame, text="Browse...", command=lambda: self._browse_open(
            self._ssh_key_var, [("Clés SSH", "*.pem *.key id_rsa id_ed25519"), ("Tous", "*.*")]
        )).grid(row=0, column=2, padx=(4, 0), pady=6)

        # --- Fieldset HTTPS ---
        https_frame = ttk.LabelFrame(f, text="HTTPS", padding=8)
        https_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        https_frame.columnconfigure(1, weight=1)

        ttk.Label(https_frame, text="Login :", anchor="e").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=6)
        self._git_https_login_var = tk.StringVar(value=prefs_mod.get(self._working, "git", "https_login", default=""))
        ttk.Entry(https_frame, textvariable=self._git_https_login_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=6)

        ttk.Label(https_frame, text="Mot de passe :", anchor="e").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=6)
        git_pwd_encoded = prefs_mod.get(self._working, "git", "https_password", default="")
        self._git_https_pwd_var = tk.StringVar(value=_decode_password(git_pwd_encoded))
        self._git_pwd_entry = ttk.Entry(https_frame, textvariable=self._git_https_pwd_var, show="●")
        self._git_pwd_entry.grid(row=1, column=1, sticky="ew", pady=6)
        self._git_pwd_visible = False
        ttk.Button(https_frame, text="👁", width=3, command=self._toggle_git_pwd).grid(row=1, column=2, padx=(4, 0), pady=6)

    # ------------------------------------------------------------------
    # Onglet Livraison
    # ------------------------------------------------------------------

    def _tab_livraison(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=15)
        nb.add(f, text="Livraison")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        # --- Entité émettrice ---
        em = ttk.LabelFrame(f, text="Entité émettrice", padding=10)
        em.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))
        em.columnconfigure(1, weight=1)

        self._em_nom_var          = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "emettrice", "nom",          default=""))
        self._em_client_var      = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "emettrice", "client",       default=""))
        self._em_projet_var      = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "emettrice", "projet",       default=""))
        self._em_mode_var        = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "emettrice", "mode",         default=""))
        self._em_reception_var   = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "emettrice", "livreur", default=""))

        for row, (label, var) in enumerate([
            ("Nom :",               self._em_nom_var),
            ("Nom du client :",     self._em_client_var),
            ("Nom du projet :",     self._em_projet_var),
            ("Mode de livraison :", self._em_mode_var),
            ("Livreur par défaut :",self._em_reception_var),
        ]):
            ttk.Label(em, text=label, anchor="e").grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
            ttk.Entry(em, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)

        # --- Entité destinataire ---
        dest = ttk.LabelFrame(f, text="Entité destinataire", padding=10)
        dest.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))
        dest.columnconfigure(1, weight=1)

        self._dest_nom_var        = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "destinataire", "nom",          default=""))
        self._dest_client_var    = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "destinataire", "client",       default=""))
        self._dest_reception_var = tk.StringVar(value=prefs_mod.get(self._working, "livraison", "destinataire", "reception_par", default=""))

        for row, (label, var) in enumerate([
            ("Nom :",                self._dest_nom_var),
            ("Nom du client :",      self._dest_client_var),
            ("Réception par défaut :", self._dest_reception_var),
        ]):
            ttk.Label(dest, text=label, anchor="e").grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
            ttk.Entry(dest, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)

        # --- (Numérotation FLI supprimée — saisie manuelle à l'écran 2) ---

    # ------------------------------------------------------------------
    # Onglet SFTP
    # ------------------------------------------------------------------

    def _tab_sftp(self, nb: ttk.Notebook) -> None:
        f = ttk.Frame(nb, padding=15)
        nb.add(f, text="SFTP")
        f.columnconfigure(1, weight=1)

        # Hôte
        ttk.Label(f, text="Hôte :").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=6)
        self._sftp_host_var = tk.StringVar(value=prefs_mod.get(self._working, "sftp", "host", default=""))
        ttk.Entry(f, textvariable=self._sftp_host_var).grid(row=0, column=1, columnspan=2, sticky="ew", pady=6)

        # Port
        ttk.Label(f, text="Port :").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=6)
        self._sftp_port_var = tk.StringVar(value=str(prefs_mod.get(self._working, "sftp", "port", default=22)))
        ttk.Spinbox(f, from_=1, to=65535, width=8, textvariable=self._sftp_port_var).grid(row=1, column=1, sticky="w", pady=6)

        # Utilisateur
        ttk.Label(f, text="Utilisateur :").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=6)
        self._sftp_user_var = tk.StringVar(value=prefs_mod.get(self._working, "sftp", "username", default=""))
        ttk.Entry(f, textvariable=self._sftp_user_var).grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)

        # Mot de passe
        ttk.Label(f, text="Mot de passe :").grid(row=3, column=0, sticky="e", padx=(0, 8), pady=6)
        encoded = prefs_mod.get(self._working, "sftp", "password", default="")
        self._sftp_pwd_var = tk.StringVar(value=_decode_password(encoded))
        self._pwd_entry = ttk.Entry(f, textvariable=self._sftp_pwd_var, show="●")
        self._pwd_entry.grid(row=3, column=1, sticky="ew", pady=6)
        self._pwd_visible = False
        ttk.Button(f, text="👁", width=3, command=self._toggle_pwd).grid(row=3, column=2, padx=(4, 0), pady=6)

    # ------------------------------------------------------------------
    # Gestion des projets
    # ------------------------------------------------------------------

    def _reload_projects(self) -> None:
        for item in self._proj_tree.get_children():
            self._proj_tree.delete(item)
        for p in prefs_mod.get(self._working, "projects", default=[]):
            self._proj_tree.insert("", "end", values=(p.get("name", ""), p.get("code", "")))

    def _on_proj_select(self, _event=None) -> None:
        state = "normal" if self._proj_tree.selection() else "disabled"
        self._btn_modifier.config(state=state)
        self._btn_supprimer.config(state=state)

    def _add_project(self) -> None:
        default_method = prefs_mod.get(self._working, "git", "conn_method", default="SSH")
        dlg = ProjectDialog(self._win, title="Nouveau projet", default_conn_method=default_method, prefs=self._prefs)
        if dlg.result:
            projects = prefs_mod.get(self._working, "projects", default=[])
            projects.append(dlg.result)
            prefs_mod.set_(self._working, "projects", value=projects)
            self._reload_projects()
            GitSyncDialog(self._win, dlg.result, self._working)

    def _edit_project(self) -> None:
        sel = self._proj_tree.selection()
        if not sel:
            return
        idx = self._proj_tree.index(sel[0])
        projects = prefs_mod.get(self._working, "projects", default=[])
        default_method = prefs_mod.get(self._working, "git", "conn_method", default="SSH")
        dlg = ProjectDialog(self._win, title="Modifier le projet", data=projects[idx], default_conn_method=default_method, prefs=self._prefs)
        if dlg.result:
            projects[idx] = dlg.result
            prefs_mod.set_(self._working, "projects", value=projects)
            self._reload_projects()
            GitSyncDialog(self._win, dlg.result, self._working)

    def _delete_project(self) -> None:
        sel = self._proj_tree.selection()
        if not sel:
            return
        idx = self._proj_tree.index(sel[0])
        projects = prefs_mod.get(self._working, "projects", default=[])
        name = projects[idx].get("name", "ce projet")
        if messagebox.askyesno("Confirmer", f"Supprimer le projet « {name} » ?", parent=self._win):
            projects.pop(idx)
            prefs_mod.set_(self._working, "projects", value=projects)
            self._reload_projects()

    # ------------------------------------------------------------------
    # Git / SFTP — toggle mots de passe
    # ------------------------------------------------------------------

    def _toggle_git_pwd(self) -> None:
        self._git_pwd_visible = not self._git_pwd_visible
        self._git_pwd_entry.config(show="" if self._git_pwd_visible else "●")

    def _toggle_pwd(self) -> None:
        self._pwd_visible = not self._pwd_visible
        self._pwd_entry.config(show="" if self._pwd_visible else "●")

    # ------------------------------------------------------------------
    # Browse helpers
    # ------------------------------------------------------------------

    def _browse_dir(self, var: tk.StringVar) -> None:
        initial = var.get() if os.path.isdir(var.get()) else os.path.expanduser("~")
        path = filedialog.askdirectory(parent=self._win, initialdir=initial)
        if path:
            var.set(path)

    def _browse_open(self, var: tk.StringVar, filetypes=None) -> None:
        initial = os.path.dirname(var.get()) or os.path.expanduser("~")
        path = filedialog.askopenfilename(
            parent=self._win, initialdir=initial,
            filetypes=filetypes or [("Tous", "*.*")]
        )
        if path:
            var.set(path)

    def _browse_save(self, var: tk.StringVar, filetypes=None) -> None:
        initial_dir  = os.path.dirname(var.get()) or os.path.expanduser("~")
        initial_file = os.path.basename(var.get())
        path = filedialog.asksaveasfilename(
            parent=self._win, initialdir=initial_dir,
            initialfile=initial_file,
            filetypes=filetypes or [("Tous", "*.*")]
        )
        if path:
            var.set(path)

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def _export(self) -> None:
        self._collect()
        path = filedialog.asksaveasfilename(
            parent=self._win,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")],
            title="Exporter les paramètres",
        )
        if not path:
            return
        export = copy.deepcopy(self._working)
        prefs_mod.set_(export, "sftp", "password",        value="")  # ne pas exporter les mots de passe
        prefs_mod.set_(export, "git",  "https_password",  value="")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(export, fh, indent=2, ensure_ascii=False)
            messagebox.showinfo("Export", "Paramètres exportés avec succès.", parent=self._win)
        except OSError as exc:
            messagebox.showerror("Erreur d'export", str(exc), parent=self._win)

    def _import(self) -> None:
        path = filedialog.askopenfilename(
            parent=self._win,
            filetypes=[("JSON", "*.json"), ("Tous", "*.*")],
            title="Importer les paramètres",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                imported = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            messagebox.showerror("Erreur d'import", str(exc), parent=self._win)
            return

        # Fusion en conservant log_window
        saved_log_win = self._working.get("log_window", {})
        self._working = prefs_mod.deep_merge(self._working, imported)
        self._working["log_window"] = saved_log_win

        # Rafraîchir les widgets
        self._username_var.set(prefs_mod.get(self._working, "general", "username", default=""))
        self._workdir_var.set(prefs_mod.get(self._working, "general", "work_dir", default=""))
        self._logfile_var.set(prefs_mod.get(self._working, "general", "log_file", default=""))
        self._ssh_key_var.set(prefs_mod.get(self._working, "git", "ssh_key", default=""))
        self._git_https_login_var.set(prefs_mod.get(self._working, "git", "https_login", default=""))
        self._git_https_pwd_var.set(_decode_password(prefs_mod.get(self._working, "git", "https_password", default="")))
        self._sftp_host_var.set(prefs_mod.get(self._working, "sftp", "host", default=""))
        self._sftp_port_var.set(str(prefs_mod.get(self._working, "sftp", "port", default=22)))
        self._sftp_user_var.set(prefs_mod.get(self._working, "sftp", "username", default=""))
        self._reload_projects()
        # Livraison
        self._em_nom_var.set(prefs_mod.get(self._working,    "livraison", "emettrice",    "nom",    default=""))
        self._em_client_var.set(prefs_mod.get(self._working, "livraison", "emettrice",    "client", default=""))
        self._em_projet_var.set(prefs_mod.get(self._working, "livraison", "emettrice",    "projet", default=""))
        self._em_mode_var.set(prefs_mod.get(self._working,   "livraison", "emettrice",    "mode",   default=""))
        self._dest_nom_var.set(prefs_mod.get(self._working,        "livraison", "destinataire", "nom",          default=""))
        self._dest_client_var.set(prefs_mod.get(self._working,    "livraison", "destinataire", "client",       default=""))
        self._dest_reception_var.set(prefs_mod.get(self._working, "livraison", "destinataire", "reception_par", default=""))
        self._em_reception_var.set(prefs_mod.get(self._working,   "livraison", "emettrice",    "livreur", default=""))
        messagebox.showinfo("Import", "Paramètres importés. Validez avec OK ou Appliquer.", parent=self._win)

    # ------------------------------------------------------------------
    # Collect / Apply / OK
    # ------------------------------------------------------------------

    def _collect(self) -> None:
        """Lit tous les widgets → self._working."""
        prefs_mod.set_(self._working, "general", "username", value=self._username_var.get())
        prefs_mod.set_(self._working, "general", "work_dir", value=self._workdir_var.get())
        prefs_mod.set_(self._working, "general", "log_file", value=self._logfile_var.get())
        prefs_mod.set_(self._working, "git", "ssh_key",        value=self._ssh_key_var.get())
        prefs_mod.set_(self._working, "git", "https_login",    value=self._git_https_login_var.get())
        prefs_mod.set_(self._working, "git", "https_password", value=_encode_password(self._git_https_pwd_var.get()))
        prefs_mod.set_(self._working, "sftp", "host",     value=self._sftp_host_var.get())
        prefs_mod.set_(self._working, "sftp", "username", value=self._sftp_user_var.get())
        prefs_mod.set_(self._working, "sftp", "password", value=_encode_password(self._sftp_pwd_var.get()))
        try:
            port = max(1, min(65535, int(self._sftp_port_var.get())))
        except ValueError:
            port = 22
        prefs_mod.set_(self._working, "sftp", "port", value=port)
        # Livraison
        prefs_mod.set_(self._working, "livraison", "emettrice",    "nom",    value=self._em_nom_var.get())
        prefs_mod.set_(self._working, "livraison", "emettrice",    "client", value=self._em_client_var.get())
        prefs_mod.set_(self._working, "livraison", "emettrice",    "projet", value=self._em_projet_var.get())
        prefs_mod.set_(self._working, "livraison", "emettrice",    "mode",   value=self._em_mode_var.get())
        prefs_mod.set_(self._working, "livraison", "destinataire", "nom",          value=self._dest_nom_var.get())
        prefs_mod.set_(self._working, "livraison", "destinataire", "client",       value=self._dest_client_var.get())
        prefs_mod.set_(self._working, "livraison", "destinataire", "reception_par", value=self._dest_reception_var.get())
        prefs_mod.set_(self._working, "livraison", "emettrice",    "livreur", value=self._em_reception_var.get())
        prefs_mod.set_(self._working, "sftp", "port", value=port)

    def _apply(self) -> None:
        self._collect()
        self._prefs.clear()
        self._prefs.update(self._working)
        prefs_mod.save(self._prefs)
        if self._on_apply:
            self._on_apply(self._prefs)

    def _on_close(self) -> None:
        """Sauvegarde la geometry puis ferme."""
        prefs_mod.set_(self._prefs, "prefs_dialog", "geometry", value=self._win.geometry())
        prefs_mod.save(self._prefs)
        self._win.destroy()

    def _ok(self) -> None:
        self._apply()
        self._on_close()


# ------------------------------------------------------------------
# Helpers mot de passe (obfuscation base64 — non chiffré)
# ------------------------------------------------------------------

def _encode_password(plain: str) -> str:
    if not plain:
        return ""
    return base64.b64encode(plain.encode("utf-8")).decode("ascii")


def _decode_password(encoded: str) -> str:
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode("ascii")).decode("utf-8")
    except Exception:
        return ""
