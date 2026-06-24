from __future__ import annotations

from typing import Any

from local_ai_bridge.core.project_prompts import (
    load_project_ignore,
    load_project_prompt,
    save_project_ignore,
    save_project_prompt,
)

MAX_POWER_USER_TEXT_LENGTH = 100_000


def _required_bool(body: dict[str, Any], key: str) -> bool:
    value = body.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Il campo {key} deve essere booleano.")
    return value


def _required_text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Il campo {key} deve essere testuale.")
    if len(value) > MAX_POWER_USER_TEXT_LENGTH:
        raise ValueError(
            f"Il campo {key} supera il limite di {MAX_POWER_USER_TEXT_LENGTH} caratteri."
        )
    return value


def power_user_settings_payload(state) -> dict[str, Any]:
    with state.lock:
        workspace = state.workspace
        return {
            "include_custom_prompts": bool(state.settings.include_custom_prompts),
            "global_prompt": state.settings.global_prompt,
            "markdown_exchange_mode": bool(state.settings.markdown_exchange_mode),
            "textual_file_operations_mode": bool(
                state.settings.textual_file_operations_mode
            ),
            "project_available": workspace is not None,
            "workspace": str(workspace) if workspace is not None else None,
            "project_prompt": (
                load_project_prompt(workspace) if workspace is not None else ""
            ),
            "project_ignore": (
                load_project_ignore(workspace) if workspace is not None else ""
            ),
        }


def update_power_user_settings(state, body: dict[str, Any]) -> dict[str, Any]:
    if body.get("confirm") != "SAVE_POWER_USER_SETTINGS":
        raise ValueError("Conferma di salvataggio power-user mancante.")

    include_custom_prompts = _required_bool(body, "include_custom_prompts")
    markdown_exchange_mode = (
        _required_bool(body, "markdown_exchange_mode")
        if "markdown_exchange_mode" in body
        else bool(state.settings.markdown_exchange_mode)
    )
    textual_file_operations_mode = _required_bool(
        body, "textual_file_operations_mode"
    )
    global_prompt = _required_text(body, "global_prompt").strip()
    project_prompt = _required_text(body, "project_prompt")
    project_ignore = _required_text(body, "project_ignore")

    with state.lock:
        workspace = state.workspace
        if workspace is None and (project_prompt.strip() or project_ignore.strip()):
            raise ValueError(
                "Apri un progetto prima di salvare prompt o esclusioni specifiche."
            )

        if workspace is not None:
            save_project_prompt(workspace, project_prompt)
            save_project_ignore(workspace, project_ignore)

        latest_settings = state.settings_store.load()
        latest_settings.include_custom_prompts = include_custom_prompts
        latest_settings.global_prompt = global_prompt
        latest_settings.markdown_exchange_mode = markdown_exchange_mode
        latest_settings.textual_file_operations_mode = textual_file_operations_mode
        state.settings = latest_settings
        state._save_settings()

    payload = power_user_settings_payload(state)
    payload["message"] = "Impostazioni power-user salvate."
    return payload
