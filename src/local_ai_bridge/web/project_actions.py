from __future__ import annotations

from pathlib import Path
from typing import Any

from local_ai_bridge.core.settings import SettingsStore
from local_ai_bridge.services.reporting import create_batch_project_reports_zip
from local_ai_bridge.core.project_notes import (
    delete_project_note, load_project_notes, project_note_payload, upsert_project_note,
)
from local_ai_bridge.core.superpowers import delete_superpower, list_superpowers, save_superpower, superpower_payload


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
    if path == "/api/project-notes/list":
        workspace = state.require_workspace()
        return {"items": [project_note_payload(item) for item in load_project_notes(workspace)]}

    if path == "/api/project-notes/save":
        workspace = state.require_workspace()
        upsert_project_note(
            workspace,
            note_id=str(body.get("id", "")),
            title=str(body.get("title", "")),
            content=str(body.get("content", "")),
            todo=bool(body.get("todo", False)),
            completed=bool(body.get("completed", False)),
        )
        return {"items": [project_note_payload(item) for item in load_project_notes(workspace)]}

    if path == "/api/project-notes/delete":
        workspace = state.require_workspace()
        delete_project_note(workspace, str(body.get("id", "")))
        return {"items": [project_note_payload(item) for item in load_project_notes(workspace)]}

    if path == "/api/superpowers/list":
        return {"items": [superpower_payload(item) for item in list_superpowers()]}

    if path == "/api/superpowers/save":
        save_superpower(
            str(body.get("id", "")),
            str(body.get("title", "")),
            str(body.get("markdown", "")),
            description=str(body.get("description", "")),
            category=str(body.get("category", "Generale")),
        )
        return {"items": [superpower_payload(item) for item in list_superpowers()]}

    if path == "/api/superpowers/delete":
        delete_superpower(str(body.get("id", "")))
        return {"items": [superpower_payload(item) for item in list_superpowers()]}

    if path == "/api/workspace":
        workspace = state.set_workspace(str(body.get("path", "")))
        return {"workspace": str(workspace)}

    if path == "/api/settings/workspace-root":
        raise ValueError(
            "La modifica della cartella root dei progetti è bloccata nella Web UI: "
            "può essere eseguita solo dalle Impostazioni del programma BridgAI."
        )


    if path == "/api/projects/batch-report":
        if body.get("confirm") != "BATCH_REPORT":
            raise ValueError("Conferma report batch mancante.")
        projects_root = state.require_project_root()
        result = create_batch_project_reports_zip(
            projects_root,
            task=str(body.get("task", "") or "Report batch del progetto."),
            settings=state.settings,
        )
        artifact = state.register_artifact(
            result.path,
            filename=result.path.name,
            content_type="application/zip",
        )
        return {
            "artifact_id": artifact.artifact_id,
            "filename": artifact.filename,
            "path": str(result.path),
            "projects": result.projects,
            "count": len(result.projects),
        }

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
