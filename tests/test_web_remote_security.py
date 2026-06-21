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
    assert 'id="passwordVisibilityToggle"' in page
    assert "togglePasswordVisibility" in page
    assert '<label for="authSecondFactor">Codice 2FA</label>' in page
    assert "Codice 2FA o recupero" not in page
    assert 'id="rememberCredentials"' in page
    assert "Basic " in page
    assert "localStorage" in page
    assert "sessionStorage" in page
    assert "storageRemove('localStorage',authKey)" in page


def test_totp_matches_rfc_6238_vector_and_rejects_replay() -> None:
    import base64

    from local_ai_bridge.web.security import totp_at, verify_totp

    secret = base64.b32encode(b"12345678901234567890").decode("ascii").rstrip("=")
    assert totp_at(secret, 59, digits=8) == "94287082"

    code = totp_at(secret, 59)
    assert verify_totp(secret, code, for_time=59, valid_window=0) == 1
    assert verify_totp(secret, code, for_time=59, valid_window=0, last_counter=1) is None


def test_two_factor_requires_password_authentication_and_can_bypass_private_lan(tmp_path: Path) -> None:
    from local_ai_bridge.web.security import generate_totp_secret, hash_password

    secret = generate_totp_secret()
    with pytest.raises(ValueError, match="username e password"):
        WebSecurityConfig.build(
            host="0.0.0.0",
            auth_token="t" * 32,
            totp_secret=secret,
            workspace_root=tmp_path,
        )

    config = WebSecurityConfig.build(
        host="0.0.0.0",
        username="admin",
        password_hash=hash_password("a sufficiently long password"),
        totp_secret=secret,
        totp_local_bypass=True,
        workspace_root=tmp_path,
    )
    assert config.requires_two_factor("192.168.1.20") is False
    assert config.requires_two_factor("10.20.30.40") is False
    assert config.requires_two_factor("8.8.8.8") is True


def test_proxy_client_address_is_trusted_only_from_loopback() -> None:
    from local_ai_bridge.web.security import client_address_from_proxy

    assert client_address_from_proxy("127.0.0.1", "198.51.100.7") == "198.51.100.7"
    assert client_address_from_proxy("192.168.1.10", "198.51.100.7") == "192.168.1.10"
    assert client_address_from_proxy("127.0.0.1", "1.2.3.4, 8.8.8.8") == "8.8.8.8"


def test_recovery_codes_are_high_entropy_and_hashable() -> None:
    from local_ai_bridge.web.security import generate_recovery_codes, hash_recovery_code

    codes = generate_recovery_codes()
    assert len(codes) == 8
    assert len(set(codes)) == 8
    assert all(len(code) == 14 for code in codes)
    assert all(len(hash_recovery_code(code)) == 64 for code in codes)

def test_launcher_forwards_totp_credentials_behind_loopback_reverse_proxy() -> None:
    from local_ai_bridge.web.launcher import _add_authentication_environment

    environment: dict[str, str] = {}
    _add_authentication_environment(
        environment,
        username="admin",
        password_hash="pbkdf2-value",
        totp_secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        totp_local_bypass=True,
    )

    assert environment["BRIDGAI_WEB_USERNAME"] == "admin"
    assert environment["BRIDGAI_WEB_PASSWORD_HASH"] == "pbkdf2-value"
    assert environment["BRIDGAI_WEB_TOTP_SECRET"]
    assert environment["BRIDGAI_WEB_TOTP_LOCAL_BYPASS"] == "1"

