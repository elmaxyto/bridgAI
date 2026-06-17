from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from local_ai_bridge.services import google_drive, google_drive_auth


def test_token_path_is_isolated_in_app_data_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(google_drive_auth.core_settings, "app_data_dir", lambda: tmp_path)

    assert google_drive.token_path() == tmp_path / "google_drive" / "token.json"
    assert google_drive.client_secrets_path() == tmp_path / "google_drive" / "credentials.json"
    assert google_drive.token_path().parent.is_dir()


def test_offline_drive_failure_is_translated_without_unhandled_error(monkeypatch) -> None:
    class OfflineRequest:
        def execute(self):
            raise OSError("network unavailable")

    class OfflineFiles:
        def list(self, **_kwargs):
            return OfflineRequest()

    class OfflineService:
        def files(self):
            return OfflineFiles()

    @contextmanager
    def offline_service(interactive: bool):
        assert interactive is False
        yield OfflineService()

    monkeypatch.setattr(google_drive, "drive_service", offline_service)

    with pytest.raises(google_drive.GoogleDriveError, match="Elenco ZIP"):
        google_drive.list_import_zips()
