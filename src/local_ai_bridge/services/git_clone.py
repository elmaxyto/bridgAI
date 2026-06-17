from __future__ import annotations

import os
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

from local_ai_bridge.services.git import GitIntegrationError, git_available


_CLONE_SCP_PATTERN = re.compile(
    r"^(?:(?P<user>[A-Za-z0-9._-]+)@)?(?P<host>[A-Za-z0-9.-]+):"
    r"(?P<path>[A-Za-z0-9._~][A-Za-z0-9._~/-]*)$"
)


def normalize_clone_url(value: str) -> str:
    """Validate a remote Git URL without allowing local or helper protocols."""
    repository = value.strip()
    if not repository:
        raise GitIntegrationError("Inserisci l'URL del repository da clonare.")
    if repository.startswith("-") or any(ord(char) < 32 for char in repository):
        raise GitIntegrationError("URL del repository non valido.")

    scp_match = _CLONE_SCP_PATTERN.fullmatch(repository)
    if scp_match:
        if ".." in Path(scp_match.group("path")).parts:
            raise GitIntegrationError("Percorso remoto non valido.")
        return repository

    parsed = urllib.parse.urlsplit(repository)
    if parsed.scheme not in {"https", "ssh"}:
        raise GitIntegrationError(
            "Sono ammessi soltanto URL HTTPS, SSH o nel formato git@host:owner/repo.git."
        )
    if not parsed.hostname or not parsed.path.strip("/"):
        raise GitIntegrationError("URL del repository incompleto.")
    if parsed.password is not None:
        raise GitIntegrationError("Non inserire password o token nell'URL del repository.")
    if parsed.query or parsed.fragment:
        raise GitIntegrationError("L'URL del repository non può contenere query o frammenti.")
    if ".." in Path(parsed.path).parts:
        raise GitIntegrationError("Percorso remoto non valido.")
    return repository


def clone_destination_name(repository_url: str) -> str:
    repository = normalize_clone_url(repository_url)
    scp_match = _CLONE_SCP_PATTERN.fullmatch(repository)
    path_part = scp_match.group("path") if scp_match else urllib.parse.urlsplit(repository).path
    name = path_part.rstrip("/").rsplit("/", 1)[-1]
    if name.lower().endswith(".git"):
        name = name[:-4]
    if not name:
        raise GitIntegrationError("Impossibile ricavare il nome del progetto dall'URL.")
    return name


def _run_clone(repository: str, destination: Path, timeout: int) -> str:
    environment = os.environ.copy()
    environment.setdefault("GIT_TERMINAL_PROMPT", "0")
    command = ["git", "clone", "--", repository, destination.name]
    try:
        result = subprocess.run(
            command,
            cwd=destination.parent,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitIntegrationError(f"Clonazione scaduta dopo {timeout} secondi.") from exc
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile avviare Git: {exc}") from exc

    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        raise GitIntegrationError(f"Git non ha completato la clonazione: {output or result.returncode}")
    return output or "Repository clonato."


def clone_repository(repository_url: str, destination: Path, timeout: int = 600) -> str:
    if not git_available():
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.")
    repository = normalize_clone_url(repository_url)
    destination = destination.expanduser()
    if destination.exists() or destination.is_symlink():
        raise GitIntegrationError("La cartella di destinazione esiste già.")
    parent = destination.parent.resolve(strict=True)
    if not parent.is_dir():
        raise GitIntegrationError("La root dei progetti non è una directory valida.")
    destination = parent / destination.name

    try:
        output = _run_clone(repository, destination, timeout)
    except Exception:
        if destination.exists() and destination.parent.resolve() == parent:
            shutil.rmtree(destination, ignore_errors=True)
        raise
    if not destination.is_dir():
        raise GitIntegrationError("Git non ha creato la cartella del progetto.")
    return output
