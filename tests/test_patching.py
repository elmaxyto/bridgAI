from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_bridge.core.sessions import SessionManager
from local_ai_bridge.services.apply import ApplyService
from local_ai_bridge.services.patching import (
    GeminiPatchParseError,
    apply_search_replace,
    inspect_full_file,
    inspect_gemini_response,
    inspect_patch,
    parse_gemini_patch_document,
    parse_gemini_patch_response,
)


def patch(search: str, replacement: str) -> str:
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replacement}\n>>>>>>> REPLACE"


def test_patch_requires_blocks() -> None:
    with pytest.raises(ValueError, match="Nessun blocco"):
        apply_search_replace("a", "nessuna patch")


def test_patch_rejects_ambiguous_search() -> None:
    with pytest.raises(ValueError, match="ambiguo"):
        apply_search_replace("x\nx\n", patch("x", "y"))


def test_patch_preserves_crlf() -> None:
    result = apply_search_replace("a\r\nb\r\n", patch("b", "c"))
    assert result.new_text == "a\r\nc\r\n"


def test_inspect_patch_builds_diff(tmp_path: Path) -> None:
    file = tmp_path / "app.py"
    file.write_text("value = 1\n", encoding="utf-8")
    plan = inspect_patch(tmp_path, "app.py", patch("value = 1", "value = 2"))
    assert plan.changes[0].target == "app.py"
    assert "+value = 2" in plan.diff


def test_full_python_file_is_validated(tmp_path: Path) -> None:
    with pytest.raises(SyntaxError):
        inspect_full_file(tmp_path, "new.py", "def broken(:\n")


def test_full_file_can_preserve_an_outer_code_fence(tmp_path: Path) -> None:
    content = "```python\nprint('inside')\n```\n"

    default_plan = inspect_full_file(tmp_path, "snippet.md", content)
    preserved_plan = inspect_full_file(tmp_path, "snippet.md", content, strip_fence=False)

    assert default_plan.metadata["contents"]["snippet.md"] == b"print('inside')"
    assert preserved_plan.metadata["contents"]["snippet.md"] == content.encode("utf-8")


def test_gemini_response_groups_multiple_blocks_by_file() -> None:
    response = """
### `src/example.py`
```python
<<<<<<< SEARCH
value = 1
=======
value = 2
>>>>>>> REPLACE

<<<<<<< SEARCH
enabled = False
=======
enabled = True
>>>>>>> REPLACE
```

File: tests/test_example.py
<<<<<<< SEARCH
assert value == 1
=======
assert value == 2
>>>>>>> REPLACE
"""

    parsed = parse_gemini_patch_response(response)

    assert [target for target, _patch_text in parsed] == [
        "src/example.py",
        "tests/test_example.py",
    ]
    assert "value = 2" in parsed[0][1]
    assert "enabled = True" in parsed[0][1]
    assert parsed[0][1].count("<<<<<<< SEARCH") == 2
    assert "assert value == 2" in parsed[1][1]


def test_gemini_parser_accepts_begin_end_file_and_extensionless_target() -> None:
    response = """
BEGIN_FILE: Dockerfile
<<<<<<< SEARCH
FROM python:3.11
=======
FROM python:3.12
>>>>>>> REPLACE
END_FILE
"""

    document = parse_gemini_patch_document(response)

    assert document.block_count == 1
    assert document.ignored_block_count == 0
    assert document.files[0].target == "Dockerfile"
    assert document.files[0].block_lines == (3,)


def test_gemini_parser_handles_the_full_answer_format_used_by_gemini() -> None:
    response = """
## 1. Analisi sintetica del problema
Testo descrittivo che cita `src/ignored.py` ma non dichiara una patch.

## 4. Patch applicabile

FILE: src/local_ai_bridge/ui/layouts.py

```text
<<<<<<< SEARCH
    drive_group = QGroupBox(_('Google Drive per Gemini Web'))
=======
    drive_group = QGroupBox(_('Utilizza Gemini'))
>>>>>>> REPLACE
```

FILE: src/local_ai_bridge/resources/i18n_en.json

```text
<<<<<<< SEARCH
  "Google Drive per Gemini Web": "Google Drive for Gemini Web",
=======
  "Utilizza Gemini": "Use Gemini",
>>>>>>> REPLACE
```
"""

    document = parse_gemini_patch_document(response)

    assert [item.target for item in document.files] == [
        "src/local_ai_bridge/ui/layouts.py",
        "src/local_ai_bridge/resources/i18n_en.json",
    ]
    assert document.block_count == 2
    assert document.ignored_block_count == 0


def test_gemini_response_requires_path_before_patch() -> None:
    with pytest.raises(GeminiPatchParseError, match=r"Riga 1:.*FILE"):
        parse_gemini_patch_response(patch("value = 1", "value = 2"))


def test_gemini_parser_rejects_traversal_path() -> None:
    response = f"FILE: ../outside.py\n{patch('old', 'new')}"

    with pytest.raises(GeminiPatchParseError, match=r"Riga 1:.*percorso FILE non valido"):
        parse_gemini_patch_document(response)


def test_gemini_parser_rejects_windows_absolute_path() -> None:
    response = f"FILE: C:\\project\\app.py\n{patch('old', 'new')}"

    with pytest.raises(GeminiPatchParseError, match=r"Riga 1:.*percorso FILE non valido"):
        parse_gemini_patch_document(response)


def test_gemini_parser_reports_orphan_replace_with_line_number() -> None:
    response = "FILE: src/app.py\n>>>>>>> REPLACE"

    with pytest.raises(GeminiPatchParseError, match=r"Riga 2:.*senza un blocco SEARCH"):
        parse_gemini_patch_document(response)


def test_gemini_parser_reports_malformed_marker() -> None:
    response = "FILE: src/app.py\n<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE"

    with pytest.raises(GeminiPatchParseError, match=r"Riga 2:.*marcatore patch non valido"):
        parse_gemini_patch_document(response)


def test_gemini_parser_rejects_duplicate_separator() -> None:
    response = """
FILE: src/app.py
<<<<<<< SEARCH
old
=======
=======
new
>>>>>>> REPLACE
"""

    with pytest.raises(GeminiPatchParseError, match=r"Riga 6:.*più di un separatore"):
        parse_gemini_patch_document(response)


def test_gemini_parser_rejects_empty_search() -> None:
    response = "FILE: src/app.py\n<<<<<<< SEARCH\n=======\nnew\n>>>>>>> REPLACE"

    with pytest.raises(GeminiPatchParseError, match=r"Riga 2:.*SEARCH è vuoto"):
        parse_gemini_patch_document(response)


def test_gemini_parser_rejects_explicit_file_without_patch() -> None:
    response = "FILE: src/unused.py\n\nFILE: src/app.py\n" + patch("old", "new")

    with pytest.raises(GeminiPatchParseError, match=r"Riga 1:.*non contiene alcun blocco"):
        parse_gemini_patch_document(response)


def test_gemini_parser_does_not_reuse_a_file_declaration_after_prose() -> None:
    response = """
FILE: src/app.py
Questa sezione descrive soltanto il file.
<<<<<<< SEARCH
old
=======
new
>>>>>>> REPLACE
"""

    with pytest.raises(GeminiPatchParseError, match=r"Riga 4:.*FILE"):
        parse_gemini_patch_document(response)


def test_gemini_response_builds_one_multifile_plan(tmp_path: Path) -> None:
    source = tmp_path / "src"
    tests = tmp_path / "tests"
    source.mkdir()
    tests.mkdir()
    (source / "example.py").write_text("value = 1\n", encoding="utf-8")
    (tests / "test_example.py").write_text("assert value == 1\n", encoding="utf-8")
    response = """
FILE: src/example.py
<<<<<<< SEARCH
value = 1
=======
value = 2
>>>>>>> REPLACE

FILE: tests/test_example.py
<<<<<<< SEARCH
assert value == 1
=======
assert value == 2
>>>>>>> REPLACE
"""

    plan = inspect_gemini_response(tmp_path, response)

    assert plan.plan_type == "patch"
    assert [change.target for change in plan.changes] == [
        "src/example.py",
        "tests/test_example.py",
    ]
    assert "+value = 2" in plan.diff
    assert "+assert value == 2" in plan.diff
    assert set(plan.metadata["contents"]) == {
        "src/example.py",
        "tests/test_example.py",
    }
    assert plan.metadata["import_summary"] == {
        "files": 2,
        "blocks": 2,
        "ignored_blocks": 0,
        "targets": ["src/example.py", "tests/test_example.py"],
    }

    manager = SessionManager()
    manager.root = tmp_path / "sessions"
    manager.root.mkdir()
    ApplyService(manager).apply(plan)

    assert (source / "example.py").read_text(encoding="utf-8") == "value = 2\n"
    assert (tests / "test_example.py").read_text(encoding="utf-8") == "assert value == 2\n"


def test_gemini_inspection_identifies_the_failing_target(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    response = "FILE: app.py\n" + patch("missing = 1", "value = 2")

    with pytest.raises(ValueError, match=r"File app.py .*SEARCH non trovato"):
        inspect_gemini_response(tmp_path, response)
