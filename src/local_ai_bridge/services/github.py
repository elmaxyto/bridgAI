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
    generate_commit_message,
    create_commit,
    push_current_branch,
    _current_changes,
    is_git_repository,
    validate_remote_name,
)
from local_ai_bridge.services.gitignore import (
    ensure_publish_gitignore,
    gitignore_update_needed,
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


def _repository_slug(remote_url: str | None) -> str | None:
    if not remote_url:
        return None
    try:
        slug, _canonical = normalize_github_repository(remote_url)
    except GitIntegrationError:
        return None
    return slug


def _repository_web_url(remote_url: str | None) -> str | None:
    slug = _repository_slug(remote_url)
    return f"https://github.com/{slug}" if slug else None


def simple_github_status(workspace: Path) -> dict[str, object]:
    """Return the small set of facts needed by the one-click GitHub UI."""
    repository = is_git_repository(workspace)
    remote = git_remote_url(workspace, "origin") if repository else None
    changes = _current_changes(workspace) if repository else []
    gitignore_pending = gitignore_update_needed(workspace) if repository else False
    gitignore_already_changed = any(path.replace("\\", "/") == ".gitignore" for _action, path in changes)
    change_count = len(changes) + int(gitignore_pending and not gitignore_already_changed)
    return {
        "git_available": git_available(),
        "github_cli_available": github_cli_available(),
        "is_repository": repository,
        "published": bool(remote),
        "has_changes": change_count > 0,
        "change_count": change_count,
        "gitignore_update_pending": gitignore_pending,
        "repository_name": _repository_slug(remote),
        "suggested_repository_name": workspace.name,
        "repository_url": _repository_web_url(remote),
        "action": "update" if remote else "publish",
    }


def publish_or_update_github(
    workspace: Path,
    *,
    repository_name: str | None = None,
    visibility: str = "private",
    session_manager=None,
) -> dict[str, object]:
    """Publish or update the current project with one explicit user action.

    The function initializes Git when needed, creates a reviewable automatic
    commit from real changes, creates a GitHub repository when origin is absent,
    and pushes the current branch. It never pulls, merges, rebases, or force-pushes.
    """
    if not git_available():
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.")
    if not github_cli_available():
        raise GitIntegrationError("GitHub CLI (gh) non è installata.")
    accounts = list_github_accounts()
    if not accounts:
        raise GitIntegrationError("Nessun account GitHub collegato. Accedi a GitHub e riprova.")
    if visibility not in {"private", "public"}:
        raise GitIntegrationError("Visibilità GitHub non valida.")

    if not is_git_repository(workspace):
        git_init(workspace)

    protection = ensure_publish_gitignore(workspace)
    changes = _current_changes(workspace)
    commit_created = False
    commit_message = None
    if changes:
        commit_message = generate_commit_message(workspace, session_manager)
        create_commit(workspace, commit_message)
        commit_created = True

    if not git_has_commits(workspace):
        raise GitIntegrationError("Il progetto non contiene file da pubblicare.")

    remote = git_remote_url(workspace, "origin")
    created_repository = False
    if not remote:
        name = _validate_new_repository_name(repository_name or workspace.name)
        create_github_repository(
            workspace,
            name,
            visibility=visibility,
            description=f"Progetto {workspace.name} pubblicato con BridgAI",
            push=False,
        )
        remote = git_remote_url(workspace, "origin")
        created_repository = True

    push_output = push_current_branch(workspace)
    output_parts = [part for part in (protection.summary, push_output) if part]
    return {
        "message": "Progetto pubblicato su GitHub." if created_repository else "GitHub aggiornato correttamente.",
        "repository_created": created_repository,
        "commit_created": commit_created,
        "commit_message": commit_message,
        "change_count": len(changes),
        "gitignore_created": protection.created,
        "gitignore_updated": protection.changed,
        "untracked_generated_count": len(protection.untracked_paths),
        "repository_url": _repository_web_url(remote),
        "output": "\n\n".join(output_parts),
    }
