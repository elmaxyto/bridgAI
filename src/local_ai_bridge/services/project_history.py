from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from local_ai_bridge.core.io import atomic_write
from local_ai_bridge.core.models import SessionRecord

HISTORY_MARKDOWN = "BRIDGAI_HISTORY.md"
HISTORY_JOURNAL = ".bridgai/applied-history.jsonl"
_HISTORY_HEADER = (
    "# BridgAI project history\n\n"
    "Cronostoria permanente delle modifiche applicate tramite BridgAI.\n\n"
)
_TRACKED_OPERATIONS = {"zip", "patch", "full_file"}
_TRACKED_STATUSES = {"applied", "rolled_back", "failed_rolled_back"}


@dataclass(slots=True)
class ProjectHistoryEntry:
    session_id: str
    created_at: str
    operation: str
    status: str
    commit_message: str | None
    files: list[str]
    test_results: list[dict[str, Any]]
    source: str | None = None
    error: str | None = None


def project_history_markdown_path(workspace: Path) -> Path:
    return workspace.resolve() / HISTORY_MARKDOWN


def project_history_journal_path(workspace: Path) -> Path:
    return workspace.resolve() / HISTORY_JOURNAL


def _entry_key(entry: ProjectHistoryEntry) -> tuple[str, str]:
    return entry.session_id, entry.status


def _record_is_project_history_candidate(record: SessionRecord) -> bool:
    return record.operation in _TRACKED_OPERATIONS and record.status in _TRACKED_STATUSES


def _entry_from_record(record: SessionRecord) -> ProjectHistoryEntry:
    files = [str(item.get("target") or "").strip() for item in record.files]
    return ProjectHistoryEntry(
        session_id=record.session_id,
        created_at=record.created_at,
        operation=record.operation,
        status=record.status,
        commit_message=record.commit_message,
        files=[item for item in files if item],
        test_results=list(record.test_results),
        source=record.source,
        error=record.error,
    )


def _entry_to_dict(entry: ProjectHistoryEntry) -> dict[str, Any]:
    return {
        "schema": 1,
        "session_id": entry.session_id,
        "created_at": entry.created_at,
        "operation": entry.operation,
        "status": entry.status,
        "commit_message": entry.commit_message,
        "files": entry.files,
        "test_results": entry.test_results,
        "source": entry.source,
        "error": entry.error,
    }


def _entry_from_dict(data: dict[str, Any]) -> ProjectHistoryEntry:
    return ProjectHistoryEntry(
        session_id=str(data.get("session_id") or ""),
        created_at=str(data.get("created_at") or ""),
        operation=str(data.get("operation") or ""),
        status=str(data.get("status") or ""),
        commit_message=data.get("commit_message") if isinstance(data.get("commit_message"), str) else None,
        files=[str(item) for item in data.get("files") or [] if str(item).strip()],
        test_results=list(data.get("test_results") or []),
        source=data.get("source") if isinstance(data.get("source"), str) else None,
        error=data.get("error") if isinstance(data.get("error"), str) else None,
    )


def _status_label(status: str) -> str:
    return {
        "applied": "applicata",
        "rolled_back": "ripristinata",
        "failed_rolled_back": "fallita e ripristinata",
    }.get(status, status)


def _operation_label(operation: str) -> str:
    return {
        "zip": "ZIP",
        "patch": "patch",
        "full_file": "file completo",
    }.get(operation, operation)


def _format_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M:%S %Z").strip()


def _sort_key(entry: ProjectHistoryEntry) -> tuple[str, str, str]:
    return entry.created_at, entry.session_id, entry.status


def _commit_title(message: str | None) -> str:
    if not message:
        return "Nessun messaggio salvato"
    for line in message.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "Nessun messaggio salvato"


def _markdown_block(entry: ProjectHistoryEntry) -> str:
    lines = [
        f"## {_format_timestamp(entry.created_at)} — {_operation_label(entry.operation)} — {_status_label(entry.status)}",
        "",
        f"**Sessione:** `{entry.session_id}`",
        f"**Messaggio:** {_commit_title(entry.commit_message)}",
    ]
    if entry.commit_message:
        details = [line.rstrip() for line in entry.commit_message.splitlines()[1:] if line.strip()]
        if details:
            lines.extend(["", "**Dettagli:**", *details])
    if entry.files:
        lines.extend(["", "**File modificati:**"])
        lines.extend(f"- `{item}`" for item in entry.files)
    if entry.test_results:
        passed = sum(1 for item in entry.test_results if item.get("status") == "passed")
        failed = sum(1 for item in entry.test_results if item.get("status") in {"failed", "timeout", "error"})
        lines.extend(["", f"**Test salvati:** {passed} ok, {failed} problemi"])
    if entry.error:
        lines.extend(["", f"**Errore:** {entry.error}"])
    return "\n".join(lines).rstrip() + "\n"


def _deduplicate_entries(entries: Iterable[ProjectHistoryEntry]) -> list[ProjectHistoryEntry]:
    by_key: dict[tuple[str, str], ProjectHistoryEntry] = {}
    for entry in entries:
        if not entry.session_id:
            continue
        by_key[_entry_key(entry)] = entry
    return sorted(by_key.values(), key=_sort_key)


def _write_history_files(workspace: Path, entries: Iterable[ProjectHistoryEntry]) -> None:
    ordered = _deduplicate_entries(entries)
    journal = project_history_journal_path(workspace)
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal_text = "".join(
        json.dumps(_entry_to_dict(entry), ensure_ascii=False, sort_keys=True) + "\n"
        for entry in ordered
    )
    atomic_write(journal, journal_text.encode("utf-8"))

    markdown = project_history_markdown_path(workspace)
    markdown_text = _HISTORY_HEADER
    if ordered:
        markdown_text += "\n".join(_markdown_block(entry).rstrip() for entry in ordered) + "\n"
    atomic_write(markdown, markdown_text.encode("utf-8"))


def append_project_history(workspace: Path, record: SessionRecord) -> None:
    """Persist an apply/rollback event inside the project itself.

    The session store lives in the application data directory and can disappear when
    the app data is cleaned or when the project moves to another machine. This
    project-local journal is intentionally stored in the workspace so the history can
    be committed, copied, backed up, and reviewed with the rest of the project.
    """
    entry = _entry_from_record(record)
    entries = list(_iter_journal_entries(workspace))
    entries.append(entry)
    _write_history_files(workspace, entries)


def _iter_journal_entries(workspace: Path) -> Iterable[ProjectHistoryEntry]:
    journal = project_history_journal_path(workspace)
    if not journal.exists():
        return []
    entries: list[ProjectHistoryEntry] = []
    for line in journal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entry = _entry_from_dict(payload)
            if entry.session_id:
                entries.append(entry)
    return entries


def migrate_project_history_from_sessions(workspace: Path, session_manager) -> int:
    """Silently copy old app-data apply sessions into the project journal.

    Older BridgAI versions kept apply history only under the local app-data
    ``sessions`` directory. This migration is deliberately idempotent and quiet: it
    imports only records for the currently opened workspace and never blocks the UI.
    """
    entries = list(_iter_journal_entries(workspace))
    seen = {_entry_key(entry) for entry in entries}
    imported = 0
    for _directory, record in session_manager.iter_for_workspace(workspace):
        if not _record_is_project_history_candidate(record):
            continue
        entry = _entry_from_record(record)
        key = _entry_key(entry)
        if key in seen:
            continue
        entries.append(entry)
        seen.add(key)
        imported += 1
    if imported:
        _write_history_files(workspace, entries)
    return imported


def read_project_history_entries(workspace: Path, session_manager=None, limit: int = 50) -> list[ProjectHistoryEntry]:
    if session_manager is not None:
        try:
            migrate_project_history_from_sessions(workspace, session_manager)
        except Exception:
            # Lo storico locale resta solo un fallback: un errore di migrazione non
            # deve impedire di mostrare la scheda Pubblicazione.
            pass

    entries = list(_iter_journal_entries(workspace))
    seen = {_entry_key(entry) for entry in entries}
    if session_manager is not None:
        for _directory, record in session_manager.iter_for_workspace(workspace):
            if not _record_is_project_history_candidate(record):
                continue
            entry = _entry_from_record(record)
            key = _entry_key(entry)
            if key in seen:
                continue
            entries.append(entry)
            seen.add(key)
    entries.sort(key=lambda item: item.created_at, reverse=True)
    return entries[:limit]
