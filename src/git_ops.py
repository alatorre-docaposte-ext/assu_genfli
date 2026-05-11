"""
git_ops.py — Opérations Git (clone / pull) via GitPython.

Gère SSH (clé + passphrase optionnelle) et HTTPS (credentials en base64).
"""
from __future__ import annotations

import base64
import datetime
import os
import shutil
import tempfile
from typing import Callable

import git

from src.logger import get_logger

_log = get_logger()


# ---------------------------------------------------------------------------
# Diff Git
# ---------------------------------------------------------------------------

def get_tags(repo_path: str, pattern: str = "") -> list[str]:
    """
    Retourne tous les tags du dépôt triés par date de commit (plus récent en premier).
    Si pattern est fourni (ex: '*-beta1'), filtre par fnmatch.
    """
    import fnmatch
    _log.debug("[git] get_tags  cwd=%s  pattern=%r", repo_path, pattern)
    try:
        repo = git.Repo(repo_path)
        tags_sorted = sorted(repo.tags, key=lambda t: t.commit.committed_date, reverse=True)
        names = [t.name for t in tags_sorted]
        if pattern:
            names = [n for n in names if fnmatch.fnmatch(n, pattern)]
        _log.debug("[git] get_tags  → %d tag(s) found", len(names))
        return names
    except (git.InvalidGitRepositoryError, git.GitCommandError, Exception) as exc:
        _log.warning("[git] get_tags  cwd=%s  error: %s", repo_path, exc)
        return []


def get_latest_beta1_tag(repo_path: str) -> str:
    """Retourne le tag le plus récent correspondant à *-beta1, ou '' si aucun."""
    tags = get_tags(repo_path, pattern="*-beta1")
    return tags[0] if tags else ""


def get_last_fli_commit(repo_path: str, code: str, max_commits: int = 50) -> dict | None:
    """
    Parcourt les derniers commits (jusqu'à max_commits) et retourne le premier
    dont le message correspond au pattern FLI_{code}_EXT_LIV_\\d+.

    Retourne un dict {message, date (datetime), fli_id (int)} ou None.
    """
    import re
    pattern = re.compile(rf"FLI_{re.escape(code.upper())}_EXT_LIV_(\d+)", re.IGNORECASE)
    _log.debug("[git] get_last_fli_commit  cwd=%s  code=%s  max=%d", repo_path, code, max_commits)
    try:
        repo = git.Repo(repo_path)
        for commit in repo.iter_commits(max_count=max_commits):
            msg = commit.message.strip().split("\n")[0]
            m = pattern.search(msg)
            if m:
                result = {
                    "message": msg,
                    "date":    datetime.datetime.fromtimestamp(commit.committed_date),
                    "fli_id":  int(m.group(1)),
                }
                _log.info("[git] get_last_fli_commit  cwd=%s  → %s  (id=%d)",
                          repo_path, msg, result["fli_id"])
                return result
    except (git.InvalidGitRepositoryError, git.GitCommandError, Exception) as exc:
        _log.warning("[git] get_last_fli_commit  cwd=%s  error: %s", repo_path, exc)
    _log.info("[git] get_last_fli_commit  cwd=%s  → no FLI commit found in last %d commits",
              repo_path, max_commits)
    return None


def get_next_beta1_tag(repo_path: str) -> str:
    """
    Calcule le prochain tag -beta1 à partir du dernier tag de version connu.

    Stratégie :
      1. Cherche le dernier tag *-beta1  → extrait vMAJ.MIN.PATCH  → propose vMAJ.MIN.(PATCH+1)-beta1
      2. Si absent, cherche le dernier tag vMAJ.MIN.PATCH (sans suffixe) et fait pareil.
      3. Si rien trouvé, retourne ''.

    Exemples :
      v1.2.93-beta1  → v1.2.94-beta1
      v1.2.93        → v1.2.94-beta1
    """
    import re
    ver_re = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-beta1)?$")

    def _parse(tag_name: str):
        m = ver_re.match(tag_name)
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

    all_tags = get_tags(repo_path)          # triés par date desc
    for name in all_tags:
        parts = _parse(name)
        if parts:
            maj, min_, patch = parts
            result = f"v{maj}.{min_}.{patch + 1}-beta1"
            _log.info("[git] get_next_beta1_tag  cwd=%s  last=%s  → %s", repo_path, name, result)
            return result
    _log.info("[git] get_next_beta1_tag  cwd=%s  → no versioned tag found", repo_path)
    return ""


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


def get_diff_files_head_vs_prev(repo_path: str) -> list[tuple[str, str]]:
    """
    Retourne [(change_type, path)] entre le commit précédent (HEAD~1) et HEAD.
    change_type : 'A' (ajouté), 'M' (modifié), 'D' (supprimé), 'R' (renommé), 'T' (type).
    Retourne une liste vide s'il n'y a pas de commit précédent.
    """
    repo = git.Repo(repo_path)
    head = repo.head.commit
    if not head.parents:
        return []
    prev = head.parents[0]
    result = []
    for diff in prev.diff(head):
        path = diff.b_path or diff.a_path
        result.append((diff.change_type, path))
    return result


def get_all_files_at_head(repo_path: str) -> list[str]:
    """
    Retourne tous les fichiers présents au HEAD du dépôt.
    Équivalent de `git ls-tree -r --name-only HEAD`.
    """
    try:
        repo = git.Repo(repo_path)
        commit = repo.head.commit
        return sorted(item.path for item in commit.tree.traverse()
                      if item.type == "blob")
    except (git.InvalidGitRepositoryError, git.GitCommandError, Exception):
        return []


def get_commit_log(repo_path: str, max_count: int = 60) -> list[dict]:
    """
    Retourne les derniers commits du dépôt avec leurs tags associés.
    Chaque dict : hash, short_hash, date, author, message, tags (list[str]).
    """
    try:
        repo = git.Repo(repo_path)
        # Mapping SHA → liste de noms de tags
        tag_map: dict[str, list[str]] = {}
        for t in repo.tags:
            sha = t.commit.hexsha
            tag_map.setdefault(sha, []).append(t.name)
        result = []
        for c in repo.iter_commits(max_count=max_count):
            result.append({
                "hash":       c.hexsha,
                "short_hash": c.hexsha[:7],
                "date":       datetime.datetime.fromtimestamp(c.committed_date).strftime("%Y-%m-%d %H:%M"),
                "author":     c.author.name,
                "message":    c.message.strip().split("\n")[0],
                "tags":       tag_map.get(c.hexsha, []),
            })
        return result
    except (git.InvalidGitRepositoryError, git.GitCommandError, Exception):
        return []


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


# ---------------------------------------------------------------------------
# Livraison : copie fichiers + commit + tag (+ push optionnel)
# ---------------------------------------------------------------------------

def copy_and_deliver(
    src_root: str,
    dest_root: str,
    files: list[dict],
    commit_message: str,
    tag: str,
    conn_method: str,
    prefs: dict,
    on_progress: Callable[[str], None],
    push: bool = False,
    remote_url: str = "",
    passphrase: str = "",
) -> bool:
    """
    Copie les fichiers de src_root vers dest_root selon leur dest_path,
    puis commit + tag dans dest_root, et push optionnel.

    files : [{path: chemin_relatif_dans_src_root,
              dest_path: chemin_relatif_dans_dest_root}]
    Retourne True si aucune erreur, False sinon.
    """
    if not dest_root or not os.path.isdir(dest_root):
        on_progress(f"  ✘ Répertoire destination introuvable : {dest_root!r}")
        return False
    if not src_root or not os.path.isdir(src_root):
        on_progress(f"  ✘ Dépôt DEV introuvable : {src_root!r}")
        return False

    try:
        repo = git.Repo(dest_root)
    except git.InvalidGitRepositoryError:
        on_progress(f"  ✘ {dest_root!r} n'est pas un dépôt Git")
        return False

    copied: list[str] = []
    had_error = False

    # 1. Copie des fichiers
    for f in files:
        src_rel  = f["path"].replace("/", os.sep)
        dest_rel = (f.get("dest_path") or f["path"]).replace("/", os.sep)
        src_abs  = os.path.join(src_root,  src_rel)
        dest_abs = os.path.join(dest_root, dest_rel)

        if not os.path.isfile(src_abs):
            on_progress(f"  ⚠ Absent dans DEV : {f['path']}")
            had_error = True
            continue
        try:
            os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
            shutil.copy2(src_abs, dest_abs)
            dest_unix = dest_rel.replace(os.sep, "/")
            copied.append(dest_unix)
            on_progress(f"  ✓ {dest_unix}")
        except Exception as exc:
            on_progress(f"  ✘ {f['path']} : {exc}")
            had_error = True

    if not copied:
        on_progress("  ⚠ Aucun fichier copié — commit annulé")
        return False

    # 2. git add
    try:
        on_progress(f"  git add ({len(copied)} fichier(s))…")
        repo.index.add(copied)
    except Exception as exc:
        on_progress(f"  ✘ git add : {exc}")
        return False

    # 3. git commit
    try:
        on_progress(f"  git commit : {commit_message}")
        repo.index.commit(commit_message)
    except Exception as exc:
        on_progress(f"  ✘ git commit : {exc}")
        return False

    # 4. git tag
    if tag:
        try:
            existing = [t.name for t in repo.tags]
            if tag in existing:
                on_progress(f"  ⚠ Tag {tag!r} existe déjà — ignoré")
            else:
                repo.create_tag(tag)
                on_progress(f"  git tag {tag}")
        except Exception as exc:
            on_progress(f"  ⚠ git tag : {exc}")

    # 5. push (optionnel)
    if push and remote_url:
        git_prefs = prefs.get("git", {})
        askpass_path: str | None = None
        try:
            env, askpass_path = _build_env(conn_method, git_prefs, passphrase)
            on_progress("  git push…")
            with repo.git.custom_environment(**env):
                origin = repo.remotes["origin"]
                origin.push()
                if tag:
                    origin.push(tag)
            on_progress("  ✔ Poussé")
        except Exception as exc:
            on_progress(f"  ✘ push : {exc}")
            had_error = True
        finally:
            if askpass_path and os.path.exists(askpass_path):
                try:
                    os.unlink(askpass_path)
                except OSError:
                    pass

    on_progress(f"  ✔ {len(copied)} fichier(s) livrés dans {os.path.basename(dest_root)}")
    return not had_error
