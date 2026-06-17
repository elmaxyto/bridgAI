from __future__ import annotations

from local_ai_bridge.core.models import ChangePlan, SessionRecord
from local_ai_bridge.core.sessions import SessionManager


class ApplyService:
    def __init__(self, sessions: SessionManager | None = None) -> None:
        self.sessions = sessions or SessionManager()

    def apply(self, plan: ChangePlan) -> SessionRecord:
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
