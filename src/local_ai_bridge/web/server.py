from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from local_ai_bridge.services.git import GitIntegrationError
from local_ai_bridge.web.network import local_ipv4_addresses
from local_ai_bridge.web.project_actions import resolve_startup_workspace_root
from local_ai_bridge.web.security import (
    AuthenticationRateLimitError,
    WebSecurityConfig,
    client_address_from_proxy,
)
from local_ai_bridge.web.server_routes import (
    MAX_JSON_BODY_BYTES,
    RouteResponse,
    dispatch_get_request,
    dispatch_post_request,
)
from local_ai_bridge.web.state import BridgeState


def _application_version() -> str:
    try:
        from local_ai_bridge import __version__ as package_version
    except ImportError:
        package_version = ""

    if isinstance(package_version, str) and package_version.strip():
        return package_version.strip()

    try:
        return version("local-ai-bridge")
    except PackageNotFoundError:
        return "development"


APPLICATION_VERSION = _application_version()


_CLIENT_DISCONNECT_WINERRORS = {10053, 10054, 10058}


def _is_client_disconnect(exc: BaseException) -> bool:
    """Return True when the peer closed the HTTP connection mid-response."""
    return isinstance(
        exc,
        (BrokenPipeError, ConnectionAbortedError, ConnectionResetError),
    ) or getattr(exc, "winerror", None) in _CLIENT_DISCONNECT_WINERRORS


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

    def _send_route_response(self, response: RouteResponse) -> None:
        if response.kind == "json":
            self._json(
                response.status,
                response.payload or {},
                extension=response.extension,
            )
            return
        if response.kind == "html":
            self._html(str(response.body))
            return
        if response.kind == "artifact":
            self._send_artifact(response.artifact_id, extension=response.extension)
            return
        if response.kind == "bytes":
            data = (
                response.body
                if isinstance(response.body, bytes)
                else str(response.body).encode("utf-8")
            )
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(data)))
            if response.security:
                self._send_security_headers()
            for key, value in response.headers:
                self.send_header(key, value)
            if response.extension:
                self._send_extension_headers()
            self.end_headers()
            self.wfile.write(data)
            return
        raise ValueError(f"Tipo risposta non supportato: {response.kind}")

    def do_OPTIONS(self) -> None:
        try:
            self._do_OPTIONS()
        except OSError as exc:
            if _is_client_disconnect(exc):
                self.close_connection = True
                return
            raise

    def _do_OPTIONS(self) -> None:
        if not urllib.parse.urlsplit(self.path).path.startswith("/api/extension/"):
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_security_headers()
        self._send_extension_headers()
        self.end_headers()

    def do_GET(self) -> None:
        try:
            self._do_GET()
        except OSError as exc:
            if _is_client_disconnect(exc):
                self.close_connection = True
                return
            raise

    def _do_GET(self) -> None:
        parsed_path = urllib.parse.urlsplit(self.path).path
        try:
            response = dispatch_get_request(
                parsed_path,
                self.server.state,
                self.server.server_address,
                self.headers,
                self._client_ip(),
                self.client_address[0],
                APPLICATION_VERSION,
            )
            self._send_route_response(response)
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
        except OSError as exc:
            if _is_client_disconnect(exc):
                raise
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"{type(exc).__name__}: {exc}"},
                extension=parsed_path.startswith("/api/extension/"),
            )
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"{type(exc).__name__}: {exc}"},
                extension=parsed_path.startswith("/api/extension/"),
            )

    def do_POST(self) -> None:
        try:
            self._do_POST()
        except OSError as exc:
            if _is_client_disconnect(exc):
                self.close_connection = True
                return
            raise

    def _do_POST(self) -> None:
        parsed_path = urllib.parse.urlsplit(self.path).path
        try:
            response = dispatch_post_request(
                parsed_path,
                self.server.state,
                self.headers,
                self._client_ip(),
                self.client_address[0],
                APPLICATION_VERSION,
                self._read_json,
                self._read_body,
            )
            self._send_route_response(response)
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
        except OSError as exc:
            if _is_client_disconnect(exc):
                raise
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"{type(exc).__name__}: {exc}"},
                extension=parsed_path.startswith("/api/extension/"),
            )
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"{type(exc).__name__}: {exc}"},
                extension=parsed_path.startswith("/api/extension/"),
            )


class BridgeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: BridgeState) -> None:
        super().__init__(address, BridgeHandler)
        self.state = state

    def handle_error(self, request: Any, client_address: tuple[str, int]) -> None:
        exc = sys.exc_info()[1]
        if exc is not None and _is_client_disconnect(exc):
            return
        super().handle_error(request, client_address)


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
        for ip in local_ipv4_addresses():
            print(f"  Rete locale: http://{ip}:{server.server_address[1]}/")
    if security.remote_mode:
        if security.requires_authentication:
            print(
                "Accesso remoto attivo: usa HTTPS tramite VPN o reverse proxy; "
                "il server integrato non cifra il traffico."
            )
        else:
            print(
                "Accesso dalla rete locale SENZA autenticazione. Tutti i dispositivi "
                "nella stessa rete possono accedere."
            )
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
    totp_local_bypass = os.environ.get(
        "BRIDGAI_WEB_TOTP_LOCAL_BYPASS", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
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
