from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

import pytest

from local_ai_bridge.web.server import BridgeHTTPServer, BridgeState
from local_ai_bridge.web.page import render_index, render_manifest
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


def _upload_file(
    url: str,
    filename: str,
    data: bytes,
    csrf: str,
) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/octet-stream",
            "X-File-Name": urllib.parse.quote(filename),
            "X-Local-Bridge-CSRF": csrf,
        },
    )
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


def test_mobile_header_keeps_only_brand_language_and_theme_controls() -> None:
    page = render_index("csrf", "1.0.0")

    assert ".header-row{display:flex;align-items:center;justify-content:space-between" in page
    assert ".brand small{display:none}" in page
    assert ".header-meta{flex:0 0 auto;min-width:0;justify-content:flex-end" in page
    assert ".project-chip,.header-meta .badge{display:none}" in page
    assert ".language-control select{min-height:2.45rem}" in page
    assert ".theme-toggle{width:2.45rem;height:2.45rem" in page


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


def test_web_superpower_button_uses_compact_svg_without_emoji() -> None:
    page = render_index("csrf", "1.1.0")
    assert '<svg class="button-icon"' in page
    assert ".button-icon{display:block;width:1.15rem;height:1.15rem" in page
    assert ".icon-button{display:inline-flex" in page
    assert "⚡ Richiama superpoteri" not in page
    assert "apiGet('/api/superpowers/list')" in page
    assert "api('/api/superpowers/list',{})" not in page


def test_web_superpower_list_uses_safe_dom_rendering_and_compact_checkboxes() -> None:
    page = render_index("csrf", "1.1.0")

    assert "escapeHtml(" not in page
    assert "title.textContent=item.title||item.id||''" in page
    assert "description.textContent=item.description||''" in page
    assert "example.textContent=superpowerExample(item)" in page
    assert ".superpower-item input[type=checkbox]{width:1.1rem" in page
    assert ".superpower-example{" in page
    assert "Nessun superpotere corrisponde ai filtri." in page


def test_web_superpower_catalog_is_available_through_get(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    state = BridgeState()
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(base + "/api/superpowers/list")
        assert status == 200
        assert payload["items"]
        assert all(item["id"] and item["title"] for item in payload["items"])
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
    assert "Continua su DeepSeek" in page
    assert "Prepara i file richiesti" in page
    assert "Applica aggiornamento" in page
    assert 'id="zipUpdateInput"' in page
    assert 'id="textUpdateInput" hidden' in page
    assert 'id="markdownUpdateFile"' in page
    assert 'accept=".md,.txt,text/markdown,text/plain"' in page
    assert "Analizza file" in page
    assert "Oppure incolla manualmente la risposta" in page
    assert 'id="patchText"' in page
    assert "Analizza testo incollato" in page
    assert "uploadMarkdownUpdate()" in page
    assert "SEARCH/REPLACE" not in page
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
    assert summary["source_name"] == "update.zip"
    assert summary["warning_count"] == 1
    assert summary["origin"] == "zip: update.zip"
    assert "Python compileall" in summary["tests"]


def test_web_page_renders_pre_apply_checklist() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="preApplyChecklist"' in page
    assert "Checklist pre-applicazione" in page
    assert "data.pre_apply" in page
    assert "Hai controllato la checklist pre-applicazione?" in page


def test_web_page_shows_update_recap_from_commit_message() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="updateRecap"' in page
    assert "Recap aggiornamento" in page
    assert "currentCommitMessage=typeof data.commit_message==='string'" in page
    assert "Recap aggiornamento:" in page
    assert "Nessun commit-message.md presente nello ZIP" in page
    assert "currentPatchFilename" in page
    assert "File patch: ${currentPatchFilename||'-'}" in page


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
    assert "document.startViewTransition" in page
    assert "theme-reveal" in page
    assert "prefers-reduced-motion:reduce" in page
    assert "theme-toggle-active" in page


def test_web_page_interprets_partial_test_results() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'onclick="runTests()"' in page
    assert "data.interpretation" in page
    assert ".feedback.warning" in page
    assert "I test non annullano automaticamente l’aggiornamento" in page


def test_web_page_exposes_favicon_language_and_dictation_controls() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'rel="icon" href="/favicon.svg?v=' in page
    assert '<img class="brand-mark" src="/favicon.svg?v=' in page
    assert page.count('/favicon.svg?v=') == 3
    assert 'id="languageSelect"' in page
    assert 'changeLanguage(this.value)' in page
    assert 'bridgai-web-language' in page
    assert 'id="dictationButton"' in page
    assert 'class="microphone-icon"' in page
    assert 'aria-label="Avvia dettatura vocale"' in page
    assert ">Dettatura</span>" in page
    assert 'toggleDictation()' in page
    assert 'SpeechRecognition' in page
    assert 'webkitSpeechRecognition' in page
    assert "navigator.mediaDevices.getUserMedia" in page
    assert "window.isSecureContext" in page
    assert "Accesso al microfono negato" in page
    assert "Il microfono richiede una connessione HTTPS" in page
    assert ".dictation-button{position:absolute" in page
    assert "border-radius:50%" in page


def test_web_icon_urls_change_with_the_official_icon_content(monkeypatch, tmp_path: Path) -> None:
    icon = tmp_path / "app_icon.svg"
    icon.write_text("<svg>first</svg>", encoding="utf-8")
    monkeypatch.setattr("local_ai_bridge.web.page._icon_path", lambda: icon)

    first_page = render_index("csrf", "1.0.0")
    first_manifest = json.loads(render_manifest("1.0.0"))

    icon.write_text("<svg>second</svg>", encoding="utf-8")
    second_page = render_index("csrf", "1.0.0")
    second_manifest = json.loads(render_manifest("1.0.0"))

    assert first_page != second_page
    assert first_manifest["icons"][0]["src"] != second_manifest["icons"][0]["src"]
    assert first_manifest["icons"][0]["src"] in first_page
    assert second_manifest["icons"][0]["src"] in second_page


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
        expected = (
            Path(__file__).parents[1]
            / "src"
            / "local_ai_bridge"
            / "resources"
            / "app_icon.svg"
        ).read_text(encoding="utf-8")
        assert body == expected
        assert "data:image/png;base64," in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_page_exposes_two_factor_login_without_storing_password() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="authSecondFactor"' in page
    assert 'autocomplete="one-time-code"' in page
    assert '<label for="authSecondFactor">Codice 2FA</label>' in page
    assert "Codice 2FA o recupero" not in page
    assert 'id="passwordVisibilityToggle"' in page
    assert 'onclick="togglePasswordVisibility()"' in page
    assert 'aria-label="Mostra password"' in page
    assert 'class="password-icon"' in page
    assert 'password-icon-show' in page
    assert 'password-icon-hide' in page
    assert "👁" not in page
    assert "/api/auth/info" in page
    assert "/api/auth/login" in page
    assert "/api/auth/logout" in page
    assert "bridgai-web-session" in page
    assert "Ricorda l’accesso su questo browser" in page
    assert "La password e il codice 2FA non vengono conservati" in page


def test_web_page_exposes_remote_browser_automation_controls() -> None:
    page = render_index("csrf", "1.0.0")
    assert 'id="automationSendButton"' in page
    assert 'id="browserAutomation"' in page
    assert 'id="automationServerUrl"' in page
    assert 'id="automationToken"' in page
    assert "/api/browser-automation/configure" in page
    assert "/api/browser-automation/queue" in page
    assert "/api/browser-automation/status" in page
    assert "window.location.origin" in page
    assert "Per collegare un browser remoto" in page


def test_web_page_exposes_power_user_settings_without_sensitive_fields() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="powerUserSettings"' in page
    assert page.index('id="powerUserSettings"') > page.index('id="verificationTools"')
    assert 'id="includeCustomPrompts"' in page
    assert 'id="globalPrompt"' in page
    assert 'id="projectPrompt"' in page
    assert 'id="projectIgnore"' in page
    assert 'id="preferredWebAi"' in page
    assert 'onchange="applyPreferredWebAiPreset()"' in page
    assert 'id="requestedFilesFormat"' in page
    assert 'id="updateFormat"' in page
    assert 'data-provider="chatgpt"' in page
    assert 'data-provider="claude"' in page
    assert 'data-provider="gemini"' in page
    assert 'data-provider="deepseek"' in page
    assert 'id="textualFileOperationsMode"' not in page
    assert "/api/power-user/settings" in page
    assert "Credenziali, 2FA, root progetti e chiavi cloud" in page
    assert "Power-user settings" in page
    assert "Open a project to edit project-specific prompts and exclusions." in page
    assert 'id="aiAssistantCloudKey"' not in page
    assert 'id="webTotpSecret"' not in page
    assert "BEGIN_FILE / OPERATION / PATH / CONTENT / END_FILE" not in page


def test_web_power_user_settings_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = BridgeState()
    state.settings.gemini_drive_enabled = True
    state.settings.markdown_exchange_mode = True
    state.settings.web_port = 9876
    state.settings_store.save(state.settings)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, _ = _request(
            base + "/api/workspace",
            "POST",
            {"path": str(workspace)},
            state.csrf_token,
        )
        assert status == 200

        status, payload = _request(base + "/api/power-user/settings")
        assert status == 200
        assert payload["project_available"] is True
        assert payload["workspace"] == str(workspace.resolve())
        assert payload["preferred_web_ai"] == "custom"

        status, payload = _request(
            base + "/api/power-user/settings",
            "POST",
            {
                "include_custom_prompts": False,
                "global_prompt": "Usa sempre type hints.",
                "preferred_web_ai": "custom",
                "markdown_exchange_mode": True,
                "textual_file_operations_mode": True,
                "project_prompt": "Mantieni compatibilità Python 3.11.",
                "project_ignore": "dist/\n*.sqlite\n",
                "confirm": "SAVE_POWER_USER_SETTINGS",
            },
            state.csrf_token,
        )
        assert status == 200
        assert payload["message"] == "Impostazioni power-user salvate."
        assert payload["include_custom_prompts"] is False
        assert payload["preferred_web_ai"] == "custom"
        assert payload["markdown_exchange_mode"] is True
        assert payload["textual_file_operations_mode"] is True
        assert payload["project_prompt"] == "Mantieni compatibilità Python 3.11."
        assert payload["project_ignore"] == "dist/\n*.sqlite\n"
        assert state.settings.global_prompt == "Usa sempre type hints."
        assert state.settings.gemini_drive_enabled is True
        assert state.settings.markdown_exchange_mode is True
        assert state.settings.web_port == 9876

        status, persisted = _request(base + "/api/power-user/settings")
        assert status == 200
        assert persisted["global_prompt"] == "Usa sempre type hints."
        assert persisted["project_prompt"] == "Mantieni compatibilità Python 3.11."
        assert persisted["project_ignore"] == "dist/\n*.sqlite\n"

        status, payload = _request(
            base + "/api/power-user/settings",
            "POST",
            {
                "include_custom_prompts": False,
                "global_prompt": "Usa sempre type hints.",
                "preferred_web_ai": "gemini",
                "markdown_exchange_mode": True,
                "textual_file_operations_mode": False,
                "project_prompt": "Mantieni compatibilità Python 3.11.",
                "project_ignore": "dist/\n*.sqlite\n",
                "confirm": "SAVE_POWER_USER_SETTINGS",
            },
            state.csrf_token,
        )
        assert status == 200
        assert payload["preferred_web_ai"] == "gemini"
        assert payload["markdown_exchange_mode"] is False
        assert payload["textual_file_operations_mode"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_power_user_settings_require_confirmation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    state = BridgeState()
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(
            base + "/api/power-user/settings",
            "POST",
            {
                "include_custom_prompts": False,
                "global_prompt": "not saved",
                "markdown_exchange_mode": False,
                "textual_file_operations_mode": False,
                "project_prompt": "",
                "project_ignore": "",
            },
            state.csrf_token,
        )
        assert status == 400
        assert "Conferma" in payload["error"]
        assert state.settings.global_prompt == ""
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_report_cannot_toggle_advanced_text_file_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = BridgeState()
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, _payload = _request(
            base + "/api/workspace",
            "POST",
            {"path": str(workspace)},
            state.csrf_token,
        )
        assert status == 200

        status, payload = _request(
            base + "/api/report",
            "POST",
            {"task": "Crea un file", "textual_file_operations_mode": True},
            state.csrf_token,
        )
        assert status == 200
        assert "**FORMATO MODIFICHE — File Markdown di aggiornamento**" not in payload["report"]

        status, payload = _request(base + "/api/status")
        assert status == 200
        assert payload["textual_file_operations_mode"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_text_file_operations_mode_generates_and_inspects(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "obsolete.txt").write_text("old\n", encoding="utf-8")
    state = BridgeState()
    state.settings.textual_file_operations_mode = True
    state.settings_store.save(state.settings)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(
            base + "/api/workspace",
            "POST",
            {"path": str(workspace)},
            state.csrf_token,
        )
        assert status == 200

        status, payload = _request(
            base + "/api/report",
            "POST",
            {"task": "Crea un file ed elimina quello obsoleto"},
            state.csrf_token,
        )
        assert status == 200
        assert "**FORMATO MODIFICHE — File Markdown di aggiornamento**" in payload["report"]

        status, payload = _request(base + "/api/status")
        assert status == 200
        assert payload["textual_file_operations_mode"] is True

        response = '''
BEGIN_FILE
OPERATION: CREATE
PATH: created.txt
FINAL_NEWLINE: YES
CONTENT:
```text
created
```
END_FILE
BEGIN_FILE
OPERATION: DELETE
PATH: obsolete.txt
END_FILE
'''
        status, payload = _request(
            base + "/api/patch/inspect",
            "POST",
            {"text": response},
            state.csrf_token,
        )
        assert status == 200
        assert [item["kind"] for item in payload["changes"]] == ["create", "delete"]

        wrapped_response = '''Ecco il risultato:
```text
**BEGIN_FILE**
**OPERATION: CREA**
**PATH: `wrapped.txt`**
CONTENT:
~~~text
wrapped
~~~~
**END_FILE**
```
'''
        status, payload = _request(
            base + "/api/patch/inspect",
            "POST",
            {"text": wrapped_response},
            state.csrf_token,
        )
        assert status == 200
        assert [item["kind"] for item in payload["changes"]] == ["create"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_markdown_update_upload_matches_pasted_text_and_validates_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = BridgeState()
    state.settings.textual_file_operations_mode = True
    state.settings_store.save(state.settings)
    server = BridgeHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    update = """<!-- BRIDGAI:FILE commit-message.md -->
<!-- BRIDGAI:TEXT final-newline=1 -->
```markdown
feat(web): persist Markdown update metadata

- create the uploaded file
```

BEGIN_FILE
OPERATION: CREATE
PATH: created.txt
FINAL_NEWLINE: YES
CONTENT:
```text
created
```
END_FILE
"""
    try:
        status, _payload = _request(
            base + "/api/workspace",
            "POST",
            {"path": str(workspace)},
            state.csrf_token,
        )
        assert status == 200

        status, pasted = _request(
            base + "/api/patch/inspect",
            "POST",
            {"text": update},
            state.csrf_token,
        )
        assert status == 200
        assert pasted["commit_message"].startswith(
            "feat(web): persist Markdown update metadata"
        )

        status, uploaded_md = _upload_file(
            base + "/api/markdown/upload",
            "bridgai-update.md",
            update.encode("utf-8"),
            state.csrf_token,
        )
        assert status == 200
        assert uploaded_md["changes"] == pasted["changes"]
        assert uploaded_md["diff"] == pasted["diff"]
        assert uploaded_md["commit_message"] == pasted["commit_message"]
        assert uploaded_md["pre_apply"]["source_name"].endswith("bridgai-update.md")

        status, uploaded_txt = _upload_file(
            base + "/api/markdown/upload",
            "bridgai-update.txt",
            update.encode("utf-8"),
            state.csrf_token,
        )
        assert status == 200
        assert uploaded_txt["changes"] == pasted["changes"]
        assert uploaded_txt["commit_message"] == pasted["commit_message"]
        assert uploaded_txt["pre_apply"]["source_name"].endswith("bridgai-update.txt")

        status, payload = _upload_file(
            base + "/api/markdown/upload",
            "empty.md",
            b"",
            state.csrf_token,
        )
        assert status == 400
        assert "vuoto" in payload["error"].lower()

        status, payload = _upload_file(
            base + "/api/markdown/upload",
            "invalid.txt",
            b"\xff\xfe\x00",
            state.csrf_token,
        )
        assert status == 400
        assert "UTF-8" in payload["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_web_power_user_settings_expose_ai_compatibility_table() -> None:
    page = render_index("csrf", "1.0.0")

    assert 'id="aiWebCompatibility"' in page
    assert '<summary>Compatibilità con le AI Web</summary>' in page
    assert 'class="compatibility-table"' in page
    assert '<th scope="row">Gemini Pro</th><td>ZIP o Markdown</td><td>Markdown</td>' in page
    assert '<th scope="row">DeepSeek</th><td>Markdown</td><td>Markdown</td>' in page
    assert '<th scope="row">Perplexity</th><td>Markdown consigliato</td><td>Markdown</td>' in page
    assert '<th scope="row">Microsoft Copilot</th><td>Markdown</td><td>Markdown</td>' in page
    assert 'ZIP → ZIP è il flusso consigliato ed è l’unico verificato come pienamente funzionante.' in page
    assert 'le patch Markdown potrebbero non essere applicabili in tutti i casi.' in page
    assert '.compatibility-table-wrap' in page


def test_web_project_notes_can_be_added_to_task() -> None:
    page = render_index("csrf", "1.1.1")
    assert "notes-grid" in page
    assert "projectNoteSearch" in page
    assert "Aggiungi alla richiesta" in page
    assert "function addProjectNoteToTask()" in page
    assert "projectNoteRequestText(item)" in page



def test_web_page_requires_extra_confirmation_for_high_risk_recovery() -> None:
    page = render_index("csrf", "1.0.0")

    assert "currentPlanRequiresExplicitConfirmation" in page
    assert "highRiskRecoveryMessage" in page
    assert "HIGH_RISK_APPLY" in page
    assert "alta severità, conferma extra richiesta" in page


class _FakeRecord:
    def to_dict(self) -> dict:
        return {"session_id": "session", "files": []}


class _FakeApplyService:
    def __init__(self) -> None:
        self.confirmed: bool | None = None

    def apply(self, plan, *, explicit_confirmation: bool = False):
        self.confirmed = explicit_confirmation
        if plan.metadata.get("requires_explicit_confirmation") and not explicit_confirmation:
            raise ValueError("conferma esplicita richiesta")
        return _FakeRecord()


class _FakeBridgeState:
    def __init__(self, workspace: Path, plan: ChangePlan) -> None:
        self.workspace = workspace
        self.plan = plan
        self.apply_service = _FakeApplyService()
        self.cleared: str | None = None

    def require_workspace(self) -> Path:
        return self.workspace

    def get_plan(self, plan_id: str) -> ChangePlan:
        assert plan_id == "plan-1"
        return self.plan

    def clear_plan(self, plan_id: str) -> None:
        self.cleared = plan_id


def _high_risk_plan(workspace: Path) -> ChangePlan:
    return ChangePlan(
        plan_type="full_file",
        workspace=workspace,
        source_path=None,
        changes=[FileChange("app.py", "app.py", "create", None, "new", size=8)],
        diff="--- /dev/null\n+++ b/app.py\n",
        metadata={
            "contents": {"app.py": b"VALUE=1\n"},
            "requires_explicit_confirmation": True,
            "recovery_severity": "high",
            "recovery_actions": [
                {"action": "python_syntax_error", "severity": "high", "target": "app.py"}
            ],
        },
    )


def test_web_apply_rejects_high_risk_plan_without_explicit_confirmation(tmp_path: Path) -> None:
    from local_ai_bridge.web.bridge_actions import dispatch_bridge_action

    state = _FakeBridgeState(tmp_path, _high_risk_plan(tmp_path))

    with pytest.raises(ValueError, match="conferma esplicita"):
        dispatch_bridge_action(
            state,
            "/api/plan/apply",
            {"plan_id": "plan-1", "confirm": "APPLY"},
            "127.0.0.1",
        )

    assert state.apply_service.confirmed is False
    assert state.cleared is None


def test_web_apply_passes_high_risk_explicit_confirmation(tmp_path: Path) -> None:
    from local_ai_bridge.web.bridge_actions import dispatch_bridge_action

    state = _FakeBridgeState(tmp_path, _high_risk_plan(tmp_path))

    payload = dispatch_bridge_action(
        state,
        "/api/plan/apply",
        {
            "plan_id": "plan-1",
            "confirm": "APPLY",
            "explicit_confirmation": "HIGH_RISK_APPLY",
        },
        "127.0.0.1",
    )

    assert state.apply_service.confirmed is True
    assert state.cleared == "plan-1"
    assert payload["session"]["session_id"] == "session"


def test_web_page_exposes_batch_project_reports_button() -> None:
    html = render_index("csrf-token", "1.2.3")

    assert "Report batch progetti" in html
    assert "createBatchProjectReports()" in html
    assert "batchReportModal" in html
    assert "Creazione report progetti" in html
    assert "/api/projects/batch-report" in html
