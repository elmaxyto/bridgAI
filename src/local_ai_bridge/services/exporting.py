from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from local_ai_bridge.core.safety import SafetyError, project_identity, resolve_workspace_target


DOWNLOAD_PATTERN = re.compile(r"(?im)^\s*#scarica\s+(.+?)\s*$")
MARKDOWN_BOLD_PATTERN = re.compile(r"\*\*([^*\r\n]+?)\*\*")
PROJECT_METADATA_NAME = "bridgai-project.json"


def _normalize_requested_path(raw: str) -> str:
    """Restore path characters that Markdown commonly rewrites while copying.

    A filename such as ``__init__.py`` can be rendered as bold text and copied
    back as ``**init**.py``.  Converting paired Markdown bold markers back to
    double underscores is deterministic and preserves the intended filename;
    no globbing or fuzzy filesystem lookup is performed.
    """
    value = raw.strip().strip("`\"'")
    return MARKDOWN_BOLD_PATTERN.sub(r"__\1__", value)


def parse_download_requests(text: str) -> list[str]:
    requested: list[str] = []
    for match in DOWNLOAD_PATTERN.finditer(text or ""):
        for raw in match.group(1).split(","):
            value = _normalize_requested_path(raw)
            if value and value not in requested:
                requested.append(value)
    return requested


def validate_requested_files(workspace: Path, requested: list[str]) -> list[tuple[str, Path]]:
    if not requested:
        raise ValueError("Nessun comando #scarica rilevato.")
    valid: list[tuple[str, Path]] = []
    errors: list[str] = []
    for relative in requested:
        try:
            path = resolve_workspace_target(workspace, relative, allow_missing=False)
            valid.append((Path(relative.replace("\\", "/")).as_posix(), path))
        except SafetyError as exc:
            errors.append(f"{relative}: {exc}")
    if errors:
        raise ValueError("Richieste non valide:\n" + "\n".join(errors))
    return valid


def create_export_zip(workspace: Path, requested: list[str], destination: Path) -> Path:
    valid = validate_requested_files(workspace, requested)
    destination.parent.mkdir(parents=True, exist_ok=True)
    metadata = project_identity(workspace)
    metadata["instructions"] = (
        "Copy this file unchanged into every update ZIP returned for this project. "
        "BridgAI uses it to reject updates prepared for a different workspace."
    )
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(PROJECT_METADATA_NAME, json.dumps(metadata, ensure_ascii=False, indent=2))
        for relative, path in valid:
            archive.write(path, arcname=relative)
    return destination
