from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from local_ai_bridge.core import settings as settings_module
from local_ai_bridge.services import browser_extension
from local_ai_bridge.ui import browser_extension_actions


def _use_temp_exchange(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings_module, "app_data_dir", lambda: tmp_path)


def test_extension_token_is_stable_when_already_strong() -> None:
    token = "x" * 40
    assert browser_extension.ensure_extension_token(token) == token
    assert len(browser_extension.ensure_extension_token("")) >= 32


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
    browser_extension.mark_extension_seen("0.1.0")
    snapshot = browser_extension.connection_snapshot()
    assert snapshot["connected"] is True
    assert snapshot["extension_version"] == "0.1.0"


def test_chrome_extension_resources_are_shipped() -> None:
    directory = browser_extension.browser_extension_directory()
    assert (directory / "manifest.json").is_file()
    assert (directory / "background.js").is_file()
    assert (directory / "content.js").is_file()
    assert (directory / "download_tracking.js").is_file()


def test_extension_local_bridge_fetches_run_in_service_worker() -> None:
    directory = browser_extension.browser_extension_directory()
    background = (directory / "background.js").read_text(encoding="utf-8")
    content = (directory / "content.js").read_text(encoding="utf-8")
    downloads = (directory / "download_tracking.js").read_text(encoding="utf-8")
    options = (directory / "options.js").read_text(encoding="utf-8")

    assert 'message?.type === "BRIDGAI_VERIFY"' in background
    assert "artifactBase64" in background
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
    assert 'importScripts("download_tracking.js")' in background
    assert 'message?.type === "BRIDGAI_EXPECT_ZIP_DOWNLOAD"' in background
    assert 'type: "BRIDGAI_EXPECT_ZIP_DOWNLOAD"' in content
    assert '"/api/extension/download-complete"' in downloads
    assert "chrome.downloads.onCreated" in downloads
    assert "chrome.downloads.onChanged" in downloads
    assert "chrome.downloads.onDeterminingFilename" in downloads
    assert '"/api/extension/download-directory"' in background
    assert '"/api/extension/error"' in background
    assert 'type: "BRIDGAI_AUTOMATION_ERROR"' in content
    assert "waitForAttachmentReady" in content
    assert "trustedDownloadSource" in downloads
    assert "startedAfterExpectation" in downloads
    assert "downloadSubdirectory" in background
    assert "downloadFilename(current, message.filename)" in background
    assert "normalizedBridgeUrl" in background
    assert "chrome.permissions.request" in options
    assert "downloadSubdirectory" in options
    assert "serverUrl" in options


def test_chrome_extension_manifest_version_is_updated() -> None:
    import json

    directory = browser_extension.browser_extension_directory()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.5.0"
    assert manifest["optional_host_permissions"] == ["https://*/*"]


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
    assert "manuale" in window.simple_apply_zip_button.tooltip
    assert len(messages) == 1
    assert "Applica" in messages[0][0]
    assert "manuale" in messages[0][1]
    assert len(statuses) == 1



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
