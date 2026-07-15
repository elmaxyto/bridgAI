from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Callable, Mapping

from local_ai_bridge.web.browser_automation import dispatch_browser_automation_action
from local_ai_bridge.web.extension_api import (
    ExtensionResult,
    authenticate_extension,
    dispatch_get as dispatch_extension_get,
    dispatch_post as dispatch_extension_post,
)
from local_ai_bridge.web.network import connection_status_payload
from local_ai_bridge.web.page import render_favicon_svg, render_index, render_manifest
from local_ai_bridge.web.power_user_settings import (
    power_user_settings_payload,
    update_power_user_settings,
)
from local_ai_bridge.web.project_actions import dispatch_project_action, project_status_payload
from local_ai_bridge.web.security import is_loopback_address
from local_ai_bridge.web.server_uploads import (
    MAX_UPLOAD_BYTES,
    upload_markdown_update,
    upload_zip_update,
)
from local_ai_bridge.web.state import BridgeState

MAX_JSON_BODY_BYTES = 2_000_000


@dataclass(frozen=True, slots=True)
class RouteResponse:
    kind: str
    status: int = HTTPStatus.OK
    payload: dict[str, Any] | None = None
    body: str | bytes = b""
    content_type: str = ""
    headers: tuple[tuple[str, str], ...] = ()
    artifact_id: str = ""
    extension: bool = False
    security: bool = True


def json_response(
    payload: dict[str, Any],
    status: int = HTTPStatus.OK,
    *,
    extension: bool = False,
) -> RouteResponse:
    return RouteResponse("json", status=status, payload=payload, extension=extension)


def html_response(body: str) -> RouteResponse:
    return RouteResponse("html", body=body)


def bytes_response(
    data: bytes,
    content_type: str,
    *,
    status: int = HTTPStatus.OK,
    headers: tuple[tuple[str, str], ...] = (),
    extension: bool = False,
    security: bool = True,
) -> RouteResponse:
    return RouteResponse(
        "bytes",
        status=status,
        body=data,
        content_type=content_type,
        headers=headers,
        extension=extension,
        security=security,
    )


def artifact_response(artifact_id: str, *, extension: bool = False) -> RouteResponse:
    return RouteResponse("artifact", artifact_id=artifact_id, extension=extension)


def _require_api_access(
    state: BridgeState,
    headers: Mapping[str, str],
    client_ip: str,
    *,
    write: bool = False,
) -> None:
    if not state.accepts_api_authorization(headers.get("Authorization"), client_ip):
        raise PermissionError("Autenticazione non valida, incompleta o scaduta.")
    if write and headers.get("X-Local-Bridge-CSRF") != state.csrf_token:
        raise PermissionError("Token CSRF non valido.")


def _extension_settings_for_request(
    headers: Mapping[str, str],
    client_ip: str,
    direct_client_ip: str,
):
    direct_is_loopback = is_loopback_address(direct_client_ip)
    forwarded_proto = headers.get("X-Forwarded-Proto") or ""
    proxy_reports_https = (
        direct_is_loopback
        and forwarded_proto.rsplit(",", 1)[-1].strip().lower() == "https"
    )
    extension_client_ip = client_ip
    if proxy_reports_https and is_loopback_address(client_ip):
        extension_client_ip = "reverse-proxy-client"
    return authenticate_extension(
        extension_client_ip,
        headers,
        secure_transport=(
            is_loopback_address(extension_client_ip) or proxy_reports_https
        ),
    )


def _extension_response(result: ExtensionResult) -> RouteResponse:
    if result.kind == "artifact":
        return artifact_response(result.artifact_id, extension=True)
    return json_response(result.payload or {}, extension=True)


def _connection_payload(
    state: BridgeState,
    server_address: tuple[str, int],
    host_header: str | None,
) -> dict[str, Any]:
    return connection_status_payload(
        bind_host=str(server_address[0]),
        port=int(server_address[1]),
        remote_mode=state.security.remote_mode,
        host_header=host_header,
    )


def _status_payload(
    state: BridgeState,
    server_address: tuple[str, int],
    host_header: str | None,
    client_ip: str,
    application_version: str,
) -> dict[str, Any]:
    payload = project_status_payload(state, application_version)
    payload.update(state.auth_info(client_ip))
    payload["markdown_exchange_mode"] = bool(state.settings.markdown_exchange_mode)
    payload["preferred_web_ai"] = state.settings.preferred_web_ai
    payload["textual_file_operations_mode"] = bool(
        state.settings.textual_file_operations_mode
    )
    payload.update(_connection_payload(state, server_address, host_header))
    return payload


def dispatch_get_request(
    path: str,
    state: BridgeState,
    server_address: tuple[str, int],
    headers: Mapping[str, str],
    client_ip: str,
    direct_client_ip: str,
    application_version: str,
) -> RouteResponse:
    if path == "/":
        connection = _connection_payload(state, server_address, headers.get("Host"))
        return html_response(
            render_index(
                state.csrf_token,
                application_version,
                connection_address=connection["connection_address"],
            )
        )
    if path == "/favicon.svg":
        return bytes_response(
            render_favicon_svg().encode("utf-8"),
            "image/svg+xml; charset=utf-8",
            headers=(
                ("Cache-Control", "public, max-age=86400"),
                ("X-Content-Type-Options", "nosniff"),
            ),
            security=False,
        )
    if path == "/manifest.webmanifest":
        return bytes_response(
            render_manifest(application_version).encode("utf-8"),
            "application/manifest+json; charset=utf-8",
        )

    if path.startswith("/api/extension/"):
        settings = _extension_settings_for_request(headers, client_ip, direct_client_ip)
        result = dispatch_extension_get(
            path,
            state,
            settings,
            application_version=application_version,
        )
        return _extension_response(result)

    if path == "/api/auth/info":
        return json_response(state.auth_info(client_ip))

    _require_api_access(state, headers, client_ip)
    if path == "/api/power-user/settings":
        return json_response(power_user_settings_payload(state))
    if path == "/api/superpowers/list":
        payload = dispatch_project_action(state, path, {})
        return json_response(payload or {"items": []})
    if path == "/api/status":
        return json_response(
            _status_payload(
                state,
                server_address,
                headers.get("Host"),
                client_ip,
                application_version,
            )
        )
    if path.startswith("/api/artifacts/"):
        return artifact_response(path.rsplit("/", 1)[-1])
    return json_response({"error": "Risorsa non trovata."}, status=HTTPStatus.NOT_FOUND)


def dispatch_post_request(
    path: str,
    state: BridgeState,
    headers: Mapping[str, str],
    client_ip: str,
    direct_client_ip: str,
    application_version: str,
    read_json: Callable[[], dict[str, Any]],
    read_body: Callable[[int], bytes],
) -> RouteResponse:
    if path.startswith("/api/extension/"):
        settings = _extension_settings_for_request(headers, client_ip, direct_client_ip)
        result = dispatch_extension_post(
            path,
            state,
            settings,
            headers=headers,
            read_json=read_json,
            read_body=read_body,
            maximum_upload_bytes=MAX_UPLOAD_BYTES,
        )
        return _extension_response(result)
    if path == "/api/auth/login":
        if headers.get("X-Local-Bridge-CSRF") != state.csrf_token:
            raise PermissionError("Token CSRF non valido.")
        body = read_json()
        session = state.create_auth_session(
            headers.get("Authorization"),
            str(body.get("second_factor", "")),
            client_ip,
        )
        return json_response(
            {
                "session_token": session.token,
                "expires_in": int(session.expires_at - time.monotonic()),
                "second_factor": session.second_factor,
            }
        )
    if path == "/api/auth/logout":
        if headers.get("X-Local-Bridge-CSRF") != state.csrf_token:
            raise PermissionError("Token CSRF non valido.")
        state.revoke_auth_session(headers.get("Authorization"))
        return json_response({"message": "Sessione terminata."})

    _require_api_access(state, headers, client_ip, write=True)
    if path == "/api/zip/upload":
        return json_response(
            upload_zip_update(state, headers.get("X-File-Name"), read_body)
        )
    if path == "/api/markdown/upload":
        return json_response(
            upload_markdown_update(state, headers.get("X-File-Name"), read_body)
        )
    return json_response(dispatch_web_action(state, path, read_json(), client_ip))


def dispatch_web_action(
    state: BridgeState,
    path: str,
    body: dict[str, Any],
    client_ip: str,
) -> dict[str, Any]:
    project_payload = dispatch_project_action(state, path, body)
    if project_payload is not None:
        return project_payload

    if path == "/api/restart":
        _restart_process_async()
        return {"message": "Riavvio in corso..."}

    automation_payload = dispatch_browser_automation_action(state, path, body)
    if automation_payload is not None:
        return automation_payload

    if path == "/api/power-user/settings":
        return update_power_user_settings(state, body)

    from local_ai_bridge.web.bridge_actions import dispatch_bridge_action

    payload = dispatch_bridge_action(state, path, body, client_ip)
    if payload is not None:
        return payload

    raise ValueError("Endpoint non supportato.")


def _restart_process_async() -> None:
    def perform_restart() -> None:
        from local_ai_bridge.services.system import build_restart_command

        time.sleep(0.5)
        try:
            cmd = build_restart_command()
            os.chdir(cmd.working_directory)
            os.execv(cmd.program, [cmd.program] + cmd.arguments)
        except Exception as exc:
            print(f"Errore durante il riavvio: {exc}", flush=True)
            os._exit(1)

    threading.Thread(target=perform_restart, daemon=True).start()
