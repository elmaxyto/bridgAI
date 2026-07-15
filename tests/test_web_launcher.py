from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from local_ai_bridge.core.settings import SettingsStore
from local_ai_bridge.web import launcher


def test_web_settings_are_backward_compatible(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("local_ai_bridge.core.settings.app_data_dir", lambda: tmp_path)
    (tmp_path / "settings.json").write_text('{"language": "it"}', encoding="utf-8")
    settings = SettingsStore().load()
    assert settings.web_auto_start is False
    assert settings.web_open_browser is True
    assert settings.web_port == 8765
    assert settings.web_stop_on_exit is True
    assert settings.windows_show_diagnostic_consoles is False


def test_web_url_validates_port() -> None:
    assert launcher.web_url(9000) == "http://127.0.0.1:9000/"
    with pytest.raises(ValueError):
        launcher.web_url(0)


def test_existing_server_is_reused(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(launcher, "is_web_server_ready", lambda port: True)
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    result = launcher.start_web_interface(8765)
    assert result.already_running is True
    assert result.process is None
    assert opened == ["http://127.0.0.1:8765/"]


def test_server_uses_same_python_interpreter(monkeypatch) -> None:
    calls: list[tuple[list[str], dict]] = []

    class Process:
        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return Process()

    readiness = iter([False, True])
    monkeypatch.setattr(launcher, "is_web_server_ready", lambda port: next(readiness))
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: None)
    result = launcher.start_web_interface(9000, popen=fake_popen)
    assert result.already_running is False
    expected_root = launcher.project_root()
    assert calls[0][0] == [
        launcher.sys.executable,
        str(expected_root / "run.py"),
        "--web-server",
        "--port",
        "9000",
        "--no-browser",
    ]
    assert calls[0][1]["cwd"] == str(expected_root)
    assert calls[0][1]["env"]["PYTHONPATH"].split(launcher.os.pathsep)[0] == str(expected_root / "src")
    assert calls[0][1]["stdin"] is subprocess.DEVNULL
    assert calls[0][1]["stdout"] is not None
    assert calls[0][1]["stderr"] is subprocess.STDOUT


def test_server_receives_project_root_from_desktop_settings(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    class Process:
        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        calls.append(command)
        return Process()

    readiness = iter([False, True])
    monkeypatch.setattr(launcher, "is_web_server_ready", lambda port: next(readiness))
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: None)

    launcher.start_web_interface(9001, workspace_root=tmp_path, popen=fake_popen)

    assert calls[0][-2:] == ["--workspace-root", str(tmp_path)]


def test_stop_terminates_owned_process() -> None:
    events: list[str] = []

    class Process:
        def poll(self):
            return None

        def terminate(self):
            events.append("terminate")

        def wait(self, timeout):
            events.append("wait")

    launcher.stop_web_interface(Process())
    assert events == ["terminate", "wait"]


def test_project_root_points_above_src() -> None:
    root = launcher.project_root()
    assert (root / "src" / "local_ai_bridge").is_dir()


def test_visible_windows_server_uses_console_python_from_pythonw(monkeypatch, tmp_path: Path) -> None:
    pythonw = tmp_path / "pythonw.exe"
    python = tmp_path / "python.exe"
    pythonw.touch()
    python.touch()
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher.sys, "executable", str(pythonw))

    assert launcher._python_executable(show_console=True) == str(python)
    assert launcher._python_executable(show_console=False) == str(pythonw)


def test_subprocess_environment_preserves_existing_pythonpath(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYTHONPATH", "existing-path")
    environment = launcher._subprocess_environment(tmp_path)
    assert environment["PYTHONPATH"] == str(tmp_path / "src") + launcher.os.pathsep + "existing-path"


def test_remote_server_receives_binding_and_credentials(monkeypatch, tmp_path: Path) -> None:
    calls = []

    class Process:
        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return Process()

    readiness = iter([False, True])
    monkeypatch.setattr(launcher, "is_web_server_ready", lambda port: next(readiness))
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: None)
    launcher.start_web_interface(
        9002,
        workspace_root=tmp_path,
        remote_access=True,
        username="admin",
        password_hash="pbkdf2_sha256$1$c2FsdA==$ZGlnZXN0",
        popen=fake_popen,
    )
    command, kwargs = calls[0]
    assert command[-4:] == ["--host", "0.0.0.0", "--workspace-root", str(tmp_path)]
    assert kwargs["env"]["BRIDGAI_WEB_USERNAME"] == "admin"
    assert kwargs["env"]["BRIDGAI_WEB_PASSWORD_HASH"].startswith("pbkdf2_sha256$")


def test_browser_extension_status_uses_dedicated_token(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"enabled": true, "application_version": "1.0.0"}'

    captured = {}

    class FakeOpener:
        def open(self, request, timeout=None):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response()

    monkeypatch.setattr(launcher.urllib.request, "build_opener", lambda *args: FakeOpener())
    payload = launcher.browser_extension_service_status(8765, "t" * 40)
    assert payload["enabled"] is True
    assert captured["request"].get_header("X-bridgai-extension-token") == "t" * 40


def test_windows_direct_server_uses_repository_batch_and_waits_for_readiness(monkeypatch) -> None:
    calls: list[tuple[list[str], dict]] = []

    class Process:
        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return Process()

    readiness = iter([False, True])
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "is_web_server_ready", lambda port: next(readiness))
    result = launcher.start_windows_direct_web_server(8765, popen=fake_popen)

    script = launcher.project_root() / "web_server_force_win.bat"
    assert result.already_running is False
    assert calls[0][0] == ["cmd.exe", "/c", str(script)]
    assert calls[0][1]["cwd"] == str(launcher.project_root())
    assert calls[0][1]["stdin"] is subprocess.DEVNULL
    assert calls[0][1]["stdout"] is not None
    assert calls[0][1]["stderr"] is subprocess.STDOUT
    assert calls[0][1]["env"]["PYTHONPATH"].split(launcher.os.pathsep)[0] == str(
        (launcher.project_root() / "src").resolve()
    )


def test_windows_direct_server_can_open_a_diagnostic_console(monkeypatch) -> None:
    calls: list[dict] = []

    class Process:
        def poll(self):
            return None

    def fake_popen(_command, **kwargs):
        calls.append(kwargs)
        return Process()

    readiness = iter([False, True])
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher.subprocess, "CREATE_NEW_CONSOLE", 1234, raising=False)
    monkeypatch.setattr(launcher, "is_web_server_ready", lambda port: next(readiness))

    launcher.start_windows_direct_web_server(8765, show_console=True, popen=fake_popen)

    assert calls[0]["creationflags"] == 1234
    assert calls[0]["stdin"] is None
    assert calls[0]["stdout"] is None
    assert calls[0]["stderr"] is None


def test_windows_force_batch_exits_with_the_server() -> None:
    script = launcher.project_root() / "web_server_force_win.bat"
    content = script.read_text(encoding="utf-8")
    assert (
        '"%~dp0.venv\\Scripts\\python.exe" "%~dp0run.py" '
        '--web-server --port 8765'
    ) in content
    assert 'set "PYTHONPATH=%~dp0src;%PYTHONPATH%"' in content
    assert "pause" not in content.casefold()
    assert content.rstrip().endswith("exit /b %ERRORLEVEL%")


def test_readiness_probe_drains_response_before_closing(monkeypatch) -> None:
    events: list[str] = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("close")

        def read(self):
            events.append("read")
            return b"ok"

    class FakeOpener:
        def open(self, request, timeout=None):
            return Response()

    monkeypatch.setattr(
        launcher.urllib.request,
        "build_opener",
        lambda *args: FakeOpener(),
    )

    assert launcher.is_web_server_ready(8765) is True
    assert events == ["read", "close"]
