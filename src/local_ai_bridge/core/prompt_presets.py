from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


@dataclass(frozen=True, slots=True)
class PromptPreset:
    preset_id: str
    label: str
    description: str
    instructions: str


class PromptPresetError(ValueError):
    """Raised when a prompt preset identifier or catalog is invalid."""


def _validated_text(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PromptPresetError(f"Campo preset non valido: {key}")
    return value.strip()


def load_prompt_presets() -> tuple[PromptPreset, ...]:
    resource = files("local_ai_bridge.resources").joinpath("prompt_presets.json")
    try:
        raw = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise PromptPresetError("Catalogo dei preset non disponibile o non valido.") from exc
    if not isinstance(raw, list):
        raise PromptPresetError("Il catalogo dei preset deve essere una lista.")

    presets: list[PromptPreset] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise PromptPresetError("Ogni preset deve essere un oggetto JSON.")
        preset_id = _validated_text(item, "id")
        if preset_id in seen:
            raise PromptPresetError(f"Preset duplicato: {preset_id}")
        seen.add(preset_id)
        presets.append(
            PromptPreset(
                preset_id=preset_id,
                label=_validated_text(item, "label"),
                description=_validated_text(item, "description"),
                instructions=_validated_text(item, "instructions"),
            )
        )
    return tuple(presets)


def get_prompt_preset(preset_id: str | None) -> PromptPreset | None:
    normalized = (preset_id or "").strip()
    if not normalized:
        return None
    for preset in load_prompt_presets():
        if preset.preset_id == normalized:
            return preset
    raise PromptPresetError(f"Preset sconosciuto: {normalized}")


def compose_task_with_preset(task: str, preset_id: str | None) -> str:
    user_task = task.strip()
    preset = get_prompt_preset(preset_id)
    if preset is None:
        return user_task
    preset_block = (
        f"## Preset selezionato: {preset.label}\n\n"
        f"{preset.instructions}\n\n"
        "Le istruzioni del preset integrano il task dell'utente senza sostituirlo."
    )
    return f"{user_task}\n\n{preset_block}" if user_task else preset_block
