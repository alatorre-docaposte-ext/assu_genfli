"""
sftp_ops.py — Envoi de fichiers via SFTP (paramiko).
"""
from __future__ import annotations

import base64
import os
from typing import Callable

from src.logger import get_logger

_log = get_logger()


def _decode_password(encoded: str) -> str:
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def upload_files(
    host: str,
    port: int,
    username: str,
    password: str,
    remote_root: str,
    local_paths: list[str],
    on_progress: Callable[[str], None],
) -> bool:
    """
    Envoie chaque fichier de local_paths vers remote_root/<basename> via SFTP.
    Retourne True si tous les fichiers ont été envoyés sans erreur.
    """
    try:
        import paramiko
    except ImportError:
        on_progress("  ✘ Bibliothèque paramiko manquante (pip install paramiko)")
        return False

    if not host:
        on_progress("  ⚠ SFTP : hôte non configuré — ignoré")
        return True

    had_error = False
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        on_progress(f"  SFTP connexion → {host}:{port}…")
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=30,
            look_for_keys=False,
            allow_agent=False,
        )
        sftp = client.open_sftp()

        # S'assurer que le répertoire distant existe
        if remote_root:
            _sftp_makedirs(sftp, remote_root)

        for local_path in local_paths:
            basename = os.path.basename(local_path)
            remote_path = f"{remote_root.rstrip('/')}/{basename}" if remote_root else basename
            try:
                sftp.put(local_path, remote_path)
                on_progress(f"  ✓ SFTP {basename}")
                _log.info("[sftp] upload  %s → %s:%s", local_path, host, remote_path)
            except Exception as exc:
                on_progress(f"  ✘ SFTP {basename} : {exc}")
                _log.warning("[sftp] upload error  %s : %s", local_path, exc)
                had_error = True

        sftp.close()
    except Exception as exc:
        on_progress(f"  ✘ SFTP connexion : {exc}")
        _log.warning("[sftp] connexion error  %s : %s", host, exc)
        had_error = True
    finally:
        client.close()

    return not had_error


def upload_files_from_prefs(
    prefs: dict,
    local_paths: list[str],
    on_progress: Callable[[str], None],
) -> bool:
    """
    Raccourci : lit les paramètres SFTP dans prefs et appelle upload_files.
    """
    sftp = prefs.get("sftp", {})
    host        = sftp.get("host", "").strip()
    port        = int(sftp.get("port", 22))
    username    = sftp.get("username", "").strip()
    password    = _decode_password(sftp.get("password", ""))
    remote_root = sftp.get("remote_root", "").strip()
    return upload_files(host, port, username, password, remote_root, local_paths, on_progress)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _sftp_makedirs(sftp, remote_path: str) -> None:
    """Crée récursivement remote_path sur le serveur SFTP (mkdir -p)."""
    import stat as _stat
    parts = remote_path.replace("\\", "/").split("/")
    current = ""
    for part in parts:
        if not part:
            current = "/"
            continue
        current = f"{current}/{part}" if current and current != "/" else (f"/{part}" if current == "/" else part)
        try:
            mode = sftp.stat(current).st_mode
            if not _stat.S_ISDIR(mode):
                raise OSError(f"{current!r} existe mais n'est pas un répertoire")
        except FileNotFoundError:
            sftp.mkdir(current)
