from __future__ import annotations

from pathlib import Path

from local_ai_bridge.web import launcher, server


def test_server_version_does_not_require_package_dunder_version() -> None:
    assert isinstance(server.APPLICATION_VERSION, str)
    assert server.APPLICATION_VERSION


def test_web_log_path_is_inside_app_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "app_data_dir", lambda: tmp_path)
    assert launcher.web_log_path() == tmp_path / "logs" / "web_server.log"
    assert (tmp_path / "logs").is_dir()
