from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_bridge.services.text_update_import import (
    TextUpdateImportError,
    inspect_text_update_response,
)


def test_text_update_import_accepts_text_operations_from_markdown_entrypoint(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    plan = inspect_text_update_response(
        tmp_path,
        """
BEGIN_FILE app.py
OPERATION: REPLACE
FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 2
```
END_FILE app.py
""",
        preferred="markdown_exchange",
    )

    assert plan.metadata["text_update_format"] == "file Markdown di aggiornamento"
    assert plan.changes[0].target == "app.py"
    assert any("Formato riconosciuto" in warning for warning in plan.warnings)


def test_text_update_import_carries_commit_message_metadata_for_full_file_updates(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    document = '''<!-- BRIDGAI:FILE commit-message.md -->
<!-- BRIDGAI:TEXT final-newline=1 -->
```markdown
feat(app): update value

- replace the application value
```

BEGIN_FILE app.py
OPERATION: REPLACE
FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 2
```
END_FILE app.py
'''

    plan = inspect_text_update_response(
        tmp_path,
        document,
        preferred="text_file_operations",
    )

    assert plan.plan_type == "full_file"
    assert plan.metadata["commit_message"].startswith("feat(app): update value")
    assert [change.target for change in plan.changes] == ["app.py"]
    assert "commit-message.md" not in plan.metadata["contents"]


def test_text_update_import_accepts_markdown_exchange_from_text_entrypoint(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    document = """
<!-- BRIDGAI:FILE app.py -->
<!-- BRIDGAI:TEXT final-newline=1 -->
```python
VALUE = 2
```
"""

    plan = inspect_text_update_response(
        tmp_path,
        document,
        preferred="text_file_operations",
    )

    assert plan.metadata["text_update_format"] == "Markdown Exchange"
    assert plan.metadata["import_summary"]["replace"] == 1
    assert plan.changes[0].target == "app.py"
    assert any("Formato riconosciuto" in warning for warning in plan.warnings)


def test_text_update_import_reports_both_parser_failures(tmp_path: Path) -> None:
    with pytest.raises(TextUpdateImportError) as exc_info:
        inspect_text_update_response(tmp_path, "testo senza marcatori applicabili")

    message = str(exc_info.value)
    assert "BEGIN_FILE/END_FILE" in message
    assert "Markdown Exchange" in message


def test_text_update_import_marks_cross_format_fallback_as_high_severity(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    plan = inspect_text_update_response(
        tmp_path,
        '''BEGIN_FILE app.py
OPERATION: REPLACE
CONTENT:
```python
VALUE = 2
```
END_FILE app.py
''',
        preferred="markdown_exchange",
    )

    assert plan.metadata["text_update_format"] == "file Markdown di aggiornamento"
    assert plan.metadata["recovery_severity"] == "high"
    assert plan.metadata["requires_explicit_confirmation"] is True
    assert any(
        item.get("action") == "fallback_parser_used"
        for item in plan.metadata["recovery_actions"]
    )


def test_text_update_import_does_not_fallback_after_detected_invalid_primary_format(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    document = '''<!-- BRIDGAI:FILE app.py -->
questa non è una fence valida
BEGIN_FILE app.py
OPERATION: REPLACE
CONTENT:
```python
VALUE = 2
```
END_FILE app.py
'''

    with pytest.raises(TextUpdateImportError, match="Markdown Exchange.*rilevato"):
        inspect_text_update_response(
            tmp_path,
            document,
            preferred="markdown_exchange",
        )


def test_text_update_import_rejects_auto_ambiguous_textual_formats(
    tmp_path: Path,
) -> None:
    document = '''BRIDGAI:FILE app.py
BEGIN_FILE app.py
'''

    with pytest.raises(TextUpdateImportError, match="Formato testuale ambiguo"):
        inspect_text_update_response(tmp_path, document, preferred="auto")
