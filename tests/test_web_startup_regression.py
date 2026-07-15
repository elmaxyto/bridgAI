from __future__ import annotations

from pathlib import Path

import local_ai_bridge
from local_ai_bridge.web import launcher, server


def test_server_version_does_not_require_package_dunder_version(monkeypatch) -> None:
    monkeypatch.delattr(local_ai_bridge, "__version__", raising=False)

    assert isinstance(server._application_version(), str)
    assert server._application_version()


def test_server_version_prefers_source_package_version(monkeypatch) -> None:
    monkeypatch.setattr(local_ai_bridge, "__version__", "1.1.1", raising=False)
    monkeypatch.setattr(server, "version", lambda _: "1.0.0")

    assert server._application_version() == "1.1.1"


def test_web_log_path_is_inside_app_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "app_data_dir", lambda: tmp_path)
    assert launcher.web_log_path() == tmp_path / "logs" / "web_server.log"
    assert launcher.desktop_log_path() == tmp_path / "logs" / "desktop.log"
    assert launcher.logs_directory() == tmp_path / "logs"
    assert (tmp_path / "logs").is_dir()


def test_desktop_auto_start_forwards_totp_settings() -> None:
    app_source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "local_ai_bridge"
        / "app.py"
    ).read_text(encoding="utf-8")

    assert "totp_secret=(" in app_source
    assert "settings.web_totp_secret" in app_source
    assert "if settings.web_totp_enabled else None" in app_source
    assert "totp_local_bypass=settings.web_totp_local_bypass" in app_source
    assert "settings.windows_show_diagnostic_consoles" in app_source
    assert '{"show_console": True}' in app_source


def test_windows_uses_the_multi_resolution_ico_for_the_taskbar(monkeypatch) -> None:
    from local_ai_bridge import app

    monkeypatch.setattr(app.sys, "platform", "win32")
    icon = app._icon_path()

    assert icon.name == "app_icon.ico"
    assert icon.is_file()


def test_windows_launcher_defaults_to_hidden_and_keeps_diagnostic_opt_in() -> None:
    root = Path(__file__).resolve().parents[1]
    batch = (root / "start_windows.bat").read_text(encoding="utf-8")
    helper = (root / "start_windows_hidden.vbs").read_text(encoding="utf-8")
    run_source = (root / "run.py").read_text(encoding="utf-8")

    assert "wscript.exe" in batch
    assert "pythonw.exe" in batch
    assert "--windows-launch-mode" in batch
    assert "BRIDGAI_DESKTOP_LOG" in batch
    assert "shell.Run command, 0, False" in helper
    assert "windows_show_diagnostic_consoles" in run_source


def test_superpowers_payload_export_keeps_web_project_actions_importable() -> None:
    from local_ai_bridge.core import superpowers

    assert callable(superpowers.superpower_payload)



def test_windows_web_server_uses_the_source_bootstrap_entrypoint() -> None:
    root = Path(__file__).resolve().parents[1]
    run_source = (root / "run.py").read_text(encoding="utf-8")
    batch = (root / "web_server_force_win.bat").read_text(encoding="utf-8")

    assert '"--web-server" in sys.argv[1:]' in run_source
    assert 'from local_ai_bridge.web.server import main as web_main' in run_source
    assert '"%~dp0run.py" --web-server' in batch
