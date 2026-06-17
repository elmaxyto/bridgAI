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
    assert calls[0][0] == [launcher.sys.executable, "-m", "local_ai_bridge.web", "--port", "9000", "--no-browser"]
    expected_root = launcher.project_root()
    assert calls[0][1]["cwd"] == str(expected_root)
    assert calls[0][1]["env"]["PYTHONPATH"].split(launcher.os.pathsep)[0] == str(expected_root / "src")


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
