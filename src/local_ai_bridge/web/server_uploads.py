from __future__ import annotations

import secrets
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from local_ai_bridge.web.state import BridgeState

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


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


def upload_zip_update(
    state: BridgeState,
    filename_header: str | None,
    read_body: Callable[[int], bytes],
) -> dict[str, Any]:
    workspace = state.require_workspace()
    filename = _safe_upload_name(filename_header)
    raw = read_body(MAX_UPLOAD_BYTES)
    if not raw:
        raise ValueError("Il file ZIP è vuoto.")

    from local_ai_bridge.services.archive import inspect_zip
    from local_ai_bridge.services.temp_storage import managed_subdir
    from local_ai_bridge.web.bridge_actions import _plan_payload

    imports = managed_subdir(state.settings.temp_directory, "imports")
    target = imports / f"{secrets.token_hex(8)}_{filename}"
    target.write_bytes(raw)
    try:
        plan = inspect_zip(workspace, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    plan_id = state.register_plan(plan)
    return _plan_payload(state, plan_id)


def upload_markdown_update(
    state: BridgeState,
    filename_header: str | None,
    read_body: Callable[[int], bytes],
) -> dict[str, Any]:
    workspace = state.require_workspace()
    if not state.settings.textual_file_operations_mode:
        raise ValueError(
            "Il formato aggiornamenti attivo è ZIP. Seleziona File Markdown nelle impostazioni."
        )
    filename = _safe_markdown_upload_name(filename_header)
    raw = read_body(MAX_UPLOAD_BYTES)
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

    from local_ai_bridge.services.temp_storage import managed_subdir
    from local_ai_bridge.services.text_update_import import inspect_text_update_response
    from local_ai_bridge.web.bridge_actions import _plan_payload

    imports = managed_subdir(state.settings.temp_directory, "imports")
    target = imports / f"{secrets.token_hex(8)}_{filename}"
    target.write_bytes(raw)
    try:
        plan = inspect_text_update_response(
            workspace,
            text,
            preferred="text_file_operations",
        )
    except Exception:
        target.unlink(missing_ok=True)
        raise
    plan.source_path = target
    plan_id = state.register_plan(plan)
    return _plan_payload(state, plan_id)
