import tkinter as tk
from tkinter import ttk

from src.logger import setup_logging, get_logger
from src.log_window import LogWindow
from src.prefs_dialog import PrefsDialog
from src import preferences as prefs_mod


def main():
    # --- Initialisation logging + préférences ---
    setup_logging()
    log = get_logger()
    prefs = prefs_mod.load()

    # --- Fenêtre principale ---
    root = tk.Tk()
    root.title("assu_genfli")
    root.minsize(500, 300)

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
        PrefsDialog(root, prefs)

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

    # --- Contenu principal (placeholder Hello World) ---
    frame = ttk.LabelFrame(root, padding=20)
    frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    label = ttk.Label(frame, text="Hello World", font=("Segoe UI", 18, "bold"))
    label.grid(row=0, column=0)

    # --- Restaurer état fenêtre de log ---
    log_window.restore_from_prefs()
    log_visible_var.set(log_window.is_visible())
    log.info("Application démarrée.")

    # --- Fermeture propre ---
    def on_close():
        log.info("Application fermée.")
        prefs_mod.set_(prefs, "log_window", "visible", value=log_window.is_visible())
        if log_window.is_visible():
            log_window._save_geometry()
        prefs_mod.save(prefs)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.bind("<<AppClose>>", lambda _e: on_close())
    root.mainloop()


if __name__ == "__main__":
    main()
