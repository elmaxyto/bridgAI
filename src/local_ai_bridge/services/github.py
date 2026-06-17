from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from local_ai_bridge.services.git import (
    GitIntegrationError,
    _run_command,
    git_available,
    git_has_commits,
    git_init,
    git_remote_url,
    is_git_repository,
    validate_remote_name,
)


_GITHUB_HOST = "github.com"
_REPOSITORY_PART = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_ACCOUNT_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


@dataclass(frozen=True, slots=True)
class GitHubRepository:
    name_with_owner: str
    url: str
    is_private: bool
    description: str = ""

    @property
    def display_name(self) -> str:
        visibility = "privato" if self.is_private else "pubblico"
        return f"{self.name_with_owner} ({visibility})"


def github_cli_available() -> bool:
    return shutil.which("gh") is not None


def github_auth_status() -> str:
    if not github_cli_available():
        return (
            "GitHub CLI (gh) non è installata. Installala dal sito ufficiale, "
            "poi riavvia Local AI Bridge."
        )
    try:
        return _run_command(
            ["gh", "auth", "status", "--hostname", _GITHUB_HOST],
            timeout=30,
            check=False,
        )
    except GitIntegrationError as exc:
        return str(exc)


def github_login_command() -> tuple[str, list[str]]:
    return (
        "gh",
        [
            "auth",
            "login",
            "--hostname",
            _GITHUB_HOST,
            "--git-protocol",
            "https",
            "--web",
        ],
    )


def list_github_accounts() -> list[str]:
    if not github_cli_available():
        raise GitIntegrationError("GitHub CLI (gh) non è installata.")
    raw = _run_command(
        [
            "gh",
            "auth",
            "status",
            "--hostname",
            _GITHUB_HOST,
            "--json",
            "hosts",
            "--jq",
            '.hosts["github.com"][].login',
        ],
        timeout=30,
    )
    if raw == "Operazione completata.":
        return []
    accounts: list[str] = []
    for line in raw.splitlines():
        login = line.strip()
        if login and _ACCOUNT_NAME.fullmatch(login) and login not in accounts:
            accounts.append(login)
    return accounts


def github_switch_account(username: str) -> str:
    login = username.strip()
    if not _ACCOUNT_NAME.fullmatch(login):
        raise GitIntegrationError("Nome account GitHub non valido.")
    if not github_cli_available():
        raise GitIntegrationError("GitHub CLI (gh) non è installata.")
    return _run_command(
        [
            "gh",
            "auth",
            "switch",
            "--hostname",
            _GITHUB_HOST,
            "--user",
            login,
        ],
        timeout=30,
    )


def github_setup_git() -> str:
    if not github_cli_available():
        raise GitIntegrationError("GitHub CLI (gh) non è installata.")
    return _run_command(
        ["gh", "auth", "setup-git", "--hostname", _GITHUB_HOST],
        timeout=30,
    )


def _validate_repository_part(value: str, label: str) -> str:
    value = value.strip()
    if value in {"", ".", ".."} or value.startswith("-") or not _REPOSITORY_PART.fullmatch(value):
        raise GitIntegrationError(
            f"{label} non valido. Usa soltanto lettere, numeri, punto, trattino o underscore."
        )
    return value


def normalize_github_repository(value: str) -> tuple[str, str]:
    """Restituisce (owner/repo, URL HTTPS canonico) per un repository GitHub."""
    raw = value.strip()
    if not raw or any(character.isspace() for character in raw):
        raise GitIntegrationError("Repository GitHub non valido.")

    if raw.startswith("git@github.com:"):
        path = raw.removeprefix("git@github.com:")
    elif raw.startswith("ssh://git@github.com/"):
        path = raw.removeprefix("ssh://git@github.com/")
    elif "://" in raw:
        parsed = urlparse(raw)
        if parsed.hostname is None or parsed.hostname.lower() != _GITHUB_HOST:
            raise GitIntegrationError("Sono accettati soltanto repository ospitati su github.com.")
        path = parsed.path.lstrip("/")
    else:
        path = raw

    path = path.removesuffix(".git").strip("/")
    parts = path.split("/")
    if len(parts) != 2:
        raise GitIntegrationError("Indica il repository nel formato proprietario/nome o come URL GitHub.")
    owner = _validate_repository_part(parts[0], "Proprietario")
    name = _validate_repository_part(parts[1], "Nome repository")
    slug = f"{owner}/{name}"
    return slug, f"https://{_GITHUB_HOST}/{slug}.git"


def _validate_new_repository_name(value: str) -> str:
    raw = value.strip().strip("/")
    parts = raw.split("/")
    if len(parts) == 1:
        return _validate_repository_part(parts[0], "Nome repository")
    if len(parts) == 2:
        owner = _validate_repository_part(parts[0], "Proprietario")
        name = _validate_repository_part(parts[1], "Nome repository")
        return f"{owner}/{name}"
    raise GitIntegrationError("Nome repository non valido.")


def list_github_repositories(limit: int = 100) -> list[GitHubRepository]:
    if not github_cli_available():
        raise GitIntegrationError("GitHub CLI (gh) non è installata.")
    safe_limit = min(max(int(limit), 1), 500)
    raw = _run_command(
        [
            "gh",
            "repo",
            "list",
            "--limit",
            str(safe_limit),
            "--json",
            "nameWithOwner,url,isPrivate,description",
        ],
        timeout=60,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GitIntegrationError("GitHub CLI ha restituito un elenco repository non valido.") from exc

    repositories: list[GitHubRepository] = []
    for item in data:
        name = str(item.get("nameWithOwner", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            continue
        repositories.append(
            GitHubRepository(
                name_with_owner=name,
                url=url,
                is_private=bool(item.get("isPrivate", False)),
                description=str(item.get("description") or ""),
            )
        )
    return repositories


def create_github_repository(
    workspace: Path,
    name: str,
    *,
    visibility: str = "private",
    description: str = "",
    push: bool = False,
) -> str:
    if not github_cli_available():
        raise GitIntegrationError("GitHub CLI (gh) non è installata.")
    if visibility not in {"private", "public"}:
        raise GitIntegrationError("Visibilità GitHub non valida.")

    repository_name = _validate_new_repository_name(name)
    if not is_git_repository(workspace):
        git_init(workspace)
    existing_origin = git_remote_url(workspace, "origin")
    if existing_origin:
        raise GitIntegrationError(
            f"Il remote origin esiste già ({existing_origin}). Rimuovilo o usa Collega repository."
        )
    if push and not git_has_commits(workspace):
        raise GitIntegrationError(
            "Non ci sono commit locali da inviare. Crea almeno un commit oppure disattiva il push iniziale."
        )

    command = [
        "gh",
        "repo",
        "create",
        repository_name,
        "--source",
        ".",
        "--remote",
        "origin",
        f"--{visibility}",
    ]
    if description.strip():
        command.extend(["--description", description.strip()])
    if push:
        command.append("--push")
    output = _run_command(command, cwd=workspace, timeout=120)
    return output + "\n\nRemote origin configurato nel workspace."


def connect_github_repository(
    workspace: Path,
    repository: str,
    *,
    remote_name: str = "origin",
    replace_existing: bool = False,
) -> str:
    if not git_available():
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.")
    remote_name = validate_remote_name(remote_name)
    slug, remote_url = normalize_github_repository(repository)
    if not is_git_repository(workspace):
        git_init(workspace)

    existing = git_remote_url(workspace, remote_name)
    if existing and not replace_existing:
        raise GitIntegrationError(
            f"Il remote {remote_name} esiste già ({existing}). Conferma la sostituzione dall'interfaccia."
        )
    command = ["git", "remote", "set-url" if existing else "add", remote_name, remote_url]
    _run_command(command, cwd=workspace, timeout=30)
    action = "aggiornato" if existing else "aggiunto"
    return (
        f"Remote {remote_name} {action}: {remote_url}\n"
        f"Repository collegato: {slug}\n\n"
        "Nessun pull, merge o push è stato eseguito automaticamente."
    )
