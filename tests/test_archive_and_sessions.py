from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from local_ai_bridge.core.io import atomic_write as real_atomic_write, sha256_file
from local_ai_bridge.core.sessions import SessionManager
from local_ai_bridge.services.apply import ApplyService
from local_ai_bridge.services.archive import inspect_zip


def make_manager(tmp_path: Path) -> SessionManager:
    manager = SessionManager()
    manager.root = tmp_path / "sessions"
    manager.root.mkdir(parents=True, exist_ok=True)
    return manager


def test_simple_zip_inspect_apply_and_rollback(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "app.py").write_text("value = 1\n", encoding="utf-8")
    archive = tmp_path / "change.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("app.py", "value = 2\n")
        zf.writestr("new.txt", "created")

    plan = inspect_zip(workspace, archive)
    assert len(plan.changes) == 2
    manager = make_manager(tmp_path)
    service = ApplyService(manager)
    record = service.apply(plan)
    assert record.status == "applied"
    assert (workspace / "app.py").read_text() == "value = 2\n"
    assert (workspace / "new.txt").exists()

    rolled = service.rollback_latest(workspace)
    assert rolled.status == "rolled_back"
    assert (workspace / "app.py").read_text() == "value = 1\n"
    assert not (workspace / "new.txt").exists()


def test_manifest_hash_is_enforced(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    original = workspace / "src.py"
    original.write_text("old = True\n", encoding="utf-8")
    archive = tmp_path / "manifest.zip"
    manifest = {
        "files": [{
            "source": "out/src.py",
            "target": "src.py",
            "sha256": sha256_file(original),
        }]
    }
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("out/src.py", "old = False\n")
        zf.writestr("applymanifest.json", json.dumps(manifest))
    assert inspect_zip(workspace, archive).changes[0].target == "src.py"

    manifest["files"][0]["sha256"] = "deadbeef"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("out/src.py", "old = False\n")
        zf.writestr("applymanifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="Conflitto hash"):
        inspect_zip(workspace, archive)


def test_transaction_rolls_back_after_second_write_failure(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("A0", encoding="utf-8")
    (workspace / "b.txt").write_text("B0", encoding="utf-8")
    manager = make_manager(tmp_path)

    calls = 0

    def failing_write(path: Path, data: bytes, *, original_mode=None):
        nonlocal calls
        if path.name not in {"session.json"}:
            calls += 1
            if calls == 2:
                raise OSError("simulated failure")
        return real_atomic_write(path, data, original_mode=original_mode)

    monkeypatch.setattr("local_ai_bridge.core.sessions.atomic_write", failing_write)
    with pytest.raises(OSError, match="simulated"):
        manager.apply_transaction(workspace, "test", [("a.txt", b"A1"), ("b.txt", b"B1")])
    assert (workspace / "a.txt").read_text() == "A0"
    assert (workspace / "b.txt").read_text() == "B0"


def test_rollback_detects_later_changes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "a.txt"
    target.write_text("old", encoding="utf-8")
    manager = make_manager(tmp_path)
    manager.apply_transaction(workspace, "test", [("a.txt", b"new")])
    target.write_text("user edit", encoding="utf-8")
    with pytest.raises(RuntimeError, match="modificati dopo"):
        manager.rollback_latest(workspace)


def test_manifest_delete_is_applied_and_rollback_restores_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    obsolete = workspace / "obsolete.py"
    obsolete.write_text("legacy = True\n", encoding="utf-8")
    archive = tmp_path / "delete.zip"
    manifest = {"files": [], "delete": ["obsolete.py"]}
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("applymanifest.json", json.dumps(manifest))

    plan = inspect_zip(workspace, archive)
    assert plan.changes[0].kind == "delete"
    assert "ELIMINA obsolete.py" in plan.diff

    service = ApplyService(make_manager(tmp_path))
    service.apply(plan)
    assert not obsolete.exists()

    service.rollback_latest(workspace)
    assert obsolete.read_text(encoding="utf-8") == "legacy = True\n"


def test_manifest_delete_missing_file_is_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive = tmp_path / "delete-missing.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("applymanifest.json", json.dumps({"delete": ["missing.txt"]}))

    plan = inspect_zip(workspace, archive)
    assert plan.changes[0].kind == "delete"
    assert any("già assente" in warning for warning in plan.warnings)
    ApplyService(make_manager(tmp_path)).apply(plan)


def test_manifest_delete_hash_is_enforced(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "obsolete.txt"
    target.write_text("old", encoding="utf-8")
    archive = tmp_path / "delete-hash.zip"
    manifest = {"delete": [{"path": "obsolete.txt", "sha256": "deadbeef"}]}
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("applymanifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="Conflitto hash"):
        inspect_zip(workspace, archive)


def test_manifest_cannot_write_and_delete_same_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive = tmp_path / "duplicate-target.zip"
    manifest = {
        "files": [{"source": "new.txt", "target": "same.txt"}],
        "delete": ["same.txt"],
    }
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("new.txt", "new")
        zf.writestr("applymanifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="Target duplicato"):
        inspect_zip(workspace, archive)


def test_rollback_detects_recreated_deleted_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "obsolete.txt"
    target.write_text("old", encoding="utf-8")
    manager = make_manager(tmp_path)
    manager.apply_transaction(workspace, "test", [("obsolete.txt", None)])
    target.write_text("recreated", encoding="utf-8")
    with pytest.raises(RuntimeError, match="modificati dopo"):
        manager.rollback_latest(workspace)


def test_session_test_results_are_saved_and_reloaded(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manager = make_manager(tmp_path)
    record = manager.apply_transaction(workspace, "test", [("a.txt", b"new")])
    updated = manager.save_test_results(record, [{
        "name": "Python compileall",
        "command": ["python", "-m", "compileall"],
        "status": "passed",
        "returncode": 0,
        "output": "",
        "duration_seconds": 0.2,
    }])
    assert updated.tested_at is not None
    loaded = manager.load(manager.root / record.session_id)
    assert loaded.test_results[0]["status"] == "passed"


def test_old_session_json_is_backward_compatible(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    directory = manager.root / "old-session"
    directory.mkdir()
    (directory / "session.json").write_text(json.dumps({
        "session_id": "old-session",
        "workspace": str(tmp_path),
        "operation": "zip",
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "applied",
        "files": [],
        "source": None,
        "error": None,
    }), encoding="utf-8")
    loaded = manager.load(directory)
    assert loaded.test_results == []
    assert loaded.tested_at is None


def test_zip_commit_message_is_metadata_and_persisted(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive_path = tmp_path / "change.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("example.txt", "new content")
        zf.writestr("commit-message.md", "feat: add example\n\n- create example file")

    plan = inspect_zip(workspace, archive_path)
    assert [change.target for change in plan.changes] == ["example.txt"]
    assert plan.metadata["commit_message"].startswith("feat: add example")

    manager = make_manager(tmp_path)
    record = ApplyService(manager).apply(plan)
    loaded = manager.load(manager.root / record.session_id)
    assert loaded.commit_message == plan.metadata["commit_message"]


def test_export_zip_embeds_project_identity(tmp_path: Path) -> None:
    from local_ai_bridge.core.safety import project_identity
    from local_ai_bridge.services.exporting import create_export_zip

    workspace = tmp_path / "LocalBridge"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "local-ai-bridge"\n', encoding="utf-8"
    )
    (workspace / "app.py").write_text("value = 1\n", encoding="utf-8")
    destination = tmp_path / "context.zip"

    create_export_zip(workspace, ["app.py"], destination)

    with zipfile.ZipFile(destination) as zf:
        metadata = json.loads(zf.read("bridgai-project.json").decode("utf-8"))
        assert metadata["identity"] == project_identity(workspace)["identity"]
        assert "Copy this file unchanged" in metadata["instructions"]


def test_matching_project_identity_is_accepted_and_not_applied(tmp_path: Path) -> None:
    from local_ai_bridge.core.safety import project_identity

    workspace = tmp_path / "LocalBridge"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "local-ai-bridge"\n', encoding="utf-8"
    )
    archive = tmp_path / "matching.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("bridgai-project.json", json.dumps(project_identity(workspace)))
        zf.writestr("app.py", "value = 2\n")

    plan = inspect_zip(workspace, archive)

    assert [change.target for change in plan.changes] == ["app.py"]
    assert plan.metadata["project_metadata"]["name"] == "local-ai-bridge"
    assert not any("senza identità progetto" in warning for warning in plan.warnings)


def test_update_for_different_project_is_rejected(tmp_path: Path) -> None:
    from local_ai_bridge.core.safety import project_identity

    source = tmp_path / "ProjectA"
    source.mkdir()
    (source / "pyproject.toml").write_text('[project]\nname = "project-a"\n', encoding="utf-8")
    target = tmp_path / "ProjectB"
    target.mkdir()
    (target / "pyproject.toml").write_text('[project]\nname = "project-b"\n', encoding="utf-8")
    archive = tmp_path / "wrong-project.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("bridgai-project.json", json.dumps(project_identity(source)))
        zf.writestr("app.py", "value = 2\n")

    with pytest.raises(ValueError, match="altro progetto"):
        inspect_zip(target, archive)


def test_legacy_zip_without_project_identity_remains_compatible(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive = tmp_path / "legacy.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("app.py", "value = 2\n")

    plan = inspect_zip(workspace, archive)

    assert any("senza identità progetto" in warning for warning in plan.warnings)
