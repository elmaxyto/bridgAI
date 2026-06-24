from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from local_ai_bridge.core.io import atomic_write
from local_ai_bridge.core.safety import ArchiveLimits, SafetyError, validate_archive
from local_ai_bridge.services.operational_execution_policy import resolve_artifacts_directory
from local_ai_bridge.services.operational_missions import (
    MISSION_COMPLETED,
    MISSION_READY,
    MISSION_RUNNING,
    OperationalMission,
    OperationalMissionStore,
)


RESULT_SCHEMA = "bridgai-operational-result-v1"
RESULT_LIMITS = ArchiveLimits(
    max_members=5_000,
    max_single_file=100 * 1024 * 1024,
    max_uncompressed=500 * 1024 * 1024,
    max_compression_ratio=300.0,
)
_ALLOWED_ROOT_FILES = {"risultato.md", "manifest.json"}


class OperationalResultError(RuntimeError):
    """Raised when a result archive cannot be accepted or imported safely."""


@dataclass(frozen=True, slots=True)
class OperationalResultPreview:
    zip_path: str
    mission_id: str
    output_files: tuple[str, ...]
    total_bytes: int
    summary: str = ""
    tool_requested: bool = False

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["output_files"] = list(self.output_files)
        return payload


@dataclass(frozen=True, slots=True)
class OperationalImportResult:
    mission: OperationalMission
    output_paths: tuple[str, ...]
    stored_zip_path: str
    tool_requested: bool


def inspect_operational_result_zip(
    mission: OperationalMission,
    zip_path: str | Path,
) -> OperationalResultPreview:
    path = Path(zip_path).expanduser()
    if path.is_symlink():
        raise OperationalResultError("Lo ZIP dei risultati non può essere un link simbolico.")
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise OperationalResultError("Lo ZIP dei risultati non esiste.") from exc
    if not path.is_file() or path.suffix.casefold() != ".zip":
        raise OperationalResultError("Seleziona uno ZIP dei risultati valido.")

    try:
        with zipfile.ZipFile(path) as archive:
            safe_names = validate_archive(archive, RESULT_LIMITS)
            output_files: list[str] = []
            total_bytes = 0
            summary = ""
            manifest_mission_id = ""
            info_by_name = {info.filename.replace("\\", "/"): info for info in archive.infolist()}
            for safe_name in safe_names:
                parts = PurePosixPath(safe_name).parts
                root_name = parts[0]
                root = root_name.casefold()
                if root == "output":
                    if root_name != "output":
                        raise OperationalResultError(
                            "La cartella dei risultati deve chiamarsi esattamente output/."
                        )
                    if len(parts) < 2:
                        continue
                    relative = PurePosixPath(*parts[1:]).as_posix()
                    output_files.append(relative)
                    info = info_by_name.get(safe_name)
                    if info is not None:
                        total_bytes += info.file_size
                    continue
                if len(parts) != 1 or root not in _ALLOWED_ROOT_FILES:
                    raise OperationalResultError(
                        f"Elemento fuori dal contratto dei risultati: {safe_name}"
                    )
                if root == "risultato.md":
                    summary = _read_text_member(archive, safe_name, limit=32_000)
                elif root == "manifest.json":
                    manifest_mission_id = _manifest_mission_id(archive, safe_name)
            if not output_files:
                raise OperationalResultError(
                    "Lo ZIP non contiene alcun risultato dentro la cartella output/."
                )
            if manifest_mission_id and manifest_mission_id != mission.mission_id:
                raise OperationalResultError(
                    "Lo ZIP dichiara un identificativo di missione differente."
                )
    except (zipfile.BadZipFile, SafetyError) as exc:
        raise OperationalResultError(str(exc)) from exc

    ordered = tuple(sorted(output_files, key=str.casefold))
    return OperationalResultPreview(
        zip_path=str(path),
        mission_id=mission.mission_id,
        output_files=ordered,
        total_bytes=total_bytes,
        summary=summary.strip(),
        tool_requested=any(
            item.casefold() == "strumento_richiesto.md" or item.casefold().endswith("/strumento_richiesto.md")
            for item in ordered
        ),
    )


def import_operational_result_zip(
    store: OperationalMissionStore,
    mission_id: str,
    zip_path: str | Path,
) -> OperationalImportResult:
    mission = store.load(mission_id)
    if mission.state not in {MISSION_READY, MISSION_RUNNING}:
        raise OperationalResultError(
            "La missione selezionata non è in attesa di risultati importabili."
        )
    preview = inspect_operational_result_zip(mission, zip_path)
    output_directory = _resolved_output_directory(mission)
    artifacts = resolve_artifacts_directory(mission)
    results_directory = artifacts / "web" / "results"
    results_directory.mkdir(parents=True, exist_ok=True)
    source_zip = Path(preview.zip_path)
    stored_zip = _unique_path(results_directory, source_zip.name)
    receipt_path = results_directory / "latest-import.json"

    running = mission
    if running.state == MISSION_READY:
        running = running.transition(MISSION_RUNNING)
        store.save(running)

    created_files: list[Path] = []
    created_directories: list[Path] = []
    try:
        shutil.copy2(source_zip, stored_zip)
        with zipfile.ZipFile(stored_zip) as archive:
            info_by_safe_name = _validated_info_map(archive)
            for relative in preview.output_files:
                info = info_by_safe_name[f"output/{relative}"]
                target = _prepare_target(
                    output_directory,
                    PurePosixPath(relative),
                    created_directories,
                )
                _extract_exclusive(archive, info, target)
                created_files.append(target)
        receipt = {
            "schema": RESULT_SCHEMA,
            "mission_id": mission.mission_id,
            "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_zip": str(stored_zip),
            "output_paths": [str(path) for path in created_files],
            "tool_requested": preview.tool_requested,
        }
        atomic_write(
            receipt_path,
            json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        completed = running.transition(MISSION_COMPLETED)
        store.save(completed)
        return OperationalImportResult(
            mission=completed,
            output_paths=tuple(str(path) for path in created_files),
            stored_zip_path=str(stored_zip),
            tool_requested=preview.tool_requested,
        )
    except Exception:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        stored_zip.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        raise


def _validated_info_map(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    safe_names = validate_archive(archive, RESULT_LIMITS)
    by_raw = {info.filename.replace("\\", "/"): info for info in archive.infolist()}
    return {safe_name: by_raw[safe_name] for safe_name in safe_names}


def _manifest_mission_id(archive: zipfile.ZipFile, name: str) -> str:
    text = _read_text_member(archive, name, limit=64_000)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OperationalResultError("manifest.json dei risultati non è valido.") from exc
    if not isinstance(value, dict):
        raise OperationalResultError("manifest.json dei risultati deve essere un oggetto.")
    schema = str(value.get("schema", "")).strip()
    if schema and schema != RESULT_SCHEMA:
        raise OperationalResultError("Schema del manifest risultati non supportato.")
    return str(value.get("mission_id", "")).strip()


def _read_text_member(archive: zipfile.ZipFile, name: str, *, limit: int) -> str:
    info = next(
        (
            candidate
            for candidate in archive.infolist()
            if candidate.filename.replace("\\", "/") == name
        ),
        None,
    )
    if info is None:
        raise OperationalResultError(f"Elemento ZIP non trovato: {name}")
    if info.file_size > limit:
        raise OperationalResultError(f"File descrittivo troppo grande: {name}")
    try:
        return archive.read(info).decode("utf-8")
    except UnicodeError as exc:
        raise OperationalResultError(f"File descrittivo non UTF-8: {name}") from exc


def _resolved_output_directory(mission: OperationalMission) -> Path:
    path = Path(mission.output_directory)
    if path.is_symlink():
        raise OperationalResultError("La cartella risultati non può essere un link simbolico.")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise OperationalResultError("La cartella risultati non esiste.") from exc
    if not resolved.is_dir():
        raise OperationalResultError("La destinazione dei risultati non è una cartella.")
    return resolved


def _prepare_target(
    output_directory: Path,
    relative: PurePosixPath,
    created_directories: list[Path],
) -> Path:
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise OperationalResultError(f"Percorso risultato non valido: {relative}")
    current = output_directory
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise OperationalResultError(f"Cartella simbolica non consentita: {current}")
        if current.exists():
            if not current.is_dir():
                raise OperationalResultError(f"Un file blocca la cartella risultato: {current}")
        else:
            current.mkdir()
            created_directories.append(current)
    target = current / relative.parts[-1]
    resolved_parent = target.parent.resolve(strict=True)
    if output_directory != resolved_parent and output_directory not in resolved_parent.parents:
        raise OperationalResultError("Un risultato uscirebbe dalla cartella autorizzata.")
    if target.exists() or target.is_symlink():
        raise OperationalResultError(f"Il risultato esiste già e non verrà sovrascritto: {target}")
    return target


def _extract_exclusive(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    target: Path,
) -> None:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with archive.open(info) as source, os.fdopen(descriptor, "wb") as destination:
            descriptor = -1
            shutil.copyfileobj(source, destination, length=1024 * 1024)
            destination.flush()
            os.fsync(destination.fileno())
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        target.unlink(missing_ok=True)
        raise


def _unique_path(directory: Path, filename: str) -> Path:
    clean = Path(filename).name or "bridgai-risultati.zip"
    target = directory / clean
    counter = 2
    while target.exists():
        target = directory / f"{Path(clean).stem}-{counter}{Path(clean).suffix}"
        counter += 1
    return target
