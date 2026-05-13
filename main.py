import tkinter as tk
from tkinter import ttk

from src.logger import setup_logging, get_logger
from src.log_window import LogWindow
from src.prefs_dialog import PrefsDialog
from src.wizard import Wizard
from src.screens.screen1_project import Screen1Project
from src.screens.screen3_delivery import Screen3Delivery
from src.screens.screen2_files import Screen2Files
from src import preferences as prefs_mod
from src import db as db_mod


def main():
    # --- Initialisation logging + préférences ---
    setup_logging()
    log = get_logger()
    prefs = prefs_mod.load()

    # --- Base de données ---
    db_path = prefs_mod.get(prefs, "db", "db_path", default="")
    if db_path:
        try:
            db_mod.open_db(db_path)
        except Exception as _e:
            pass  # DB non critique au démarrage ; signalé dans les préférences

    # --- Fenêtre principale ---
    root = tk.Tk()
    root.title("assu_genfli")
    root.minsize(640, 480)
    root.geometry(prefs_mod.get(prefs, "main_window", "geometry", default="800x560"))
    if prefs_mod.get(prefs, "main_window", "state", default="normal") == "zoomed":
        root.update_idletasks()
        root.state("zoomed")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    log_window = LogWindow(root, prefs)

    # --- Barre de menu ---
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    # Menu Fichier
    menu_fichier = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Fichier", menu=menu_fichier)

    def open_prefs():
        def on_apply(_p):
            new_db_path = prefs_mod.get(_p, "db", "db_path", default="")
            if new_db_path:
                try:
                    db_mod.open_db(new_db_path)
                except Exception:
                    pass
            wizard.reload_current()
        PrefsDialog(root, prefs, on_apply=on_apply)

    menu_fichier.add_command(label="Préférences", command=open_prefs)
    menu_fichier.add_separator()
    menu_fichier.add_command(label="Quitter", command=lambda: root.event_generate("<<AppClose>>"))

    # Menu Affichage
    menu_affichage = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Affichage", menu=menu_affichage)

    # Variable booléenne reflétant l'état visible/caché de la fenêtre de log
    log_visible_var = tk.BooleanVar(value=False)

    def toggle_logs():
        log_window.toggle()
        log_visible_var.set(log_window.is_visible())

    menu_affichage.add_checkbutton(
        label="Afficher le journal",
        variable=log_visible_var,
        command=toggle_logs,
    )

    # Synchronise la coche si la fenêtre est fermée via sa propre croix/bouton
    log_window.set_on_visibility_change(lambda visible: log_visible_var.set(visible))

    # Menu DEV
    menu_dev = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="DEV", menu=menu_dev)

    dev_mode_var = tk.BooleanVar(value=bool(prefs_mod.get(prefs, "general", "dev_mode", default=False)))

    def _update_dev_title():
        suffix = "  [MODE DEV]"
        title  = root.title()
        base   = title.replace(suffix, "")
        root.title(base + suffix if dev_mode_var.get() else base)
        prefs_mod.set_(prefs, "general", "dev_mode", value=dev_mode_var.get())

    menu_dev.add_checkbutton(
        label="Mode Dev",
        variable=dev_mode_var,
        command=_update_dev_title,
    )
    # Appliquer le titre au démarrage si le mode était actif
    if dev_mode_var.get():
        _update_dev_title()

    # --- Wizard ---
    wizard = Wizard(root, prefs)
    wizard.register(Screen1Project)
    wizard.register(Screen2Files)
    wizard.register(Screen3Delivery)
    wizard.start()

    # --- Restaurer état fenêtre de log ---
    log_window.restore_from_prefs()
    log_visible_var.set(log_window.is_visible())
    log.info("Application démarrée.")

    # --- Fermeture propre ---
    def on_close():
        log.info("Application fermée.")
        prefs_mod.set_(prefs, "main_window", "geometry", value=root.geometry())
        prefs_mod.set_(prefs, "main_window", "state", value=root.state())
        prefs_mod.set_(prefs, "log_window", "visible", value=log_window.is_visible())
        if log_window.is_visible():
            log_window._save_geometry()
        prefs_mod.save(prefs)
        db_mod.close_db()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.bind("<<AppClose>>", lambda _e: on_close())
    root.mainloop()


if __name__ == "__main__":
    main()
