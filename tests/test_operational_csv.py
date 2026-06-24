from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from local_ai_bridge.services.operational_execution import (
    EXECUTION_COMPLETED,
    EXECUTION_FAILED,
    OperationalMissionExecutor,
)
from local_ai_bridge.services.operational_missions import (
    MISSION_COMPLETED,
    MISSION_FAILED,
    PROCEDURE_CSV_MERGE,
    OperationalMissionStore,
)


def _csv_output(record) -> Path:
    return next(Path(path) for path in record.output_paths if path.endswith(".csv"))


def _summary_artifact(record) -> Path:
    return next(
        Path(path)
        for path in record.artifact_paths
        if path.endswith("csv-merge-summary.json")
    )


def test_csv_merge_combines_headers_delimiters_and_encodings(tmp_path: Path) -> None:
    first = tmp_path / "primo.csv"
    first.write_text("nome;importo\nAnna;10\nLuca;20\n", encoding="utf-8")
    second = tmp_path / "secondo.csv"
    second.write_bytes("nome,città\nMarta,Roma\n".encode("cp1252"))
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Unisci vendite",
        original_request="Unisci i CSV e conserva tutte le colonne.",
        procedure_id=PROCEDURE_CSV_MERGE,
        input_paths=[first, second],
        output_directory=output,
    )
    executor = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "5" * 32
    )

    record = executor.execute(mission.mission_id)

    assert record.state == EXECUTION_COMPLETED
    assert record.procedure_id == PROCEDURE_CSV_MERGE
    assert store.load(mission.mission_id).state == MISSION_COMPLETED
    assert len(record.output_paths) == 2
    merged_text = _csv_output(record).read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(merged_text)))
    assert [row["nome"] for row in rows] == ["Anna", "Luca", "Marta"]
    assert [row["importo"] for row in rows] == ["10", "20", ""]
    assert [row["città"] for row in rows] == ["", "", "Roma"]
    assert [row["BridgAI source file"] for row in rows] == [
        "primo.csv",
        "primo.csv",
        "secondo.csv",
    ]
    summary = json.loads(_summary_artifact(record).read_text(encoding="utf-8"))
    assert summary["file_count"] == 2
    assert summary["row_count"] == 3
    assert summary["guarantees"]["originals_modified"] is False
    assert first.read_text(encoding="utf-8") == "nome;importo\nAnna;10\nLuca;20\n"
    assert second.read_bytes() == "nome,città\nMarta,Roma\n".encode("cp1252")


def test_csv_merge_discovers_nested_csv_files_in_authorized_directory(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (source / "a.csv").write_text("id,value\n1,A\n", encoding="utf-8")
    (nested / "b.csv").write_text("id,value\n2,B\n", encoding="utf-8")
    (nested / "ignore.txt").write_text("not csv", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Directory CSV",
        original_request="Combine all CSV files.",
        procedure_id=PROCEDURE_CSV_MERGE,
        input_paths=[source],
        output_directory=output,
    )

    record = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "6" * 32
    ).execute(mission.mission_id)

    rows = list(csv.DictReader(io.StringIO(_csv_output(record).read_text("utf-8-sig"))))
    assert [row["id"] for row in rows] == ["1", "2"]
    assert [row["BridgAI source file"] for row in rows] == [
        "a.csv",
        "nested/b.csv",
    ]


def test_csv_merge_rejects_non_csv_input_without_partial_outputs(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not a csv", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Invalid CSV",
        original_request="Merge this input.",
        procedure_id=PROCEDURE_CSV_MERGE,
        input_paths=[source],
        output_directory=output,
    )

    record = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "7" * 32
    ).execute(mission.mission_id)

    assert record.state == EXECUTION_FAILED
    assert "is not CSV" in record.error
    assert record.output_paths == ()
    assert list(output.iterdir()) == []
    assert store.load(mission.mission_id).state == MISSION_FAILED


def test_csv_merge_rejects_duplicate_headers(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.csv"
    source.write_text("name,Name\nA,B\n", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Duplicate columns",
        original_request="Merge CSV.",
        procedure_id=PROCEDURE_CSV_MERGE,
        input_paths=[source],
        output_directory=output,
    )

    record = OperationalMissionExecutor(
        store, execution_id_factory=lambda: "8" * 32
    ).execute(mission.mission_id)

    assert record.state == EXECUTION_FAILED
    assert "duplicate column names" in record.error
    assert list(output.iterdir()) == []


def test_csv_merge_never_overwrites_and_removes_partial_new_outputs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    source.write_text("id,value\n1,A\n", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    mission = store.create(
        title="Protected output",
        original_request="Merge without overwriting.",
        procedure_id=PROCEDURE_CSV_MERGE,
        input_paths=[source],
        output_directory=output,
    )
    execution_id = "9" * 32
    suffix = f"{mission.mission_id[:8]}-{execution_id[:8]}"
    protected_summary = output / f"bridgai-csv-riepilogo-{suffix}.txt"
    protected_summary.write_text("keep me", encoding="utf-8")

    record = OperationalMissionExecutor(
        store, execution_id_factory=lambda: execution_id
    ).execute(mission.mission_id)

    assert record.state == EXECUTION_FAILED
    assert record.output_paths == ()
    assert protected_summary.read_text(encoding="utf-8") == "keep me"
    assert not (output / f"bridgai-csv-unificato-{suffix}.csv").exists()
    assert list(output.iterdir()) == [protected_summary]
