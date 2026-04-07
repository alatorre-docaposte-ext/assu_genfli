"""
git_ops.py — Opérations Git (clone / pull) via GitPython.

Gère SSH (clé + passphrase optionnelle) et HTTPS (credentials en base64).
"""
from __future__ import annotations

import base64
import os
import tempfile
from typing import Callable

import git


# ---------------------------------------------------------------------------
# Diff Git
# ---------------------------------------------------------------------------

def get_tags(repo_path: str, pattern: str = "") -> list[str]:
    """
    Retourne tous les tags du dépôt triés par date de commit (plus récent en premier).
    Si pattern est fourni (ex: '*-beta1'), filtre par fnmatch.
    """
    import fnmatch
    try:
        repo = git.Repo(repo_path)
        tags_sorted = sorted(repo.tags, key=lambda t: t.commit.committed_date, reverse=True)
        names = [t.name for t in tags_sorted]
        if pattern:
            names = [n for n in names if fnmatch.fnmatch(n, pattern)]
        return names
    except (git.InvalidGitRepositoryError, git.GitCommandError, Exception):
        return []


def get_latest_beta1_tag(repo_path: str) -> str:
    """Retourne le tag le plus récent correspondant à *-beta1, ou '' si aucun."""
    tags = get_tags(repo_path, pattern="*-beta1")
    return tags[0] if tags else ""


def get_all_files_at_tag(repo_path: str, tag: str) -> list[str]:
    """
    Retourne tous les fichiers présents dans le dépôt au commit du tag donné.
    Équivalent de `git ls-tree -r --name-only <tag>`.
    """
    try:
        repo = git.Repo(repo_path)
        commit = repo.commit(tag)
        return sorted(item.path for item in commit.tree.traverse()
                      if item.type == "blob")
    except (git.InvalidGitRepositoryError, git.GitCommandError, Exception):
        return []


def find_previous_tag(repo_path: str, current_tag: str) -> str | None:
    """
    Trouve le tag précédent dans le dépôt local, trié par date de commit.
    Retourne None si introuvable ou si current_tag est le premier.
    """
    try:
        repo = git.Repo(repo_path)
        tags_sorted = sorted(repo.tags, key=lambda t: t.commit.committed_date)
        names = [t.name for t in tags_sorted]
        idx = names.index(current_tag)
        return names[idx - 1] if idx > 0 else None
    except (git.InvalidGitRepositoryError, git.GitCommandError, ValueError, IndexError):
        return None


def get_diff_files(
    repo_path: str,
    tag_from: str,
    tag_to: str,
) -> list[tuple[str, str]]:
    """
    Retourne [(change_type, path)] entre tag_from et tag_to.
    change_type : 'A' (ajouté), 'M' (modifié), 'D' (supprimé), 'R' (renommé), 'T' (type).
    """
    repo = git.Repo(repo_path)
    commit_from = repo.commit(tag_from)
    commit_to   = repo.commit(tag_to)
    result = []
    for diff in commit_from.diff(commit_to):
        path = diff.b_path or diff.a_path
        result.append((diff.change_type, path))
    return result


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _decode_password(encoded: str) -> str:
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def _make_askpass_script(passphrase: str) -> str:
    """
    Crée un script temporaire qui retourne la passphrase (pour SSH_ASKPASS).
    Retourne le chemin du script (à supprimer après usage).
    """
    if os.name == "nt":
        # .bat : pas de risque d'injection si passphrase ne contient pas de ^, &, etc.
        # On utilise un fichier encodé en base64 pour éviter tout problème de caractères spéciaux.
        encoded = base64.b64encode(passphrase.encode("utf-8")).decode("ascii")
        content = (
            "@echo off\n"
            f"python -c \"import base64,sys; sys.stdout.buffer.write(base64.b64decode('{encoded}') + b'\\n')\"\n"
        )
        suffix = ".bat"
    else:
        safe = passphrase.replace("'", "'\\''")
        content = f"#!/bin/sh\nprintf '%s\\n' '{safe}'\n"
        suffix = ".sh"

    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        os.close(fd)
        raise

    if os.name != "nt":
        os.chmod(path, 0o700)

    return path


def _build_env(conn_method: str, git_prefs: dict, passphrase: str) -> tuple[dict, str | None]:
    """
    Construit les variables d'environnement Git.
    Retourne (env_dict, chemin_askpass_à_supprimer_ou_None).
    """
    env: dict[str, str] = {}
    askpass_path: str | None = None

    if conn_method == "SSH":
        ssh_key = git_prefs.get("ssh_key", "").strip()
        if ssh_key:
            ssh_cmd = f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no'
            if passphrase:
                askpass_path = _make_askpass_script(passphrase)
                env["SSH_ASKPASS"] = askpass_path
                env["SSH_ASKPASS_REQUIRE"] = "force"
                # DISPLAY doit être défini (même factice) sur certains systèmes
                env.setdefault("DISPLAY", "dummy")
            else:
                ssh_cmd += " -o BatchMode=yes"
            env["GIT_SSH_COMMAND"] = ssh_cmd

    env["GIT_TERMINAL_PROMPT"] = "0"   # pas de prompt interactif
    return env, askpass_path


def _inject_https_credentials(url: str, login: str, password: str) -> str:
    """Injecte login:password dans une URL HTTPS."""
    from urllib.parse import urlparse, urlunparse, quote
    if not (login and password):
        return url
    parsed = urlparse(url)
    netloc = f"{quote(login, safe='')}:{quote(password, safe='')}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


# ---------------------------------------------------------------------------
# Classe de progression
# ---------------------------------------------------------------------------

class _Progress(git.RemoteProgress):
    def __init__(self, label: str, callback: Callable[[str, str], None]) -> None:
        super().__init__()
        self._label = label
        self._callback = callback

    def update(self, op_code, cur_count, max_count=None, message=""):
        if max_count and max_count > 0:
            pct = f"{int(cur_count / max_count * 100)}%"
        else:
            pct = "…"
        msg = f"{pct} {message}".strip()
        if msg:
            self._callback(self._label, msg)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def sync_repo(
    label: str,
    local_path: str,
    remote_url: str,
    conn_method: str,
    prefs: dict,
    on_progress: Callable[[str, str], None],
    passphrase: str = "",
) -> bool:
    """
    Clone le dépôt si absent, pull si déjà présent.
    Appelle on_progress(label, message) à chaque étape.
    Retourne True si succès, False si erreur.
    """
    if not local_path or not remote_url:
        on_progress(label, "⚠ Ignoré (chemins non configurés)")
        return True

    git_prefs = prefs.get("git", {})
    askpass_path: str | None = None

    try:
        env, askpass_path = _build_env(conn_method, git_prefs, passphrase)

        if conn_method == "HTTPS":
            login    = git_prefs.get("https_login", "")
            password = _decode_password(git_prefs.get("https_password", ""))
            url = _inject_https_credentials(remote_url, login, password)
        else:
            url = remote_url

        progress = _Progress(label, on_progress)
        dot_git  = os.path.join(local_path, ".git")

        if os.path.isdir(dot_git):
            # --- Pull ---
            on_progress(label, "Pull en cours…")
            repo = git.Repo(local_path)
            with repo.git.custom_environment(**env):
                origin = repo.remotes["origin"]
                origin.pull(progress=progress)
            on_progress(label, "✔ À jour")
        else:
            # --- Clone ---
            on_progress(label, "Clone en cours…")
            os.makedirs(local_path, exist_ok=True)
            git.Repo.clone_from(
                url, local_path,
                progress=progress,
                env=env if env else None,
            )
            on_progress(label, "✔ Cloné")

        return True

    except git.GitCommandError as exc:
        stderr = (exc.stderr or "").strip()
        on_progress(label, f"✘ {stderr or str(exc)}")
        return False
    except Exception as exc:
        on_progress(label, f"✘ {exc}")
        return False
    finally:
        if askpass_path and os.path.exists(askpass_path):
            try:
                os.unlink(askpass_path)
            except OSError:
                pass
