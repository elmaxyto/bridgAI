from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from local_ai_bridge.services import browser_extension
from local_ai_bridge.services.operational_missions import (
    CATEGORY_PRESENTATIONS,
    MISSION_COMPLETED,
    PROCEDURE_WEB_MISSION,
    PROVIDER_CHATGPT,
    OperationalMissionStore,
)
from local_ai_bridge.services.operational_results import (
    OperationalResultError,
    import_operational_result_zip,
    inspect_operational_result_zip,
)
from local_ai_bridge.services.operational_web import (
    OperationalWebError,
    build_operational_mission_package,
)


def _mission(tmp_path: Path):
    inputs = tmp_path / "inputs"
    inputs.mkdir(parents=True)
    (inputs / "report.pdf").write_bytes(b"%PDF-test")
    nested = inputs / "images"
    nested.mkdir()
    (nested / "cover.png").write_bytes(b"png-data")
    output = tmp_path / "results"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "app-data" / "missions")
    mission = store.create(
        title="Create presentation",
        original_request="Create a concise presentation from the supplied report and image.",
        procedure_id=PROCEDURE_WEB_MISSION,
        work_category=CATEGORY_PRESENTATIONS,
        provider=PROVIDER_CHATGPT,
        input_paths=[inputs / "report.pdf", nested],
        output_directory=output,
    )
    return store, mission, output


def _result_zip(path: Path, mission_id: str, *, extra: dict[str, bytes] | None = None) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("RISULTATO.md", "Presentation prepared.")
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema": "bridgai-operational-result-v1",
                    "mission_id": mission_id,
                }
            ),
        )
        archive.writestr("output/presentation.pptx", b"pptx-data")
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


def test_web_mission_package_contains_only_authorized_materials(tmp_path: Path) -> None:
    store, mission, output = _mission(tmp_path)
    original_pdf = Path(mission.input_paths[0]).read_bytes()

    package = build_operational_mission_package(mission, language="en")

    assert package.member_count == 2
    assert package.total_bytes == len(b"%PDF-test") + len(b"png-data")
    assert "Return exactly one downloadable ZIP" in package.prompt
    with zipfile.ZipFile(package.path) as archive:
        names = archive.namelist()
        assert names[:2] == ["ISTRUZIONI.md", "manifest.json"]
        assert any(name.endswith("report.pdf") for name in names)
        assert any(name.endswith("images/cover.png") for name in names)
        assert not any(str(tmp_path) in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["mission_id"] == mission.mission_id
        assert manifest["category"] == CATEGORY_PRESENTATIONS
        assert manifest["provider"] == PROVIDER_CHATGPT
    assert Path(mission.input_paths[0]).read_bytes() == original_pdf
    assert list(output.iterdir()) == []
    assert store.load(mission.mission_id) == mission


def test_web_mission_package_rejects_sensitive_or_symbolic_inputs(tmp_path: Path) -> None:
    output = tmp_path / "results"
    output.mkdir()
    store = OperationalMissionStore(tmp_path / "missions")
    secret = tmp_path / ".env"
    secret.write_text("TOKEN=secret", encoding="utf-8")
    mission = store.create(
        title="Unsafe",
        original_request="Use the input.",
        procedure_id=PROCEDURE_WEB_MISSION,
        input_paths=[secret],
        output_directory=output,
    )
    with pytest.raises(OperationalWebError, match="sensibile"):
        build_operational_mission_package(mission)

    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        return
    linked = store.create(
        title="Linked",
        original_request="Use the input.",
        procedure_id=PROCEDURE_WEB_MISSION,
        input_paths=[link],
        output_directory=output,
    )
    with pytest.raises((OperationalWebError, RuntimeError), match="symbol"):
        build_operational_mission_package(linked)


    ssh_directory = tmp_path / ".ssh"
    ssh_directory.mkdir()
    ssh_config = ssh_directory / "config"
    ssh_config.write_text("Host private", encoding="utf-8")
    sensitive_parent = store.create(
        title="Sensitive parent",
        original_request="Use the input.",
        procedure_id=PROCEDURE_WEB_MISSION,
        input_paths=[ssh_config],
        output_directory=output,
    )
    with pytest.raises(OperationalWebError, match="sensibile"):
        build_operational_mission_package(sensitive_parent)


def test_result_zip_is_previewed_and_imported_without_overwrite(tmp_path: Path) -> None:
    store, mission, output = _mission(tmp_path)
    result_zip = _result_zip(tmp_path / "result.zip", mission.mission_id)

    preview = inspect_operational_result_zip(mission, result_zip)
    assert preview.output_files == ("presentation.pptx",)
    assert preview.summary == "Presentation prepared."

    imported = import_operational_result_zip(store, mission.mission_id, result_zip)
    assert imported.mission.state == MISSION_COMPLETED
    assert Path(imported.output_paths[0]).read_bytes() == b"pptx-data"
    assert Path(imported.stored_zip_path).is_file()
    assert (Path(mission.artifacts_directory) / "web" / "results" / "latest-import.json").is_file()

    second_store, second_mission, second_output = _mission(tmp_path / "second")
    existing = second_output / "presentation.pptx"
    existing.write_bytes(b"original")
    second_zip = _result_zip(tmp_path / "second-result.zip", second_mission.mission_id)
    with pytest.raises(OperationalResultError, match="non verrà sovrascritto"):
        import_operational_result_zip(second_store, second_mission.mission_id, second_zip)
    assert existing.read_bytes() == b"original"
    assert second_store.load(second_mission.mission_id).state != MISSION_COMPLETED


def test_result_zip_rejects_wrong_mission_and_files_outside_output(tmp_path: Path) -> None:
    _store, mission, _output = _mission(tmp_path)
    wrong = _result_zip(tmp_path / "wrong.zip", "f" * 32)
    with pytest.raises(OperationalResultError, match="differente"):
        inspect_operational_result_zip(mission, wrong)

    invalid = tmp_path / "invalid.zip"
    with zipfile.ZipFile(invalid, "w") as archive:
        archive.writestr("output/result.txt", "ok")
        archive.writestr("unexpected.txt", "no")
    with pytest.raises(OperationalResultError, match="fuori dal contratto"):
        inspect_operational_result_zip(mission, invalid)


def test_operational_extension_request_keeps_kind_mission_and_initial_zip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    request_workspace = tmp_path / "request"
    request_workspace.mkdir()
    context = request_workspace / "mission.zip"
    with zipfile.ZipFile(context, "w") as archive:
        archive.writestr("ISTRUZIONI.md", "test")

    queued = browser_extension.queue_operational_request(
        request_workspace,
        "Do the mission and return a ZIP.",
        mission_id="a" * 32,
        context_zip=context,
    )
    claimed = browser_extension.claim_request()

    assert queued["request_kind"] == "operational"
    assert claimed is not None
    assert claimed["request_kind"] == "operational"
    assert claimed["mission_id"] == "a" * 32
    assert Path(claimed["context_zip_path"]) == context.resolve()
    assert claimed["context_filename"] == "mission.zip"

    browser_extension.record_response(queued["request_id"], "The ZIP is ready.")
    waiting = browser_extension.mark_waiting_result(queued["request_id"])
    assert waiting["status"] == "waiting_result"
    result = request_workspace / "result.zip"
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("output/result.txt", "done")
    ready = browser_extension.mark_result_ready(
        queued["request_id"],
        result,
        {"output_files": ["result.txt"]},
    )
    assert ready["status"] == "result_ready"
    assert ready["mission_id"] == "a" * 32
    assert ready["result_preview"] == {"output_files": ["result.txt"]}


def test_result_import_rolls_back_outputs_if_receipt_cannot_be_written(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from local_ai_bridge.services import operational_results
    from local_ai_bridge.services.operational_missions import MISSION_RUNNING

    store, mission, output = _mission(tmp_path)
    result_zip = _result_zip(tmp_path / "result-write-failure.zip", mission.mission_id)

    def fail_write(*_args, **_kwargs):
        raise OSError("receipt unavailable")

    monkeypatch.setattr(operational_results, "atomic_write", fail_write)
    with pytest.raises(OSError, match="receipt unavailable"):
        import_operational_result_zip(store, mission.mission_id, result_zip)

    assert list(output.iterdir()) == []
    assert store.load(mission.mission_id).state == MISSION_RUNNING
    results = Path(mission.artifacts_directory) / "web" / "results"
    assert not any(results.glob("*.zip"))
    assert not (results / "latest-import.json").exists()


def test_operational_extension_adapter_registers_initial_and_result_archives(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from local_ai_bridge.web import extension_operational

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    store, mission, _output = _mission(tmp_path / "mission")
    package = build_operational_mission_package(mission)
    request_workspace = package.path.parent
    queued = browser_extension.queue_operational_request(
        request_workspace,
        package.prompt,
        mission_id=mission.mission_id,
        context_zip=package.path,
    )
    request = browser_extension.claim_request()
    assert request is not None

    class State:
        def register_artifact(self, path, *, filename, content_type):
            assert Path(path) == package.path
            assert content_type == "application/zip"
            return SimpleNamespace(artifact_id="artifact-1", filename=filename)

    extension_operational.prepare_initial_operational_attachment(State(), request)
    assert request["artifact_url"] == "/api/extension/artifacts/artifact-1"
    assert request["initial_attachment"] is True

    browser_extension.record_response(queued["request_id"], "Result ready.")
    browser_extension.mark_waiting_result(queued["request_id"])
    result_zip = _result_zip(
        tmp_path / "adapter-result.zip",
        mission.mission_id,
        extra={"output/notes.txt": b"notes"},
    )
    monkeypatch.setattr(extension_operational, "OperationalMissionStore", lambda: store)
    payload = extension_operational.register_operational_result(
        queued["request_id"],
        browser_extension.current_request(queued["request_id"]),
        result_zip,
    )
    assert payload["action"] == "result_ready"
    assert payload["mission_id"] == mission.mission_id
    assert payload["preview"]["output_files"] == ["notes.txt", "presentation.pptx"]
    assert browser_extension.current_request(queued["request_id"])["status"] == "result_ready"
