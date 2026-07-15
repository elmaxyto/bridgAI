from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_NOTES_RELATIVE = ".bridgai/notes.json"
MAX_NOTES = 500
MAX_TITLE_CHARS = 200
MAX_CONTENT_CHARS = 50_000


class ProjectNoteError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectNote:
    note_id: str
    title: str
    content: str
    todo: bool
    completed: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: object) -> "ProjectNote":
        if not isinstance(data, dict):
            raise ProjectNoteError("Nota non valida.")
        note_id = str(data.get("id", "")).strip()
        title = str(data.get("title", "")).strip()
        content = str(data.get("content", ""))
        if not note_id or not title:
            raise ProjectNoteError("ID e titolo della nota sono obbligatori.")
        return cls(
            note_id=note_id,
            title=title[:MAX_TITLE_CHARS],
            content=content[:MAX_CONTENT_CHARS],
            todo=bool(data.get("todo", False)),
            completed=bool(data.get("completed", False)),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.note_id,
            "title": self.title,
            "content": self.content,
            "todo": self.todo,
            "completed": self.completed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def project_notes_path(workspace: Path) -> Path:
    return workspace / PROJECT_NOTES_RELATIVE


def load_project_notes(workspace: Path) -> list[ProjectNote]:
    try:
        raw = json.loads(project_notes_path(workspace).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    items = raw.get("notes", []) if isinstance(raw, dict) else []
    result: list[ProjectNote] = []
    for item in items[:MAX_NOTES] if isinstance(items, list) else []:
        try:
            result.append(ProjectNote.from_dict(item))
        except ProjectNoteError:
            continue
    return sorted(result, key=lambda note: note.updated_at, reverse=True)


def save_project_notes(workspace: Path, notes: list[ProjectNote]) -> Path:
    path = project_notes_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"version": 1, "notes": [note.to_dict() for note in notes[:MAX_NOTES]]}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def upsert_project_note(
    workspace: Path,
    *,
    note_id: str = "",
    title: str,
    content: str = "",
    todo: bool = False,
    completed: bool = False,
) -> ProjectNote:
    normalized_title = title.strip()[:MAX_TITLE_CHARS]
    if not normalized_title:
        raise ProjectNoteError("Il titolo della nota è obbligatorio.")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    notes = load_project_notes(workspace)
    existing = next((item for item in notes if item.note_id == note_id), None)
    note = ProjectNote(
        note_id=existing.note_id if existing else uuid.uuid4().hex,
        title=normalized_title,
        content=content[:MAX_CONTENT_CHARS],
        todo=bool(todo),
        completed=bool(completed) if todo else False,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    updated = [note] + [item for item in notes if item.note_id != note.note_id]
    save_project_notes(workspace, updated)
    return note


def delete_project_note(workspace: Path, note_id: str) -> None:
    normalized = note_id.strip()
    notes = load_project_notes(workspace)
    updated = [item for item in notes if item.note_id != normalized]
    if len(updated) == len(notes):
        raise ProjectNoteError("Nota non trovata.")
    save_project_notes(workspace, updated)


def project_note_payload(note: ProjectNote) -> dict[str, object]:
    return note.to_dict()


def project_note_request_block(note: ProjectNote) -> str:
    """Return a compact, readable block that can be appended to an AI request."""
    lines = [f"Nota di progetto: {note.title}"]
    if note.todo:
        status = "completata" if note.completed else "da completare"
        lines.append(f"Stato attività: {status}")
    content = note.content.strip()
    if content:
        lines.extend(["Dettagli:", content])
    return "\n".join(lines).strip()
