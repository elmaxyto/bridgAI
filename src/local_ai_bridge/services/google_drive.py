from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from local_ai_bridge.services.google_drive_auth import (
    GoogleDriveAuthError,
    GoogleDriveConfigurationError,
    GoogleDriveError,
    client_secrets_path,
    disconnect_account,
    drive_service,
    google_drive_data_dir,
    google_imports,
    install_client_secrets,
    is_connected,
    token_path,
)


FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
ZIP_MIME_TYPES = {"application/zip", "application/x-zip-compressed"}
ROOT_FOLDER_NAME = "LocalAIBridge"
EXPORTS_FOLDER_NAME = "Exports"
IMPORTS_FOLDER_NAME = "Imports"


def connect_account() -> str:
    try:
        with drive_service(interactive=True) as service:
            _ensure_folders(service)
            user = service.about().get(fields="user(displayName,emailAddress)").execute().get("user", {})
            return user.get("emailAddress") or user.get("displayName") or "Account Google"
    except GoogleDriveError:
        raise
    except Exception as exc:
        raise GoogleDriveError(f"Connessione a Google Drive non riuscita: {exc}") from exc


def connected_account() -> str:
    try:
        with drive_service(interactive=False) as service:
            user = service.about().get(fields="user(displayName,emailAddress)").execute().get("user", {})
            return user.get("emailAddress") or user.get("displayName") or "Account Google"
    except GoogleDriveError:
        raise
    except Exception as exc:
        raise GoogleDriveError(f"Verifica dell'account Google Drive non riuscita: {exc}") from exc


def upload_export_zip(local_path: Path) -> str:
    try:
        local_path = local_path.expanduser().resolve(strict=True)
        if not local_path.is_file() or local_path.suffix.lower() != ".zip":
            raise GoogleDriveError("Il file da caricare non è uno ZIP valido.")
        _, _, _, _, MediaFileUpload, _ = google_imports()
        with drive_service(interactive=False) as service:
            folders = _ensure_folders(service)
            media = MediaFileUpload(
                str(local_path), mimetype="application/zip", resumable=True
            )
            result = service.files().create(
                body={"name": local_path.name, "parents": [folders[EXPORTS_FOLDER_NAME]]},
                media_body=media,
                fields="id,webViewLink",
            ).execute()
            return result.get("webViewLink") or result["id"]
    except GoogleDriveError:
        raise
    except Exception as exc:
        raise GoogleDriveError(f"Caricamento ZIP su Google Drive non riuscito: {exc}") from exc


def list_import_zips() -> list[dict[str, Any]]:
    try:
        with drive_service(interactive=False) as service:
            imports_id = _ensure_folders(service)[IMPORTS_FOLDER_NAME]
            files: list[dict[str, Any]] = []
            page_token: str | None = None
            while True:
                response = service.files().list(
                    q=f"'{_query_literal(imports_id)}' in parents and trashed = false",
                    spaces="drive",
                    orderBy="modifiedTime desc",
                    pageSize=100,
                    pageToken=page_token,
                    fields=(
                        "nextPageToken,files("
                        "id,name,mimeType,modifiedTime,size,webViewLink,parents)"
                    ),
                ).execute()
                files.extend(
                    item for item in response.get("files", [])
                    if _is_zip_metadata(item)
                )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            return files
    except GoogleDriveError:
        raise
    except Exception as exc:
        raise GoogleDriveError(f"Elenco ZIP da Google Drive non riuscito: {exc}") from exc


def download_import_zip(file_id: str, local_destination: Path) -> Path:
    if not file_id or not isinstance(file_id, str):
        raise GoogleDriveError("ID file Google Drive non valido.")

    partial: Path | None = None
    try:
        _, _, _, _, _, MediaIoBaseDownload = google_imports()
        with drive_service(interactive=False) as service:
            folders = _ensure_folders(service)
            metadata = service.files().get(
                fileId=file_id,
                fields="id,name,mimeType,parents,size",
            ).execute()
            if folders[IMPORTS_FOLDER_NAME] not in metadata.get("parents", []):
                raise GoogleDriveError("Il file richiesto non appartiene alla cartella Drive Imports.")
            if not _is_zip_metadata(metadata):
                raise GoogleDriveError("Il file Drive selezionato non è uno ZIP.")

            target = _download_target(local_destination, metadata["name"])
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            partial.unlink(missing_ok=True)
            request = service.files().get_media(fileId=file_id)
            with partial.open("wb") as stream:
                downloader = MediaIoBaseDownload(stream, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            if not zipfile.is_zipfile(partial):
                raise GoogleDriveError("Il contenuto scaricato da Drive non è un archivio ZIP valido.")
            partial.replace(target)
            return target
    except GoogleDriveError:
        if partial is not None:
            partial.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if partial is not None:
            partial.unlink(missing_ok=True)
        raise GoogleDriveError(f"Download ZIP da Google Drive non riuscito: {exc}") from exc


def _ensure_folders(service: Any) -> dict[str, str]:
    root_id = _find_or_create_folder(service, ROOT_FOLDER_NAME, "root")
    return {
        ROOT_FOLDER_NAME: root_id,
        EXPORTS_FOLDER_NAME: _find_or_create_folder(service, EXPORTS_FOLDER_NAME, root_id),
        IMPORTS_FOLDER_NAME: _find_or_create_folder(service, IMPORTS_FOLDER_NAME, root_id),
    }


def _find_or_create_folder(service: Any, name: str, parent_id: str) -> str:
    escaped_name = _query_literal(name)
    escaped_parent = _query_literal(parent_id)
    response = service.files().list(
        q=(
            f"name = '{escaped_name}' and mimeType = '{FOLDER_MIME_TYPE}' "
            f"and trashed = false and '{escaped_parent}' in parents"
        ),
        spaces="drive",
        pageSize=10,
        fields="files(id,name)",
    ).execute()
    existing = response.get("files", [])
    if existing:
        return existing[0]["id"]
    created = service.files().create(
        body={"name": name, "mimeType": FOLDER_MIME_TYPE, "parents": [parent_id]},
        fields="id",
    ).execute()
    return created["id"]


def _is_zip_metadata(metadata: dict[str, Any]) -> bool:
    name = str(metadata.get("name", ""))
    mime_type = str(metadata.get("mimeType", ""))
    return name.lower().endswith(".zip") or mime_type in ZIP_MIME_TYPES


def _download_target(destination: Path, remote_name: str) -> Path:
    safe_name = Path(remote_name).name
    if safe_name != remote_name or not safe_name.lower().endswith(".zip"):
        raise GoogleDriveError("Nome file ZIP remoto non sicuro.")
    destination = destination.expanduser()
    if destination.suffix.lower() == ".zip" and not destination.is_dir():
        return destination.resolve()
    directory = destination.resolve()
    target = directory / safe_name
    counter = 1
    while target.exists():
        target = directory / f"{Path(safe_name).stem}_{counter}.zip"
        counter += 1
    return target


def _query_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
