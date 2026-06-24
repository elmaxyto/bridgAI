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
