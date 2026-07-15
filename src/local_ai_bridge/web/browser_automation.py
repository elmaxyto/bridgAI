from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from local_ai_bridge.core.settings import SettingsStore
from local_ai_bridge.services.browser_extension import (
    connection_snapshot,
    current_request,
    ensure_extension_token,
    normalize_web_ai_provider,
    queue_request,
    web_ai_provider_label,
)
from local_ai_bridge.services.pre_apply import build_pre_apply_summary


def _plan_payload(state, plan_id: str) -> dict[str, Any]:
    plan = state.get_plan(plan_id)
    return {
        "plan_id": plan_id,
        "plan_type": plan.plan_type,
        "changes": [asdict(change) for change in plan.changes],
        "warnings": plan.warnings,
        "diff": plan.diff,
        "commit_message": plan.metadata.get("commit_message"),
        "pre_apply": build_pre_apply_summary(plan),
    }


_ACTIVE_REQUEST_STATUSES = {
    "queued",
    "sent",
    "response_received",
    "context_ready",
    "waiting_update",
}


def _request_matches_workspace(state, request: dict[str, Any]) -> bool:
    try:
        current = state.require_workspace().expanduser().resolve(strict=True)
        requested = (
            Path(str(request.get("workspace", "")))
            .expanduser()
            .resolve(strict=True)
        )
    except (OSError, ValueError):
        return False
    return current == requested


def _status_payload(state) -> dict[str, Any]:
    snapshot = connection_snapshot()
    request = snapshot.get("request") or {}
    request_matches = bool(request) and _request_matches_workspace(state, request)
    request_status = str(request.get("status", "")) if request else ""
    request_busy = request_status in _ACTIVE_REQUEST_STATUSES
    payload: dict[str, Any] = {
        "enabled": bool(state.settings.browser_extension_enabled),
        "remote_access": bool(state.settings.browser_extension_remote_access),
        "token_configured": bool(state.settings.browser_extension_token.strip()),
        "connected": bool(snapshot.get("connected")),
        "extension_version": str(snapshot.get("extension_version", "")),
        "busy": request_busy,
        "request": {
            "request_id": request.get("request_id"),
            "status": request_status if request_matches else "other_workspace",
            "message": (
                request.get("message", "")
                if request_matches
                else "L’ultima automazione appartiene a un altro progetto."
            ),
            "error": request.get("error", "") if request_matches else "",
            "updated_at": request.get("updated_at", 0.0),
            "provider": request.get("provider", "chatgpt"),
        }
        if request
        else None,
    }
    plan_id = (
        str(request.get("plan_id", "")).strip()
        if request and request_matches
        else ""
    )
    if state.settings.browser_extension_enabled and plan_id:
        try:
            payload["plan"] = _plan_payload(state, plan_id)
        except ValueError:
            payload["plan"] = None
    return payload


def dispatch_browser_automation_action(
    state,
    path: str,
    body: dict[str, Any],
) -> dict[str, Any] | None:
    if path == "/api/browser-automation/status":
        return _status_payload(state)

    if path == "/api/browser-automation/configure":
        if body.get("confirm") != "ROTATE_EXTENSION_TOKEN":
            raise ValueError("Conferma esplicita richiesta per generare il token.")
        state.settings.browser_extension_enabled = True
        state.settings.browser_extension_remote_access = True
        state.settings.browser_extension_token = ensure_extension_token("")
        state.settings_store.save(state.settings)
        return {
            "enabled": True,
            "remote_access": True,
            "token": state.settings.browser_extension_token,
            "message": (
                "Token generato. Configura l’estensione su un Chrome fidato usando "
                "l’indirizzo HTTPS di questa Web UI."
            ),
        }

    if path == "/api/browser-automation/disable":
        if body.get("confirm") != "DISABLE_EXTENSION":
            raise ValueError(
                "Conferma esplicita richiesta per disabilitare l’automazione."
            )
        state.settings.browser_extension_enabled = False
        state.settings.browser_extension_remote_access = False
        state.settings.browser_extension_token = ""
        state.settings.update_zip_directory = ""
        state.settings_store.save(state.settings)
        return {"enabled": False, "message": "Automazione browser disabilitata."}

    if path == "/api/browser-automation/queue":
        if not state.settings.browser_extension_enabled:
            raise ValueError("Abilita prima l’automazione browser.")
        existing = current_request()
        if (
            existing
            and str(existing.get("status", "")) in _ACTIVE_REQUEST_STATUSES
            and body.get("replace") is not True
        ):
            raise ValueError(
                "Un’automazione è già in corso. Conferma la sostituzione "
                "oppure attendi il completamento."
            )
        report = str(body.get("report", "")).strip()
        persisted_settings = SettingsStore().load()
        provider = normalize_web_ai_provider(persisted_settings.preferred_web_ai)
        queued = queue_request(state.require_workspace(), report, provider=provider)
        return {
            "request_id": queued["request_id"],
            "status": queued["status"],
            "provider": provider,
            "message": (
                f"Richiesta accodata. Il browser fidato la invierà a "
                f"{web_ai_provider_label(provider)} appena risulterà connesso."
            ),
        }

    return None
