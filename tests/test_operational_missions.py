from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_ai_bridge.services.operational_missions import (
    MISSION_ARCHIVED,
    MISSION_DRAFT,
    MISSION_READY,
    MissionTransitionError,
    OperationalMissionStore,
)


def test_ready_mission_is_persisted_without_touching_inputs_or_output(tmp_path: Path) -> None:
    input_file = tmp_path / "source.txt"
    input_file.write_text("original", encoding="utf-8")
    output_directory = tmp_path / "results"
    output_directory.mkdir()
    store = OperationalMissionStore(tmp_path / "app-data" / "missions")

    mission = store.create(
        title="Quarterly summary",
        original_request="Summarize the selected documents.",
        workspace=tmp_path / "workspace",
        input_paths=[input_file],
        output_directory=output_directory,
    )

    loaded = store.load(mission.mission_id)
    assert loaded == mission
    assert loaded.state == MISSION_READY
    assert loaded.input_paths == (str(input_file),)
    assert loaded.output_directory == str(output_directory)
    assert Path(loaded.artifacts_directory).is_dir()
    assert input_file.read_text(encoding="utf-8") == "original"
    assert list(output_directory.iterdir()) == []


def test_incomplete_mission_remains_draft_and_deduplicates_inputs(tmp_path: Path) -> None:
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Draft mission",
        original_request="Prepare a result later.",
        input_paths=["/tmp/source", "/tmp/source", ""],
    )

    assert mission.state == MISSION_DRAFT
    assert mission.input_paths == ("/tmp/source",)
    assert mission.output_directory == ""


def test_history_is_separate_ordered_and_keeps_archived_records(tmp_path: Path) -> None:
    store = OperationalMissionStore(tmp_path / "missions")
    first = store.create(title="First", original_request="First request")
    second = store.create(title="Second", original_request="Second request")
    archived = store.archive(first.mission_id)

    history = store.list_missions(include_archived=True)
    active = store.list_missions(include_archived=False)

    assert history[0].mission_id == archived.mission_id
    assert {mission.mission_id for mission in history} == {
        first.mission_id,
        second.mission_id,
    }
    assert [mission.mission_id for mission in active] == [second.mission_id]
    assert archived.state == MISSION_ARCHIVED
    assert archived.archived_at


def test_invalid_state_transition_is_rejected(tmp_path: Path) -> None:
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(title="Draft", original_request="Not ready")

    with pytest.raises(MissionTransitionError):
        mission.transition("completed")


def test_corrupt_records_do_not_break_history(tmp_path: Path) -> None:
    store = OperationalMissionStore(tmp_path / "missions")
    valid = store.create(title="Valid", original_request="Keep this record")
    corrupt_directory = store.root / ("a" * 32)
    corrupt_directory.mkdir(parents=True)
    (corrupt_directory / "mission.json").write_text("{broken", encoding="utf-8")

    history = store.list_missions()

    assert [mission.mission_id for mission in history] == [valid.mission_id]


def test_managed_artifacts_path_cannot_be_redirected(tmp_path: Path) -> None:
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(title="Safe", original_request="Keep artifacts managed")
    record_path = store.root / mission.mission_id / "mission.json"
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["artifacts_directory"] = str(tmp_path / "outside")
    record_path.write_text(json.dumps(payload), encoding="utf-8")

    assert store.list_missions() == []


def test_mission_procedure_is_persisted_and_old_records_default_to_inventory(
    tmp_path: Path,
) -> None:
    from local_ai_bridge.services.operational_missions import (
        PROCEDURE_CSV_MERGE,
        PROCEDURE_INPUT_INVENTORY,
    )

    store = OperationalMissionStore(tmp_path / "missions")
    csv_mission = store.create(
        title="Merge CSV",
        original_request="Combine the selected tables.",
        procedure_id=PROCEDURE_CSV_MERGE,
    )
    assert store.load(csv_mission.mission_id).procedure_id == PROCEDURE_CSV_MERGE

    legacy = store.create(title="Legacy", original_request="Inventory inputs.")
    record_path = store.root / legacy.mission_id / "mission.json"
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload.pop("procedure_id")
    record_path.write_text(json.dumps(payload), encoding="utf-8")

    assert store.load(legacy.mission_id).procedure_id == PROCEDURE_INPUT_INVENTORY


def test_web_mission_category_and_provider_are_persisted_with_legacy_defaults(
    tmp_path: Path,
) -> None:
    from local_ai_bridge.services.operational_missions import (
        CATEGORY_CUSTOM,
        CATEGORY_PRESENTATIONS,
        PROCEDURE_WEB_MISSION,
        PROVIDER_CHATGPT,
        PROVIDER_CLAUDE,
    )

    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Slides",
        original_request="Create a presentation.",
        procedure_id=PROCEDURE_WEB_MISSION,
        work_category=CATEGORY_PRESENTATIONS,
        provider=PROVIDER_CLAUDE,
    )
    loaded = store.load(mission.mission_id)
    assert loaded.work_category == CATEGORY_PRESENTATIONS
    assert loaded.provider == PROVIDER_CLAUDE

    record_path = store.root / mission.mission_id / "mission.json"
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload.pop("work_category")
    payload.pop("provider")
    record_path.write_text(json.dumps(payload), encoding="utf-8")
    legacy = store.load(mission.mission_id)
    assert legacy.work_category == CATEGORY_CUSTOM
    assert legacy.provider == PROVIDER_CHATGPT


def test_archiving_a_running_web_mission_cancels_it_first(tmp_path: Path) -> None:
    from local_ai_bridge.services.operational_missions import (
        MISSION_ARCHIVED,
        MISSION_RUNNING,
        PROCEDURE_WEB_MISSION,
    )

    store = OperationalMissionStore(tmp_path / "missions")
    input_file = tmp_path / "input.txt"
    input_file.write_text("data", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    mission = store.create(
        title="Web task",
        original_request="Process the input.",
        procedure_id=PROCEDURE_WEB_MISSION,
        input_paths=[input_file],
        output_directory=output,
    )
    running = mission.transition(MISSION_RUNNING)
    store.save(running)

    archived = store.archive(mission.mission_id)

    assert archived.state == MISSION_ARCHIVED
    assert store.load(mission.mission_id).state == MISSION_ARCHIVED


def test_mission_accepts_project_superpower_as_work_category(tmp_path: Path) -> None:
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Review",
        original_request="Review the files",
        work_category="analisi-critica",
    )
    assert mission.work_category == "analisi-critica"


def test_web_mission_persists_optional_operational_superpower(tmp_path: Path) -> None:
    from local_ai_bridge.services.operational_missions import (
        CATEGORY_DOCUMENTS,
        PROCEDURE_WEB_MISSION,
    )
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Report",
        original_request="Prepare the report.",
        procedure_id=PROCEDURE_WEB_MISSION,
        work_category=CATEGORY_DOCUMENTS,
        superpower_id="sintesi-operativa",
    )
    loaded = store.load(mission.mission_id)
    assert loaded.work_category == CATEGORY_DOCUMENTS
    assert loaded.superpower_id == "sintesi-operativa"
