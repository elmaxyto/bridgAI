from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from local_ai_bridge.web.server import BridgeHTTPServer, BridgeState
from local_ai_bridge.web.page import render_index


def _request(url: str, method: str = "GET", payload: dict | None = None, csrf: str | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-Local-Bridge-CSRF"] = csrf
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_local_server_status_and_csrf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    state = BridgeState()
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/", timeout=5) as response:
            page = response.read().decode("utf-8")
        assert f"127.0.0.1:{server.server_address[1]}" in page

        status, payload = _request(base + "/api/status")
        assert status == 200
        assert payload["workspace"] is None

        status, payload = _request(base + "/api/workspace", "POST", {"path": str(tmp_path)})
        assert status == 403
        assert "CSRF" in payload["error"]

        status, payload = _request(
            base + "/api/workspace", "POST", {"path": str(tmp_path)}, state.csrf_token
        )
        assert status == 200
        assert payload["workspace"] == str(tmp_path.resolve())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_page_shows_root_as_desktop_managed_read_only_setting() -> None:
    page = render_index("csrf", "1.0.0")
    assert 'id="workspaceRoot" readonly' in page
    assert "Salva root" not in page
    assert "saveWorkspaceRoot" not in page
    assert "Configura la root nelle Impostazioni del programma BridgAI" in page


def test_web_page_shows_connection_address() -> None:
    page = render_index(
        "csrf",
        "1.0.0",
        connection_address="192.168.1.44:8765",
    )
    assert "Collegati a" in page
    assert 'id="connectionAddress">192.168.1.44:8765</strong>' in page
    assert "renderConnection(status)" in page


def test_restart_endpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    state = BridgeState()
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    
    restart_called = threading.Event()
    
    def mock_execv(prog, args):
        restart_called.set()
        raise RuntimeError("execv called successfully")
        
    def mock_exit(code):
        pass
        
    import os
    monkeypatch.setattr(os, "execv", mock_execv)
    monkeypatch.setattr(os, "_exit", mock_exit)
    
    try:
        status, payload = _request(
            base + "/api/restart", "POST", {}, state.csrf_token
        )
        assert status == 200
        assert "Riavvio" in payload["message"]
        
        # Wait for the background thread to run the restart logic
        assert restart_called.wait(timeout=2.0)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_page_uses_guided_simple_workflow() -> None:
    page = render_index("csrf", "1.0.0")

    assert "Cosa vuoi fare oggi?" in page
    assert "Prepara richiesta per l’AI" in page
    assert "Continua su ChatGPT" in page
    assert "Continua su Claude" in page
    assert "Continua su Gemini" in page
    assert "Prepara i file richiesti" in page
    assert "Applica aggiornamento" in page
    assert 'id="verificationTools"' in page
    assert "Verifica e strumenti avanzati" in page
    assert "5. Verifica" not in page
    assert "4. Analizza la modifica restituita" not in page
