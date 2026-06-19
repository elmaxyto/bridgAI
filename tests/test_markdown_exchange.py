import os
from pathlib import Path

import pytest

from local_ai_bridge.core.safety import SafetyError
from local_ai_bridge.services.markdown_exchange import (
    MarkdownExchangeError,
    MarkdownExchangeNotFound,
    encode_files_to_markdown,
    export_files_to_markdown,
    markdown_export_path,
    parse_markdown_response,
)
from local_ai_bridge.services.temp_storage import latest_markdown_file


def _write(workspace: Path, relative: str, data: str | bytes) -> Path:
    target = workspace / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        target.write_bytes(data)
    else:
        target.write_text(data, encoding="utf-8")
    return target


def test_encode_produces_markers_and_language_fence(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('hello')\n")

    document = encode_files_to_markdown(tmp_path, ["src/app.py"])

    assert "<!-- BRIDGAI:MARKDOWN-EXCHANGE 1 -->" in document
    assert "<!-- BRIDGAI:PROJECT " in document
    assert "<!-- BRIDGAI:FILE src/app.py -->" in document
    assert "<!-- BRIDGAI:TEXT final-newline=1 -->" in document
    assert "```python\nprint('hello')\n```" in document


def test_encode_skips_binary_with_explicit_marker(tmp_path: Path) -> None:
    _write(tmp_path, "assets/icon.bin", b"\x00\x01\xff")

    document = encode_files_to_markdown(tmp_path, ["assets/icon.bin"])

    assert "<!-- BRIDGAI:FILE assets/icon.bin -->" in document
    assert "<!-- BRIDGAI:BINARY size=3 sha256=" in document
    assert "```" not in document


def test_encode_blocks_sensitive_path(tmp_path: Path) -> None:
    _write(tmp_path, ".env", "TOKEN=secret\n")

    with pytest.raises(ValueError, match="sensibile"):
        encode_files_to_markdown(tmp_path, [".env"])


def test_parse_single_file(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "value = 1\n")
    document = encode_files_to_markdown(tmp_path, ["src/app.py"]).replace(
        "value = 1", "value = 2"
    )

    plan = parse_markdown_response(tmp_path, document)

    assert [change.target for change in plan.changes] == ["src/app.py"]
    assert plan.metadata["provider"] == "markdown_exchange"
    assert plan.metadata["contents"]["src/app.py"] == b"value = 2\n"
    assert "-value = 1" in plan.diff
    assert "+value = 2" in plan.diff


def test_parse_multi_file(tmp_path: Path) -> None:
    _write(tmp_path, "a.txt", "old a\n")
    _write(tmp_path, "nested/b.json", '{"old": true}\n')
    document = encode_files_to_markdown(tmp_path, ["a.txt", "nested/b.json"])
    document = document.replace("old a", "new a").replace('"old": true', '"new": true')

    plan = parse_markdown_response(tmp_path, document)

    assert {change.target for change in plan.changes} == {"a.txt", "nested/b.json"}
    assert plan.metadata["contents"]["a.txt"] == b"new a\n"
    assert plan.metadata["contents"]["nested/b.json"] == b'{"new": true}\n'


def test_parse_malformed_marker_adds_warning_when_valid_file_exists(tmp_path: Path) -> None:
    _write(tmp_path, "a.txt", "old\n")
    document = encode_files_to_markdown(tmp_path, ["a.txt"])
    document += "<!-- BRIDGAI:FILE -->\n"

    plan = parse_markdown_response(tmp_path, document)

    assert any("marcatore BRIDGAI:FILE non valido" in warning for warning in plan.warnings)


def test_parse_ignores_root_commit_message(tmp_path: Path) -> None:
    _write(tmp_path, "a.txt", "old\n")
    document = """<!-- BRIDGAI:FILE commit-message.md -->
```markdown
feat: should not be applied
```
<!-- BRIDGAI:FILE a.txt -->
<!-- BRIDGAI:TEXT final-newline=1 -->
```text
new
```
"""

    plan = parse_markdown_response(tmp_path, document)

    assert [change.target for change in plan.changes] == ["a.txt"]
    assert any("commit-message.md ignorato" in warning for warning in plan.warnings)


def test_encode_uses_longer_fence_for_embedded_backticks(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "before\n```python\nprint('x')\n```\nafter\n")

    document = encode_files_to_markdown(tmp_path, ["README.md"])
    plan = parse_markdown_response(tmp_path, document)

    assert "````markdown" in document
    assert plan.metadata["contents"]["README.md"] == (tmp_path / "README.md").read_bytes()


@pytest.mark.parametrize("content", ["no newline", "with newline\n", ""])
def test_round_trip_preserves_final_newline(tmp_path: Path, content: str) -> None:
    _write(tmp_path, "note.txt", content)

    document = encode_files_to_markdown(tmp_path, ["note.txt"])
    plan = parse_markdown_response(tmp_path, document)

    assert plan.metadata["contents"]["note.txt"] == content.encode("utf-8")


def test_round_trip_preserves_file_that_is_itself_a_code_fence(tmp_path: Path) -> None:
    content = "```python\nprint('inside')\n```\n"
    _write(tmp_path, "snippet.md", content)

    document = encode_files_to_markdown(tmp_path, ["snippet.md"])
    plan = parse_markdown_response(tmp_path, document)

    assert plan.metadata["contents"]["snippet.md"] == content.encode("utf-8")


def test_parse_rejects_duplicate_target_case_insensitively(tmp_path: Path) -> None:
    _write(tmp_path, "a.txt", "old\n")
    document = """<!-- BRIDGAI:FILE a.txt -->
```text
one
```
<!-- BRIDGAI:FILE A.txt -->
```text
two
```
"""

    with pytest.raises(MarkdownExchangeError, match="duplicato"):
        parse_markdown_response(tmp_path, document)


def test_parse_rejects_sensitive_or_traversal_target(tmp_path: Path) -> None:
    sensitive = "<!-- BRIDGAI:FILE .env -->\n```text\nsecret\n```\n"
    traversal = "<!-- BRIDGAI:FILE ../outside.txt -->\n```text\nno\n```\n"

    with pytest.raises(SafetyError):
        parse_markdown_response(tmp_path, sensitive)
    with pytest.raises(SafetyError):
        parse_markdown_response(tmp_path, traversal)


def test_parse_rejects_document_for_different_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    _write(source, "a.txt", "source\n")
    _write(target, "a.txt", "target\n")
    document = encode_files_to_markdown(source, ["a.txt"])

    with pytest.raises(SafetyError, match="workspace differente"):
        parse_markdown_response(target, document)


def test_parse_without_markers_signals_not_found(tmp_path: Path) -> None:
    with pytest.raises(MarkdownExchangeNotFound):
        parse_markdown_response(tmp_path, "ordinary SEARCH/REPLACE response")


def test_export_reuses_stable_project_markdown_path(tmp_path: Path) -> None:
    workspace = tmp_path / "DemoProject"
    exports = tmp_path / "exports"
    workspace.mkdir()
    _write(workspace, "src/app.py", "value = 1\n")

    first = export_files_to_markdown(workspace, ["src/app.py"], exports)
    _write(workspace, "src/app.py", "value = 2\n")
    second = export_files_to_markdown(workspace, ["src/app.py"], exports)

    assert first == second == markdown_export_path(workspace, exports)
    assert first.name == "DemoProject_ai_context.md"
    assert "value = 2" in first.read_text(encoding="utf-8")
    assert "value = 1" not in first.read_text(encoding="utf-8")
    assert list(exports.glob("*.md")) == [first]


def test_export_path_is_distinct_for_different_project_names(tmp_path: Path) -> None:
    alpha = tmp_path / "Alpha"
    beta = tmp_path / "Beta"
    exports = tmp_path / "exports"
    alpha.mkdir()
    beta.mkdir()

    assert markdown_export_path(alpha, exports).name == "Alpha_ai_context.md"
    assert markdown_export_path(beta, exports).name == "Beta_ai_context.md"


def test_latest_markdown_file_accepts_md_and_markdown(tmp_path: Path) -> None:
    older = _write(tmp_path, "older.md", "old")
    newer = _write(tmp_path, "newer.markdown", "new")
    _write(tmp_path, "ignored.txt", "ignore")
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(newer, ns=(2_000_000_000, 2_000_000_000))

    assert latest_markdown_file(tmp_path) == newer
    assert latest_markdown_file(tmp_path / "missing") is None
