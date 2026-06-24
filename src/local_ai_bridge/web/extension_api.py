from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Mapping
from urllib.parse import unquote

from local_ai_bridge.core.settings import AppSettings, SettingsStore
from local_ai_bridge.services.browser_extension import (
    claim_request,
    connection_snapshot,
    current_request,
    mark_context_ready,
    mark_extension_seen,
    mark_error,
    mark_update_ready,
    mark_waiting_result,
    mark_waiting_update,
    record_response,
)
from local_ai_bridge.services.pre_apply import build_pre_apply_summary
from local_ai_bridge.web.extension_downloads import configure_download_directory
from local_ai_bridge.web.extension_operational import (
    prepare_initial_operational_attachment,
    register_operational_result,
)
from local_ai_bridge.web.security import is_loopback_address


@dataclass(slots=True)
class ExtensionResult:
    kind: Literal["json", "artifact"]
    payload: dict[str, Any] | None = None
    artifact_id: str = ""


def authenticate_extension(
    client_ip: str,
    headers: Mapping[str, str],
    *,
    secure_transport: bool = False,
) -> AppSettings:
    settings = SettingsStore().load()
    local_client = is_loopback_address(client_ip)
    if not local_client and not settings.browser_extension_remote_access:
        raise PermissionError(
            "L’API dell’estensione remota non è abilitata per questo server."
        )
    if not local_client and not secure_transport:
        raise PermissionError(
            "L’API dell’estensione remota richiede una connessione HTTPS."
        )
    expected = settings.browser_extension_token.strip()
    supplied = str(headers.get("X-BridgAI-Extension-Token", "")).strip()
    if (
        not settings.browser_extension_enabled
        or not expected
        or not supplied
        or not secrets.compare_digest(expected, supplied)
    ):
        raise PermissionError("Estensione non abilitata o token non valido.")
    if not local_client and len(expected) < 32:
        raise PermissionError("Il token dell’estensione remota non è abbastanza robusto.")
    mark_extension_seen(str(headers.get("X-BridgAI-Extension-Version", "")))
    return settings


def dispatch_get(
    path: str,
    state,
    settings: AppSettings,
    *,
    application_version: str,
) -> ExtensionResult:
    if path == "/api/extension/status":
        snapshot = connection_snapshot()
        request = snapshot.get("request") or {}
        return ExtensionResult(
            "json",
            {
                "enabled": True,
                "application_version": application_version,
                "extension_connected": snapshot.get("connected", False),
                "request_id": request.get("request_id"),
                "request_status": request.get("message", ""),
                "auto_send": settings.browser_extension_auto_send,
                "auto_receive": settings.browser_extension_auto_receive,
                "auto_export": settings.browser_extension_auto_export,
                "auto_download": settings.browser_extension_auto_download,
                "update_directory": settings.update_zip_directory.strip(),
            },
        )
    if path == "/api/extension/next":
        request = claim_request()
        if request is not None:
            request["auto_export"] = settings.browser_extension_auto_export
            request["auto_download"] = settings.browser_extension_auto_download
            if request.get("request_kind") == "operational":
                prepare_initial_operational_attachment(state, request)
        return ExtensionResult("json", {"request": request})
    prefix = "/api/extension/artifacts/"
    if path.startswith(prefix):
        artifact_id = path[len(prefix):].strip()
        if not artifact_id or "/" in artifact_id:
            raise FileNotFoundError("File dell’estensione non trovato.")
        state.get_artifact(artifact_id)
        return ExtensionResult("artifact", artifact_id=artifact_id)
    raise FileNotFoundError("Endpoint dell’estensione non trovato.")


def dispatch_post(
    path: str,
    state,
    settings: AppSettings,
    *,
    headers: Mapping[str, str],
    read_json: Callable[[], dict[str, Any]],
    read_body: Callable[[int], bytes],
    maximum_upload_bytes: int,
) -> ExtensionResult:
    if path == "/api/extension/response":
        return ExtensionResult(
            "json",
            _handle_response(state, settings, read_json()),
        )
    if path == "/api/extension/zip":
        return ExtensionResult(
            "json",
            _handle_zip(
                state,
                settings,
                headers,
                read_body(maximum_upload_bytes),
            ),
        )
    if path == "/api/extension/download-complete":
        return ExtensionResult(
            "json",
            _handle_download_complete(state, settings, read_json()),
        )
    if path == "/api/extension/download-directory":
        return ExtensionResult(
            "json",
            configure_download_directory(settings, read_json()),
        )
    if path == "/api/extension/error":
        return ExtensionResult(
            "json",
            _handle_error(read_json()),
        )
    raise FileNotFoundError("Endpoint dell’estensione non trovato.")



def _handle_error(body: dict[str, Any]) -> dict[str, Any]:
    request_id = str(body.get("request_id", "")).strip()
    message = str(body.get("message", "")).strip()
    if not request_id:
        raise ValueError("Identificativo della richiesta dell’estensione mancante.")
    if not message:
        raise ValueError("Messaggio di errore dell’estensione mancante.")
    record = mark_error(request_id, message[:2000])
    return {
        "action": "error_recorded",
        "request_id": request_id,
        "message": str(record.get("message", "")),
    }

def _request_workspace(request_id: str) -> tuple[dict[str, Any], Path]:
    request = current_request(request_id)
    if request is None:
        raise ValueError("Richiesta dell’estensione non trovata.")
    candidate = Path(str(request.get("workspace", ""))).expanduser()
    if candidate.is_symlink():
        raise ValueError("Il workspace dell’estensione non può essere un link simbolico.")
    workspace = candidate.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("Il workspace dell’estensione non è una directory valida.")
    return request, workspace


def _handle_response(
    state,
    settings: AppSettings,
    body: dict[str, Any],
) -> dict[str, Any]:
    from local_ai_bridge.services.exporting import (
        create_export_zip,
        parse_download_requests,
    )
    from local_ai_bridge.services.temp_storage import managed_subdir

    request_id = str(body.get("request_id", "")).strip()
    text = str(body.get("text", ""))
    record_response(request_id, text)
    request, workspace = _request_workspace(request_id)
    if request.get("request_kind") == "operational":
        mark_waiting_result(request_id)
        return {
            "action": "wait_for_zip" if settings.browser_extension_auto_download else "manual",
            "files": [],
            "mission_id": str(request.get("mission_id", "")),
        }
    requested = parse_download_requests(text)
    if requested and settings.browser_extension_auto_export:
        exports = managed_subdir(settings.temp_directory, "exports")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        created = create_export_zip(
            workspace,
            requested,
            exports / f"{workspace.name}_ai_context_{stamp}.zip",
        )
        artifact = state.register_artifact(created, content_type="application/zip")
        mark_context_ready(request_id, created, requested)
        return {
            "action": "attach_context",
            "artifact_url": f"/api/extension/artifacts/{artifact.artifact_id}",
            "filename": artifact.filename,
            "files": requested,
            "followup_prompt": (
                "Ho allegato lo ZIP con i file reali richiesti. Procedi con le modifiche. "
                "Se servono altri file, richiedili nuovamente con una singola riga "
                "#scarica; altrimenti restituisci un unico ZIP applicabile da BridgAI, "
                "con la struttura relativa del progetto alla radice e commit-message.md."
            ),
        }
    if requested and not settings.browser_extension_auto_export:
        return {"action": "manual", "files": requested}
    mark_waiting_update(request_id)
    return {
        "action": "wait_for_zip" if settings.browser_extension_auto_download else "manual",
        "files": requested,
    }


def _safe_zip_name(value: str | None) -> str:
    raw = unquote(value or "bridgai_update.zip")
    name = Path(raw).name.replace("\x00", "").strip() or "bridgai_update.zip"
    if Path(name).suffix.lower() != ".zip":
        raise ValueError("È possibile caricare soltanto un file ZIP.")
    return name


def _update_directory(settings: AppSettings) -> Path:
    configured = settings.update_zip_directory.strip()
    if configured:
        return Path(configured).expanduser()
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    from local_ai_bridge.services.temp_storage import managed_subdir

    return managed_subdir(settings.temp_directory, "imports")


def _unique_update_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = directory / f"{stamp}_{filename}"
    counter = 1
    while target.exists():
        target = directory / f"{stamp}_{counter}_{filename}"
        counter += 1
    return target


def _register_update_path(
    state,
    request_id: str,
    workspace: Path,
    target: Path,
    *,
    delete_on_error: bool = False,
) -> dict[str, Any]:
    request = current_request(request_id)
    if request is None:
        raise ValueError("Richiesta dell’estensione non trovata.")
    if request.get("request_kind") == "operational":
        return register_operational_result(
            request_id,
            request,
            target,
            delete_on_error=delete_on_error,
        )

    from local_ai_bridge.services.archive import inspect_zip

    try:
        plan = inspect_zip(workspace, target)
        pre_apply = build_pre_apply_summary(plan)
    except Exception:
        if delete_on_error:
            target.unlink(missing_ok=True)
        raise
    plan_id = state.register_plan(plan)
    mark_update_ready(request_id, target, pre_apply, plan_id=plan_id)
    return {
        "action": "update_ready",
        "path": str(target),
        "plan_id": plan_id,
        "pre_apply": pre_apply,
    }


def _allowed_download_directories(settings: AppSettings) -> tuple[Path, ...]:
    directories: list[Path] = []
    configured = settings.update_zip_directory.strip()
    if configured:
        directories.append(Path(configured).expanduser().resolve(strict=False))
    downloads = (Path.home() / "Downloads").resolve(strict=False)
    if downloads not in directories:
        directories.append(downloads)
    return tuple(directories)


def _downloaded_zip_path(settings: AppSettings, raw_path: object) -> Path:
    value = str(raw_path or "").strip()
    if not value or "\x00" in value:
        raise ValueError("Chrome non ha comunicato un percorso ZIP valido.")
    supplied = Path(value).expanduser()
    if supplied.is_symlink():
        raise ValueError("Lo ZIP scaricato non può essere un link simbolico.")
    target = supplied.resolve(strict=True)
    if not target.is_file() or target.suffix.lower() != ".zip":
        raise ValueError("Il file scaricato da Chrome non è uno ZIP valido.")
    if not any(target.is_relative_to(root) for root in _allowed_download_directories(settings)):
        raise ValueError(
            "Lo ZIP scaricato è fuori dalla cartella aggiornamenti configurata o da Download."
        )
    return target


def _handle_download_complete(
    state,
    settings: AppSettings,
    body: dict[str, Any],
) -> dict[str, Any]:
    request_id = str(body.get("request_id", "")).strip()
    request, workspace = _request_workspace(request_id)
    target = _downloaded_zip_path(settings, body.get("path"))
    created_at = float(request.get("created_at") or 0.0)
    if created_at and target.stat().st_mtime < created_at - 2.0:
        raise ValueError("Lo ZIP scaricato è precedente alla richiesta corrente.")
    context_path = str(request.get("context_zip_path", "")).strip()
    if context_path and target == Path(context_path).expanduser().resolve(strict=False):
        raise ValueError("Lo ZIP scaricato coincide con il contesto inviato all’AI.")

    status = str(request.get("status", ""))
    if request.get("request_kind") == "operational":
        if status == "result_ready" and str(request.get("result_zip_path", "")) == str(target):
            return {
                "action": "result_ready",
                "path": str(target),
                "mission_id": str(request.get("mission_id", "")),
                "preview": dict(request.get("result_preview") or {}),
            }
        if status not in {"waiting_result", "result_ready"}:
            raise ValueError("La missione non è in attesa dello ZIP dei risultati.")
    else:
        if status == "update_ready" and str(request.get("update_zip_path", "")) == str(target):
            plan_id = str(request.get("plan_id", "")).strip()
            if plan_id:
                return {
                    "action": "update_ready",
                    "path": str(target),
                    "plan_id": plan_id,
                    "pre_apply": dict(request.get("pre_apply") or {}),
                }
        if status not in {"waiting_update", "update_ready"}:
            raise ValueError("La richiesta non è in attesa dello ZIP finale.")
    return _register_update_path(state, request_id, workspace, target)


def _handle_zip(
    state,
    settings: AppSettings,
    headers: Mapping[str, str],
    raw: bytes,
) -> dict[str, Any]:
    request_id = str(headers.get("X-BridgAI-Request-ID", "")).strip()
    _request, workspace = _request_workspace(request_id)
    filename = _safe_zip_name(headers.get("X-File-Name"))
    if not raw:
        raise ValueError("Lo ZIP finale ricevuto dall’estensione è vuoto.")

    target = _unique_update_path(_update_directory(settings), filename)
    target.write_bytes(raw)
    return _register_update_path(
        state,
        request_id,
        workspace,
        target,
        delete_on_error=True,
    )
