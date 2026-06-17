from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(slots=True)
class FileChange:
    source: str
    target: str
    kind: Literal["create", "modify", "binary", "delete"]
    old_sha256: str | None
    new_sha256: str | None
    expected_sha256: str | None = None
    size: int = 0


@dataclass(slots=True)
class ChangePlan:
    plan_type: Literal["zip", "patch", "full_file"]
    workspace: Path
    source_path: Path | None
    changes: list[FileChange]
    diff: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TestResult:
    name: str
    command: list[str]
    status: Literal["passed", "failed", "unavailable", "timeout", "error"]
    returncode: int | None
    output: str
    duration_seconds: float


@dataclass(slots=True)
class SkillResult:
    ok: bool
    message: str
    data: Any = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    workspace: str
    operation: str
    created_at: str
    status: str
    files: list[dict[str, Any]]
    source: str | None = None
    error: str | None = None
    test_results: list[dict[str, Any]] = field(default_factory=list)
    tested_at: str | None = None
    commit_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
