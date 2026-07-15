from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from local_ai_bridge.core.settings import app_data_dir
from local_ai_bridge.core.superpowers import SuperpowerError, normalize_superpower_id

from local_ai_bridge.services.operational_catalog import (
    CATEGORY_CUSTOM,
    CATEGORY_DOCUMENTS,
    CATEGORY_FILE_ORGANIZATION,
    CATEGORY_IMAGES,
    CATEGORY_PRESENTATIONS,
    CATEGORY_SPREADSHEETS,
    CATEGORY_TRANSLATION,
    CATEGORY_WRITING,
    MISSION_ARCHIVED,
    MISSION_CANCELLED,
    MISSION_COMPLETED,
    MISSION_DRAFT,
    MISSION_FAILED,
    MISSION_PROCEDURES,
    MISSION_PROVIDERS,
    MISSION_READY,
    MISSION_RECORD_VERSION,
    MISSION_RUNNING,
    MISSION_STATES,
    MISSION_TRANSITIONS,
    MISSION_WORK_CATEGORIES,
    PROCEDURE_CSV_MERGE,
    PROCEDURE_INPUT_INVENTORY,
    PROCEDURE_WEB_MISSION,
    PROVIDER_CHATGPT,
    PROVIDER_CLAUDE,
    PROVIDER_GEMINI,
)

_MISSION_ID = re.compile(r"^[0-9a-f]{32}$")


class MissionError(ValueError):
    """Base error for invalid or unreadable operational missions."""


class MissionValidationError(MissionError):
    """Raised when mission data does not satisfy the persisted contract."""


class MissionTransitionError(MissionError):
    """Raised when a state transition is not allowed."""


class MissionNotFoundError(MissionError):
    """Raised when a persisted mission cannot be found."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validated_text(value: object, label: str, required: bool = False) -> str:
    if not isinstance(value, str):
        raise MissionValidationError(f"{label} must be text")
    text = value.strip()
    if required and not text:
        raise MissionValidationError(f"{label} is required")
    return text


def _normalized_paths(values: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise MissionValidationError("input paths must contain only text values")
        path = value.strip()
        if not path:
            continue
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(path)
    return tuple(normalized)



def _validated_work_category(value: object) -> str:
    text = _validated_text(value, "work category", required=True)
    try:
        return normalize_superpower_id(text)
    except SuperpowerError as exc:
        raise MissionValidationError("mission work category is invalid") from exc

def _validated_timestamp(value: object, label: str) -> str:
    text = _validated_text(value, label, required=True)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MissionValidationError(f"{label} is not an ISO timestamp") from exc
    return text


def _validated_mission_id(value: object) -> str:
    text = _validated_text(value, "mission id", required=True)
    if not _MISSION_ID.fullmatch(text):
        raise MissionValidationError("mission id is invalid")
    return text


@dataclass(frozen=True, slots=True)
class OperationalMission:
    mission_id: str
    title: str
    original_request: str
    procedure_id: str
    work_category: str
    superpower_id: str
    provider: str
    workspace: str
    input_paths: tuple[str, ...]
    output_directory: str
    artifacts_directory: str
    state: str
    created_at: str
    updated_at: str
    archived_at: str = ""
    record_version: int = MISSION_RECORD_VERSION

    @classmethod
    def from_dict(cls, data: object) -> "OperationalMission":
        if not isinstance(data, dict):
            raise MissionValidationError("mission record must be an object")
        if data.get("record_version", MISSION_RECORD_VERSION) != MISSION_RECORD_VERSION:
            raise MissionValidationError("mission record version is unsupported")
        raw_inputs = data.get("input_paths", [])
        if not isinstance(raw_inputs, (list, tuple)):
            raise MissionValidationError("input paths must be a list")
        procedure_id = _validated_text(
            data.get("procedure_id", PROCEDURE_INPUT_INVENTORY),
            "procedure id",
            required=True,
        )
        if procedure_id not in MISSION_PROCEDURES:
            raise MissionValidationError("mission procedure is unsupported")
        work_category = _validated_work_category(
            data.get("work_category", CATEGORY_CUSTOM)
        )
        provider = _validated_text(
            data.get("provider", PROVIDER_CHATGPT),
            "provider",
            required=True,
        )
        if provider not in MISSION_PROVIDERS:
            raise MissionValidationError("mission provider is unsupported")
        state = _validated_text(data.get("state"), "state", required=True)
        if state not in MISSION_STATES:
            raise MissionValidationError("mission state is invalid")
        archived_at = _validated_text(data.get("archived_at", ""), "archived at")
        if state == MISSION_ARCHIVED and not archived_at:
            raise MissionValidationError("archived missions require an archive timestamp")
        if archived_at:
            archived_at = _validated_timestamp(archived_at, "archived at")
        return cls(
            mission_id=_validated_mission_id(data.get("mission_id")),
            title=_validated_text(data.get("title"), "title", required=True),
            original_request=_validated_text(
                data.get("original_request"), "original request", required=True
            ),
            procedure_id=procedure_id,
            work_category=work_category,
            superpower_id=_validated_text(data.get("superpower_id", ""), "superpower id"),
            provider=provider,
            workspace=_validated_text(data.get("workspace", ""), "workspace"),
            input_paths=_normalized_paths(raw_inputs),
            output_directory=_validated_text(
                data.get("output_directory", ""), "output directory"
            ),
            artifacts_directory=_validated_text(
                data.get("artifacts_directory"),
                "artifacts directory",
                required=True,
            ),
            state=state,
            created_at=_validated_timestamp(data.get("created_at"), "created at"),
            updated_at=_validated_timestamp(data.get("updated_at"), "updated at"),
            archived_at=archived_at,
            record_version=MISSION_RECORD_VERSION,
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["input_paths"] = list(self.input_paths)
        return payload

    def transition(self, target_state: str, at: str | None = None) -> "OperationalMission":
        if target_state not in MISSION_STATES:
            raise MissionTransitionError(f"unknown mission state: {target_state}")
        if target_state == self.state:
            return self
        if target_state not in MISSION_TRANSITIONS[self.state]:
            raise MissionTransitionError(
                f"mission cannot move from {self.state} to {target_state}"
            )
        changed_at = at or _now()
        return replace(
            self,
            state=target_state,
            updated_at=changed_at,
            archived_at=changed_at if target_state == MISSION_ARCHIVED else "",
        )


class OperationalMissionStore:
    """Persist mission metadata outside workspaces and software-change sessions."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else app_data_dir() / "missions"

    def _mission_directory(self, mission_id: str) -> Path:
        return self.root / _validated_mission_id(mission_id)

    def _record_path(self, mission_id: str) -> Path:
        return self._mission_directory(mission_id) / "mission.json"

    def _artifacts_directory(self, mission_id: str) -> Path:
        return self._mission_directory(mission_id) / "artifacts"

    def create(
        self,
        *,
        title: str,
        original_request: str,
        procedure_id: str = PROCEDURE_INPUT_INVENTORY,
        work_category: str = CATEGORY_CUSTOM,
        superpower_id: str = "",
        provider: str = PROVIDER_CHATGPT,
        workspace: str | Path | None = None,
        input_paths: Iterable[str | Path] = (),
        output_directory: str | Path | None = None,
    ) -> OperationalMission:
        clean_title = _validated_text(title, "title", required=True)
        clean_request = _validated_text(
            original_request, "original request", required=True
        )
        clean_procedure = _validated_text(
            procedure_id, "procedure id", required=True
        )
        if clean_procedure not in MISSION_PROCEDURES:
            raise MissionValidationError("mission procedure is unsupported")
        clean_category = _validated_work_category(work_category)
        clean_superpower_id = _validated_text(superpower_id, "superpower id")
        if clean_superpower_id:
            try:
                clean_superpower_id = normalize_superpower_id(clean_superpower_id)
            except SuperpowerError as exc:
                raise MissionValidationError("mission superpower id is invalid") from exc
        clean_provider = _validated_text(provider, "provider", required=True)
        if clean_provider not in MISSION_PROVIDERS:
            raise MissionValidationError("mission provider is unsupported")
        raw_inputs: Iterable[str | Path]
        if isinstance(input_paths, (str, Path)):
            raw_inputs = (input_paths,)
        else:
            raw_inputs = input_paths
        clean_inputs = _normalized_paths(str(path) for path in raw_inputs)
        clean_output = _validated_text(
            "" if output_directory is None else str(output_directory),
            "output directory",
        )
        clean_workspace = _validated_text(
            "" if workspace is None else str(workspace), "workspace"
        )
        mission_id = uuid.uuid4().hex
        mission_directory = self._mission_directory(mission_id)
        artifacts_directory = self._artifacts_directory(mission_id)
        artifacts_directory.mkdir(parents=True, exist_ok=False)
        timestamp = _now()
        state = MISSION_READY if clean_inputs and clean_output else MISSION_DRAFT
        mission = OperationalMission(
            mission_id=mission_id,
            title=clean_title,
            original_request=clean_request,
            procedure_id=clean_procedure,
            work_category=clean_category,
            superpower_id=clean_superpower_id,
            provider=clean_provider,
            workspace=clean_workspace,
            input_paths=clean_inputs,
            output_directory=clean_output,
            artifacts_directory=str(artifacts_directory),
            state=state,
            created_at=timestamp,
            updated_at=timestamp,
        )
        try:
            self.save(mission)
        except Exception:
            try:
                artifacts_directory.rmdir()
                mission_directory.rmdir()
            except OSError:
                pass
            raise
        return mission

    def save(self, mission: OperationalMission) -> Path:
        mission_id = _validated_mission_id(mission.mission_id)
        expected_artifacts = self._artifacts_directory(mission_id)
        if Path(mission.artifacts_directory) != expected_artifacts:
            raise MissionValidationError(
                "artifacts directory must remain inside the managed mission directory"
            )
        record_path = self._record_path(mission_id)
        expected_artifacts.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            mission.to_dict(), ensure_ascii=False, indent=2
        ).encode("utf-8")
        temporary = record_path.with_suffix(".json.tmp")
        try:
            temporary.write_bytes(payload)
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            temporary.replace(record_path)
            try:
                os.chmod(record_path, 0o600)
            except OSError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
        return record_path

    def load(self, mission_id: str) -> OperationalMission:
        record_path = self._record_path(mission_id)
        if not record_path.is_file():
            raise MissionNotFoundError(f"mission not found: {mission_id}")
        try:
            data = json.loads(record_path.read_text(encoding="utf-8"))
            mission = OperationalMission.from_dict(data)
        except MissionError:
            raise
        except Exception as exc:
            raise MissionValidationError(
                f"mission record is unreadable: {mission_id}"
            ) from exc
        expected_artifacts = self._artifacts_directory(mission.mission_id)
        if Path(mission.artifacts_directory) != expected_artifacts:
            raise MissionValidationError(
                "mission record points outside its managed artifacts directory"
            )
        return mission

    def list_missions(
        self, *, include_archived: bool = True
    ) -> list[OperationalMission]:
        if not self.root.is_dir():
            return []
        missions: list[OperationalMission] = []
        for directory in self.root.iterdir():
            if not directory.is_dir() or not _MISSION_ID.fullmatch(directory.name):
                continue
            try:
                mission = self.load(directory.name)
            except MissionError:
                continue
            if not include_archived and mission.state == MISSION_ARCHIVED:
                continue
            missions.append(mission)
        missions.sort(key=lambda item: (item.updated_at, item.mission_id), reverse=True)
        return missions

    def archive(self, mission_id: str) -> OperationalMission:
        mission = self.load(mission_id)
        if mission.state == MISSION_RUNNING:
            mission = mission.transition(MISSION_CANCELLED)
            self.save(mission)
        archived = mission.transition(MISSION_ARCHIVED)
        self.save(archived)
        return archived
