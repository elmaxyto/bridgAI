from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from local_ai_bridge.core.io import atomic_write
from local_ai_bridge.services.operational_csv import build_csv_merge_products
from local_ai_bridge.services.operational_execution_policy import (
    MissionExecutionError,
    build_inventory_payload,
    resolve_artifacts_directory,
    validate_execution_boundaries,
)
from local_ai_bridge.services.operational_missions import (
    MISSION_COMPLETED,
    MISSION_FAILED,
    MISSION_READY,
    PROCEDURE_CSV_MERGE,
    PROCEDURE_INPUT_INVENTORY,
    OperationalMission,
    OperationalMissionStore,
)


EXECUTION_RUNNING = "running"
EXECUTION_COMPLETED = "completed"
EXECUTION_FAILED = "failed"
EXECUTION_STATES = (
    EXECUTION_RUNNING,
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
)
EXECUTION_RECORD_VERSION = 1


@dataclass(frozen=True, slots=True)
class OperationalExecutionRecord:
    execution_id: str
    mission_id: str
    procedure_id: str
    state: str
    started_at: str
    finished_at: str
    log_path: str
    artifact_paths: tuple[str, ...]
    output_paths: tuple[str, ...]
    error: str = ""
    record_version: int = EXECUTION_RECORD_VERSION

    @classmethod
    def from_dict(cls, data: object) -> "OperationalExecutionRecord":
        if not isinstance(data, dict):
            raise MissionExecutionError("execution record must be an object")
        if data.get("record_version", EXECUTION_RECORD_VERSION) != EXECUTION_RECORD_VERSION:
            raise MissionExecutionError("execution record version is unsupported")
        execution_id = str(data.get("execution_id", "")).strip()
        mission_id = str(data.get("mission_id", "")).strip()
        procedure_id = str(data.get("procedure_id", "")).strip()
        state = str(data.get("state", "")).strip()
        started_at = str(data.get("started_at", "")).strip()
        finished_at = str(data.get("finished_at", "")).strip()
        log_path = str(data.get("log_path", "")).strip()
        artifact_paths = data.get("artifact_paths", [])
        output_paths = data.get("output_paths", [])
        error = str(data.get("error", "")).strip()
        _validate_hex_id(execution_id, "execution")
        _validate_hex_id(mission_id, "mission")
        if not procedure_id:
            raise MissionExecutionError("procedure id is required")
        if state not in EXECUTION_STATES:
            raise MissionExecutionError("execution state is invalid")
        if not started_at or not log_path:
            raise MissionExecutionError("execution timestamps and log path are required")
        if state != EXECUTION_RUNNING and not finished_at:
            raise MissionExecutionError("finished executions require a finish timestamp")
        if state == EXECUTION_FAILED and not error:
            raise MissionExecutionError("failed executions require an error")
        if not isinstance(artifact_paths, (list, tuple)) or not isinstance(
            output_paths, (list, tuple)
        ):
            raise MissionExecutionError("execution paths must be lists")
        return cls(
            execution_id=execution_id,
            mission_id=mission_id,
            procedure_id=procedure_id,
            state=state,
            started_at=started_at,
            finished_at=finished_at,
            log_path=log_path,
            artifact_paths=tuple(str(path) for path in artifact_paths),
            output_paths=tuple(str(path) for path in output_paths),
            error=error,
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["artifact_paths"] = list(self.artifact_paths)
        payload["output_paths"] = list(self.output_paths)
        return payload


@dataclass(frozen=True, slots=True)
class _GeneratedProduct:
    filename: str
    data: bytes


class OperationalMissionExecutor:
    """Run declared built-in procedures inside explicit mission boundaries."""

    def __init__(
        self,
        store: OperationalMissionStore,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.store = store
        self._execution_id_factory = execution_id_factory or (lambda: uuid.uuid4().hex)

    def execute(self, mission_id: str) -> OperationalExecutionRecord:
        mission = self.store.load(mission_id)
        if mission.state != MISSION_READY:
            raise MissionExecutionError("only ready missions can be executed")
        execution_id = self._execution_id_factory()
        _validate_hex_id(execution_id, "execution id factory result")
        artifacts_directory = resolve_artifacts_directory(mission)
        run_directory = artifacts_directory / "runs" / execution_id
        run_directory.mkdir(parents=True, exist_ok=False)
        log_path = run_directory / "execution.log"
        record_path = run_directory / "execution.json"
        started_at = _now()
        record = OperationalExecutionRecord(
            execution_id=execution_id,
            mission_id=mission.mission_id,
            procedure_id=mission.procedure_id,
            state=EXECUTION_RUNNING,
            started_at=started_at,
            finished_at="",
            log_path=str(log_path),
            artifact_paths=(),
            output_paths=(),
        )
        _write_record(record_path, record)
        running_mission = mission.transition("running", at=started_at)
        try:
            self.store.save(running_mission)
        except Exception:
            shutil.rmtree(run_directory, ignore_errors=True)
            raise

        created_artifacts: list[Path] = []
        created_outputs: list[Path] = []
        try:
            _append_log(log_path, f"Execution started: {mission.procedure_id}")
            paths = validate_execution_boundaries(running_mission, run_directory)
            _append_log(log_path, f"Validated {len(paths.inputs)} authorized input(s).")
            artifact_products, output_products = _build_products(
                running_mission,
                execution_id,
                paths,
                _now(),
            )
            for product in artifact_products:
                target = run_directory / product.filename
                atomic_write(target, product.data)
                created_artifacts.append(target)
            for product in output_products:
                target = paths.output_directory / product.filename
                _exclusive_write(target, product.data)
                created_outputs.append(target)
            _verify_products(created_artifacts, created_outputs)
            for target in created_outputs:
                _append_log(log_path, f"Created output: {target}")
            finished_at = _now()
            completed = replace(
                record,
                state=EXECUTION_COMPLETED,
                finished_at=finished_at,
                artifact_paths=tuple(str(path) for path in created_artifacts),
                output_paths=tuple(str(path) for path in created_outputs),
            )
            _write_record(record_path, completed)
            self.store.save(running_mission.transition(MISSION_COMPLETED, at=finished_at))
            _append_log(log_path, "Execution completed successfully.")
            return completed
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            _remove_created_outputs(created_outputs)
            try:
                _append_log(log_path, f"Execution failed: {message}")
            except OSError:
                pass
            finished_at = _now()
            failed = replace(
                record,
                state=EXECUTION_FAILED,
                finished_at=finished_at,
                artifact_paths=tuple(
                    str(path) for path in created_artifacts if path.is_file()
                ),
                output_paths=(),
                error=message,
            )
            try:
                _write_record(record_path, failed)
            finally:
                self.store.save(running_mission.transition(MISSION_FAILED, at=finished_at))
            return failed

    def latest_execution(self, mission_id: str) -> OperationalExecutionRecord | None:
        mission = self.store.load(mission_id)
        runs_directory = Path(mission.artifacts_directory) / "runs"
        if not runs_directory.is_dir():
            return None
        records: list[OperationalExecutionRecord] = []
        for record_path in runs_directory.glob("*/execution.json"):
            try:
                data = json.loads(record_path.read_text(encoding="utf-8"))
                record = OperationalExecutionRecord.from_dict(data)
            except (OSError, json.JSONDecodeError, MissionExecutionError):
                continue
            if record.mission_id == mission_id:
                records.append(record)
        records.sort(key=lambda item: (item.started_at, item.execution_id), reverse=True)
        return records[0] if records else None


def _build_products(
    mission: OperationalMission,
    execution_id: str,
    paths,
    generated_at: str,
) -> tuple[tuple[_GeneratedProduct, ...], tuple[_GeneratedProduct, ...]]:
    suffix = f"{mission.mission_id[:8]}-{execution_id[:8]}"
    if mission.procedure_id == PROCEDURE_INPUT_INVENTORY:
        payload = build_inventory_payload(
            mission, execution_id, mission.procedure_id, paths, generated_at
        )
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return (
            (_GeneratedProduct("input-inventory.json", data),),
            (_GeneratedProduct(f"bridgai-input-inventory-{suffix}.json", data),),
        )
    if mission.procedure_id == PROCEDURE_CSV_MERGE:
        products = build_csv_merge_products(
            mission, execution_id, mission.procedure_id, paths, generated_at
        )
        return (
            (_GeneratedProduct("csv-merge-summary.json", products.summary_json),),
            (
                _GeneratedProduct(f"bridgai-csv-unificato-{suffix}.csv", products.merged_csv),
                _GeneratedProduct(f"bridgai-csv-riepilogo-{suffix}.txt", products.summary_text),
            ),
        )
    raise MissionExecutionError(f"unsupported mission procedure: {mission.procedure_id}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validate_hex_id(value: str, label: str) -> None:
    if len(value) != 32 or any(ch not in "0123456789abcdef" for ch in value):
        raise MissionExecutionError(f"{label} is invalid")


def _append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{_now()} {message}\n")
        stream.flush()
        os.fsync(stream.fileno())


def _exclusive_write(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _verify_products(artifacts: list[Path], outputs: list[Path]) -> None:
    if not artifacts or not outputs:
        raise MissionExecutionError("the procedure did not declare all expected products")
    if any(not path.is_file() for path in (*artifacts, *outputs)):
        raise MissionExecutionError("the expected execution outputs are missing")


def _remove_created_outputs(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _write_record(path: Path, record: OperationalExecutionRecord) -> None:
    atomic_write(
        path,
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2).encode("utf-8"),
    )
