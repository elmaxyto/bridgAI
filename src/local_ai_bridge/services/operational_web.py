from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from local_ai_bridge.services.operational_execution_policy import (
    MissionExecutionError,
    resolve_artifacts_directory,
    validate_execution_boundaries,
)
from local_ai_bridge.services.operational_missions import (
    CATEGORY_CUSTOM,
    CATEGORY_DOCUMENTS,
    CATEGORY_FILE_ORGANIZATION,
    CATEGORY_IMAGES,
    CATEGORY_PRESENTATIONS,
    CATEGORY_SPREADSHEETS,
    CATEGORY_WRITING,
    OperationalMission,
)


PACKAGE_SCHEMA = "bridgai-operational-mission-v1"
MAX_PACKAGE_MEMBERS = 2_000
MAX_PACKAGE_FILE_BYTES = 100 * 1024 * 1024
MAX_PACKAGE_TOTAL_BYTES = 500 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class OperationalWebError(RuntimeError):
    """Raised when a Web mission package cannot be prepared safely."""


@dataclass(frozen=True, slots=True)
class OperationalMissionPackage:
    path: Path
    prompt: str
    member_count: int
    total_bytes: int


_CATEGORY_HINTS_IT = {
    CATEGORY_DOCUMENTS: "Lavora sui documenti e sui PDF allegati e produci nuovi documenti nella forma richiesta.",
    CATEGORY_SPREADSHEETS: "Analizza fogli di calcolo e dati, preservando formule e struttura quando possibile.",
    CATEGORY_PRESENTATIONS: "Crea o aggiorna una presentazione professionale usando i materiali allegati.",
    CATEGORY_IMAGES: "Crea o modifica immagini e materiali grafici secondo la richiesta.",
    CATEGORY_WRITING: "Prepara testi, relazioni o riepiloghi basandoti esclusivamente sui materiali allegati.",
    CATEGORY_FILE_ORGANIZATION: "Organizza e rinomina logicamente copie dei file senza alterare gli originali.",
    CATEGORY_CUSTOM: "Svolgi la richiesta usando esclusivamente i materiali autorizzati nello ZIP.",
}
_CATEGORY_HINTS_EN = {
    CATEGORY_DOCUMENTS: "Work on the attached documents and PDFs and create the requested new documents.",
    CATEGORY_SPREADSHEETS: "Analyze spreadsheets and data, preserving formulas and structure where possible.",
    CATEGORY_PRESENTATIONS: "Create or update a professional presentation using the attached materials.",
    CATEGORY_IMAGES: "Create or edit images and graphic materials according to the request.",
    CATEGORY_WRITING: "Prepare text, reports, or summaries using only the attached materials.",
    CATEGORY_FILE_ORGANIZATION: "Organize and logically rename copies of files without changing the originals.",
    CATEGORY_CUSTOM: "Carry out the request using only the authorized materials in the ZIP.",
}


def build_operational_mission_package(
    mission: OperationalMission,
    *,
    language: str = "it",
) -> OperationalMissionPackage:
    """Create the exact ZIP that will be attached to the selected Web AI."""
    if not mission.input_paths or not mission.output_directory:
        raise OperationalWebError("La missione richiede input e cartella risultati.")
    try:
        artifacts = resolve_artifacts_directory(mission)
        outbound = artifacts / "web" / "outbound"
        outbound.mkdir(parents=True, exist_ok=True)
        paths = validate_execution_boundaries(mission, outbound)
    except MissionExecutionError as exc:
        raise OperationalWebError(str(exc)) from exc

    members: list[tuple[Path, str, int]] = []
    used_roots: set[str] = set()
    total_bytes = 0
    for index, (_declared, input_path) in enumerate(paths.inputs, start=1):
        if _sensitive_input_path(input_path):
            raise OperationalWebError(
                f"Percorso sensibile escluso dal pacchetto: {input_path}"
            )
        root_name = _unique_root_name(input_path.name, index, used_roots)
        if input_path.is_file():
            size = _validated_file_size(input_path)
            members.append((input_path, f"input/{root_name}", size))
            total_bytes += size
        else:
            for source, relative in _iter_directory_files(input_path):
                size = _validated_file_size(source)
                members.append((source, f"input/{root_name}/{relative}", size))
                total_bytes += size
                if len(members) > MAX_PACKAGE_MEMBERS:
                    raise OperationalWebError(
                        f"Troppi file autorizzati: massimo {MAX_PACKAGE_MEMBERS}."
                    )
                if total_bytes > MAX_PACKAGE_TOTAL_BYTES:
                    raise OperationalWebError(
                        "Gli input superano il limite complessivo di 500 MiB."
                    )
    if not members:
        raise OperationalWebError("Gli input autorizzati non contengono file regolari.")
    if len(members) > MAX_PACKAGE_MEMBERS:
        raise OperationalWebError(f"Troppi file autorizzati: massimo {MAX_PACKAGE_MEMBERS}.")
    if total_bytes > MAX_PACKAGE_TOTAL_BYTES:
        raise OperationalWebError("Gli input superano il limite complessivo di 500 MiB.")

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prompt = operational_web_prompt(mission, language=language)
    instructions = _instructions_document(mission, generated_at, language=language)
    manifest = {
        "schema": PACKAGE_SCHEMA,
        "mission_id": mission.mission_id,
        "category": mission.work_category,
        "provider": mission.provider,
        "generated_at": generated_at,
        "request": mission.original_request,
        "input_files": [
            {"path": archive_name, "size_bytes": size}
            for _source, archive_name, size in members
        ],
        "result_contract": {
            "zip_required": True,
            "output_directory": "output/",
            "summary_file": "RISULTATO.md",
            "overwrite_originals": False,
        },
    }

    target = outbound / f"bridgai-missione-{mission.mission_id[:12]}.zip"
    temporary = target.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
            strict_timestamps=False,
        ) as archive:
            archive.writestr("ISTRUZIONI.md", instructions)
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
            for source, archive_name, _size in members:
                archive.write(source, arcname=archive_name)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return OperationalMissionPackage(target, prompt, len(members), total_bytes)


def operational_web_prompt(mission: OperationalMission, *, language: str = "it") -> str:
    short_id = mission.mission_id[:12]
    if language.lower().startswith("en"):
        hint = _CATEGORY_HINTS_EN.get(mission.work_category, _CATEGORY_HINTS_EN[CATEGORY_CUSTOM])
        return (
            "Carry out the BridgAI operational mission in the attached ZIP. "
            "Read ISTRUZIONI.md and manifest.json first. "
            f"Mission: {short_id}. {hint} "
            "Return exactly one downloadable ZIP. Put every deliverable under output/, "
            "add RISULTATO.md at the ZIP root, never modify the supplied originals, and "
            "do not return absolute paths. If a dedicated local program is truly required, "
            "also add output/STRUMENTO_RICHIESTO.md describing the proposed tool."
        )
    hint = _CATEGORY_HINTS_IT.get(mission.work_category, _CATEGORY_HINTS_IT[CATEGORY_CUSTOM])
    return (
        "Svolgi la missione operativa BridgAI contenuta nello ZIP allegato. "
        "Leggi prima ISTRUZIONI.md e manifest.json. "
        f"Missione: {short_id}. {hint} "
        "Restituisci esattamente uno ZIP scaricabile. Metti ogni risultato dentro output/, "
        "aggiungi RISULTATO.md nella radice dello ZIP, non modificare gli originali forniti "
        "e non restituire percorsi assoluti. Se è davvero necessario uno strumento locale "
        "dedicato, aggiungi anche output/STRUMENTO_RICHIESTO.md con la specifica proposta."
    )


def _instructions_document(
    mission: OperationalMission,
    generated_at: str,
    *,
    language: str,
) -> str:
    if language.lower().startswith("en"):
        return f"""# BridgAI operational mission

Mission ID: `{mission.mission_id}`  
Category: `{mission.work_category}`  
Generated: `{generated_at}`

## Requested result

{mission.original_request}

## Rules

- Use only files under `input/`.
- Treat all inputs as read-only originals.
- Put every final deliverable under `output/`.
- Add `RISULTATO.md` at the ZIP root with a concise description of the work.
- Return one ZIP only; do not use absolute paths or parent-directory traversal.
- Do not include credentials, hidden system files, or unrelated material.
- If the mission requires a new local tool, include `output/STRUMENTO_RICHIESTO.md` with its purpose, inputs, outputs, dependencies, and safety constraints.
"""
    return f"""# Missione operativa BridgAI

ID missione: `{mission.mission_id}`  
Categoria: `{mission.work_category}`  
Generata: `{generated_at}`

## Risultato richiesto

{mission.original_request}

## Regole

- Usa soltanto i file contenuti in `input/`.
- Considera tutti gli input originali in sola lettura.
- Metti ogni risultato finale dentro `output/`.
- Aggiungi `RISULTATO.md` nella radice dello ZIP con una descrizione sintetica del lavoro.
- Restituisci un solo ZIP; non usare percorsi assoluti o risalite di directory.
- Non includere credenziali, file di sistema nascosti o materiale non pertinente.
- Se la missione richiede un nuovo strumento locale, includi `output/STRUMENTO_RICHIESTO.md` con scopo, input, output, dipendenze e vincoli di sicurezza.
"""


def _unique_root_name(name: str, index: int, used: set[str]) -> str:
    clean = _SAFE_NAME.sub("-", name.strip()).strip(".-") or f"input-{index}"
    candidate = f"{index:03d}-{clean}"
    suffix = 2
    while candidate.casefold() in used:
        candidate = f"{index:03d}-{clean}-{suffix}"
        suffix += 1
    used.add(candidate.casefold())
    return candidate


def _iter_directory_files(root: Path):
    stack: list[Path] = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise OperationalWebError(f"Impossibile leggere la cartella autorizzata: {directory}") from exc
        directories: list[Path] = []
        for entry in entries:
            path = Path(entry.path)
            if entry.is_symlink():
                raise OperationalWebError(f"Link simbolico non consentito negli input: {path}")
            if entry.is_dir(follow_symlinks=False):
                directories.append(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise OperationalWebError(f"Tipo di input non supportato: {path}")
            relative = path.relative_to(root).as_posix()
            if _sensitive_member(relative):
                raise OperationalWebError(f"File sensibile escluso dal pacchetto: {relative}")
            yield path, relative
        stack.extend(reversed(directories))


def _validated_file_size(path: Path) -> int:
    if path.is_symlink() or not path.is_file():
        raise OperationalWebError(f"Input non regolare o simbolico: {path}")
    size = path.stat().st_size
    if size > MAX_PACKAGE_FILE_BYTES:
        raise OperationalWebError(f"File troppo grande per il pacchetto (100 MiB): {path.name}")
    return size


def _sensitive_input_path(path: Path) -> bool:
    parts = list(path.parts)
    if path.anchor and parts and parts[0] == path.anchor:
        parts = parts[1:]
    return _sensitive_member("/".join(parts))


def _sensitive_member(relative: str) -> bool:
    from local_ai_bridge.core.safety import is_sensitive_relative_path

    return is_sensitive_relative_path(relative)
