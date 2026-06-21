from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import Callable

from local_ai_bridge.core.settings import app_data_dir


@dataclass(slots=True)
class WebLaunchResult:
    url: str
    process: subprocess.Popen[bytes] | None
    already_running: bool


def web_url(port: int) -> str:
    if not 1 <= int(port) <= 65535:
        raise ValueError("La porta web deve essere compresa tra 1 e 65535.")
    return f"http://127.0.0.1:{int(port)}/"


def is_web_server_ready(port: int, timeout: float = 0.35) -> bool:
    request = urllib.request.Request(web_url(port), headers={"Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False



def browser_extension_service_status(
    port: int,
    token: str,
    timeout: float = 0.75,
) -> dict[str, object]:
    if not token.strip():
        raise ValueError("Token dell’estensione mancante.")
    request = urllib.request.Request(
        web_url(port) + "api/extension/status",
        headers={"X-BridgAI-Extension-Token": token.strip()},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            message = str(payload.get("error", ""))
        except Exception:
            message = ""
        raise RuntimeError(message or f"Servizio estensione HTTP {exc.code}.") from exc
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise RuntimeError("Il servizio locale dell’estensione non è raggiungibile.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Risposta non valida dal servizio dell’estensione.")
    return payload


def web_log_path() -> Path:
    path = app_data_dir() / "logs" / "web_server.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _subprocess_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    source_directory = str(root / "src")
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        source_directory
        if not existing
        else source_directory + os.pathsep + existing
    )
    return environment


def _creation_flags() -> int:
    if sys.platform == "win32":
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return 0


def _add_authentication_environment(
    environment: dict[str, str],
    *,
    username: str | None,
    password_hash: str | None,
    totp_secret: str | None,
    totp_local_bypass: bool,
) -> None:
    # Authentication must also be available while the integrated server is
    # bound to loopback behind an HTTPS reverse proxy such as Nginx.
    if not username or not password_hash:
        return
    environment["BRIDGAI_WEB_USERNAME"] = username
    environment["BRIDGAI_WEB_PASSWORD_HASH"] = password_hash
    if totp_secret:
        environment["BRIDGAI_WEB_TOTP_SECRET"] = totp_secret
        environment["BRIDGAI_WEB_TOTP_LOCAL_BYPASS"] = (
            "1" if totp_local_bypass else "0"
        )


def start_web_interface(
    port: int = 8765,
    *,
    open_browser: bool = True,
    workspace_root: str | Path | None = None,
    remote_access: bool = False,
    username: str | None = None,
    password_hash: str | None = None,
    totp_secret: str | None = None,
    totp_local_bypass: bool = False,
    wait_seconds: float = 5.0,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
) -> WebLaunchResult:
    url = web_url(port)
    if is_web_server_ready(port):
        if remote_access:
            raise RuntimeError(
                f"Un server web è già attivo sulla porta {port}. "
                "Fermalo prima di avviarne uno nuovo con accesso dalla rete."
            )
        if open_browser:
            webbrowser.open(url)
        return WebLaunchResult(url=url, process=None, already_running=True)

    command = [
        sys.executable,
        "-m",
        "local_ai_bridge.web",
        "--port",
        str(port),
        "--no-browser",
    ]
    if remote_access:
        command.extend(["--host", "0.0.0.0"])
    if workspace_root is not None and str(workspace_root).strip():
        command.extend(["--workspace-root", str(Path(workspace_root).expanduser())])
    root = project_root()
    log_path = web_log_path()
    log_stream = log_path.open("ab")
    environment = _subprocess_environment(root)
    _add_authentication_environment(
        environment,
        username=username,
        password_hash=password_hash,
        totp_secret=totp_secret,
        totp_local_bypass=totp_local_bypass,
    )
    try:
        process = popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            creationflags=_creation_flags(),
            cwd=str(root),
            env=environment,
        )
    finally:
        log_stream.close()

    deadline = time.monotonic() + max(0.0, wait_seconds)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Il server web locale si è chiuso durante l'avvio. Dettagli: {log_path}")
        if is_web_server_ready(port):
            if open_browser:
                webbrowser.open(url)
            return WebLaunchResult(url=url, process=process, already_running=False)
        time.sleep(0.1)

    try:
        process.terminate()
    except OSError:
        pass
    raise RuntimeError(f"Il server web locale non ha risposto su {url}. Dettagli: {log_path}")


def stop_web_interface(process: subprocess.Popen[bytes] | None, timeout: float = 2.0) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)
