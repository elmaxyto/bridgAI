from __future__ import annotations

from local_ai_bridge.core.models import ChangePlan, SessionRecord
from local_ai_bridge.core.sessions import SessionManager

HIGH_RISK_CONFIRMATION_TOKEN = "HIGH_RISK_APPLY"


def plan_requires_explicit_confirmation(plan: ChangePlan) -> bool:
    return plan.metadata.get("requires_explicit_confirmation") is True


def update_recap(
    plan: ChangePlan,
    file_limit: int = 20,
    source_label: str = "File patch:",
    files_label: str = "File interessati:",
    warnings_label: str = "Avvisi:",
    more_files_template: str = "• ... e altri {count} file",
    more_warnings_template: str = "• ... e altri {count} avvisi",
) -> str:
    """Return a human-readable recap for an update confirmation dialog."""
    parts: list[str] = []
    if plan.source_path is not None:
        parts.append(f"{source_label} {plan.source_path.name}")

    commit_message = plan.metadata.get("commit_message")
    if isinstance(commit_message, str) and commit_message.strip():
        parts.append(commit_message.strip())

    if plan.changes:
        names = [f"• {item.target}" for item in plan.changes[:file_limit]]
        if len(plan.changes) > file_limit:
            names.append(more_files_template.format(count=len(plan.changes) - file_limit))
        parts.append(files_label + "\n" + "\n".join(names))

    if plan.warnings:
        warning_lines = [f"• {item}" for item in plan.warnings[:5]]
        if len(plan.warnings) > 5:
            warning_lines.append(more_warnings_template.format(count=len(plan.warnings) - 5))
        parts.append(warnings_label + "\n" + "\n".join(warning_lines))

    return "\n\n".join(parts)


class ApplyService:
    def __init__(self, sessions: SessionManager | None = None) -> None:
        self.sessions = sessions or SessionManager()

    def apply(
        self,
        plan: ChangePlan,
        *,
        explicit_confirmation: bool = False,
    ) -> SessionRecord:
        if plan_requires_explicit_confirmation(plan) and not explicit_confirmation:
            raise ValueError(
                "Il piano contiene recuperi ad alta severità e richiede "
                "una conferma esplicita prima dell'applicazione."
            )
        contents = plan.metadata.get("contents")
        if not isinstance(contents, dict):
            raise ValueError("Il piano non contiene dati applicabili.")
        ordered: list[tuple[str, bytes | None]] = []
        for change in plan.changes:
            if change.kind == "delete":
                ordered.append((change.target, None))
                continue
            data = contents.get(change.target)
            if not isinstance(data, bytes):
                raise ValueError(f"Contenuto mancante per {change.target}")
            ordered.append((change.target, data))
        source = str(plan.source_path) if plan.source_path else None
        commit_message = plan.metadata.get("commit_message")
        if not isinstance(commit_message, str):
            commit_message = None
        return self.sessions.apply_transaction(
            plan.workspace, plan.plan_type, ordered, source=source, commit_message=commit_message
        )

    def rollback_latest(self, workspace):
        return self.sessions.rollback_latest(workspace)
