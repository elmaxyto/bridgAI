from __future__ import annotations

from pathlib import Path
from typing import Any

from local_ai_bridge.core.settings import SettingsStore


def resolve_startup_workspace_root(
    configured_root: str | Path | None,
    fixed_workspace: str | Path | None,
) -> tuple[str | Path | None, bool]:
    explicit = configured_root is not None and str(configured_root).strip() != ""
    if explicit or fixed_workspace is not None:
        return configured_root, explicit
    stored = SettingsStore().load().web_workspace_root.strip()
    return stored or None, bool(stored)


def project_status_payload(state, version: str) -> dict[str, Any]:
    return {
        "version": version,
        "workspace": str(state.workspace) if state.workspace else None,
        "workspace_root": str(state.security.workspace_root) if state.security.workspace_root else None,
        "workspace_root_locked": state.workspace_root_locked,
        "fixed_workspace": state.security.fixed_workspace is not None,
        "can_manage_projects": state.can_manage_projects,
        "remote_mode": state.security.remote_mode,
        "authentication": state.security.requires_authentication,
        "workspaces": state.workspace_choices(),
        "pending_plan": state.pending_plan.plan_id if state.pending_plan else None,
    }


def dispatch_project_action(state, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
    if path == "/api/workspace":
        workspace = state.set_workspace(str(body.get("path", "")))
        return {"workspace": str(workspace)}

    if path == "/api/settings/workspace-root":
        raise ValueError(
            "La modifica della cartella root dei progetti è bloccata nella Web UI: "
            "può essere eseguita solo dalle Impostazioni del programma BridgAI."
        )

    if path == "/api/projects/create":
        if body.get("confirm") != "CREATE":
            raise ValueError("Conferma di creazione progetto mancante.")
        initialize_git = body.get("initialize_git", True)
        if not isinstance(initialize_git, bool):
            raise ValueError("Il valore initialize_git deve essere booleano.")
        workspace, output = state.create_project(
            str(body.get("name", "")),
            initialize_git=initialize_git,
        )
        return {"workspace": str(workspace), "output": output, "workspaces": state.workspace_choices()}

    if path == "/api/projects/clone":
        if body.get("confirm") != "CLONE":
            raise ValueError("Conferma di clonazione mancante.")
        workspace, output = state.clone_project(
            str(body.get("repository", "")),
            str(body.get("name", "")),
        )
        return {"workspace": str(workspace), "output": output, "workspaces": state.workspace_choices()}

    return None
