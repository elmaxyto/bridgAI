from __future__ import annotations

from pathlib import Path
from typing import Any

from local_ai_bridge.services.browser_extension import mark_result_ready
from local_ai_bridge.services.operational_missions import OperationalMissionStore
from local_ai_bridge.services.operational_results import inspect_operational_result_zip


def prepare_initial_operational_attachment(state, request: dict[str, Any]) -> None:
    """Register the mission package for the extension's first ChatGPT message."""
    context = Path(str(request.get("context_zip_path", ""))).expanduser()
    if context.is_symlink():
        raise ValueError("Il pacchetto operativo non può essere un link simbolico.")
    context = context.resolve(strict=True)
    if not context.is_file() or context.suffix.casefold() != ".zip":
        raise ValueError("Il pacchetto operativo non è disponibile.")
    artifact = state.register_artifact(
        context,
        filename=str(request.get("context_filename") or context.name),
        content_type="application/zip",
    )
    request["artifact_url"] = f"/api/extension/artifacts/{artifact.artifact_id}"
    request["filename"] = artifact.filename
    request["initial_attachment"] = True


def register_operational_result(
    request_id: str,
    request: dict[str, Any],
    target: Path,
    *,
    delete_on_error: bool = False,
) -> dict[str, Any]:
    """Validate a returned ZIP against its persisted mission before exposing it."""
    try:
        mission_id = str(request.get("mission_id", "")).strip()
        mission = OperationalMissionStore().load(mission_id)
        preview = inspect_operational_result_zip(mission, target)
    except Exception:
        if delete_on_error:
            target.unlink(missing_ok=True)
        raise
    payload = preview.to_dict()
    mark_result_ready(request_id, target, payload)
    return {
        "action": "result_ready",
        "path": str(target),
        "mission_id": mission_id,
        "preview": payload,
    }
