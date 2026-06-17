from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from local_ai_bridge.core.settings import SettingsStore
from local_ai_bridge.services import git as git_service
from local_ai_bridge.services import git_clone as git_clone_service
from local_ai_bridge.web.security import WebSecurityConfig, WorkspacePolicy, validate_project_name
from local_ai_bridge.web.server import BridgeHTTPServer
from local_ai_bridge.web.state import BridgeState


def _post(base: str, path: str, payload: dict, *, token: str, csrf: str):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Local-Bridge-CSRF": csrf,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_project_names_are_portable_and_safe() -> None:
    assert validate_project_name("  demo project  ") == "demo project"
    for invalid in ("", ".hidden", "..", "a/b", "a\\b", "CON", "name.", "bad:name"):
        with pytest.raises(ValueError):
            validate_project_name(invalid)


def test_workspace_policy_lists_only_first_level_non_hidden_directories(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    direct = root / "direct"
    nested = direct / "nested"
    hidden = root / ".hidden"
    direct.mkdir(parents=True)
    nested.mkdir()
    hidden.mkdir()
    config = WebSecurityConfig.build(workspace_root=root)
    policy = WorkspacePolicy(config)

    assert policy.available_workspaces() == [{"name": "direct", "value": str(direct.resolve())}]
    assert policy.resolve_selection("direct") == direct.resolve()
    with pytest.raises(ValueError, match="primo livello"):
        policy.resolve_selection(str(nested))


def test_workspace_root_is_persisted_and_invalidates_outside_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    project = first_root / "project"
    project.mkdir(parents=True)
    second_root.mkdir()
    state = BridgeState(security=WebSecurityConfig.build(workspace_root=first_root))
    state.set_workspace("project")

    changed = state.set_workspace_root(str(second_root))

    assert changed == second_root.resolve()
    assert state.workspace is None
    assert SettingsStore().load().web_workspace_root == str(second_root.resolve())


def test_create_project_can_skip_git_initialization(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    root = tmp_path / "projects"
    root.mkdir()
    state = BridgeState(security=WebSecurityConfig.build(workspace_root=root))

    workspace, output = state.create_project("new-project", initialize_git=False)

    assert workspace == (root / "new-project").resolve()
    assert output == "Cartella progetto creata."
    assert state.workspace == workspace


def test_clone_url_validation_rejects_local_and_embedded_credentials() -> None:
    assert git_clone_service.normalize_clone_url("https://github.com/example/project.git") == (
        "https://github.com/example/project.git"
    )
    assert git_clone_service.normalize_clone_url("git@github.com:example/project.git") == (
        "git@github.com:example/project.git"
    )
    assert git_clone_service.clone_destination_name("ssh://git@example.com/example/project.git") == "project"
    for invalid in (
        "file:///tmp/project",
        "/tmp/project",
        "ext::sh -c bad",
        "https://user:secret@example.com/project.git",
    ):
        with pytest.raises(git_service.GitIntegrationError):
            git_clone_service.normalize_clone_url(invalid)


def test_clone_repository_uses_validated_direct_child_and_cleans_partial_directory(
    tmp_path: Path, monkeypatch
) -> None:
    destination = tmp_path / "project"
    calls: list[tuple[list[str], Path | None, int]] = []
    monkeypatch.setattr(git_clone_service, "git_available", lambda: True)

    def fake_run(repository, target, timeout):
        calls.append((["git", "clone", "--", repository, target.name], target.parent, timeout))
        destination.mkdir()
        return "cloned"

    monkeypatch.setattr(git_clone_service, "_run_clone", fake_run)
    result = git_clone_service.clone_repository("https://github.com/example/project.git", destination)

    assert result == "cloned"
    assert calls == [
        (["git", "clone", "--", "https://github.com/example/project.git", "project"], tmp_path, 600)
    ]


def test_project_management_endpoints_create_and_open_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    token = "p" * 32
    root = tmp_path / "projects"
    root.mkdir()
    security = WebSecurityConfig.build(host="0.0.0.0", auth_token=token, workspace_root=root)
    state = BridgeState(security=security)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _post(
            base,
            "/api/projects/create",
            {"name": "phone-project", "initialize_git": False, "confirm": "CREATE"},
            token=token,
            csrf=state.csrf_token,
        )
        assert status == 200
        assert payload["workspace"] == str((root / "phone-project").resolve())
        assert payload["workspaces"] == [
            {"name": "phone-project", "value": str((root / "phone-project").resolve())}
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_locked_root_cannot_be_changed_through_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    token = "l" * 32
    root = tmp_path / "projects"
    other = tmp_path / "other"
    root.mkdir()
    other.mkdir()
    security = WebSecurityConfig.build(host="0.0.0.0", auth_token=token, workspace_root=root)
    state = BridgeState(security=security, workspace_root_locked=True)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _post(
            base,
            "/api/settings/workspace-root",
            {"path": str(other), "confirm": "CHANGE_ROOT"},
            token=token,
            csrf=state.csrf_token,
        )
        assert status == 400
        assert "bloccata" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_create_project_initializes_git_only_when_requested(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    root = tmp_path / "projects"
    root.mkdir()
    calls: list[Path] = []
    monkeypatch.setattr(git_service, "git_init", lambda workspace: calls.append(workspace) or "initialized")
    state = BridgeState(security=WebSecurityConfig.build(workspace_root=root))

    workspace, output = state.create_project("with-git", initialize_git=True)

    assert calls == [workspace]
    assert output == "initialized"


def test_clone_failure_removes_partial_destination(tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "partial"
    monkeypatch.setattr(git_clone_service, "git_available", lambda: True)

    def failing_clone(repository, target, timeout):
        target.mkdir()
        (target / "partial.txt").write_text("incomplete", encoding="utf-8")
        raise git_service.GitIntegrationError("clone failed")

    monkeypatch.setattr(git_clone_service, "_run_clone", failing_clone)
    with pytest.raises(git_service.GitIntegrationError, match="clone failed"):
        git_clone_service.clone_repository("https://github.com/example/partial.git", destination)
    assert not destination.exists()


def test_startup_root_uses_persisted_setting_when_not_explicit(tmp_path: Path, monkeypatch) -> None:
    from local_ai_bridge.core.settings import AppSettings
    from local_ai_bridge.web.project_actions import resolve_startup_workspace_root

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    root = tmp_path / "projects"
    root.mkdir()
    store = SettingsStore()
    store.save(AppSettings(web_workspace_root=str(root)))

    resolved, locked = resolve_startup_workspace_root(None, None)
    assert resolved == str(root)
    assert locked is True

    resolved, locked = resolve_startup_workspace_root(root, None)
    assert resolved == root
    assert locked is True


def test_workspace_root_endpoint_is_never_remotely_configurable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    token = "r" * 32
    root = tmp_path / "projects"
    other = tmp_path / "other"
    root.mkdir()
    other.mkdir()
    security = WebSecurityConfig.build(host="0.0.0.0", auth_token=token, workspace_root=root)
    state = BridgeState(security=security)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _post(
            base,
            "/api/settings/workspace-root",
            {"path": str(other), "confirm": "CHANGE_ROOT"},
            token=token,
            csrf=state.csrf_token,
        )
        assert status == 400
        assert "solo dalle Impostazioni" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
