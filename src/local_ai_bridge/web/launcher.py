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
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(web_url(port), headers={"Accept": "text/html"})
    try:
        with opener.open(request, timeout=timeout) as response:
            # Read the whole response before closing the socket. On Windows,
            # closing immediately after the headers can abort the server write
            # and produce repeated WinError 10053 tracebacks.
            response.read()
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
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(
        web_url(port) + "api/extension/status",
        headers={"X-BridgAI-Extension-Token": token.strip()},
    )
    try:
        with opener.open(request, timeout=timeout) as response:
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


def logs_directory() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def desktop_log_path() -> Path:
    return logs_directory() / "desktop.log"


def web_log_path() -> Path:
    return logs_directory() / "web_server.log"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _subprocess_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    source_directory = str((root.expanduser().resolve() / "src").resolve())
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        source_directory
        if not existing
        else source_directory + os.pathsep + existing
    )
    return environment


def _creation_flags(show_console: bool = False) -> int:
    if sys.platform != "win32":
        return 0
    flag_name = "CREATE_NEW_CONSOLE" if show_console else "CREATE_NO_WINDOW"
    return int(getattr(subprocess, flag_name, 0))


def _python_executable(show_console: bool = False) -> str:
    executable = Path(sys.executable)
    if (
        sys.platform == "win32"
        and show_console
        and executable.name.casefold() == "pythonw.exe"
    ):
        console_executable = executable.with_name("python.exe")
        if console_executable.is_file():
            return str(console_executable)
    return str(executable)


def _web_server_command(root: Path, show_console: bool) -> list[str]:
    """Build a source-tree-safe command for the web subprocess."""
    executable = _python_executable(show_console)
    runner = root / "run.py"
    if runner.is_file():
        return [executable, str(runner), "--web-server"]
    return [executable, "-m", "local_ai_bridge.web"]


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
    show_console: bool = False,
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

    root = project_root()
    command = _web_server_command(root, show_console)
    command.extend(["--port", str(port), "--no-browser"])
    if remote_access:
        command.extend(["--host", "0.0.0.0"])
    if workspace_root is not None and str(workspace_root).strip():
        command.extend(["--workspace-root", str(Path(workspace_root).expanduser())])
    log_path = web_log_path()
    visible_console = sys.platform == "win32" and show_console
    log_stream = None if visible_console else log_path.open("ab")
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
            stdin=None if visible_console else subprocess.DEVNULL,
            stdout=None if visible_console else log_stream,
            stderr=None if visible_console else subprocess.STDOUT,
            creationflags=_creation_flags(show_console),
            cwd=str(root),
            env=environment,
        )
    finally:
        if log_stream is not None:
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



def start_windows_direct_web_server(
    port: int = 8765,
    *,
    show_console: bool = False,
    wait_seconds: float = 8.0,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
) -> WebLaunchResult:
    """Launch the repository Windows batch script and wait until the server responds."""
    url = web_url(port)
    if is_web_server_ready(port):
        return WebLaunchResult(url=url, process=None, already_running=True)
    if sys.platform != "win32":
        raise RuntimeError("L’avvio diretto tramite script è disponibile solo su Windows.")
    if int(port) != 8765:
        raise RuntimeError("Lo script di avvio diretto supporta la porta 8765.")

    script = project_root() / "web_server_force_win.bat"
    if not script.is_file():
        raise RuntimeError(f"Script server Web non trovato: {script}")
    visible_console = bool(show_console)
    log_path = web_log_path()
    log_stream = None if visible_console else log_path.open("ab")
    try:
        process = popen(
            ["cmd.exe", "/c", str(script)],
            cwd=str(project_root()),
            stdin=None if visible_console else subprocess.DEVNULL,
            stdout=None if visible_console else log_stream,
            stderr=None if visible_console else subprocess.STDOUT,
            creationflags=_creation_flags(show_console),
            env=_subprocess_environment(project_root()),
        )
    finally:
        if log_stream is not None:
            log_stream.close()
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Il server Web diretto si è chiuso durante l’avvio.")
        if is_web_server_ready(port):
            return WebLaunchResult(url=url, process=process, already_running=False)
        time.sleep(0.1)
    try:
        process.terminate()
    except OSError:
        pass
    raise RuntimeError(f"Il server Web diretto non ha risposto su {url}.")


def stop_web_interface(process: subprocess.Popen[bytes] | None, timeout: float = 2.0) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)