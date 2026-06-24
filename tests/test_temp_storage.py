from __future__ import annotations

from pathlib import Path
import zipfile

from local_ai_bridge.services.temp_storage import (
    clean_managed_temp, configured_temp_root, latest_zip_file, managed_subdir, stage_import_zip,
)


def test_configured_root_uses_managed_subdirectory(tmp_path: Path) -> None:
    root = configured_temp_root(tmp_path)
    assert root == (tmp_path / "LocalAIBridgeTemp").resolve()
    assert (root / ".local_ai_bridge_temp").is_file()
    assert (root / "exports").is_dir()
    assert (root / "ai_models").is_dir()
    assert managed_subdir(tmp_path, "ai_models").is_dir()


def test_stage_import_zip_copies_to_managed_area(tmp_path: Path) -> None:
    source = tmp_path / "change.zip"
    with zipfile.ZipFile(source, "w") as zf:
        zf.writestr("demo.txt", "ok")
    base = tmp_path / "base"
    staged = stage_import_zip(source, base)
    assert staged.parent == managed_subdir(base, "imports")
    assert staged.read_bytes() == source.read_bytes()


def test_clean_only_managed_directory(tmp_path: Path) -> None:
    outside = tmp_path / "keep.txt"
    outside.write_text("keep", encoding="utf-8")
    root = configured_temp_root(tmp_path)
    (root / "exports" / "remove.zip").write_bytes(b"123")
    result = clean_managed_temp(tmp_path)
    assert result.files_removed == 1
    assert outside.read_text(encoding="utf-8") == "keep"
    assert (root / ".local_ai_bridge_temp").exists()
    assert (root / "exports").is_dir()
    assert (root / "ai_models").is_dir()


def test_latest_zip_file_returns_most_recent_zip(tmp_path: Path) -> None:
    older = tmp_path / "older.zip"
    newer = tmp_path / "newer.ZIP"
    ignored = tmp_path / "notes.txt"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    ignored.write_text("ignore", encoding="utf-8")
    import os
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
    assert latest_zip_file(tmp_path) == newer


def test_latest_zip_file_handles_missing_or_empty_directory(tmp_path: Path) -> None:
    assert latest_zip_file("") is None
    assert latest_zip_file(tmp_path / "missing") is None
    assert latest_zip_file(tmp_path) is None
