from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from local_ai_bridge.web import network as web_network
from local_ai_bridge.web.security import WebSecurityConfig
from local_ai_bridge.web.server import BridgeHTTPServer, BridgeState


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    token: str | None = None,
    csrf: str | None = None,
):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if csrf:
        headers["X-Local-Bridge-CSRF"] = csrf
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_authenticated_server_lists_only_authorized_workspaces(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    root = tmp_path / "workspaces"
    allowed = root / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir(parents=True)
    outside.mkdir()
    token = "t" * 32
    security = WebSecurityConfig.build(host="0.0.0.0", auth_token=token, workspace_root=root)
    state = BridgeState(security=security)
    monkeypatch.setattr(web_network, "local_ipv4_addresses", lambda: ["192.168.1.44"])
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, _ = _json_request(base + "/api/status")
        assert status == 401

        status, payload = _json_request(base + "/api/status", token=token)
        assert status == 200
        assert payload["remote_mode"] is True
        assert payload["connection_address"] == f"192.168.1.44:{server.server_address[1]}"
        assert payload["network_addresses"] == [
            f"192.168.1.44:{server.server_address[1]}"
        ]
        assert payload["workspaces"] == [{"name": "allowed", "value": str(allowed.resolve())}]

        status, payload = _json_request(
            base + "/api/workspace",
            method="POST",
            payload={"path": "allowed"},
            token=token,
            csrf=state.csrf_token,
        )
        assert status == 200
        assert payload["workspace"] == str(allowed.resolve())

        status, payload = _json_request(
            base + "/api/workspace",
            method="POST",
            payload={"path": str(outside)},
            token=token,
            csrf=state.csrf_token,
        )
        assert status == 400
        assert "root autorizzata" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_authenticated_artifact_download(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    token = "a" * 32
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    security = WebSecurityConfig.build(host="0.0.0.0", auth_token=token, fixed_workspace=workspace)
    state = BridgeState(security=security)
    artifact_file = tmp_path / "result.zip"
    artifact_file.write_bytes(b"PK-test")
    artifact = state.register_artifact(artifact_file, content_type="application/zip")
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = urllib.request.Request(
            base + f"/api/artifacts/{artifact.artifact_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "application/zip"
            assert response.read() == b"PK-test"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_remote_export_returns_downloadable_zip(tmp_path: Path, monkeypatch) -> None:
    import zipfile

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    token = "z" * 32
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.py").write_text("print('ok')\n", encoding="utf-8")
    security = WebSecurityConfig.build(host="0.0.0.0", auth_token=token, fixed_workspace=workspace)
    state = BridgeState(security=security)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _json_request(
            base + "/api/export",
            method="POST",
            payload={"text": "#scarica sample.py"},
            token=token,
            csrf=state.csrf_token,
        )
        assert status == 200
        request = urllib.request.Request(
            base + f"/api/artifacts/{payload['artifact_id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        downloaded = tmp_path / "download.zip"
        with urllib.request.urlopen(request, timeout=5) as response:
            downloaded.write_bytes(response.read())
        with zipfile.ZipFile(downloaded) as archive:
            assert "sample.py" in archive.namelist()
            assert archive.read("sample.py") == b"print('ok')\n"
            assert "bridgai-project.json" in archive.namelist()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_two_factor_login_issues_session_and_rejects_totp_replay(tmp_path: Path, monkeypatch) -> None:
    import base64

    from local_ai_bridge.web.security import generate_totp_secret, hash_password, totp_at

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    secret = generate_totp_secret()
    security = WebSecurityConfig.build(
        host="0.0.0.0",
        username="admin",
        password_hash=hash_password("correct horse battery staple"),
        totp_secret=secret,
        fixed_workspace=workspace,
    )
    state = BridgeState(security=security)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    basic = "Basic " + base64.b64encode(b"admin:correct horse battery staple").decode("ascii")
    code = totp_at(secret)

    def login(second_factor: str):
        request = urllib.request.Request(
            base + "/api/auth/login",
            data=json.dumps({"second_factor": second_factor}).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": basic,
                "X-Local-Bridge-CSRF": state.csrf_token,
                "X-Forwarded-For": "8.8.8.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    try:
        status, payload = login(code)
        assert status == 200
        assert payload["second_factor"] == "totp"
        session = payload["session_token"]

        request = urllib.request.Request(
            base + "/api/status",
            headers={"Authorization": f"Bearer {session}", "X-Forwarded-For": "8.8.8.8"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            status_payload = json.loads(response.read().decode("utf-8"))
        assert status_payload["two_factor_enabled"] is True
        assert status_payload["two_factor_required"] is True

        replay_status, replay_payload = login(code)
        assert replay_status == 403
        assert "già utilizzato" in replay_payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_private_lan_can_skip_second_factor_when_explicitly_enabled(tmp_path: Path, monkeypatch) -> None:
    import base64

    from local_ai_bridge.web.security import generate_totp_secret, hash_password

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    security = WebSecurityConfig.build(
        host="0.0.0.0",
        username="admin",
        password_hash=hash_password("correct horse battery staple"),
        totp_secret=generate_totp_secret(),
        totp_local_bypass=True,
        fixed_workspace=workspace,
    )
    state = BridgeState(security=security)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    basic = "Basic " + base64.b64encode(b"admin:correct horse battery staple").decode("ascii")
    request = urllib.request.Request(
        base + "/api/auth/login",
        data=b'{"second_factor":""}',
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": basic,
            "X-Local-Bridge-CSRF": state.csrf_token,
            "X-Forwarded-For": "192.168.1.55",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["second_factor"] == "local-bypass"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
