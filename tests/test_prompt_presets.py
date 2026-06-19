from __future__ import annotations

import pytest

from local_ai_bridge.core.prompt_presets import (
    PromptPresetError,
    compose_task_with_preset,
    get_prompt_preset,
    load_prompt_presets,
)


def test_builtin_prompt_presets_have_unique_ids() -> None:
    presets = load_prompt_presets()
    assert {preset.preset_id for preset in presets} == {
        "debug",
        "safe_refactor",
        "write_tests",
        "security_review",
        "analysis_only",
    }
    assert len({preset.preset_id for preset in presets}) == len(presets)


def test_compose_task_keeps_user_text_and_adds_preset() -> None:
    task = "Correggi il crash quando il file è vuoto."
    composed = compose_task_with_preset(task, "debug")
    assert composed.startswith(task)
    assert "Preset selezionato: Debug guidato" in composed
    assert "causa radice" in composed
    assert task == "Correggi il crash quando il file è vuoto."


def test_compose_task_without_preset_only_normalizes_outer_whitespace() -> None:
    assert compose_task_with_preset("  Task utente  ", "") == "Task utente"


def test_unknown_prompt_preset_is_rejected() -> None:
    with pytest.raises(PromptPresetError, match="Preset sconosciuto"):
        get_prompt_preset("missing")
