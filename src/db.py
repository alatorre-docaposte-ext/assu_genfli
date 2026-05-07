"""
db.py — Gestion de la base de données SQLite.

Schéma :
  projects      : (id, code, name) — reflète les projets configurés
  routing_rules : (id, project_id, pattern, target, priority)
                  Règles de routage glob → cible (WFD | RESS | COMMUN | BOTH | NONE)
                  Évaluées dans l'ordre priority DESC, id ASC — première règle gagne.
  file_routes   : (id, project_id, path, target)
                  Surcharges par fichier exact (priorité absolue sur les règles glob).
"""
from __future__ import annotations

import fnmatch
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TARGETS: tuple[str, ...] = ("WFD", "RESS", "COMMUN", "BOTH", "NONE")

# Current schema version — bump when DDL changes.
_SCHEMA_VERSION = 2

_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT    NOT NULL UNIQUE,
    name TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS routing_rules (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pattern    TEXT    NOT NULL,
    target     TEXT    NOT NULL CHECK(target IN ('WFD', 'RESS', 'COMMUN', 'BOTH', 'NONE')),
    priority   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(project_id, pattern)
);

CREATE TABLE IF NOT EXISTS file_routes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    path       TEXT    NOT NULL,
    target     TEXT    NOT NULL CHECK(target IN ('WFD', 'RESS', 'COMMUN', 'BOTH', 'NONE')),
    UNIQUE(project_id, path)
);
"""

_MIGRATION_V2 = """
-- Recreate routing_rules with expanded CHECK constraint (adds COMMUN)
ALTER TABLE routing_rules RENAME TO _routing_rules_old;
CREATE TABLE routing_rules (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pattern    TEXT    NOT NULL,
    target     TEXT    NOT NULL CHECK(target IN ('WFD', 'RESS', 'COMMUN', 'BOTH', 'NONE')),
    priority   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(project_id, pattern)
);
INSERT INTO routing_rules SELECT * FROM _routing_rules_old;
DROP TABLE _routing_rules_old;

-- Recreate file_routes with expanded CHECK constraint
ALTER TABLE file_routes RENAME TO _file_routes_old;
CREATE TABLE file_routes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    path       TEXT    NOT NULL,
    target     TEXT    NOT NULL CHECK(target IN ('WFD', 'RESS', 'COMMUN', 'BOTH', 'NONE')),
    UNIQUE(project_id, path)
);
INSERT INTO file_routes SELECT * FROM _file_routes_old;
DROP TABLE _file_routes_old;
"""

# ---------------------------------------------------------------------------
# Connexion module-level (singleton desktop)
# ---------------------------------------------------------------------------

_conn: sqlite3.Connection | None = None


def open_db(path: str) -> sqlite3.Connection:
    """Ouvre (ou rouvre) la base de données. Crée/migre le schéma si nécessaire."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    # Bootstrap schema
    _conn.executescript(_DDL)
    _conn.commit()

    # Run migrations based on user_version pragma
    current_version = _conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version < 2:
        _conn.executescript(_MIGRATION_V2)
        _conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        _conn.commit()

    return _conn


def get_db() -> sqlite3.Connection | None:
    """Retourne la connexion ouverte, ou None si aucune base n'est configurée."""
    return _conn


def close_db() -> None:
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


# ---------------------------------------------------------------------------
# Projets
# ---------------------------------------------------------------------------

def upsert_project(conn: sqlite3.Connection, code: str, name: str) -> int:
    """Insère ou met à jour un projet. Retourne son id."""
    conn.execute(
        "INSERT INTO projects (code, name) VALUES (?, ?)"
        " ON CONFLICT(code) DO UPDATE SET name = excluded.name",
        (code, name),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM projects WHERE code = ?", (code,)).fetchone()
    return row["id"]


def get_project_id(conn: sqlite3.Connection, code: str) -> int | None:
    row = conn.execute("SELECT id FROM projects WHERE code = ?", (code,)).fetchone()
    return row["id"] if row else None


def list_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM projects ORDER BY name").fetchall()


# ---------------------------------------------------------------------------
# Règles de routage
# ---------------------------------------------------------------------------

def list_rules(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM routing_rules WHERE project_id = ?"
        " ORDER BY priority DESC, id ASC",
        (project_id,),
    ).fetchall()


def add_rule(conn: sqlite3.Connection, project_id: int,
             pattern: str, target: str, priority: int = 0) -> None:
    conn.execute(
        "INSERT INTO routing_rules (project_id, pattern, target, priority) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(project_id, pattern)"
        "   DO UPDATE SET target = excluded.target, priority = excluded.priority",
        (project_id, pattern, target, priority),
    )
    conn.commit()


def update_rule(conn: sqlite3.Connection, rule_id: int,
                pattern: str, target: str, priority: int) -> None:
    conn.execute(
        "UPDATE routing_rules SET pattern = ?, target = ?, priority = ? WHERE id = ?",
        (pattern, target, priority, rule_id),
    )
    conn.commit()


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    conn.execute("DELETE FROM routing_rules WHERE id = ?", (rule_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Surcharges par fichier
# ---------------------------------------------------------------------------

def list_file_routes(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM file_routes WHERE project_id = ? ORDER BY path",
        (project_id,),
    ).fetchall()


def set_file_route(conn: sqlite3.Connection, project_id: int,
                   path: str, target: str) -> None:
    conn.execute(
        "INSERT INTO file_routes (project_id, path, target) VALUES (?, ?, ?)"
        " ON CONFLICT(project_id, path) DO UPDATE SET target = excluded.target",
        (project_id, path, target),
    )
    conn.commit()


def delete_file_route(conn: sqlite3.Connection, project_id: int, path: str) -> None:
    conn.execute(
        "DELETE FROM file_routes WHERE project_id = ? AND path = ?",
        (project_id, path),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Résolution de cible
# ---------------------------------------------------------------------------

def resolve_target(conn: sqlite3.Connection, project_id: int, path: str) -> str:
    """
    Retourne la cible pour un chemin donné.
    Ordre de priorité : file_routes (exact) > routing_rules (glob, priority DESC) > 'NONE'.
    """
    norm = path.replace("\\", "/")

    # 1. Surcharge par fichier exact
    row = conn.execute(
        "SELECT target FROM file_routes WHERE project_id = ? AND path = ?",
        (project_id, norm),
    ).fetchone()
    if row:
        return row["target"]

    # 2. Règles glob (déjà triées priority DESC, id ASC)
    for rule in list_rules(conn, project_id):
        if fnmatch.fnmatch(norm, rule["pattern"]):
            return rule["target"]

    return "NONE"


def resolve_targets_batch(conn: sqlite3.Connection,
                          project_id: int,
                          paths: list[str]) -> dict[str, str]:
    """Résout les cibles pour une liste de chemins en une seule passe."""
    overrides = {
        row["path"]: row["target"]
        for row in list_file_routes(conn, project_id)
    }
    rules = list_rules(conn, project_id)

    result: dict[str, str] = {}
    for path in paths:
        norm = path.replace("\\", "/")
        if norm in overrides:
            result[path] = overrides[norm]
            continue
        matched = "NONE"
        for rule in rules:
            if fnmatch.fnmatch(norm, rule["pattern"]):
                matched = rule["target"]
                break
        result[path] = matched
    return result
