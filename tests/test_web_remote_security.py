from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_bridge.web.security import WebSecurityConfig, WorkspacePolicy
from local_ai_bridge.web.page import render_index, render_manifest


def test_remote_binding_requires_long_token_and_workspace_boundary(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="token"):
        WebSecurityConfig.build(host="0.0.0.0", workspace_root=tmp_path)

    with pytest.raises(ValueError, match="workspace-root"):
        WebSecurityConfig.build(host="0.0.0.0", auth_token="x" * 32)


def test_workspace_policy_rejects_paths_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "workspaces"
    allowed = root / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir(parents=True)
    outside.mkdir()
    config = WebSecurityConfig.build(
        host="0.0.0.0",
        auth_token="a" * 32,
        workspace_root=root,
    )
    policy = WorkspacePolicy(config)

    assert policy.resolve_selection("allowed") == allowed.resolve()
    with pytest.raises(ValueError, match="root autorizzata"):
        policy.resolve_selection(str(outside))


def test_bearer_token_comparison() -> None:
    config = WebSecurityConfig.build(auth_token="secret-token-value-that-is-long")
    assert config.accepts_authorization("Bearer secret-token-value-that-is-long") is True
    assert config.accepts_authorization("Bearer wrong") is False
    assert config.accepts_authorization(None) is False


def test_mobile_page_contains_upload_and_auth_controls() -> None:
    page = render_index("csrf-value", "1.0.0")
    assert 'type="file"' in page
    assert "Authorization" in page
    assert "/api/patch/inspect" in page
    assert "/api/artifacts/" in page
    assert 'id="workspaceRoot" readonly' in page
    assert "/api/settings/workspace-root" not in page
    assert "Configura la root nelle Impostazioni del programma BridgAI" in page
    assert "/api/projects/create" in page
    assert "/api/projects/clone" in page
    assert "csrf-value" in page
    assert '"display": "standalone"' in render_manifest("1.0.0")


def test_username_password_authentication(tmp_path: Path) -> None:
    import base64
    from local_ai_bridge.web.security import hash_password, verify_password

    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded) is True
    assert verify_password("wrong password", encoded) is False

    config = WebSecurityConfig.build(
        host="0.0.0.0",
        username="admin",
        password_hash=encoded,
        workspace_root=tmp_path,
    )
    header = "Basic " + base64.b64encode(b"admin:correct horse battery staple").decode("ascii")
    assert config.accepts_authorization(header) is True
    assert config.accepts_authorization("Basic " + base64.b64encode(b"admin:wrong password").decode("ascii")) is False
    assert config.accepts_authorization(None) is False


def test_mobile_page_contains_username_and_password_login() -> None:
    page = render_index("csrf-value", "1.0.0")
    assert 'id="authUsername"' in page
    assert 'id="authPassword"' in page
    assert 'id="rememberCredentials"' in page
    assert "Basic " in page
    assert "localStorage" in page
    assert "sessionStorage" in page
    assert "storageRemove('localStorage',authKey)" in page
