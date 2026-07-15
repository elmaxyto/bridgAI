from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from local_ai_bridge.core.sessions import SessionManager
from local_ai_bridge.services.apply import ApplyService
from local_ai_bridge.services.text_file_operations import (
    TextFileOperationsParseError,
    inspect_text_file_operations,
    parse_text_file_operations,
)


def test_text_file_operations_build_create_replace_delete_plan(tmp_path: Path) -> None:
    (tmp_path / "replace.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "delete.txt").write_text("obsolete\n", encoding="utf-8")
    response = '''
BEGIN_FILE
OPERATION: CREATE
PATH: created.py
FINAL_NEWLINE: YES
CONTENT:
```python
CREATED = True
```
END_FILE

BEGIN_FILE
OPERATION: REPLACE
PATH: replace.py
FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 2
```
END_FILE

BEGIN_FILE
OPERATION: DELETE
PATH: delete.txt
END_FILE
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert [change.kind for change in plan.changes] == ["create", "modify", "delete"]
    assert plan.metadata["contents"]["created.py"] == b"CREATED = True\n"
    assert plan.metadata["contents"]["replace.py"] == b"VALUE = 2\n"
    assert "delete.txt" not in plan.metadata["contents"]
    assert plan.metadata["operations"] == {"create": 1, "replace": 1, "delete": 1}
    assert "/dev/null" in plan.diff

    manager = SessionManager()
    manager.root = tmp_path / "sessions"
    manager.root.mkdir()
    service = ApplyService(manager)
    service.apply(plan)

    assert (tmp_path / "created.py").read_text(encoding="utf-8") == "CREATED = True\n"
    assert (tmp_path / "replace.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert not (tmp_path / "delete.txt").exists()

    service.rollback_latest(tmp_path)
    assert not (tmp_path / "created.py").exists()
    assert (tmp_path / "replace.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (tmp_path / "delete.txt").read_text(encoding="utf-8") == "obsolete\n"


def test_text_file_operations_reject_commit_message_as_project_file(
    tmp_path: Path,
) -> None:
    response = '''
BEGIN_FILE commit-message.md
OPERATION: CREATE
FINAL_NEWLINE: YES
CONTENT:
```markdown
feat: should be metadata
```
END_FILE commit-message.md
'''

    with pytest.raises(ValueError, match="metadato BridgAI"):
        inspect_text_file_operations(tmp_path, response)


def test_text_file_operations_preserve_requested_final_newline(tmp_path: Path) -> None:
    response = '''
BEGIN_FILE
OPERATION: CREATE
PATH: no-newline.txt
FINAL_NEWLINE: NO
CONTENT:
```text
value
```
END_FILE
'''
    plan = inspect_text_file_operations(tmp_path, response)
    assert plan.metadata["contents"]["no-newline.txt"] == b"value"


def test_text_file_operations_preserve_dunder_paths(tmp_path: Path) -> None:
    response = '''
BEGIN_FILE
OPERATION: CREATE
PATH: src/demo/__init__.py
FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 1
```
END_FILE
'''
    plan = inspect_text_file_operations(tmp_path, response)
    assert plan.changes[0].target == "src/demo/__init__.py"


def test_text_file_operations_reject_incoherent_operations(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("old\n", encoding="utf-8")
    create_existing = '''
BEGIN_FILE
OPERATION: CREATE
PATH: existing.txt
FINAL_NEWLINE: YES
CONTENT:
```text
new
```
END_FILE
'''
    with pytest.raises(ValueError, match="CREATE richiede un file inesistente"):
        inspect_text_file_operations(tmp_path, create_existing)

    delete_missing = '''
BEGIN_FILE
OPERATION: DELETE
PATH: missing.txt
END_FILE
'''
    with pytest.raises((ValueError, FileNotFoundError)):
        inspect_text_file_operations(tmp_path, delete_missing)


def test_text_file_operations_reject_duplicate_and_delete_content() -> None:
    duplicate = '''
BEGIN_FILE
OPERATION: CREATE
PATH: src/App.py
FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 1
```
END_FILE
BEGIN_FILE
OPERATION: CREATE
PATH: src/app.py
FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 2
```
END_FILE
'''
    with pytest.raises(TextFileOperationsParseError, match="duplicato"):
        parse_text_file_operations(duplicate)

    delete_with_content = '''
BEGIN_FILE
OPERATION: DELETE
PATH: old.py
CONTENT:
```python
pass
```
END_FILE
'''
    with pytest.raises(TextFileOperationsParseError, match="DELETE non deve contenere CONTENT"):
        parse_text_file_operations(delete_with_content)


def test_text_file_operations_tolerate_prose_but_reject_unsafe_paths() -> None:
    response = '''Ecco i file richiesti:
BEGIN_FILE
OPERATION: DELETE
PATH: safe.txt
END_FILE
Operazioni completate.
'''
    document = parse_text_file_operations(response)
    assert document.operations[0].target == "safe.txt"
    assert document.ignored_lines == (1, 6)

    traversal = '''
BEGIN_FILE
OPERATION: DELETE
PATH: ../outside.txt
END_FILE
'''
    with pytest.raises(TextFileOperationsParseError, match="percorso relativo non valido"):
        parse_text_file_operations(traversal)


def test_text_file_operations_accept_longer_fence_for_markdown(tmp_path: Path) -> None:
    response = '''
BEGIN_FILE
OPERATION: CREATE
PATH: docs/example.md
FINAL_NEWLINE: YES
CONTENT:
````markdown
# Example

```python
print("inside")
```
````
END_FILE
'''
    plan = inspect_text_file_operations(tmp_path, response)
    assert plan.metadata["contents"]["docs/example.md"] == (
        b'# Example\n\n```python\nprint("inside")\n```\n'
    )


def test_text_file_operations_preserve_existing_crlf_and_utf8_bom(tmp_path: Path) -> None:
    target = tmp_path / "windows.py"
    target.write_bytes(codecs.BOM_UTF8 + b"VALUE = 1\r\n")
    response = '''
BEGIN_FILE
OPERATION: REPLACE
PATH: windows.py
FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 2
```
END_FILE
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["windows.py"] == (
        codecs.BOM_UTF8 + b"VALUE = 2\r\n"
    )
    assert "-VALUE = 1" in plan.diff
    assert "+VALUE = 2" in plan.diff


def test_text_file_operations_reject_non_utf8_and_unchanged_replacements(
    tmp_path: Path,
) -> None:
    latin1 = tmp_path / "latin1.txt"
    latin1.write_bytes("caffè\n".encode("latin-1"))
    replace_latin1 = '''
BEGIN_FILE
OPERATION: REPLACE
PATH: latin1.txt
FINAL_NEWLINE: YES
CONTENT:
```text
caffè aggiornato
```
END_FILE
'''
    with pytest.raises(ValueError, match="non è UTF-8"):
        inspect_text_file_operations(tmp_path, replace_latin1)

    unchanged = tmp_path / "unchanged.txt"
    unchanged.write_text("same\n", encoding="utf-8")
    replace_unchanged = '''
BEGIN_FILE
OPERATION: REPLACE
PATH: unchanged.txt
FINAL_NEWLINE: YES
CONTENT:
```text
same
```
END_FILE
'''
    with pytest.raises(ValueError, match="non modifica il contenuto"):
        inspect_text_file_operations(tmp_path, replace_unchanged)


def test_text_file_operations_accept_common_gemini_markdown_variants(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    response = '''Ecco il file aggiornato:
```text
**BEGIN_FILE**
**OPERATION: UPDATE**
**PATH: `existing.txt`**
CONTENT:
~~~text filename=existing.txt
new
~~~~
**END_FILE**
```
Operazione completata.
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["existing.txt"] == b"new\n"
    assert plan.metadata["ignored_text_lines"] == [1, 2, 11, 12]
    assert plan.metadata["inferred_final_newline"] == ["existing.txt"]
    assert any("righe esterne" in item for item in plan.warnings)
    assert any("FINAL_NEWLINE assente" in item for item in plan.warnings)


def test_text_file_operations_infer_newline_when_gemini_omits_field(
    tmp_path: Path,
) -> None:
    create_response = '''
BEGIN FILE
OPERAZIONE = CREA
PERCORSO = created.txt
CONTENUTO:
```text
created
````
END FILE
'''
    create_plan = inspect_text_file_operations(tmp_path, create_response)
    assert create_plan.metadata["contents"]["created.txt"] == b"created\n"

    existing = tmp_path / "without-newline.txt"
    existing.write_text("old", encoding="utf-8")
    replace_response = '''
INIZIO_FILE
OPERAZIONE: AGGIORNA
FILE: without-newline.txt
CONTENUTO:
```text
new
```
FINE_FILE
'''
    replace_plan = inspect_text_file_operations(tmp_path, replace_response)
    assert replace_plan.metadata["contents"]["without-newline.txt"] == b"new"


def test_text_file_operations_enforce_explicit_final_newline_choice(
    tmp_path: Path,
) -> None:
    response = '''
BEGIN_FILE
OPERATION: CREATE
PATH: exact.txt
FINAL_NEWLINE: NO
CONTENT:
```text
value

```
END_FILE
'''
    plan = inspect_text_file_operations(tmp_path, response)
    assert plan.metadata["contents"]["exact.txt"] == b"value"


def test_text_file_operations_reject_ambiguous_placeholder_values() -> None:
    response = '''
BEGIN_FILE
OPERATION: CREATE oppure REPLACE
PATH: example.txt
FINAL_NEWLINE: YES oppure NO
CONTENT:
```text
value
```
END_FILE
'''
    with pytest.raises(TextFileOperationsParseError, match="un solo valore"):
        parse_text_file_operations(response)


def test_text_file_operations_reject_orphan_structured_fields() -> None:
    response = '''
OPERATION: CREATE
BEGIN_FILE
OPERATION: CREATE
PATH: example.txt
FINAL_NEWLINE: YES
CONTENT:
```text
value
```
END_FILE
'''
    with pytest.raises(TextFileOperationsParseError, match="fuori da un blocco"):
        parse_text_file_operations(response)


def test_text_file_operations_recovers_missing_end_after_closed_fence(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("old\n", encoding="utf-8")
    response = '''Ecco la modifica:
BEGIN_FILE existing.txt
OPERATION: REPLACE
CONTENT:
```text
new
```
Grazie.
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["existing.txt"] == b"new\n"
    assert any("END_FILE assente" in item for item in plan.metadata["normalized_text_formatting"])
    assert any("formattazione incompleta" in item for item in plan.warnings)


def test_text_file_operations_recovers_missing_end_before_next_block(
    tmp_path: Path,
) -> None:
    response = '''BEGIN_FILE first.txt
OPERATION: CREATE
CONTENT:
```text
one
```
BEGIN_FILE second.txt
OPERATION: CREATE
CONTENT:
```text
two
```
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["first.txt"] == b"one\n"
    assert plan.metadata["contents"]["second.txt"] == b"two\n"
    assert [change.target for change in plan.changes] == ["first.txt", "second.txt"]
    assert sum(
        "END_FILE assente" in item
        for item in plan.metadata["normalized_text_formatting"]
    ) == 2


def test_text_file_operations_recovers_missing_code_fence_when_end_is_present(
    tmp_path: Path,
) -> None:
    response = '''BEGIN_FILE broken.txt
OPERATION: CREATE
CONTENT:
```text
value
END_FILE
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["broken.txt"] == b"value\n"
    assert any(
        "fence Markdown non chiusa" in item
        for item in plan.metadata["normalized_text_formatting"]
    )


def test_text_file_operations_accept_compact_inline_metadata_and_end_path(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "src" / "app.py"
    existing.parent.mkdir()
    existing.write_text("VALUE = 1\n", encoding="utf-8")
    response = '''BEGIN_FILE src/app.py OPERATION: REPLACE FINAL_NEWLINE: YES
CONTENT:
```python
VALUE = 2
```
END_FILE src/app.py
BEGIN_FILE notes.txt CREATE
FINAL_NEWLINE: NO
CONTENT:
```text
created
```
END_FILE notes.txt
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["src/app.py"] == b"VALUE = 2\n"
    assert plan.metadata["contents"]["notes.txt"] == b"created"
    assert plan.metadata["operations"] == {"create": 1, "replace": 1, "delete": 0}
    assert any(
        "metadati letti dal marcatore BEGIN_FILE" in item
        for item in plan.metadata["normalized_text_formatting"]
    )


def test_text_file_operations_accept_missing_content_before_fence_and_infer_operation(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("old\n", encoding="utf-8")
    response = '''BEGIN_FILE existing.txt
```text
new
```
END_FILE existing.txt
BEGIN_FILE created.txt
```text
created
```
END_FILE created.txt
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["existing.txt"] == b"new\n"
    assert plan.metadata["contents"]["created.txt"] == b"created\n"
    assert plan.metadata["inferred_operations"] == [
        "existing.txt: REPLACE",
        "created.txt: CREATE",
    ]
    assert plan.metadata["operations"] == {"create": 1, "replace": 1, "delete": 0}
    assert any("CONTENT assente" in item for item in plan.metadata["normalized_text_formatting"])
    assert any("OPERATION assente" in item for item in plan.warnings)


def test_text_file_operations_rejects_mismatched_end_path() -> None:
    response = '''BEGIN_FILE a.txt
OPERATION: CREATE
CONTENT:
```text
value
```
END_FILE b.txt
'''

    with pytest.raises(TextFileOperationsParseError, match="END_FILE dichiara b.txt"):
        parse_text_file_operations(response)


def test_unfenced_content_validates_end_file_target(tmp_path: Path) -> None:
    document = """
BEGIN_FILE src/app.py
OPERATION: REPLACE
CONTENT:
print('ok')
END_FILE src/other.py
"""

    with pytest.raises(
        TextFileOperationsParseError,
        match="END_FILE dichiara src/other.py",
    ):
        parse_text_file_operations(document)


def test_text_file_operations_marks_inferred_create_as_high_severity(
    tmp_path: Path,
) -> None:
    response = '''BEGIN_FILE created_typo.txt
```text
created
```
END_FILE created_typo.txt
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["contents"]["created_typo.txt"] == b"created\n"
    assert plan.metadata["recovery_severity"] == "high"
    assert plan.metadata["requires_explicit_confirmation"] is True
    assert any(
        item.get("action") == "create_inferred_for_missing_target"
        for item in plan.metadata["recovery_actions"]
    )


def test_text_file_operations_rejects_greedy_fence_after_prose() -> None:
    response = '''BEGIN_FILE src/app.py
OPERATION: REPLACE
Ecco prima un comando da terminale:
```bash
pip install example
```
CONTENT:
```python
print("ok")
```
END_FILE src/app.py
'''

    with pytest.raises(TextFileOperationsParseError, match="campo non riconosciuto"):
        parse_text_file_operations(response)


def test_text_file_operations_marks_unclosed_fence_at_eof_as_high_severity(
    tmp_path: Path,
) -> None:
    response = '''BEGIN_FILE notes.txt
OPERATION: CREATE
CONTENT:
```text
value
Fammi sapere se vuoi altro.
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert plan.metadata["recovery_severity"] == "high"
    assert plan.metadata["requires_explicit_confirmation"] is True
    assert any(
        item.get("action") == "missing_code_fence"
        for item in plan.metadata["recovery_actions"]
    )


def test_text_file_operations_keeps_diff_for_invalid_python_with_high_severity(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    response = '''BEGIN_FILE app.py
OPERATION: REPLACE
CONTENT:
```python
def broken(:
```
END_FILE app.py
'''

    plan = inspect_text_file_operations(tmp_path, response)

    assert "def broken" in plan.diff
    assert plan.metadata["recovery_severity"] == "high"
    assert plan.metadata["requires_explicit_confirmation"] is True
    assert plan.metadata["syntax_error_targets"] == ["app.py"]
    assert any(
        item.get("action") == "python_syntax_error"
        for item in plan.metadata["recovery_actions"]
    )
