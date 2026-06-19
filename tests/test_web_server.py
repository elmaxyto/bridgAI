from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from local_ai_bridge.web.server import BridgeHTTPServer, BridgeState
from local_ai_bridge.web.page import render_index
from local_ai_bridge.core.models import ChangePlan, FileChange
from local_ai_bridge.services.pre_apply import build_pre_apply_summary


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


def test_web_github_card_distinguishes_new_and_linked_repository() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="githubRepoLabel"' in page
    assert "Nome nuova repository GitHub" in page
    assert 'placeholder="nome-nuova-repository"' in page
    assert "Repository GitHub collegata" in page
    assert "data.repository_name" in page
    assert "data.suggested_repository_name" in page
    assert "workspaceChanged" in page
    assert "Crea repository e pubblica" in page
    assert "Pubblica aggiornamenti" in page
    assert 'placeholder="nome-progetto"' not in page


def test_web_zip_upload_streams_selected_file_without_array_buffer() -> None:
    page = render_index("csrf", "1.0.0")

    assert "body:file" in page
    assert "file.arrayBuffer()" not in page
    assert "Upload non riuscito" in page


def test_web_checkbox_is_rendered_as_accessible_switch() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="initializeGit" type="checkbox" checked' in page
    assert 'class="switch-track"' in page
    assert '.switch-row input:checked+.switch-track' in page
    assert '.inline-check' not in page


def test_web_page_exposes_prompt_presets() -> None:
    page = render_index("csrf", "1.0.0")
    assert 'id="promptPreset"' in page
    assert 'value="debug"' in page
    assert "Debug guidato" in page
    assert "preset_id" in page


def test_pre_apply_summary_reports_risks_and_available_tests(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "sample.py").write_text("print('ok')\n", encoding="utf-8")
    plan = ChangePlan(
        plan_type="zip",
        workspace=tmp_path,
        source_path=tmp_path / "update.zip",
        changes=[
            FileChange("a.py", "a.py", "create", None, "new", size=10),
            FileChange("image.png", "image.png", "binary", "old", "new", size=20),
            FileChange("old.py", "old.py", "delete", "old", None),
        ],
        diff="",
        warnings=["Controllare il file binario"],
        metadata={"commit_message": "feat: update"},
    )

    summary = build_pre_apply_summary(plan)

    assert summary["total"] == 3
    assert summary["created"] == 1
    assert summary["deleted"] == 1
    assert summary["binary"] == 1
    assert summary["has_commit_message"] is True
    assert summary["warning_count"] == 1
    assert summary["origin"] == "zip: update.zip"
    assert "Python compileall" in summary["tests"]


def test_web_page_renders_pre_apply_checklist() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="preApplyChecklist"' in page
    assert "Checklist pre-applicazione" in page
    assert "data.pre_apply" in page
    assert "Hai controllato la checklist pre-applicazione?" in page


def test_web_page_supports_persistent_light_and_dark_themes() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="themeToggle"' in page
    assert 'onclick="toggleTheme()"' in page
    assert 'bridgai-web-theme' in page
    assert ':root[data-theme="light"]' in page
    assert "prefers-color-scheme: light" in page
    assert "localStorage.getItem('bridgai-web-theme')" in page
    assert "Passa alla modalità chiara" in page
    assert "Passa alla modalità scura" in page
    assert "meta[name=\"theme-color\"]" in page


def test_web_page_interprets_partial_test_results() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'onclick="runTests()"' in page
    assert "data.interpretation" in page
    assert ".feedback.warning" in page
    assert "I test non annullano automaticamente l’aggiornamento" in page


def test_web_page_exposes_favicon_language_and_dictation_controls() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'rel="icon" href="/favicon.svg"' in page
    assert 'id="languageSelect"' in page
    assert 'changeLanguage(this.value)' in page
    assert 'bridgai-web-language' in page
    assert 'id="dictationButton"' in page
    assert 'toggleDictation()' in page
    assert 'SpeechRecognition' in page
    assert 'webkitSpeechRecognition' in page


def test_web_server_serves_svg_favicon(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    state = BridgeState()
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/favicon.svg", timeout=5) as response:
            body = response.read().decode("utf-8")
            assert response.headers.get_content_type() == "image/svg+xml"
        assert body.startswith("<svg")
        assert "linearGradient" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
