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
REQUEST_DEVELOPMENT = "development"
REQUEST_OPERATIONAL = "operational"
SUPPORTED_WEB_AI_PROVIDERS = ("chatgpt", "claude", "gemini")
_PROVIDER_LABELS = {
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "gemini": "Gemini",
}
_PROVIDER_URLS = {
    "chatgpt": "https://chatgpt.com/",
    "claude": "https://claude.ai/new",
    "gemini": "https://gemini.google.com/app",
}


def normalize_web_ai_provider(value: object) -> str:
    """Return the provider supported by the browser extension.

    ``custom`` and an empty legacy value keep the historical ChatGPT behavior.
    Other unknown identifiers are rejected instead of opening an unexpected site.
    """
    provider = str(value or "").strip().lower()
    if provider in {"", "custom"}:
        return "chatgpt"
    if provider not in SUPPORTED_WEB_AI_PROVIDERS:
        raise ValueError(
            f"Provider AI Web non supportato dall’estensione: {provider}."
        )
    return provider


def web_ai_provider_label(value: object) -> str:
    """Return the display label for a normalized browser provider."""
    return _PROVIDER_LABELS[normalize_web_ai_provider(value)]


def web_ai_provider_url(value: object) -> str:
    """Return the canonical web URL used to wake a supported provider tab."""
    return _PROVIDER_URLS[normalize_web_ai_provider(value)]


def normalize_extension_providers(value: object) -> tuple[str, ...]:
    """Return the providers explicitly advertised by a browser extension.

    Extensions predating provider negotiation are treated as ChatGPT-only so a
    stale service worker cannot silently receive Claude or Gemini requests.
    """
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, (list, tuple, set, frozenset)):
        raw_values = value
    else:
        raw_values = ()
    normalized: list[str] = []
    for item in raw_values:
        provider = str(item or "").strip().lower()
        if provider in SUPPORTED_WEB_AI_PROVIDERS and provider not in normalized:
            normalized.append(provider)
    return tuple(normalized or ("chatgpt",))


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
        "extension_providers": ["chatgpt"],
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
    state["extension_providers"] = list(
        normalize_extension_providers(state.get("extension_providers"))
    )
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
    """Queue the existing development workflow without changing its contract."""
    return _queue(
        workspace,
        prompt,
        provider=provider,
        request_kind=REQUEST_DEVELOPMENT,
    )


def queue_operational_request(
    request_workspace: Path,
    prompt: str,
    *,
    mission_id: str,
    context_zip: Path,
    provider: str = "chatgpt",
) -> dict[str, Any]:
    context = context_zip.expanduser()
    if context.is_symlink():
        raise ValueError("Il pacchetto della missione non può essere un link simbolico.")
    context = context.resolve(strict=True)
    if not context.is_file() or context.suffix.casefold() != ".zip":
        raise ValueError("Il pacchetto della missione non è uno ZIP valido.")
    clean_mission_id = mission_id.strip()
    if len(clean_mission_id) != 32 or any(
        character not in "0123456789abcdef" for character in clean_mission_id
    ):
        raise ValueError("L’identificativo della missione operativa non è valido.")
    return _queue(
        request_workspace,
        prompt,
        provider=provider,
        request_kind=REQUEST_OPERATIONAL,
        mission_id=clean_mission_id,
        context_zip=context,
    )


def _queue(
    workspace: Path,
    prompt: str,
    *,
    provider: str,
    request_kind: str,
    mission_id: str = "",
    context_zip: Path | None = None,
) -> dict[str, Any]:
    resolved = workspace.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("Il workspace dell’automazione non è valido.")
    text = prompt.strip()
    if not text:
        raise ValueError("La richiesta da inviare all’estensione è vuota.")
    if request_kind not in {REQUEST_DEVELOPMENT, REQUEST_OPERATIONAL}:
        raise ValueError("Tipo di richiesta dell’estensione non supportato.")
    now = time.time()
    request = {
        "request_id": secrets.token_urlsafe(18),
        "request_kind": request_kind,
        "mission_id": mission_id,
        "workspace": str(resolved),
        "provider": normalize_web_ai_provider(provider),
        "prompt": text,
        "status": "queued",
        "message": (
            "Missione pronta per l’estensione."
            if request_kind == REQUEST_OPERATIONAL
            else "Richiesta pronta per l’estensione."
        ),
        "created_at": now,
        "updated_at": now,
        "claimed_at": 0.0,
        "response_text": "",
        "response_received_at": 0.0,
        "context_zip_path": str(context_zip) if context_zip else "",
        "context_filename": context_zip.name if context_zip else "",
        "requested_files": [],
        "update_zip_path": "",
        "result_zip_path": "",
        "result_preview": {},
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


def claim_request(supported_providers: object | None = None) -> dict[str, Any] | None:
    supported = (
        None
        if supported_providers is None
        else set(normalize_extension_providers(supported_providers))
    )

    def claim(state: dict[str, Any]) -> dict[str, Any] | None:
        request = state.get("request")
        if not isinstance(request, dict) or request.get("status") != "queued":
            return None
        provider = normalize_web_ai_provider(request.get("provider"))
        if supported is not None and provider not in supported:
            raise ValueError(
                f"L’estensione Chrome collegata non supporta {web_ai_provider_label(provider)}. "
                "Ricarica l’estensione dalla pagina chrome://extensions e riprova."
            )
        now = time.time()
        request["status"] = "sent"
        request["message"] = (
            "Missione consegnata all’estensione."
            if request.get("request_kind") == REQUEST_OPERATIONAL
            else "Richiesta consegnata all’estensione."
        )
        request["claimed_at"] = now
        request["updated_at"] = now
        return {
            "request_id": request["request_id"],
            "request_kind": request.get("request_kind", REQUEST_DEVELOPMENT),
            "mission_id": request.get("mission_id", ""),
            "provider": request["provider"],
            "prompt": request["prompt"],
            "workspace": request["workspace"],
            "context_zip_path": request.get("context_zip_path", ""),
            "context_filename": request.get("context_filename", ""),
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
        now = time.time()
        request["response_text"] = response
        request["response_received_at"] = now
        request["status"] = "response_received"
        request["message"] = "Risposta dell’AI ricevuta."
        request["updated_at"] = now
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


def mark_waiting_result(request_id: str) -> dict[str, Any]:
    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["status"] = "waiting_result"
        request["message"] = "In attesa dello ZIP dei risultati dell’AI."
        request["updated_at"] = time.time()
        return dict(request)

    return _mutate(update)


def mark_text_update_ready(
    request_id: str,
    pre_apply: dict[str, Any] | None = None,
    *,
    plan_id: str,
) -> dict[str, Any]:
    clean_plan_id = plan_id.strip()
    if not clean_plan_id:
        raise ValueError("Il piano dell’aggiornamento testuale è mancante.")

    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["update_zip_path"] = ""
        request["plan_id"] = clean_plan_id
        request["pre_apply"] = dict(pre_apply or {})
        request["status"] = "update_ready"
        request["message"] = (
            "Aggiornamento testuale pronto: controlla l’anteprima e applicalo manualmente."
        )
        request["updated_at"] = time.time()
        request["error"] = ""
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


def mark_result_ready(
    request_id: str,
    path: Path,
    preview: dict[str, Any],
) -> dict[str, Any]:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("Lo ZIP dei risultati non è valido.")

    def update(state: dict[str, Any]) -> dict[str, Any]:
        request = _request_for_id(state, request_id)
        request["result_zip_path"] = str(resolved)
        request["result_preview"] = dict(preview)
        request["status"] = "result_ready"
        request["message"] = "Risultati pronti: controllali e importali nella cartella autorizzata."
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


def mark_extension_seen(
    extension_version: str = "",
    supported_providers: object = (),
) -> None:
    providers = normalize_extension_providers(supported_providers)

    def update(state: dict[str, Any]) -> None:
        state["extension_last_seen_at"] = time.time()
        state["extension_providers"] = list(providers)
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
        "extension_providers": list(
            normalize_extension_providers(state.get("extension_providers"))
        ),
        "request": dict(request) if isinstance(request, dict) else None,
    }
