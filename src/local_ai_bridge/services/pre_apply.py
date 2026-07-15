from __future__ import annotations

from pathlib import Path
from typing import Any

from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.services.testing import detect_test_commands


def build_pre_apply_summary(plan: ChangePlan) -> dict[str, Any]:
    """Build a read-only checklist describing a plan before it is applied."""
    counts = {"create": 0, "modify": 0, "delete": 0, "binary": 0}
    for change in plan.changes:
        counts[change.kind] = counts.get(change.kind, 0) + 1

    tests = [name for name, _command, _timeout, _env in detect_test_commands(plan.workspace)]
    source = plan.source_path.name if plan.source_path else None
    origin = plan.plan_type
    if source:
        origin = f"{origin}: {source}"

    return {
        "total": len(plan.changes),
        "created": counts["create"],
        "modified": counts["modify"],
        "deleted": counts["delete"],
        "binary": counts["binary"],
        "has_binary": counts["binary"] > 0,
        "has_commit_message": bool(str(plan.metadata.get("commit_message", "")).strip()),
        "source_name": source,
        "warning_count": len(plan.warnings),
        "warnings": list(plan.warnings),
        "tests": tests,
        "origin": origin,
    }


def format_pre_apply_summary(summary: dict[str, Any]) -> str:
    tests = summary.get("tests") or []
    test_text = ", ".join(str(item) for item in tests) if tests else "Nessun controllo rilevato"
    commit_text = "presente" if summary.get("has_commit_message") else "assente"
    binary_text = str(summary.get("binary", 0)) if summary.get("has_binary") else "nessuno"
    return (
        f"File coinvolti: {summary.get('total', 0)} "
        f"(creati {summary.get('created', 0)}, modificati {summary.get('modified', 0)}, "
        f"eliminati {summary.get('deleted', 0)})\n"
        f"File binari: {binary_text}\n"
        f"commit-message.md: {commit_text}\n"
        f"File patch: {summary.get('source_name') or '-'}\n"
        f"Avvisi: {summary.get('warning_count', 0)}\n"
        f"Controlli disponibili dopo l’applicazione: {test_text}\n"
        f"Origine piano: {summary.get('origin', '-') }"
    )
