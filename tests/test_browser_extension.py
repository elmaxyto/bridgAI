from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace

from local_ai_bridge.core import settings as settings_module
from local_ai_bridge.services import browser_extension
from local_ai_bridge.ui import browser_extension_actions
from local_ai_bridge.web import browser_automation


def _use_temp_exchange(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings_module, "app_data_dir", lambda: tmp_path)


def test_extension_token_is_stable_when_already_strong() -> None:
    token = "x" * 40
    assert browser_extension.ensure_extension_token(token) == token
    assert len(browser_extension.ensure_extension_token("")) >= 32


def test_browser_provider_normalization_is_explicit_and_backward_compatible() -> None:
    assert browser_extension.normalize_web_ai_provider("chatgpt") == "chatgpt"
    assert browser_extension.normalize_web_ai_provider("CLAUDE") == "claude"
    assert browser_extension.normalize_web_ai_provider("gemini") == "gemini"
    assert browser_extension.normalize_web_ai_provider("custom") == "chatgpt"
    assert browser_extension.normalize_web_ai_provider("") == "chatgpt"
    assert browser_extension.web_ai_provider_url("chatgpt") == "https://chatgpt.com/"
    assert browser_extension.web_ai_provider_url("claude") == "https://claude.ai/new"
    assert browser_extension.web_ai_provider_url("gemini") == "https://gemini.google.com/app"
    try:
        browser_extension.normalize_web_ai_provider("unexpected-provider")
    except ValueError as exc:
        assert "non supportato" in str(exc)
    else:
        raise AssertionError("Un provider sconosciuto deve essere rifiutato.")


def test_extension_request_lifecycle(tmp_path: Path, monkeypatch) -> None:
    _use_temp_exchange(monkeypatch, tmp_path / "data")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = tmp_path / "context.zip"
    context.write_bytes(b"context")
    update = tmp_path / "update.zip"
    update.write_bytes(b"update")

    queued = browser_extension.queue_request(workspace, "Build the feature")
    assert queued["status"] == "queued"

    claimed = browser_extension.claim_request()
    assert claimed is not None
    assert claimed["request_id"] == queued["request_id"]
    assert browser_extension.claim_request() is None

    received = browser_extension.record_response(
        queued["request_id"],
        "#scarica src/example.py",
    )
    assert received["status"] == "response_received"
    assert received["response_received_at"] >= received["created_at"]

    context_ready = browser_extension.mark_context_ready(
        queued["request_id"],
        context,
        ["src/example.py"],
    )
    assert context_ready["status"] == "context_ready"
    assert context_ready["requested_files"] == ["src/example.py"]

    waiting = browser_extension.mark_waiting_update(queued["request_id"])
    assert waiting["status"] == "waiting_update"

    ready = browser_extension.mark_update_ready(
        queued["request_id"],
        update,
        {"total": 1},
        plan_id="plan-1",
    )
    assert ready["status"] == "update_ready"
    assert ready["update_zip_path"] == str(update.resolve())
    assert ready["pre_apply"] == {"total": 1}
    assert ready["plan_id"] == "plan-1"

    failed = browser_extension.mark_error(
        queued["request_id"],
        "ChatGPT upload failed",
    )
    assert failed["status"] == "error"
    assert failed["error"] == "ChatGPT upload failed"


def test_extension_connection_snapshot_uses_recent_heartbeat(tmp_path: Path, monkeypatch) -> None:
    _use_temp_exchange(monkeypatch, tmp_path / "data")
    assert browser_extension.connection_snapshot()["connected"] is False
    browser_extension.mark_extension_seen("0.1.0", "claude,gemini")
    snapshot = browser_extension.connection_snapshot()
    assert snapshot["connected"] is True
    assert snapshot["extension_version"] == "0.1.0"
    assert snapshot["extension_providers"] == ["claude", "gemini"]


def test_stale_chatgpt_only_extension_cannot_claim_other_provider(
    tmp_path: Path, monkeypatch
) -> None:
    _use_temp_exchange(monkeypatch, tmp_path / "data")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    queued = browser_extension.queue_request(workspace, "task", provider="claude")

    try:
        browser_extension.claim_request(["chatgpt"])
    except ValueError as exc:
        assert "Claude" in str(exc)
        assert "chrome://extensions" in str(exc)
    else:
        raise AssertionError("Un’estensione ChatGPT-only non deve ricevere richieste Claude.")

    current = browser_extension.current_request(queued["request_id"])
    assert current is not None
    assert current["status"] == "queued"
    claimed = browser_extension.claim_request(["chatgpt", "claude", "gemini"])
    assert claimed is not None
    assert claimed["provider"] == "claude"


def test_chrome_extension_resources_are_shipped() -> None:
    directory = browser_extension.browser_extension_directory()
    assert (directory / "manifest.json").is_file()
    assert (directory / "background.js").is_file()
    assert (directory / "content.js").is_file()
    assert (directory / "providers.js").is_file()
    assert (directory / "download_tracking.js").is_file()


def test_extension_local_bridge_fetches_run_in_service_worker() -> None:
    directory = browser_extension.browser_extension_directory()
    background = (directory / "background.js").read_text(encoding="utf-8")
    content = (directory / "content.js").read_text(encoding="utf-8")
    providers = (directory / "providers.js").read_text(encoding="utf-8")
    downloads = (directory / "download_tracking.js").read_text(encoding="utf-8")
    options = (directory / "options.js").read_text(encoding="utf-8")

    assert 'message?.type === "BRIDGAI_VERIFY"' in background
    assert "artifactBase64" in background
    assert "request.initial_attachment" in background
    assert 'type: "BRIDGAI_ATTACH_CONTEXT"' in background
    assert 'type: "BRIDGAI_VERIFY"' in options
    assert "fetch(`http://127.0.0.1:" not in options
    assert "fetch(message.artifactUrl" not in content
    assert "base64Bytes(message.artifactBase64)" in content
    assert "waitForZipTarget" in content
    assert 'bridgeResult?.action === "wait_for_zip"' in content
    assert "target.element.click()" in content
    assert "hasZipSignature" in background
    assert "filenameFromContentDisposition" in background
    assert "fallback_download" in background
    assert "click_link" in background
    assert 'importScripts("providers.js", "download_tracking.js")' in background
    assert '"X-BridgAI-Extension-Providers"' in background
    assert "async function providerTab(providerValue)" in background
    assert "function tabBelongsToProvider(tab, provider)" in background
    assert "async function activateProviderTab(tab, provider)" in background
    assert "chrome.tabs.update(tab.id, { active: true })" in background
    assert "chrome.windows.update(activated.windowId, { focused: true }).catch" in background
    assert "const readyTab = await chrome.tabs.get(tab.id)" in background
    assert "request.provider" in background
    assert 'files: ["providers.js", "content.js"]' in background
    assert 'claude: Object.freeze({' in providers
    assert 'gemini: Object.freeze({' in providers
    assert "function requireKnown(value)" in providers
    assert "function trustedDownloadUrlFor(providerValue, value)" in providers
    assert "streamingSelectors" in providers
    assert "trustedDownloadUrlFor(providerId, message.url)" in background
    assert "FAST_POLL_INTERVAL_MS = 1000" in background
    assert "MIN_POLL_DEBOUNCE_MS = 400" in background
    assert "now - lastPollTime < MIN_POLL_DEBOUNCE_MS" in background
    assert "setInterval(poll, FAST_POLL_INTERVAL_MS)" in background
    assert "chrome.tabs.onActivated.addListener(() => poll())" in background
    assert "if (info.status === \"complete\") poll();" in background
    assert "globalThis.__bridgAIContentScriptLoaded" in content
    assert "RESPONSE_STABLE_CYCLES = 5" in content
    assert "stableCycles < RESPONSE_STABLE_CYCLES" in content
    assert "providerApi.fromLocation(window.location)" in content
    assert 'message?.type === "BRIDGAI_EXPECT_ZIP_DOWNLOAD"' in background
    assert 'type: "BRIDGAI_EXPECT_ZIP_DOWNLOAD"' in content
    assert '"/api/extension/download-complete"' in downloads
    assert '"result_ready"' in downloads
    assert "chrome.downloads.onCreated" in downloads
    assert "chrome.downloads.onChanged" in downloads
    assert "chrome.downloads.onDeterminingFilename" in downloads
    assert '"/api/extension/download-directory"' in background
    assert '"/api/extension/error"' in background
    assert 'type: "BRIDGAI_AUTOMATION_ERROR"' in content
    assert "waitForAttachmentReady" in content
    assert "watchPassiveDownloadDirective" in content
    assert "submitAssistantResponse" in content
    assert "handleBridgeResponseAction" in content
    assert "CONTENT_HEARTBEAT_MS = 1000" in content
    assert "passiveDirectiveWatchRunning" in content
    assert "finally(() => {" in content
    assert "document.visibilityState !== \"visible\"" in content
    assert "trustedDownloadSource" in downloads
    assert "BridgAIWebAIProviders.trustedDownloadUrl" in downloads
    workflow = (
        directory.parents[1] / "ui" / "workflow_actions.py"
    ).read_text(encoding="utf-8")
    assert "if self.settings.markdown_exchange_mode" in workflow
    assert "or self.settings.textual_file_operations_mode" not in workflow
    assert "startedAfterExpectation" in downloads
    assert "downloadSubdirectory" in background
    assert "bridgai-download-directory-${Date.now()}" in background
    assert ".bridgai-download-directory-${Date.now()}" not in background
    assert "downloadFilename(current, message.filename)" in background
    assert "normalizedBridgeUrl" in background
    assert "chrome.permissions.request" in options
    assert "downloadSubdirectory" in options
    assert "serverUrl" in options


def test_chrome_extension_manifest_version_is_updated() -> None:
    import json

    directory = browser_extension.browser_extension_directory()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.6.5"
    assert manifest["optional_host_permissions"] == ["https://*/*"]
    matches = manifest["content_scripts"][0]["matches"]
    assert matches == [
        "https://chatgpt.com/*",
        "https://claude.ai/*",
        "https://gemini.google.com/*",
    ]
    assert manifest["content_scripts"][0]["js"] == ["providers.js", "content.js"]


def test_response_watcher_requires_complete_download_directive_and_handles_reused_nodes() -> None:
    directory = browser_extension.browser_extension_directory()
    content = (directory / "content.js").read_text(encoding="utf-8")

    assert "function assistantResponseBaseline()" in content
    assert "function isNewAssistantResponse(messages, baseline)" in content
    assert "latest !== baseline.latest" in content
    assert "text !== baseline.text" in content
    assert "function downloadRequestDirective(text)" in content
    assert r"/^#scarica\s*:?[ \t]+(.+?)\s*$/i" in content
    assert r"/^#{1,6}\s+(#scarica\b)/i" in content
    assert r"""/^['"`*_\s]+|['"`*_\s]+$/g""" in content
    assert "requireDownloadRequest && !downloadRequestDirective(text)" in content
    assert "watchResponse(requestId, baseline, requireDownloadRequest)" in content
    assert "sendPrompt(message.requestId, message.followupPrompt, false)" in content


class _RecordedWidget:
    def __init__(self) -> None:
        self.text = ""
        self.enabled = False
        self.tooltip = ""

    def setText(self, value: str) -> None:
        self.text = value

    def setEnabled(self, value: bool) -> None:
        self.enabled = value

    def setToolTip(self, value: str) -> None:
        self.tooltip = value


def test_update_ready_notifies_once_and_keeps_apply_manual(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    update = tmp_path / "update.zip"
    update.write_bytes(b"update")
    request = {
        "request_id": "request-1",
        "workspace": str(workspace),
        "status": "update_ready",
        "response_text": "",
        "update_zip_path": str(update),
    }
    monkeypatch.setattr(browser_extension_actions, "_", lambda text: text)
    monkeypatch.setattr(
        browser_extension_actions,
        "connection_snapshot",
        lambda: {"request": dict(request)},
    )
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        browser_extension_actions,
        "QMessageBox",
        SimpleNamespace(
            information=lambda _parent, title, message: messages.append((title, message))
        ),
    )

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = SimpleNamespace(
        browser_extension_enabled=True,
        browser_extension_auto_receive=False,
        browser_extension_auto_download=False,
    )
    window.workspace = workspace
    window._browser_extension_seen_response_id = ""
    window._browser_extension_seen_update_path = ""
    window.zip_path_edit = _RecordedWidget()
    window.simple_apply_zip_button = _RecordedWidget()
    statuses: list[str] = []
    window._show_status = statuses.append

    window.poll_browser_extension()
    window.poll_browser_extension()

    assert window.zip_path_edit.text == str(update)
    assert window.simple_apply_zip_button.enabled is True
    assert "Applica" in window.simple_apply_zip_button.text
    assert "Shift" in window.simple_apply_zip_button.text
    assert "manuale" in window.simple_apply_zip_button.tooltip
    assert "Shift" in window.simple_apply_zip_button.tooltip
    assert len(messages) == 1
    assert "Applica" in messages[0][0]
    assert "manuale" in messages[0][1]
    assert len(statuses) == 1


def test_apply_update_button_advertises_shift_click_manual_selection() -> None:
    directory = browser_extension.browser_extension_directory()
    ui_root = directory.parents[1] / "ui"
    workflow = (ui_root / "tabs" / "workflow.py").read_text(encoding="utf-8")
    change_actions = (ui_root / "change_actions.py").read_text(encoding="utf-8")

    assert "Applica aggiornamento · Shift: scegli ZIP" in workflow
    assert "refresh_apply_zip_button_hint()" in workflow
    assert "QApplication.keyboardModifiers() & Qt.ShiftModifier" in change_actions
    assert "self.choose_zip()" in change_actions
    assert "Shift+clic" in change_actions


def test_manual_download_adoption_ignores_zip_before_response_time(
    tmp_path: Path,
) -> None:
    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = SimpleNamespace(update_zip_directory=str(tmp_path))
    old_zip = tmp_path / "old.zip"
    old_zip.write_bytes(b"old")

    now = time.time()
    os.utime(old_zip, (now - 60.0, now - 60.0))
    request = {
        "created_at": now - 120.0,
        "response_received_at": now,
        "context_zip_path": "",
    }

    assert window._find_downloaded_extension_zip(request) is None

    fresh_zip = tmp_path / "fresh.zip"
    fresh_zip.write_bytes(b"fresh")
    os.utime(fresh_zip, (now + 1.0, now + 1.0))

    assert window._find_downloaded_extension_zip(request) == fresh_zip



def test_disabling_browser_extension_restores_standard_download_directory() -> None:
    class Store:
        def __init__(self) -> None:
            self.saved = None

        def save(self, settings) -> None:
            self.saved = settings

        def load(self):
            return self.saved

    class Widget:
        def __init__(self) -> None:
            self.text = "configured"

        def setText(self, value: str) -> None:
            self.text = value

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        def refresh_browser_extension_settings(self) -> None:
            pass

    window = Window()
    window.settings = SimpleNamespace(
        browser_extension_enabled=True,
        browser_extension_token="token",
        update_zip_directory="C:/Downloads/BridgAI",
    )
    window.settings_store = Store()
    window.update_zip_directory_edit = Widget()
    window.settings_update_zip_directory_edit = Widget()
    messages = []
    window._show_status = messages.append

    window.set_browser_extension_enabled(False)

    assert window.settings.browser_extension_enabled is False
    assert window.settings.update_zip_directory == ""
    assert window.update_zip_directory_edit.text == ""
    assert window.settings_update_zip_directory_edit.text == ""
    assert window.settings_store.saved is window.settings
    assert messages


def test_windows_extension_server_button_starts_force_script(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "web_server_force_win.bat"
    script.write_text("@echo off\n", encoding="utf-8")
    launched: list[str] = []

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        def __init__(self) -> None:
            self.statuses: list[str] = []

        def _show_status(self, message: str) -> None:
            self.statuses.append(message)

    monkeypatch.setattr(browser_extension_actions.sys, "platform", "win32")
    monkeypatch.setattr(browser_extension_actions, "project_root", lambda: tmp_path)
    monkeypatch.setattr(browser_extension_actions.os, "startfile", launched.append, raising=False)

    window = Window()
    window.start_browser_extension_web_server()

    assert launched == [str(script)]
    assert window.statuses
    assert "Windows" in window.statuses[-1]


def _extension_window_settings() -> SimpleNamespace:
    return SimpleNamespace(
        browser_extension_enabled=True,
        browser_extension_auto_send=True,
        browser_extension_token="t" * 40,
        preferred_web_ai="chatgpt",
        gemini_drive_enabled=False,
        markdown_exchange_mode=False,
        web_port=8765,
        web_workspace_root="",
        web_remote_access=False,
        web_username="",
        web_password_hash="",
        web_totp_enabled=False,
        web_totp_secret="",
        web_totp_local_bypass=False,
    )


def test_queue_report_uses_selected_web_ai_provider(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured: dict[str, object] = {}

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window.settings.preferred_web_ai = "claude"
    window.settings.markdown_exchange_mode = False
    window.workspace = workspace
    window.simple_apply_zip_button = _RecordedWidget()
    window._show_status = lambda _message: None
    window.ensure_browser_extension_service = lambda silent=False: True

    def queue(workspace_arg, report_arg, **kwargs):
        captured.update(workspace=workspace_arg, report=report_arg, **kwargs)
        return {"request_id": "request-claude"}

    monkeypatch.setattr(browser_extension_actions, "queue_request", queue)

    assert window.queue_report_with_browser_extension("report") is True
    assert captured["provider"] == "claude"
    assert captured["workspace"] == workspace


def test_web_queue_uses_persisted_preferred_web_ai_provider(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured: dict[str, object] = {}

    state = SimpleNamespace(
        settings=SimpleNamespace(
            browser_extension_enabled=True,
            preferred_web_ai="chatgpt",
        ),
        require_workspace=lambda: workspace,
    )
    monkeypatch.setattr(browser_automation, "current_request", lambda: None)
    monkeypatch.setattr(
        browser_automation,
        "SettingsStore",
        lambda: SimpleNamespace(
            load=lambda: SimpleNamespace(preferred_web_ai="gemini")
        ),
    )

    def queue(workspace_arg, report_arg, **kwargs):
        captured.update(workspace=workspace_arg, report=report_arg, **kwargs)
        return {"request_id": "request-gemini", "status": "queued"}

    monkeypatch.setattr(browser_automation, "queue_request", queue)

    payload = browser_automation.dispatch_browser_automation_action(
        state,
        "/api/browser-automation/queue",
        {"report": "report"},
    )

    assert payload is not None
    assert payload["provider"] == "gemini"
    assert captured["provider"] == "gemini"
    assert "Gemini" in payload["message"]


def test_queue_report_starts_service_before_publishing_request(tmp_path: Path, monkeypatch) -> None:
    events: list[str] = []
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window.workspace = workspace
    window.simple_apply_zip_button = _RecordedWidget()
    window._show_status = lambda message: events.append(f"status:{message}")
    window.ensure_browser_extension_service = lambda silent=False: events.append("ensure") or True

    monkeypatch.setattr(
        browser_extension_actions,
        "connection_snapshot",
        lambda: {"connected": True, "last_seen_at": browser_extension_actions.time.time()},
    )
    monkeypatch.setattr(
        browser_extension_actions,
        "queue_request",
        lambda *_args, **_kwargs: events.append("queue") or {"request_id": "request-1"},
    )

    assert window.queue_report_with_browser_extension("report") is True
    assert events[:2] == ["ensure", "queue"]


def test_queue_report_wakes_provider_when_extension_is_not_recently_seen(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    opened: list[str] = []

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window.settings.preferred_web_ai = "claude"
    window.workspace = workspace
    window.simple_apply_zip_button = _RecordedWidget()
    window._show_status = lambda _message: None
    window.ensure_browser_extension_service = lambda silent=False: True

    monkeypatch.setattr(
        browser_extension_actions,
        "connection_snapshot",
        lambda: {"connected": False},
    )
    monkeypatch.setattr(
        browser_extension_actions,
        "queue_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(
        browser_extension_actions.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    assert window.queue_report_with_browser_extension("report") is True
    assert opened == ["https://claude.ai/new"]


def test_queue_report_wakes_provider_when_previous_heartbeat_is_stale(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    opened: list[str] = []

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window.workspace = workspace
    window.simple_apply_zip_button = _RecordedWidget()
    window._show_status = lambda _message: None
    window.ensure_browser_extension_service = lambda silent=False: True

    monkeypatch.setattr(browser_extension_actions.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        browser_extension_actions,
        "connection_snapshot",
        lambda: {"connected": True, "last_seen_at": 90.0},
    )
    monkeypatch.setattr(
        browser_extension_actions,
        "queue_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(
        browser_extension_actions.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    assert window.queue_report_with_browser_extension("report") is True
    assert opened == ["https://chatgpt.com/"]


def test_queue_report_does_not_open_extra_provider_tab_when_extension_is_connected(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    opened: list[str] = []

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window.workspace = workspace
    window.simple_apply_zip_button = _RecordedWidget()
    window._show_status = lambda _message: None
    window.ensure_browser_extension_service = lambda silent=False: True

    monkeypatch.setattr(
        browser_extension_actions,
        "connection_snapshot",
        lambda: {"connected": True, "last_seen_at": browser_extension_actions.time.time()},
    )
    monkeypatch.setattr(
        browser_extension_actions,
        "queue_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(
        browser_extension_actions.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    assert window.queue_report_with_browser_extension("report") is True
    assert opened == []


def test_queue_report_is_not_published_when_service_cannot_start(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    queued: list[str] = []

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window.workspace = workspace
    window._show_status = lambda _message: None
    window.ensure_browser_extension_service = lambda silent=False: False
    monkeypatch.setattr(
        browser_extension_actions,
        "queue_request",
        lambda *_args, **_kwargs: queued.append("queue") or {"request_id": "request-1"},
    )

    assert window.queue_report_with_browser_extension("report") is False
    assert queued == []


def test_ensure_extension_service_checks_endpoint_then_starts_and_rechecks(monkeypatch) -> None:
    events: list[str] = []
    checks = iter([RuntimeError("offline"), {"enabled": True}])
    process = object()

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window._show_status = lambda _message: None

    def status(*_args, **_kwargs):
        events.append("status")
        result = next(checks)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(browser_extension_actions, "browser_extension_service_status", status)
    monkeypatch.setattr(
        browser_extension_actions,
        "start_web_interface",
        lambda *_args, **_kwargs: events.append("start") or SimpleNamespace(process=process),
    )

    assert window.ensure_browser_extension_service(silent=True) is True
    assert events == ["status", "start", "status"]
    assert window.web_process is process


def test_ensure_extension_service_uses_direct_windows_script_before_recheck(monkeypatch) -> None:
    events: list[str] = []
    checks = iter([RuntimeError("offline"), {"enabled": True}])
    process = object()

    class Window(browser_extension_actions.BrowserExtensionActionsMixin):
        pass

    window = Window()
    window.settings = _extension_window_settings()
    window.settings.web_port = 8765
    window._show_status = lambda _message: None

    def status(*_args, **_kwargs):
        events.append("status")
        result = next(checks)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(browser_extension_actions.sys, "platform", "win32")
    monkeypatch.setattr(browser_extension_actions, "browser_extension_service_status", status)
    monkeypatch.setattr(
        browser_extension_actions,
        "start_windows_direct_web_server",
        lambda *_args, **_kwargs: events.append("direct") or SimpleNamespace(process=process),
    )
    monkeypatch.setattr(
        browser_extension_actions,
        "start_web_interface",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("fallback not expected")),
    )

    assert window.ensure_browser_extension_service(silent=True) is True
    assert events == ["status", "direct", "status"]
    assert window.web_process is process
