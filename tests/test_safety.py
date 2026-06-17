from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from local_ai_bridge.core.safety import (
    SafetyError, is_sensitive_relative_path, resolve_workspace_target, validate_archive,
)


def test_sensitive_paths_are_blocked() -> None:
    assert is_sensitive_relative_path(".env")
    assert is_sensitive_relative_path("config/.env.prod")
    assert is_sensitive_relative_path(".git/config")
    assert is_sensitive_relative_path("keys/private.pem")
    assert not is_sensitive_relative_path("src/token_service.py")


@pytest.mark.parametrize("raw", ["../x.py", "..\\x.py", "/tmp/x.py", "C:\\temp\\x.py"])
def test_unsafe_targets_are_rejected(tmp_path: Path, raw: str) -> None:
    with pytest.raises(SafetyError):
        resolve_workspace_target(tmp_path, raw)


def test_target_stays_inside_workspace(tmp_path: Path) -> None:
    target = resolve_workspace_target(tmp_path, "src/app.py")
    assert target == tmp_path / "src" / "app.py"


def test_zip_traversal_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "bad")
    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(SafetyError):
            validate_archive(zf)


def test_zip_env_variant_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bad-env.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("config/.env.local", "SECRET=1")
    with zipfile.ZipFile(archive) as zf:
        with pytest.raises(SafetyError):
            validate_archive(zf)


def test_manifest_delete_traversal_is_rejected(tmp_path: Path) -> None:
    import json

    from local_ai_bridge.services.archive import inspect_zip

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive = tmp_path / "bad-delete.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("applymanifest.json", json.dumps({"delete": ["../outside.txt"]}))
    with pytest.raises(SafetyError):
        inspect_zip(workspace, archive)


def test_manifest_delete_sensitive_path_is_rejected(tmp_path: Path) -> None:
    import json

    from local_ai_bridge.services.archive import inspect_zip

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive = tmp_path / "bad-sensitive-delete.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("applymanifest.json", json.dumps({"delete": [".env"]}))
    with pytest.raises(SafetyError):
        inspect_zip(workspace, archive)
