from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from local_ai_bridge.core.io import atomic_write, sha256_bytes, sha256_file
from local_ai_bridge.core.models import SessionRecord
from local_ai_bridge.core.settings import app_data_dir
from local_ai_bridge.core.safety import resolve_workspace_target


class SessionManager:
    def __init__(self) -> None:
        self.root = app_data_dir() / "sessions"
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, workspace: Path, operation: str, source: str | None = None) -> tuple[Path, SessionRecord]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        session_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
        directory = self.root / session_id
        (directory / "backup").mkdir(parents=True)
        record = SessionRecord(
            session_id=session_id,
            workspace=str(workspace.resolve()),
            operation=operation,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="preparing",
            files=[],
            source=source,
        )
        self.save(directory, record)
        return directory, record

    def save(self, directory: Path, record: SessionRecord) -> None:
        payload = json.dumps(record.to_dict(), ensure_ascii=False, indent=2).encode("utf-8")
        atomic_write(directory / "session.json", payload)

    def load(self, directory: Path) -> SessionRecord:
        data = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        return SessionRecord(**data)

    def iter_for_workspace(self, workspace: Path) -> Iterable[tuple[Path, SessionRecord]]:
        expected = str(workspace.resolve())
        for directory in sorted(self.root.iterdir(), reverse=True):
            if not directory.is_dir() or not (directory / "session.json").exists():
                continue
            try:
                record = self.load(directory)
            except Exception:
                continue
            if record.workspace == expected:
                yield directory, record


    def save_test_results(self, record: SessionRecord, results: list[dict]) -> SessionRecord:
        directory = self.root / record.session_id
        if not directory.is_dir():
            raise FileNotFoundError(f"Sessione non trovata: {record.session_id}")
        current = self.load(directory)
        current.test_results = list(results)
        current.tested_at = datetime.now(timezone.utc).isoformat()
        self.save(directory, current)
        return current

    def session_details(self, workspace: Path, session_id: str) -> tuple[Path, SessionRecord]:
        for directory, record in self.iter_for_workspace(workspace):
            if record.session_id == session_id:
                return directory, record
        raise FileNotFoundError(f"Sessione non trovata: {session_id}")

    def latest_applied(self, workspace: Path) -> tuple[Path, SessionRecord] | None:
        for item in self.iter_for_workspace(workspace):
            if item[1].status == "applied":
                return item
        return None

    def apply_transaction(
        self,
        workspace: Path,
        operation: str,
        changes: list[tuple[str, bytes | None]],
        *,
        source: str | None = None,
        commit_message: str | None = None,
    ) -> SessionRecord:
        normalized_changes: list[tuple[str, bytes | None, Path]] = []
        seen: set[str] = set()
        for relative, new_data in changes:
            target = resolve_workspace_target(workspace, relative, allow_missing=True)
            normalized = target.relative_to(workspace.resolve()).as_posix()
            key = normalized.casefold()
            if key in seen:
                raise ValueError(f"Target duplicato nel batch: {normalized}")
            seen.add(key)
            normalized_changes.append((normalized, new_data, target))
        directory, record = self.create(workspace, operation, source)
        record.commit_message = commit_message
        try:
            for relative, new_data, target in normalized_changes:
                existed = target.exists()
                old_hash = sha256_file(target) if existed else None
                original_mode = target.stat().st_mode & 0o7777 if existed else None
                backup_relative = None
                if existed:
                    backup_path = directory / "backup" / Path(relative)
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup_path)
                    backup_relative = str(backup_path.relative_to(directory))
                record.files.append({
                    "target": relative,
                    "action": "delete" if new_data is None else "write",
                    "existed_before": existed,
                    "backup_path": backup_relative,
                    "original_sha256": old_hash,
                    "applied_sha256": sha256_bytes(new_data) if new_data is not None else None,
                    "original_mode": original_mode,
                })
            self.save(directory, record)
            for relative, new_data, target in normalized_changes:
                item = next(entry for entry in record.files if entry["target"] == relative)
                if new_data is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write(target, new_data, original_mode=item.get("original_mode"))
            record.status = "applied"
            self.save(directory, record)
            self._append_project_history(workspace, record)
            return record
        except Exception as exc:
            self._restore(directory, record, check_conflicts=False)
            record.status = "failed_rolled_back"
            record.error = str(exc)
            self.save(directory, record)
            self._append_project_history(workspace, record)
            raise

    def _append_project_history(self, workspace: Path, record: SessionRecord) -> None:
        try:
            from local_ai_bridge.services.project_history import append_project_history

            append_project_history(workspace, record)
        except Exception:
            # La cronostoria permanente non deve rendere fallita una patch già applicata
            # o un rollback già completato. La sessione in app_data resta comunque salvata.
            return

    def rollback_latest(self, workspace: Path) -> SessionRecord:
        latest = self.latest_applied(workspace)
        if latest is None:
            raise FileNotFoundError("Nessuna sessione applicata disponibile per il rollback.")
        directory, record = latest
        self._restore(directory, record, check_conflicts=True)
        record.status = "rolled_back"
        self.save(directory, record)
        self._append_project_history(workspace, record)
        return record

    def _restore(self, directory: Path, record: SessionRecord, *, check_conflicts: bool) -> None:
        workspace = Path(record.workspace)
        conflicts: list[str] = []
        if check_conflicts:
            for item in record.files:
                target = workspace / Path(item["target"])
                applied_hash = item.get("applied_sha256")
                if applied_hash is None:
                    if target.exists():
                        conflicts.append(item["target"])
                elif not target.exists() or sha256_file(target) != applied_hash:
                    conflicts.append(item["target"])
        if conflicts:
            raise RuntimeError("Rollback bloccato: file modificati dopo l'applicazione: " + ", ".join(conflicts))
        for item in reversed(record.files):
            target = workspace / Path(item["target"])
            if item["existed_before"]:
                backup = directory / item["backup_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            else:
                target.unlink(missing_ok=True)
