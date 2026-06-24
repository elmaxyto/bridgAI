from __future__ import annotations

import argparse
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from local_ai_bridge.services.git import GitIntegrationError
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
from local_ai_bridge.web.project_actions import (
    dispatch_project_action,
    project_status_payload,
    resolve_startup_workspace_root,
)
from local_ai_bridge.web.security import (
    AuthenticationRateLimitError,
    WebSecurityConfig,
    client_address_from_proxy,
    is_loopback_address,
)
from local_ai_bridge.web.state import BridgeState

MAX_JSON_BODY_BYTES = 2_000_000
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _application_version() -> str:
    try:
        return version("local-ai-bridge")
    except PackageNotFoundError:
        return "development"


APPLICATION_VERSION = _application_version()


def _safe_upload_name(value: str | None) -> str:
    raw = urllib.parse.unquote(value or "update.zip")
    name = Path(raw).name.replace("\x00", "").strip() or "update.zip"
    if Path(name).suffix.lower() != ".zip":
        raise ValueError("È possibile caricare soltanto un file ZIP.")
    return name


def _safe_markdown_upload_name(value: str | None) -> str:
    raw = urllib.parse.unquote(value or "bridgai-update.md")
    name = Path(raw).name.replace("\x00", "").strip() or "bridgai-update.md"
    if Path(name).suffix.casefold() not in {".md", ".txt"}:
        raise ValueError("È possibile caricare soltanto file .md o .txt.")
    return name


class BridgeHandler(BaseHTTPRequestHandler):
    server: "BridgeHTTPServer"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} {format % args}")

    def _client_ip(self) -> str:
        return client_address_from_proxy(
            self.client_address[0],
            self.headers.get("X-Forwarded-For"),
            self.headers.get("X-Real-IP"),
        )

    def _is_local_client(self) -> bool:
        return self._client_ip() in {"127.0.0.1", "::1"}

    def _send_security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def _send_extension_headers(self) -> None:
        origin = (self.headers.get("Origin") or "").strip()
        if origin == "https://chatgpt.com" or origin.startswith("chrome-extension://"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-BridgAI-Extension-Token, X-BridgAI-Extension-Version, "
            "X-BridgAI-Request-ID, X-File-Name",
        )
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        extension: bool = False,
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_security_headers()
        if extension:
            self._send_extension_headers()
        self.end_headers()
        self.wfile.write(data)

    def _html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._send_security_headers()
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self, maximum: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length non valido.") from exc
        if length < 0 or length > maximum:
            raise ValueError("Corpo richiesta troppo grande.")
        return self.rfile.read(length)

    def _read_json(self) -> dict[str, Any]:
        raw = self._read_body(MAX_JSON_BODY_BYTES)
        value = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(value, dict):
            raise ValueError("Il corpo JSON deve essere un oggetto.")
        return value

    def _require_api_access(self, *, write: bool = False) -> None:
        if not self.server.state.accepts_api_authorization(
            self.headers.get("Authorization"), self._client_ip()
        ):
            raise PermissionError("Autenticazione non valida, incompleta o scaduta.")
        if write and self.headers.get("X-Local-Bridge-CSRF") != self.server.state.csrf_token:
            raise PermissionError("Token CSRF non valido.")

    def _send_artifact(self, artifact_id: str, *, extension: bool = False) -> None:
        artifact = self.server.state.get_artifact(artifact_id)
        size = artifact.path.stat().st_size
        filename = artifact.filename.replace('"', "_").replace("\r", "_").replace("\n", "_")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", artifact.content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._send_security_headers()
        if extension:
            self._send_extension_headers()
        self.end_headers()
        with artifact.path.open("rb") as stream:
            while chunk := stream.read(1024 * 128):
                self.wfile.write(chunk)

    def _require_extension_access(self):
        client_ip = self._client_ip()
        direct_is_loopback = is_loopback_address(self.client_address[0])
        forwarded_proto = self.headers.get("X-Forwarded-Proto") or ""
        proxy_reports_https = (
            direct_is_loopback
            and forwarded_proto.rsplit(",", 1)[-1].strip().lower() == "https"
        )
        extension_client_ip = client_ip
        if proxy_reports_https and is_loopback_address(client_ip):
            extension_client_ip = "reverse-proxy-client"
        return authenticate_extension(
            extension_client_ip,
            self.headers,
            secure_transport=(
                is_loopback_address(extension_client_ip) or proxy_reports_https
            ),
        )

    def _send_extension_result(self, result: ExtensionResult) -> None:
        if result.kind == "artifact":
            self._send_artifact(result.artifact_id, extension=True)
            return
        self._json(HTTPStatus.OK, result.payload or {}, extension=True)

    def do_OPTIONS(self) -> None:
        if not urllib.parse.urlsplit(self.path).path.startswith("/api/extension/"):
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_security_headers()
        self._send_extension_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        parsed_path = parsed.path
        try:
            if parsed.path == "/":
                connection = connection_status_payload(
                    bind_host=str(self.server.server_address[0]),
                    port=int(self.server.server_address[1]),
                    remote_mode=self.server.state.security.remote_mode,
                    host_header=self.headers.get("Host"),
                )
                self._html(
                    render_index(
                        self.server.state.csrf_token,
                        APPLICATION_VERSION,
                        connection_address=connection["connection_address"],
                    )
                )
                return
            if parsed.path == "/favicon.svg":
                data = render_favicon_svg().encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path == "/manifest.webmanifest":
                data = render_manifest(APPLICATION_VERSION).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self._send_security_headers()
                self.end_headers()
                self.wfile.write(data)
                return

            if parsed.path.startswith("/api/extension/"):
                settings = self._require_extension_access()
                result = dispatch_extension_get(
                    parsed.path,
                    self.server.state,
                    settings,
                    application_version=APPLICATION_VERSION,
                )
                self._send_extension_result(result)
                return

            if parsed.path == "/api/auth/info":
                self._json(HTTPStatus.OK, self.server.state.auth_info(self._client_ip()))
                return

            self._require_api_access()
            if parsed.path == "/api/power-user/settings":
                self._json(
                    HTTPStatus.OK,
                    power_user_settings_payload(self.server.state),
                )
                return
            if parsed.path == "/api/status":
                payload = project_status_payload(self.server.state, APPLICATION_VERSION)
                payload.update(self.server.state.auth_info(self._client_ip()))
                payload["markdown_exchange_mode"] = bool(
                    self.server.state.settings.markdown_exchange_mode
                )
                payload["textual_file_operations_mode"] = bool(
                    self.server.state.settings.textual_file_operations_mode
                )
                payload.update(
                    connection_status_payload(
                        bind_host=str(self.server.server_address[0]),
                        port=int(self.server.server_address[1]),
                        remote_mode=self.server.state.security.remote_mode,
                        host_header=self.headers.get("Host"),
                    )
                )
                self._json(HTTPStatus.OK, payload)
                return
            if parsed.path.startswith("/api/artifacts/"):
                self._send_artifact(parsed.path.rsplit("/", 1)[-1])
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "Risorsa non trovata."})
        except PermissionError as exc:
            self._json(
                HTTPStatus.UNAUTHORIZED,
                {"error": str(exc)},
                extension=parsed_path.startswith("/api/extension/"),
            )
        except FileNotFoundError as exc:
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": str(exc)},
                extension=parsed_path.startswith("/api/extension/"),
            )
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"{type(exc).__name__}: {exc}"},
                extension=parsed_path.startswith("/api/extension/"),
            )

    def do_POST(self) -> None:
        parsed_path = urllib.parse.urlsplit(self.path).path
        try:
            if parsed_path.startswith("/api/extension/"):
                settings = self._require_extension_access()
                result = dispatch_extension_post(
                    parsed_path,
                    self.server.state,
                    settings,
                    headers=self.headers,
                    read_json=self._read_json,
                    read_body=self._read_body,
                    maximum_upload_bytes=MAX_UPLOAD_BYTES,
                )
                self._send_extension_result(result)
                return
            if parsed_path == "/api/auth/login":
                if self.headers.get("X-Local-Bridge-CSRF") != self.server.state.csrf_token:
                    raise PermissionError("Token CSRF non valido.")
                body = self._read_json()
                session = self.server.state.create_auth_session(
                    self.headers.get("Authorization"),
                    str(body.get("second_factor", "")),
                    self._client_ip(),
                )
                self._json(
                    HTTPStatus.OK,
                    {
                        "session_token": session.token,
                        "expires_in": int(session.expires_at - time.monotonic()),
                        "second_factor": session.second_factor,
                    },
                )
                return
            if parsed_path == "/api/auth/logout":
                if self.headers.get("X-Local-Bridge-CSRF") != self.server.state.csrf_token:
                    raise PermissionError("Token CSRF non valido.")
                self.server.state.revoke_auth_session(self.headers.get("Authorization"))
                self._json(HTTPStatus.OK, {"message": "Sessione terminata."})
                return

            self._require_api_access(write=True)
            if parsed_path == "/api/zip/upload":
                payload = self._upload_zip()
            elif parsed_path == "/api/markdown/upload":
                payload = self._upload_markdown_update()
            else:
                payload = self._dispatch(parsed_path, self._read_json())
            self._json(HTTPStatus.OK, payload)
        except AuthenticationRateLimitError as exc:
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": str(exc)})
        except PermissionError as exc:
            self._json(
                HTTPStatus.FORBIDDEN,
                {"error": str(exc)},
                extension=parsed_path.startswith("/api/extension/"),
            )
        except (ValueError, FileNotFoundError, GitIntegrationError) as exc:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": str(exc)},
                extension=parsed_path.startswith("/api/extension/"),
            )
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"{type(exc).__name__}: {exc}"},
                extension=parsed_path.startswith("/api/extension/"),
            )

    def _upload_zip(self) -> dict[str, Any]:
        state = self.server.state
        workspace = state.require_workspace()
        filename = _safe_upload_name(self.headers.get("X-File-Name"))
        raw = self._read_body(MAX_UPLOAD_BYTES)
        if not raw:
            raise ValueError("Il file ZIP è vuoto.")
        from local_ai_bridge.services.archive import inspect_zip
        from local_ai_bridge.services.temp_storage import managed_subdir

        imports = managed_subdir(state.settings.temp_directory, "imports")
        target = imports / f"{secrets.token_hex(8)}_{filename}"
        target.write_bytes(raw)
        try:
            plan = inspect_zip(workspace, target)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        plan_id = state.register_plan(plan)
        from local_ai_bridge.web.bridge_actions import _plan_payload
        return _plan_payload(state, plan_id)

    def _upload_markdown_update(self) -> dict[str, Any]:
        state = self.server.state
        workspace = state.require_workspace()
        if not state.settings.textual_file_operations_mode:
            raise ValueError(
                "Il formato aggiornamenti attivo è ZIP. Seleziona File Markdown nelle impostazioni."
            )
        _safe_markdown_upload_name(self.headers.get("X-File-Name"))
        raw = self._read_body(MAX_UPLOAD_BYTES)
        if not raw:
            raise ValueError("Il file Markdown di aggiornamento è vuoto.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "Il file Markdown di aggiornamento non è codificato in UTF-8."
            ) from exc
        if not text.strip():
            raise ValueError("Il file Markdown di aggiornamento è vuoto.")

        from local_ai_bridge.services.text_file_operations import (
            inspect_text_file_operations,
        )

        plan = inspect_text_file_operations(workspace, text)
        plan_id = state.register_plan(plan)
        from local_ai_bridge.web.bridge_actions import _plan_payload
        return _plan_payload(state, plan_id)

    def _dispatch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        state = self.server.state
        project_payload = dispatch_project_action(state, path, body)
        if project_payload is not None:
            return project_payload

        if path == "/api/restart":
            def perform_restart():
                import time
                import os
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
            return {"message": "Riavvio in corso..."}

        automation_payload = dispatch_browser_automation_action(state, path, body)
        if automation_payload is not None:
            return automation_payload

        if path == "/api/power-user/settings":
            return update_power_user_settings(state, body)

        from local_ai_bridge.web.bridge_actions import dispatch_bridge_action
        payload = dispatch_bridge_action(state, path, body, self._client_ip())
        if payload is not None:
            return payload

        raise ValueError("Endpoint non supportato.")


class BridgeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: BridgeState) -> None:
        super().__init__(address, BridgeHandler)
        self.state = state


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    *,
    auth_token: str | None = None,
    username: str | None = None,
    password_hash: str | None = None,
    totp_secret: str | None = None,
    totp_local_bypass: bool = False,
    workspace_root: str | Path | None = None,
    workspace: str | Path | None = None,
) -> None:
    effective_root, explicit_root = resolve_startup_workspace_root(workspace_root, workspace)

    security = WebSecurityConfig.build(
        host=host,
        auth_token=auth_token,
        username=username,
        password_hash=password_hash,
        totp_secret=totp_secret,
        totp_local_bypass=totp_local_bypass,
        workspace_root=effective_root,
        fixed_workspace=workspace,
    )
    state = BridgeState(
        security=security,
        initial_workspace=workspace,
        workspace_root_locked=explicit_root or workspace is not None,
    )
    server = BridgeHTTPServer((host, port), state)
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{browser_host}:{server.server_address[1]}/"
    print(f"BridgAI Web {APPLICATION_VERSION}: {url}")
    if host in {"0.0.0.0", "::"} or security.remote_mode:
        from local_ai_bridge.web.network import local_ipv4_addresses
        for ip in local_ipv4_addresses():
            print(f"  Rete locale: http://{ip}:{server.server_address[1]}/")
    if security.remote_mode:
        if security.requires_authentication:
            print("Accesso remoto attivo: usa HTTPS tramite VPN o reverse proxy; il server integrato non cifra il traffico.")
        else:
            print("Accesso dalla rete locale SENZA autenticazione. Tutti i dispositivi nella stessa rete possono accedere.")
    print("Interrompi con Ctrl+C.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pannello web mobile-first di BridgAI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--workspace-root", help="Directory che contiene i workspace autorizzati")
    parser.add_argument("--workspace", help="Workspace unico autorizzato")
    parser.add_argument(
        "--token-env",
        default="BRIDGAI_WEB_TOKEN",
        help="Nome della variabile d'ambiente contenente il token (default: BRIDGAI_WEB_TOKEN)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = os.environ.get(args.token_env)
    username = os.environ.get("BRIDGAI_WEB_USERNAME")
    password_hash = os.environ.get("BRIDGAI_WEB_PASSWORD_HASH")
    totp_secret = os.environ.get("BRIDGAI_WEB_TOTP_SECRET")
    totp_local_bypass = os.environ.get("BRIDGAI_WEB_TOTP_LOCAL_BYPASS", "").strip().lower() in {
        "1", "true", "yes", "on"
    }
    workspace_root = args.workspace_root or os.environ.get("BRIDGAI_WORKSPACE_ROOT")
    serve(
        args.host,
        args.port,
        not args.no_browser,
        auth_token=token,
        username=username,
        password_hash=password_hash,
        totp_secret=totp_secret,
        totp_local_bypass=totp_local_bypass,
        workspace_root=workspace_root,
        workspace=args.workspace,
    )
    return 0
