from __future__ import annotations

import secrets
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from local_ai_bridge.services.pre_apply import build_pre_apply_summary
from local_ai_bridge.web.security import is_loopback_address
from local_ai_bridge.web.state import BridgeState


def _plan_payload(state: BridgeState, plan_id: str) -> dict[str, Any]:
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


def dispatch_bridge_action(
    state: BridgeState,
    path: str,
    body: dict[str, Any],
    client_ip: str,
) -> dict[str, Any] | None:
    workspace = state.require_workspace()

    if path == "/api/report":
        from local_ai_bridge.core.prompt_presets import compose_task_with_preset
        from local_ai_bridge.services.reporting import build_super_report

        task = compose_task_with_preset(
            str(body.get("task", "")),
            str(body.get("preset_id", "")),
        )
        return {"report": build_super_report(workspace, task, settings=state.settings)}

    if path == "/api/export":
        from local_ai_bridge.services.exporting import create_export_zip, parse_download_requests
        from local_ai_bridge.services.markdown_exchange import encode_files_to_markdown
        from local_ai_bridge.services.temp_storage import managed_subdir

        requested = parse_download_requests(str(body.get("text", "")))
        exports = managed_subdir(state.settings.temp_directory, "exports")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if state.settings.markdown_exchange_mode:
            created = exports / f"ai_context_{stamp}.md"
            created.write_text(
                encode_files_to_markdown(workspace, requested),
                encoding="utf-8",
            )
            content_type = "text/markdown; charset=utf-8"
            export_format = "markdown"
        else:
            created = create_export_zip(
                workspace, requested, exports / f"ai_context_{stamp}.zip"
            )
            content_type = "application/zip"
            export_format = "zip"
        artifact = state.register_artifact(created, content_type=content_type)
        return {
            "artifact_id": artifact.artifact_id,
            "filename": artifact.filename,
            "format": export_format,
            "files": requested,
        }

    if path == "/api/patch/inspect":
        from local_ai_bridge.services.patching import inspect_gemini_response
        from local_ai_bridge.services.text_file_operations import (
            inspect_text_file_operations,
        )

        plan = (
            inspect_text_file_operations(workspace, str(body.get("text", "")))
            if state.settings.textual_file_operations_mode
            else inspect_gemini_response(workspace, str(body.get("text", "")))
        )
        plan_id = state.register_plan(plan)
        return _plan_payload(state, plan_id)

    if path == "/api/zip/inspect":
        from local_ai_bridge.services.archive import inspect_zip
        from local_ai_bridge.services.temp_storage import stage_import_zip

        if state.security.remote_mode or not is_loopback_address(client_ip):
            raise ValueError("Da remoto carica lo ZIP dal dispositivo invece di indicare un percorso server.")
        staged = stage_import_zip(Path(str(body.get("path", ""))), state.settings.temp_directory)
        plan_id = state.register_plan(inspect_zip(workspace, staged))
        return _plan_payload(state, plan_id)

    if path in {"/api/plan/apply", "/api/zip/apply"}:
        if body.get("confirm") != "APPLY":
            raise ValueError("Conferma di applicazione mancante.")
        plan_id = str(body.get("plan_id", ""))
        plan = state.get_plan(plan_id)
        record = state.apply_service.apply(plan)
        state.clear_plan(plan_id)
        return {"session": record.to_dict()}

    if path == "/api/rollback":
        if body.get("confirm") != "ROLLBACK":
            raise ValueError("Conferma di rollback mancante.")
        record = state.apply_service.rollback_latest(workspace)
        return {"session": record.to_dict()}

    if path == "/api/github/simple/status":
        from local_ai_bridge.services.github import simple_github_status

        return simple_github_status(workspace)

    if path == "/api/github/simple/publish":
        if body.get("confirm") != "PUBLISH":
            raise ValueError("Conferma di pubblicazione mancante.")
        from local_ai_bridge.services.github import publish_or_update_github

        return publish_or_update_github(
            workspace,
            repository_name=str(body.get("repository_name", "")).strip() or workspace.name,
            visibility=str(body.get("visibility", "private")),
            session_manager=state.sessions,
        )

    if path == "/api/tests":
        from local_ai_bridge.services.testing import (
            format_test_results,
            interpret_test_results,
            run_detected_tests,
        )

        results = run_detected_tests(workspace)
        return {
            "output": format_test_results(results),
            "results": [asdict(item) for item in results],
            "interpretation": interpret_test_results(results),
        }

    if path == "/api/git/status":
        from local_ai_bridge.services.git import git_status

        return {"output": git_status(workspace)}

    if path == "/api/git/diff":
        from local_ai_bridge.services.git import git_diff

        return {"output": git_diff(workspace)}

    return None
