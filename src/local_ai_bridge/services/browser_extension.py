from __future__ import annotations

import json
import os
import secrets
import time
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Iterator

from local_ai_bridge.core import settings as settings_module


STATE_VERSION = 1
LOCK_TIMEOUT_SECONDS = 2.0
STALE_LOCK_SECONDS = 30.0
CONNECTED_WINDOW_SECONDS = 75.0


def browser_extension_directory() -> Path:
    """Return the unpacked Chrome extension directory shipped with BridgAI."""
    return Path(str(files("local_ai_bridge").joinpath("resources", "chrome_extension")))


def exchange_directory() -> Path:
    path = settings_module.app_data_dir() / "browser_extension"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path() -> Path:
    return exchange_directory() / "state.json"


def _default_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "extension_last_seen_at": 0.0,
        "extension_version": "",
        "request": None,
    }


@contextmanager
def _state_lock() -> Iterator[None]:
    lock_path = exchange_directory() / "state.lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, f"{os.getpid()} {time.time()}".encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > STALE_LOCK_SECONDS:
                    lock_path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("Il canale dell’estensione è temporaneamente occupato.")
            time.sleep(0.025)
    try:
        yield
    finally:
        try:
            os.close(descriptor)
        finally:
            lock_path.unlink(missing_ok=True)


def _read_unlocked() -> dict[str, Any]:
    try:
        value = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _default_state()
    if not isinstance(value, dict):
        return _default_state()
    state = _default_state()
    state.update(value)
    if not isinstance(state.get("request"), (dict, type(None))):
        state["request"] = None
    return state


def _write_unlocked(state: dict[str, Any]) -> None:
    target = state_path()
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass


def _mutate(callback: Callable[[dict[str, Any]], Any]) -> Any:
    with _state_lock():
        state = _read_unlocked()
        result = callback(state)
        _write_unlocked(state)
        return result


def load_state() -> dict[str, Any]:
    with _state_lock():
        return _read_unlocked()


def ensure_extension_token(current: str = "") -> str:
    token = current.strip()
    if len(token) >= 32:
        return token
    return secrets.token_urlsafe(32)


def queue_request(workspace: Path, prompt: str, provider: str = "chatgpt") -> dict[str, Any]:
    resolved = workspace.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("Il workspace dell’automazione non è valido.")
    text = prompt.strip()
    if not text:
        raise ValueError("La richiesta da inviare all’estensione è vuota.")
    now = time.time()
    request = {
        "request_id": secrets.token_urlsafe(18),
        "workspace": str(resolved),
        "provider": provider.strip().lower() or "chatgpt",
        "prompt": text,
        "status": "queued",
        "message": "Richiesta pronta per l’estensione.",
        "created_at": now,
        "updated_at": now,
        "claimed_at": 0.0,
        "response_text": "",
        "context_zip_path": "",
        "context_filename": "",
        "requested_files": [],
        "update_zip_path": "",
        "plan_id": "",
        "pre_apply": {},
        "error": "",
    }

    def replace_request(state: dict[str, Any]) -> dict[str, Any]:
        state["request"] = request
        return dict(request)

    return _mutate(replace_request)


def _request_for_id(state: dict[str, Any], request_id: str) -> dict[str, Any]:
    request = state.get("request")
    if not isinstance(request, dict) or not secrets.compare_digest(
        str(request.get("request_id", "")), request_id
    ):
        raise ValueError("Richiesta dell’estensione non trovata o sostituita.")
    return request


def claim_request() -> dict[str, Any] | None:
    def claim(state: dict[str, Any]) -> dict[str, Any] | None:
        request = state.get("request")
        if not isinstance(request, dict) or request.get("status") != "queued":
            return None
        now = time.time()
        request["status"] = "sent"
        request["message"] = "Richiesta consegnata all’estensione."
        request["claimed_at"] = now
        request["updated_at"] = now
        return {
            "request_id": request["request_id"],
            "provider": request["provider"],
            "prompt": request["prompt"],
            "workspace": request["workspace"],
        }

    return _mutate(claim)


def current_request(request_id: str | None = None) -> dict[str, Any] | None:
    state = load_state()
    request = state.get("request")
    if not isinstance(request, dict):
        return None
    if request_id and not secrets.compare_digest(
        str(request.get("request_id", "")), request_id
    ):
        return None
    return dict(request)


def record_response(request_id: str, text: str) -> dict[str, Any]:
    response = text.strip()
    if not response:
        raise ValueError("La risposta ricevuta dall’estensione è vuota.")

    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["response_text"] = response
        request["status"] = "response_received"
        request["message"] = "Risposta dell’AI ricevuta."
        request["updated_at"] = time.time()
        request["error"] = ""
        return dict(request)

    return _mutate(update)


def mark_context_ready(
    request_id: str,
    path: Path,
    requested_files: list[str],
) -> dict[str, Any]:
    resolved = path.resolve(strict=True)

    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["context_zip_path"] = str(resolved)
        request["context_filename"] = resolved.name
        request["requested_files"] = list(requested_files)
        request["status"] = "context_ready"
        request["message"] = "ZIP di contesto pronto per il caricamento automatico."
        request["updated_at"] = time.time()
        return dict(request)

    return _mutate(update)


def mark_waiting_update(request_id: str) -> dict[str, Any]:
    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["status"] = "waiting_update"
        request["message"] = "In attesa dello ZIP finale dell’AI."
        request["updated_at"] = time.time()
        return dict(request)

    return _mutate(update)


def mark_update_ready(
    request_id: str,
    path: Path,
    pre_apply: dict[str, Any] | None = None,
    *,
    plan_id: str = "",
) -> dict[str, Any]:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("Lo ZIP finale dell’estensione non è valido.")

    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["update_zip_path"] = str(resolved)
        request["plan_id"] = plan_id.strip()
        request["pre_apply"] = dict(pre_apply or {})
        request["status"] = "update_ready"
        request["message"] = "Aggiornamento pronto: controlla l’anteprima e applicalo manualmente."
        request["updated_at"] = time.time()
        request["error"] = ""
        return dict(request)

    return _mutate(update)


def mark_error(request_id: str, message: str) -> dict[str, Any]:
    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["status"] = "error"
        request["error"] = message.strip() or "Errore sconosciuto dell’estensione."
        request["message"] = request["error"]
        request["updated_at"] = time.time()
        return dict(request)

    return _mutate(update)


def mark_extension_seen(extension_version: str = "") -> None:
    def update(state: dict[str, Any]) -> None:
        state["extension_last_seen_at"] = time.time()
        if extension_version.strip():
            state["extension_version"] = extension_version.strip()

    _mutate(update)


def connection_snapshot() -> dict[str, Any]:
    state = load_state()
    last_seen = float(state.get("extension_last_seen_at") or 0.0)
    request = state.get("request")
    return {
        "connected": bool(last_seen and time.time() - last_seen <= CONNECTED_WINDOW_SECONDS),
        "last_seen_at": last_seen,
        "extension_version": str(state.get("extension_version", "")),
        "request": dict(request) if isinstance(request, dict) else None,
    }
