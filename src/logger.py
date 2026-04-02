"""
logger.py — Configuration centrale du logging pour assu_genfli.

Deux handlers :
  - FileHandler  : %APPDATA%/assu_genfli/logs/assu_genfli_YYYY-MM-DD.log
  - UIHandler    : transmet les enregistrements à la fenêtre de log IHM
                   via une queue thread-safe (sans dépendance directe au widget)
"""

import logging
import os
import queue
from logging.handlers import RotatingFileHandler
from datetime import date

APP_NAME = "assu_genfli"

# Queue partagée : le UIHandler y dépose, la LogWindow y lit
log_queue: queue.Queue = queue.Queue()


def get_log_dir() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(appdata, APP_NAME, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


class _UIHandler(logging.Handler):
    """Dépose chaque LogRecord dans log_queue pour que la LogWindow l'affiche."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_queue.put_nowait(record)
        except queue.Full:
            pass


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """Initialise et retourne le logger racine de l'application."""
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        # Déjà initialisé (ex : rechargement de module)
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Handler fichier (rotation : 5 Mo × 5 fichiers) ---
    log_file = os.path.join(get_log_dir(), f"{APP_NAME}_{date.today()}.log")
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # --- Handler IHM (queue) ---
    uh = _UIHandler()
    uh.setFormatter(fmt)
    uh.setLevel(logging.DEBUG)
    logger.addHandler(uh)

    return logger


def get_logger(name: str = APP_NAME) -> logging.Logger:
    """Retourne un logger enfant de l'application."""
    return logging.getLogger(name)
