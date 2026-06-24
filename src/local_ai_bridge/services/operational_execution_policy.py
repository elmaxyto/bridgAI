from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from local_ai_bridge.services.operational_missions import OperationalMission


class MissionExecutionError(RuntimeError):
    """Raised when a mission cannot be executed safely."""


@dataclass(frozen=True, slots=True)
class ValidatedExecutionPaths:
    inputs: tuple[tuple[str, Path], ...]
    output_directory: Path


def resolve_artifacts_directory(mission: OperationalMission) -> Path:
    return _resolved_directory(Path(mission.artifacts_directory), "artifacts directory")


def validate_execution_boundaries(
    mission: OperationalMission,
    run_directory: Path,
) -> ValidatedExecutionPaths:
    if not mission.input_paths or not mission.output_directory:
        raise MissionExecutionError("the mission requires inputs and an output folder")
    artifacts_directory = resolve_artifacts_directory(mission)
    output_directory = _resolved_directory(
        Path(mission.output_directory), "output directory"
    )
    resolved_inputs: list[tuple[str, Path]] = []
    for raw_path in mission.input_paths:
        path = Path(raw_path)
        if path.is_symlink():
            raise MissionExecutionError(f"symbolic-link inputs are not allowed: {path}")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise MissionExecutionError(f"input does not exist: {path}") from exc
        if not resolved.is_file() and not resolved.is_dir():
            raise MissionExecutionError(f"unsupported input type: {path}")
        resolved_inputs.append((raw_path, resolved))
    for raw_path, resolved in resolved_inputs:
        if _paths_overlap(resolved, output_directory):
            raise MissionExecutionError(
                f"input and output paths must remain separate: {raw_path}"
            )
        if _paths_overlap(resolved, artifacts_directory):
            raise MissionExecutionError(
                f"input and internal artifacts must remain separate: {raw_path}"
            )
    if _paths_overlap(output_directory, artifacts_directory):
        raise MissionExecutionError(
            "output and internal artifacts directories must remain separate"
        )
    resolved_run = run_directory.resolve(strict=True)
    if artifacts_directory not in resolved_run.parents:
        raise MissionExecutionError("execution artifacts escaped the managed directory")
    return ValidatedExecutionPaths(tuple(resolved_inputs), output_directory)


def build_inventory_payload(
    mission: OperationalMission,
    execution_id: str,
    procedure_id: str,
    paths: ValidatedExecutionPaths,
    generated_at: str,
) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for declared, resolved in paths.inputs:
        stat_result = resolved.stat()
        entries.append(
            {
                "declared_path": declared,
                "resolved_path": str(resolved),
                "kind": "file" if resolved.is_file() else "directory",
                "size_bytes": stat_result.st_size if resolved.is_file() else None,
                "modified_at": datetime.fromtimestamp(
                    stat_result.st_mtime, timezone.utc
                ).isoformat(timespec="seconds"),
            }
        )
    return {
        "schema_version": 1,
        "mission_id": mission.mission_id,
        "execution_id": execution_id,
        "procedure_id": procedure_id,
        "generated_at": generated_at,
        "request": mission.original_request,
        "output_directory": str(paths.output_directory),
        "inputs": entries,
        "guarantees": {
            "input_contents_read": False,
            "originals_modified": False,
            "network_used": False,
            "external_processes_used": False,
        },
    }


def _resolved_directory(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise MissionExecutionError(f"{label} cannot be a symbolic link")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise MissionExecutionError(f"{label} does not exist: {path}") from exc
    if not resolved.is_dir():
        raise MissionExecutionError(f"{label} is not a directory: {path}")
    return resolved


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents
