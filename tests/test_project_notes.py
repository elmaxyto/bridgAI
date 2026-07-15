from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_ai_bridge.core.project_notes import (
    ProjectNoteError, delete_project_note, load_project_notes, project_notes_path,
    upsert_project_note,
)


def test_project_notes_round_trip_and_update(tmp_path: Path) -> None:
    created = upsert_project_note(
        tmp_path, title="Idea editor", content="Aggiungere autosalvataggio", todo=True
    )
    assert project_notes_path(tmp_path).is_file()
    assert load_project_notes(tmp_path) == [created]

    updated = upsert_project_note(
        tmp_path,
        note_id=created.note_id,
        title="Idea editor aggiornata",
        content="Aggiungere autosalvataggio e ricerca",
        todo=True,
        completed=True,
    )
    notes = load_project_notes(tmp_path)
    assert len(notes) == 1
    assert notes[0] == updated
    assert updated.created_at == created.created_at
    assert updated.completed is True


def test_project_notes_reject_empty_title_and_delete(tmp_path: Path) -> None:
    with pytest.raises(ProjectNoteError, match="titolo"):
        upsert_project_note(tmp_path, title="   ")
    note = upsert_project_note(tmp_path, title="Da rimuovere")
    delete_project_note(tmp_path, note.note_id)
    assert load_project_notes(tmp_path) == []


def test_project_notes_ignore_invalid_records(tmp_path: Path) -> None:
    path = project_notes_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"notes": [{"id": "", "title": ""}, {"id": "ok", "title": "Valida"}]}), encoding="utf-8")
    notes = load_project_notes(tmp_path)
    assert [note.title for note in notes] == ["Valida"]


def test_project_note_request_block_is_ready_for_ai_prompt(tmp_path: Path) -> None:
    note = upsert_project_note(
        tmp_path,
        title="UI note",
        content="Migliorare lista e pulsanti",
        todo=True,
        completed=False,
    )

    from local_ai_bridge.core.project_notes import project_note_request_block

    block = project_note_request_block(note)
    assert "Nota di progetto: UI note" in block
    assert "Stato attività: da completare" in block
    assert "Dettagli:\nMigliorare lista e pulsanti" in block


def test_project_notes_ui_uses_standard_switches_and_shared_card_language() -> None:
    from local_ai_bridge.ui import project_notes

    source = Path(project_notes.__file__).read_text(encoding="utf-8")
    assert "from local_ai_bridge.ui.widgets import ToggleSwitch" in source
    assert "window.project_note_todo = ToggleSwitch(_('Attività'))" in source
    assert "window.project_note_completed = ToggleSwitch(_('Completata'))" in source
    assert "setProperty(\"class\", \"card\")" in source
    assert "pageTitle" in source
    assert "pageSubtitle" in source
