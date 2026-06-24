from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_ai_bridge.services.operational_execution import (
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
    MissionExecutionError,
    OperationalMissionExecutor,
    PROCEDURE_INPUT_INVENTORY,
)
from local_ai_bridge.services.operational_missions import (
    MISSION_COMPLETED,
    MISSION_DRAFT,
    MISSION_FAILED,
    OperationalMissionStore,
)


def test_inventory_execution_creates_verified_result_without_reading_content(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("private original content", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "app-data" / "missions")
    mission = store.create(
        title="Inventory",
        original_request="List the authorized inputs.",
        input_paths=[source],
        output_directory=output,
    )
    executor = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "1" * 32
    )

    record = executor.execute(mission.mission_id)

    assert record.state == EXECUTION_COMPLETED
    assert record.procedure_id == PROCEDURE_INPUT_INVENTORY
    assert store.load(mission.mission_id).state == MISSION_COMPLETED
    assert source.read_text(encoding="utf-8") == "private original content"
    assert len(record.output_paths) == 1
    result_path = Path(record.output_paths[0])
    assert result_path.parent == output
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["inputs"][0]["declared_path"] == str(source)
    assert payload["inputs"][0]["size_bytes"] == source.stat().st_size
    assert payload["guarantees"]["input_contents_read"] is False
    assert "private original content" not in result_path.read_text(encoding="utf-8")
    assert Path(record.log_path).is_file()
    assert all(Path(path).is_file() for path in record.artifact_paths)
    assert executor.latest_execution(mission.mission_id) == record


def test_missing_input_is_logged_and_marks_mission_failed(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Missing input",
        original_request="Create an inventory.",
        input_paths=[tmp_path / "missing.txt"],
        output_directory=output,
    )
    executor = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "2" * 32
    )

    record = executor.execute(mission.mission_id)

    assert record.state == EXECUTION_FAILED
    assert "does not exist" in record.error
    assert store.load(mission.mission_id).state == MISSION_FAILED
    assert Path(record.log_path).is_file()
    assert list(output.iterdir()) == []


def test_output_cannot_overlap_an_authorized_input(tmp_path: Path) -> None:
    source_directory = tmp_path / "source"
    source_directory.mkdir()
    original = source_directory / "original.txt"
    original.write_text("unchanged", encoding="utf-8")
    output = source_directory / "results"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Unsafe overlap",
        original_request="Create an inventory.",
        input_paths=[source_directory],
        output_directory=output,
    )
    executor = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "3" * 32
    )

    record = executor.execute(mission.mission_id)

    assert record.state == EXECUTION_FAILED
    assert "must remain separate" in record.error
    assert original.read_text(encoding="utf-8") == "unchanged"
    assert list(output.iterdir()) == []


def test_draft_mission_cannot_start_execution(tmp_path: Path) -> None:
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(title="Draft", original_request="Not ready yet.")
    executor = OperationalMissionExecutor(store)

    with pytest.raises(MissionExecutionError, match="only ready missions"):
        executor.execute(mission.mission_id)

    assert store.load(mission.mission_id).state == MISSION_DRAFT
    assert executor.latest_execution(mission.mission_id) is None


def test_symbolic_link_input_is_rejected_when_supported(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("original", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Linked input",
        original_request="Create an inventory.",
        input_paths=[link],
        output_directory=output,
    )
    executor = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "4" * 32
    )

    record = executor.execute(mission.mission_id)

    assert record.state == EXECUTION_FAILED
    assert "symbolic-link inputs" in record.error
    assert target.read_text(encoding="utf-8") == "original"
    assert list(output.iterdir()) == []


def test_corrupt_execution_record_is_ignored(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="History",
        original_request="Create an inventory.",
        input_paths=[source],
        output_directory=output,
    )
    executor = OperationalMissionExecutor(store)
    corrupt = Path(mission.artifacts_directory) / "runs" / ("a" * 32)
    corrupt.mkdir(parents=True)
    (corrupt / "execution.json").write_text("{broken", encoding="utf-8")

    assert executor.latest_execution(mission.mission_id) is None


def test_replaced_artifacts_directory_symlink_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Protected artifacts",
        original_request="Create an inventory.",
        input_paths=[source],
        output_directory=output,
    )
    artifacts = Path(mission.artifacts_directory)
    artifacts.rmdir()
    try:
        artifacts.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")
    executor = OperationalMissionExecutor(store)

    with pytest.raises(MissionExecutionError, match="artifacts directory cannot"):
        executor.execute(mission.mission_id)

    assert list(outside.iterdir()) == []
    assert store.load(mission.mission_id).state != MISSION_FAILED
