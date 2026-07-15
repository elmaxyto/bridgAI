from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


class GitIntegrationError(RuntimeError):
    """Errore leggibile prodotto da Git o GitHub CLI."""


def git_available() -> bool:
    return shutil.which("git") is not None


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return ((result.stdout or "") + (result.stderr or "")).strip()


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 60,
    check: bool = True,
) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitIntegrationError(f"Comando non disponibile: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitIntegrationError(f"Comando scaduto dopo {timeout} secondi: {command[0]}") from exc
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile avviare {command[0]}: {exc}") from exc

    text = _output(result)
    if check and result.returncode != 0:
        detail = text or f"codice di uscita {result.returncode}"
        raise GitIntegrationError(f"{command[0]} non ha completato l'operazione: {detail}")
    return text or "Operazione completata."


def is_git_repository(workspace: Path) -> bool:
    return (workspace / ".git").exists()


def _git(workspace: Path, args: list[str], timeout: int = 20) -> str:
    if not is_git_repository(workspace):
        return "Repository Git non rilevato."
    try:
        return _run_command(["git", *args], cwd=workspace, timeout=timeout, check=False)
    except GitIntegrationError as exc:
        return f"Git non disponibile: {exc}"


def git_status(workspace: Path) -> str:
    return _git(workspace, ["status", "--short", "--branch"])


def git_diff(workspace: Path) -> str:
    return _git(workspace, ["diff", "--stat", "--", "."]) + "\n\n" + _git(
        workspace, ["diff", "--", "."]
    )


def git_remotes(workspace: Path) -> str:
    return _git(workspace, ["remote", "-v"])


def git_init(workspace: Path) -> str:
    if not git_available():
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.")
    if is_git_repository(workspace):
        return "Il workspace è già un repository Git."
    return _run_command(
        ["git", "-c", "init.defaultBranch=main", "init"],
        cwd=workspace,
        timeout=30,
    )


def git_remote_url(workspace: Path, remote_name: str = "origin") -> str | None:
    if not is_git_repository(workspace):
        return None
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote_name],
            cwd=workspace,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def git_has_commits(workspace: Path) -> bool:
    if not is_git_repository(workspace):
        return False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=workspace,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _git_config_value(workspace: Path, key: str) -> str | None:
    if not git_available():
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.")
    if not is_git_repository(workspace):
        raise GitIntegrationError("Il workspace non è ancora un repository Git.")
    try:
        result = subprocess.run(
            ["git", "config", "--get", key],
            cwd=workspace,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitIntegrationError("Lettura della configurazione Git scaduta.") from exc
    except OSError as exc:
        raise GitIntegrationError(f"Impossibile leggere la configurazione Git: {exc}") from exc
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        detail = _output(result) or f"codice di uscita {result.returncode}"
        raise GitIntegrationError(f"Git non ha letto {key}: {detail}")
    return (result.stdout or "").strip() or None


def git_author_identity(workspace: Path) -> tuple[str | None, str | None]:
    """Return the effective Git author name and email for the workspace."""
    return (
        _git_config_value(workspace, "user.name"),
        _git_config_value(workspace, "user.email"),
    )


def _validate_identity_value(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized or "\n" in normalized or "\r" in normalized or "\x00" in normalized:
        raise GitIntegrationError(f"{label} Git non valido.")
    return normalized


def ensure_git_author_identity(workspace: Path, *, name: str, email: str) -> str:
    """Fill missing author fields locally without overriding existing Git settings."""
    current_name, current_email = git_author_identity(workspace)
    updates: list[str] = []
    if current_name is None:
        safe_name = _validate_identity_value(name, "Nome autore")
        _run_command(
            ["git", "config", "--local", "user.name", safe_name],
            cwd=workspace,
            timeout=20,
        )
        updates.append("nome")
    if current_email is None:
        safe_email = _validate_identity_value(email, "Email autore")
        _run_command(
            ["git", "config", "--local", "user.email", safe_email],
            cwd=workspace,
            timeout=20,
        )
        updates.append("email")
    if not updates:
        return ""
    return "Identità autore Git configurata localmente: " + " e ".join(updates) + "."


def git_current_branch(workspace: Path) -> str:
    if not is_git_repository(workspace):
        raise GitIntegrationError("Il workspace non è ancora un repository Git.")
    branch = _run_command(
        ["git", "branch", "--show-current"], cwd=workspace, timeout=20
    ).strip()
    if not branch or branch == "Operazione completata.":
        raise GitIntegrationError("Nessun branch corrente: crea almeno un commit prima del push.")
    return branch


def validate_remote_name(remote_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", remote_name):
        raise GitIntegrationError("Nome remote non valido.")
    return remote_name


def push_current_branch(workspace: Path, remote_name: str = "origin") -> str:
    if not git_available():
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.")
    if not is_git_repository(workspace):
        raise GitIntegrationError("Il workspace non è ancora un repository Git.")
    remote_name = validate_remote_name(remote_name)
    if not git_remote_url(workspace, remote_name):
        raise GitIntegrationError(f"Remote {remote_name} non configurato.")
    if not git_has_commits(workspace):
        raise GitIntegrationError("Non ci sono commit locali da inviare.")
    branch = git_current_branch(workspace)
    output = _run_command(
        ["git", "push", "--set-upstream", remote_name, branch],
        cwd=workspace,
        timeout=180,
    )
    return output + f"\n\nBranch {branch} inviato a {remote_name}."


def _git_lines(workspace: Path, args: list[str]) -> list[str]:
    if not git_available():
        raise GitIntegrationError("Git non è installato o non è presente nel PATH.")
    if not is_git_repository(workspace):
        raise GitIntegrationError("Il workspace non è ancora un repository Git.")
    output = _run_command(["git", *args], cwd=workspace, timeout=30)
    if output == "Operazione completata.":
        return []
    return [line for line in output.splitlines() if line.strip()]


def _current_changes(workspace: Path) -> list[tuple[str, str]]:
    lines = _git_lines(workspace, ["status", "--porcelain=v1", "--untracked-files=all"])
    changes: list[tuple[str, str]] = []
    for line in lines:
        if len(line) < 4:
            continue
        code = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if "D" in code:
            action = "delete"
        elif "A" in code or code == "??":
            action = "create"
        elif "R" in code:
            action = "rename"
        else:
            action = "modify"
        changes.append((action, path))
    return changes


def _last_commit_time(workspace: Path) -> datetime | None:
    if not git_has_commits(workspace):
        return None
    text = _run_command(
        ["git", "log", "-1", "--format=%cI"], cwd=workspace, timeout=20, check=False
    ).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _suggested_messages(session_manager, workspace: Path) -> list[str]:
    messages: list[str] = []
    last_commit = _last_commit_time(workspace)
    for _directory, record in session_manager.iter_for_workspace(workspace):
        if record.status != "applied":
            continue
        if last_commit is not None:
            try:
                created = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                created = None
            if created is not None and created <= last_commit:
                continue
        message = getattr(record, "commit_message", None)
        if isinstance(message, str) and message.strip():
            messages.append(message.strip())
    return list(reversed(messages))


def generate_commit_message(workspace: Path, session_manager=None) -> str:
    """Build a reviewable commit message from the real Git working tree and session notes."""
    changes = _current_changes(workspace)
    if not changes:
        raise GitIntegrationError("Non ci sono modifiche Git da descrivere.")

    suggestions = _suggested_messages(session_manager, workspace) if session_manager is not None else []
    suggested_title = ""
    suggested_bullets: list[str] = []
    for message in suggestions:
        lines = [line.strip() for line in message.splitlines() if line.strip()]
        if not suggested_title and lines:
            suggested_title = lines[0].lstrip("# ").strip()
        for line in lines[1:]:
            cleaned = line.lstrip("-* ").strip()
            if cleaned and cleaned not in suggested_bullets:
                suggested_bullets.append(cleaned)

    counts: dict[str, int] = {}
    for action, _path in changes:
        counts[action] = counts.get(action, 0) + 1
    if suggested_title:
        title = suggested_title[:72]
    else:
        dominant = max(counts, key=counts.get)
        verb = {"create": "add", "modify": "update", "delete": "remove", "rename": "rename"}[dominant]
        title = f"chore: {verb} {len(changes)} project file{'s' if len(changes) != 1 else ''}"

    bullets: list[str] = []
    for bullet in suggested_bullets:
        if bullet not in bullets:
            bullets.append(bullet)
    action_labels = {"create": "Add", "modify": "Update", "delete": "Remove", "rename": "Rename"}
    for action in ("create", "modify", "delete", "rename"):
        paths = [path for item_action, path in changes if item_action == action]
        if not paths:
            continue
        preview = ", ".join(paths[:5])
        if len(paths) > 5:
            preview += f", and {len(paths) - 5} more"
        bullet = f"{action_labels[action]} {preview}"
        if bullet not in bullets:
            bullets.append(bullet)
    return title + "\n\n" + "\n".join(f"- {item}" for item in bullets)


def create_commit(workspace: Path, message: str) -> str:
    """Stage current workspace changes and create a commit after explicit UI approval."""
    if not message.strip():
        raise GitIntegrationError("Il messaggio di commit è vuoto.")
    if not _current_changes(workspace):
        raise GitIntegrationError("Non ci sono modifiche da includere nel commit.")
    _run_command(["git", "add", "--all", "--", "."], cwd=workspace, timeout=60)
    return _run_command(["git", "commit", "-m", message.strip()], cwd=workspace, timeout=120)
