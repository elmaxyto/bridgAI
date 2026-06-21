from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from local_ai_bridge.core.settings import AppSettings, SettingsStore
from local_ai_bridge.services.browser_extension import queue_request
from local_ai_bridge.web.server import BridgeHTTPServer, BridgeState


def _request(
    url: str,
    *,
    method: str = "GET",
    token: str = "",
    payload: dict | None = None,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
):
    body = data
    merged = dict(headers or {})
    if token:
        merged["X-BridgAI-Extension-Token"] = token
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        merged["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=merged)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.status, json.loads(raw.decode("utf-8")), response.headers
            return response.status, raw, response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8")), exc.headers


def _update_zip() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sample.py", "print('updated')\n")
        archive.writestr(
            "commit-message.md",
            "feat(extension): test update\n\n- update sample file\n",
        )
    return stream.getvalue()


def test_extension_api_requires_local_token_and_supports_full_exchange(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.py").write_text("print('old')\n", encoding="utf-8")
    (workspace / "extra.py").write_text("print('extra')\n", encoding="utf-8")
    updates = tmp_path / "updates"
    updates.mkdir()
    token = "extension-token-with-at-least-thirty-two-characters"
    store = SettingsStore()
    store.save(
        AppSettings(
            last_workspace=str(workspace),
            browser_extension_enabled=True,
            browser_extension_token=token,
            update_zip_directory=str(updates),
        )
    )
    queued = queue_request(workspace, "Please update sample.py")

    state = BridgeState(initial_workspace=workspace)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload, _headers = _request(base + "/api/extension/status")
        assert status == 401
        assert "token" in payload["error"].lower()

        status, payload, _headers = _request(
            base + "/api/extension/status",
            token=token,
            headers={"X-Forwarded-For": "203.0.113.8"},
        )
        assert status == 401
        assert "remota" in payload["error"]

        status, payload, headers = _request(
            base + "/api/extension/next",
            token=token,
            headers={"Origin": "chrome-extension://example"},
        )
        assert status == 200
        assert payload["request"]["request_id"] == queued["request_id"]
        assert headers["Access-Control-Allow-Origin"] == "chrome-extension://example"

        status, payload, _headers = _request(
            base + "/api/extension/response",
            method="POST",
            token=token,
            payload={
                "request_id": queued["request_id"],
                "text": "#scarica sample.py",
            },
        )
        assert status == 200
        assert payload["action"] == "attach_context"
        assert payload["files"] == ["sample.py"]

        first_artifact_url = payload["artifact_url"]
        assert first_artifact_url.startswith("/api/extension/artifacts/")
        status, artifact, _headers = _request(
            base + first_artifact_url,
            token=token,
        )
        assert status == 200
        with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
            assert "sample.py" in archive.namelist()

        status, payload, _headers = _request(
            base + "/api/extension/response",
            method="POST",
            token=token,
            payload={
                "request_id": queued["request_id"],
                "text": "#scarica extra.py",
            },
        )
        assert status == 200
        assert payload["action"] == "attach_context"
        assert payload["files"] == ["extra.py"]
        assert payload["artifact_url"] != first_artifact_url
        assert "richiedili nuovamente" in payload["followup_prompt"]

        status, artifact, _headers = _request(
            base + payload["artifact_url"],
            token=token,
        )
        assert status == 200
        with zipfile.ZipFile(io.BytesIO(artifact)) as archive:
            assert "extra.py" in archive.namelist()

        status, payload, _headers = _request(
            base + "/api/extension/zip",
            method="POST",
            token=token,
            data=_update_zip(),
            headers={
                "Content-Type": "application/zip",
                "X-File-Name": "bridgai_update.zip",
                "X-BridgAI-Request-ID": queued["request_id"],
            },
        )
        assert status == 200
        assert payload["action"] == "update_ready"
        assert payload["plan_id"]
        assert Path(payload["path"]).is_file()
        assert Path(payload["path"]).parent == updates
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_extension_api_remote_access_requires_explicit_opt_in(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    token = "remote-extension-token-with-at-least-thirty-two-chars"
    store = SettingsStore()
    store.save(
        AppSettings(
            last_workspace=str(workspace),
            browser_extension_enabled=True,
            browser_extension_remote_access=False,
            browser_extension_token=token,
        )
    )
    state = BridgeState(initial_workspace=workspace)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    headers = {"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https"}
    try:
        status, payload, _ = _request(
            base + "/api/extension/status", token=token, headers=headers
        )
        assert status == 401
        assert "remota" in payload["error"]

        status, payload, _ = _request(
            base + "/api/extension/status",
            token=token,
            headers={"X-Forwarded-Proto": "https"},
        )
        assert status == 401
        assert "remota" in payload["error"]

        settings = store.load()
        settings.browser_extension_remote_access = True
        store.save(settings)

        status, payload, _ = _request(
            base + "/api/extension/status",
            token=token,
            headers={"X-Forwarded-For": "203.0.113.9"},
        )
        assert status == 401
        assert "HTTPS" in payload["error"]

        status, payload, _ = _request(
            base + "/api/extension/status",
            token=token,
            headers={"X-Forwarded-Proto": "https"},
        )
        assert status == 200
        assert payload["enabled"] is True

        status, payload, _ = _request(
            base + "/api/extension/status", token=token, headers=headers
        )
        assert status == 200
        assert payload["enabled"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_extension_api_adopts_completed_chrome_download(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "sample.py").write_text("print('old')\n", encoding="utf-8")
    updates = tmp_path / "updates"
    updates.mkdir()
    token = "extension-download-token-with-at-least-thirty-two-chars"
    store = SettingsStore()
    store.save(
        AppSettings(
            last_workspace=str(workspace),
            browser_extension_enabled=True,
            browser_extension_token=token,
            browser_extension_auto_download=True,
            update_zip_directory=str(updates),
        )
    )
    queued = queue_request(workspace, "Please update sample.py")

    state = BridgeState(initial_workspace=workspace)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload, _headers = _request(base + "/api/extension/next", token=token)
        assert status == 200
        assert payload["request"]["request_id"] == queued["request_id"]

        status, payload, _headers = _request(
            base + "/api/extension/response",
            method="POST",
            token=token,
            payload={
                "request_id": queued["request_id"],
                "text": "Ho preparato lo ZIP applicabile.",
            },
        )
        assert status == 200
        assert payload["action"] == "wait_for_zip"

        outside = tmp_path / "outside.zip"
        outside.write_bytes(_update_zip())
        status, payload, _headers = _request(
            base + "/api/extension/download-complete",
            method="POST",
            token=token,
            payload={
                "request_id": queued["request_id"],
                "path": str(outside),
                "filename": outside.name,
            },
        )
        assert status == 400
        assert "fuori" in payload["error"]

        downloaded = updates / "bridgai_update.zip"
        downloaded.write_bytes(_update_zip())
        status, payload, _headers = _request(
            base + "/api/extension/download-complete",
            method="POST",
            token=token,
            payload={
                "request_id": queued["request_id"],
                "path": str(downloaded),
                "filename": downloaded.name,
                "download_id": 42,
            },
        )
        assert status == 200
        assert payload["action"] == "update_ready"
        assert payload["plan_id"]
        assert Path(payload["path"]) == downloaded.resolve()
        assert payload["pre_apply"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_extension_api_synchronizes_and_resets_download_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    download_directory = tmp_path / "Chrome Downloads" / "BridgAI"
    download_directory.mkdir(parents=True)
    token = "extension-folder-token-with-at-least-thirty-two-characters"
    store = SettingsStore()
    store.save(
        AppSettings(
            last_workspace=str(workspace),
            browser_extension_enabled=True,
            browser_extension_token=token,
        )
    )

    state = BridgeState(initial_workspace=workspace)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        invalid_probe = download_directory / "ordinary-file.tmp"
        invalid_probe.write_bytes(b"not a BridgAI probe")
        status, payload, _headers = _request(
            base + "/api/extension/download-directory",
            method="POST",
            token=token,
            payload={"enabled": True, "path": str(invalid_probe)},
        )
        assert status == 400
        assert "verifica" in payload["error"]
        assert store.load().update_zip_directory == ""

        probe = download_directory / ".bridgai-download-directory-123-test.tmp"
        probe.write_bytes(b"BridgAI download directory probe\n")
        status, payload, _headers = _request(
            base + "/api/extension/download-directory",
            method="POST",
            token=token,
            payload={"enabled": True, "path": str(probe)},
        )
        assert status == 200
        assert payload["action"] == "download_directory_ready"
        assert Path(payload["update_directory"]) == download_directory.resolve()
        assert store.load().update_zip_directory == str(download_directory.resolve())
        assert not probe.exists()

        status, payload, _headers = _request(
            base + "/api/extension/status",
            token=token,
        )
        assert status == 200
        assert payload["update_directory"] == str(download_directory.resolve())

        status, payload, _headers = _request(
            base + "/api/extension/download-directory",
            method="POST",
            token=token,
            payload={"enabled": False, "path": ""},
        )
        assert status == 200
        assert payload["action"] == "download_directory_reset"
        assert payload["update_directory"] == ""
        assert store.load().update_zip_directory == ""
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_extension_api_records_automation_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    token = "extension-error-token-with-at-least-thirty-two-characters"
    store = SettingsStore()
    store.save(
        AppSettings(
            last_workspace=str(workspace),
            browser_extension_enabled=True,
            browser_extension_token=token,
        )
    )
    queued = queue_request(workspace, "Please update sample.py")

    state = BridgeState(initial_workspace=workspace)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload, _headers = _request(
            base + "/api/extension/error",
            method="POST",
            token=token,
            payload={
                "request_id": queued["request_id"],
                "message": "ChatGPT did not accept the attachment",
            },
        )
        assert status == 200
        assert payload["action"] == "error_recorded"

        status, payload, _headers = _request(
            base + "/api/extension/status",
            token=token,
        )
        assert status == 200
        assert payload["request_status"] == "ChatGPT did not accept the attachment"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
