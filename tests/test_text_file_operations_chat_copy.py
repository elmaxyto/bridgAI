from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_bridge.services.text_file_operations import (
    TextFileOperationsParseError,
    inspect_text_file_operations,
    parse_text_file_operations,
)


def test_parser_accepts_content_when_chat_strips_markdown_fence() -> None:
    response = """BEGIN_FILE
OPERATION: CREATE
PATH: copied-from-chat.txt
FINAL_NEWLINE: YES
CONTENT:
Contenuto copiato direttamente dalla risposta della chat.

La fence Markdown è stata rimossa dal rendering.
END_FILE
"""

    document = parse_text_file_operations(response)

    assert len(document.operations) == 1
    assert document.operations[0].target == "copied-from-chat.txt"
    assert document.operations[0].content == (
        "Contenuto copiato direttamente dalla risposta della chat.\n\n"
        "La fence Markdown è stata rimossa dal rendering."
    )
    assert document.normalizations == (
        "copied-from-chat.txt: contenuto accettato senza fence Markdown "
        "a partire dalla riga 6.",
    )


def test_inspection_warns_when_chat_strips_markdown_fence(tmp_path: Path) -> None:
    response = """BEGIN_FILE
OPERATION: CREATE
PATH: harmless-test.md
FINAL_NEWLINE: YES
CONTENT:
# Prova

File innocuo creato per verificare il flusso testuale.
END_FILE
"""

    plan = inspect_text_file_operations(tmp_path, response)

    assert [change.target for change in plan.changes] == ["harmless-test.md"]
    assert plan.metadata["normalized_text_formatting"] == [
        "harmless-test.md: contenuto accettato senza fence Markdown "
        "a partire dalla riga 6."
    ]
    assert any("formattazione incompleta o rimossa dalla chat" in item for item in plan.warnings)
    assert "# Prova" in plan.diff


def test_parser_accepts_fence_with_chat_metadata_without_normalizing() -> None:
    response = '''BEGIN_FILE
OPERATION: CREATE
PATH: fenced.txt
FINAL_NEWLINE: NO
CONTENT:
```text id="chat-generated-id"
contenuto
```
END_FILE
'''

    document = parse_text_file_operations(response)

    assert document.operations[0].content == "contenuto"
    assert document.normalizations == ()


def test_unfenced_content_still_requires_end_file() -> None:
    response = """BEGIN_FILE
OPERATION: CREATE
PATH: incomplete.txt
FINAL_NEWLINE: YES
CONTENT:
contenuto senza chiusura
"""

    with pytest.raises(
        TextFileOperationsParseError,
        match="CONTENT senza fence Markdown: manca END_FILE",
    ):
        parse_text_file_operations(response)
