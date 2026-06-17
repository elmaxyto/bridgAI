from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from local_ai_bridge.core.models import SkillResult


@dataclass(slots=True)
class SkillContext:
    workspace: Any = None
    services: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SkillSpec:
    skill_id: str
    name: str
    description: str
    permissions: frozenset[str]
    handler: Callable[[SkillContext, dict[str, Any]], SkillResult]


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillSpec] = {}

    def register(self, spec: SkillSpec) -> None:
        if spec.skill_id in self._skills:
            raise ValueError(f"Skill già registrata: {spec.skill_id}")
        self._skills[spec.skill_id] = spec

    def execute(self, skill_id: str, context: SkillContext, **parameters: Any) -> SkillResult:
        try:
            spec = self._skills[skill_id]
        except KeyError as exc:
            return SkillResult(False, f"Skill sconosciuta: {skill_id}")
        try:
            return spec.handler(context, parameters)
        except Exception as exc:
            return SkillResult(False, f"Errore nella skill {skill_id}: {exc}")

    def list_specs(self) -> list[SkillSpec]:
        return sorted(self._skills.values(), key=lambda item: item.name.casefold())
