from __future__ import annotations

import json
import re

import pytest

import local_ai_bridge.core.prompt_presets as prompt_presets_module
from local_ai_bridge.core.prompt_presets import (
    PromptPresetError,
    compose_task_with_preset,
    get_prompt_preset,
    load_prompt_presets,
)


EXPECTED_PRESET_IDS = {
    "debug",
    "safe_refactor",
    "write_tests",
    "security_review",
    "analysis_only",
}


class _FakeResource:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def joinpath(self, _name: str) -> _FakeResource:
        return self

    def read_text(self, *, encoding: str) -> str:
        assert encoding == "utf-8"
        return json.dumps(self.payload)


def _use_catalog(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    monkeypatch.setattr(
        prompt_presets_module,
        "files",
        lambda _package: _FakeResource(payload),
    )


def test_builtin_prompt_presets_have_unique_valid_ids_and_labels() -> None:
    presets = load_prompt_presets()
    assert {preset.preset_id for preset in presets} == EXPECTED_PRESET_IDS
    assert len({preset.preset_id for preset in presets}) == len(presets)
    assert len({preset.label.casefold() for preset in presets}) == len(presets)
    assert all(
        re.fullmatch(r"[a-z][a-z0-9_]{0,63}", preset.preset_id)
        for preset in presets
    )


def test_builtin_prompt_presets_use_observable_verifiable_instructions() -> None:
    instructions = "\n".join(
        preset.instructions.casefold() for preset in load_prompt_presets()
    )
    assert "chain of thought" not in instructions
    assert "pensa passo dopo passo" not in instructions
    assert "percentuale di confidenza" not in instructions
    assert "fatti verificati" in instructions
    assert "rischi residui" in instructions


def test_catalog_rejects_invalid_identifier(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_catalog(
        monkeypatch,
        [
            {
                "id": "Debug guidato",
                "label": "Debug",
                "description": "Descrizione",
                "instructions": "Istruzioni",
            }
        ],
    )
    with pytest.raises(PromptPresetError, match="ID preset non valido"):
        load_prompt_presets()


def test_catalog_rejects_duplicate_labels_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_catalog(
        monkeypatch,
        [
            {
                "id": "first",
                "label": "Debug",
                "description": "Descrizione",
                "instructions": "Istruzioni",
            },
            {
                "id": "second",
                "label": "debug",
                "description": "Altra descrizione",
                "instructions": "Altre istruzioni",
            },
        ],
    )
    with pytest.raises(PromptPresetError, match="Etichetta preset duplicata"):
        load_prompt_presets()


def test_compose_task_keeps_user_text_and_adds_preset() -> None:
    task = "Correggi il crash quando il file è vuoto."
    composed = compose_task_with_preset(task, "debug")
    assert composed.startswith(task)
    assert "## Profilo operativo: Debug guidato" in composed
    assert "causa radice" in composed
    assert "protocollo del Super-Report restano prioritari" in composed
    assert task == "Correggi il crash quando il file è vuoto."


def test_compose_task_with_only_preset_does_not_add_empty_task_section() -> None:
    composed = compose_task_with_preset("   ", "analysis_only")
    assert composed.startswith("## Profilo operativo: Solo analisi")
    assert not composed.startswith("---")


def test_compose_task_without_preset_only_normalizes_outer_whitespace() -> None:
    assert compose_task_with_preset("  Task utente  ", "") == "Task utente"


def test_unknown_prompt_preset_is_rejected() -> None:
    with pytest.raises(PromptPresetError, match="Preset sconosciuto"):
        get_prompt_preset("missing")
