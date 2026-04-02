"""
preferences.py — Chargement/sauvegarde des préférences utilisateur.

Fichier : %APPDATA%/assu_genfli/preferences.json
"""

import json
import os
from typing import Any

APP_NAME = "assu_genfli"

# Valeurs par défaut
_DEFAULTS: dict = {
    "log_window": {
        "visible": False,
        "geometry": "700x350+100+100",
    },
}


def _prefs_path() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    prefs_dir = os.path.join(appdata, APP_NAME)
    os.makedirs(prefs_dir, exist_ok=True)
    return os.path.join(prefs_dir, "preferences.json")


def load() -> dict:
    """Charge les préférences depuis le disque. Fusionne avec les défauts."""
    path = _prefs_path()
    prefs = _deep_merge({}, _DEFAULTS)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            prefs = _deep_merge(prefs, saved)
        except (json.JSONDecodeError, OSError):
            pass  # Fichier corrompu → on repart des défauts
    return prefs


def save(prefs: dict) -> None:
    """Sauvegarde les préférences sur le disque."""
    path = _prefs_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass


def get(prefs: dict, *keys: str, default: Any = None) -> Any:
    """Lecture sécurisée d'une valeur imbriquée : get(prefs, 'log_window', 'visible')."""
    node = prefs
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def set_(prefs: dict, *keys: str, value: Any) -> None:
    """Écriture sécurisée d'une valeur imbriquée : set_(prefs, 'log_window', 'visible', value=True)."""
    node = prefs
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    node[keys[-1]] = value


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
