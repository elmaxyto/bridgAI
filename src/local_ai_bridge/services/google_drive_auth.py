from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from local_ai_bridge.core import settings as core_settings


SCOPES = ("https://www.googleapis.com/auth/drive",)


class GoogleDriveError(RuntimeError):
    """Base error exposed to the UI for controlled Drive failures."""


class GoogleDriveConfigurationError(GoogleDriveError):
    """The local OAuth client configuration is missing or invalid."""


class GoogleDriveAuthError(GoogleDriveError):
    """The stored authorization cannot be used."""


def google_drive_data_dir() -> Path:
    path = core_settings.app_data_dir() / "google_drive"
    path.mkdir(parents=True, exist_ok=True)
    return path


def token_path() -> Path:
    return google_drive_data_dir() / "token.json"


def client_secrets_path() -> Path:
    return google_drive_data_dir() / "credentials.json"


def is_connected() -> bool:
    return token_path().is_file()


def install_client_secrets(source: Path) -> Path:
    try:
        source = source.expanduser().resolve(strict=True)
        payload = json.loads(source.read_text(encoding="utf-8"))
        installed = payload["installed"]
        required = {"client_id", "client_secret", "auth_uri", "token_uri"}
        if not required.issubset(installed):
            raise KeyError("campi OAuth mancanti")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise GoogleDriveConfigurationError(
            "Il file selezionato non è una credenziale OAuth per applicazione desktop valida."
        ) from exc

    destination = client_secrets_path()
    temporary = destination.with_suffix(".tmp")
    shutil.copyfile(source, temporary)
    _restrict_file_permissions(temporary)
    temporary.replace(destination)
    return destination


def disconnect_account() -> None:
    try:
        token_path().unlink(missing_ok=True)
    except OSError as exc:
        raise GoogleDriveError(f"Impossibile eliminare il token Google Drive: {exc}") from exc


@contextmanager
def drive_service(interactive: bool) -> Iterator[Any]:
    _, _, _, build, _, _ = google_imports()
    credentials = _load_credentials(interactive=interactive)
    try:
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        raise GoogleDriveError(f"Impossibile inizializzare il client Google Drive: {exc}") from exc
    try:
        yield service
    finally:
        close = getattr(service, "close", None)
        if callable(close):
            close()


def google_imports() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    except ImportError as exc:
        raise GoogleDriveConfigurationError(
            "Dipendenze Google Drive mancanti. Reinstalla i requisiti dell'applicazione."
        ) from exc
    return Request, Credentials, InstalledAppFlow, build, MediaFileUpload, MediaIoBaseDownload


def _load_credentials(interactive: bool) -> Any:
    Request, Credentials, InstalledAppFlow, _, _, _ = google_imports()
    credentials = None
    stored_token = token_path()
    if stored_token.is_file():
        try:
            credentials = Credentials.from_authorized_user_file(str(stored_token), SCOPES)
        except (OSError, ValueError) as exc:
            raise GoogleDriveAuthError(
                "Il token Google Drive salvato non è valido. Scollega e riconnetti l'account."
            ) from exc

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _save_token(credentials)
        except Exception as exc:
            raise GoogleDriveAuthError(
                "Il token Google Drive non può essere aggiornato. Verifica la rete o riconnetti l'account."
            ) from exc

    if credentials and credentials.valid:
        return credentials
    if not interactive:
        raise GoogleDriveAuthError("Account Google Drive non connesso.")

    secrets = client_secrets_path()
    if not secrets.is_file():
        raise GoogleDriveConfigurationError(
            "Credenziali OAuth mancanti. Seleziona il file credentials.json di un client Desktop."
        )
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
        credentials = flow.run_local_server(port=0, open_browser=True)
        _save_token(credentials)
        return credentials
    except Exception as exc:
        raise GoogleDriveAuthError(f"Autorizzazione OAuth non riuscita: {exc}") from exc


def _save_token(credentials: Any) -> None:
    destination = token_path()
    temporary = destination.with_suffix(".tmp")
    try:
        temporary.write_text(credentials.to_json(), encoding="utf-8")
        _restrict_file_permissions(temporary)
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise GoogleDriveError(f"Impossibile salvare il token Google Drive: {exc}") from exc


def _restrict_file_permissions(path: Path) -> None:
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError:
            pass
