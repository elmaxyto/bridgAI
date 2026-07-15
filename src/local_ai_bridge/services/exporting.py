from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from local_ai_bridge.core.safety import SafetyError, project_identity, resolve_workspace_target
from local_ai_bridge.core.settings import AppSettings, SettingsStore
from local_ai_bridge.services.external_contexts import (
    parse_external_context_reference,
    resolve_external_context_file,
)


# Kept for backward compatibility (some callers/tests may import this constant
# directly). The actual parsing now goes through the more tolerant, line-based
# scan below, which recognizes the same strict "#scarica ..." form plus a few
# common Markdown-mangled variants of it.
DOWNLOAD_PATTERN = re.compile(r"(?im)^\s*#scarica\s+(.+?)\s*$")
MARKDOWN_BOLD_PATTERN = re.compile(r"\*\*([^*\r\n]+?)\*\*")
PROJECT_METADATA_NAME = "bridgai-project.json"

# Leading list/quote markers that AI Web assistants commonly prepend to a
# "#scarica" line or to each file entry of a multi-line list: "- #scarica x",
# "1. #scarica x", "> #scarica x", "* file.py", "• file.py".
_LEADING_MARKUP_PATTERN = re.compile(r"^(?:[>\-*\u2022]+\s*|\d+[.)]\s+)")

# Symmetric Markdown wrapping that assistants sometimes apply to the whole
# line: a fenced-inline directive like `` `#scarica a.py, b.py` `` or an
# emphasized one like ``**#scarica a.py, b.py**``.
_WRAP_MARKS = ("**", "__", "`", "*", "_")

# A "#scarica" line with nothing after it opens a block form where the
# requested files follow on subsequent lines instead of on the same line:
#   #scarica
#   - a.py
#   - b.py
_DOWNLOAD_HEADER_PATTERN = re.compile(r"(?i)^#scarica\s*:?\s*$")
_DOWNLOAD_INLINE_PATTERN = re.compile(r"(?i)^#scarica\s+(.+?)\s*$")


def _normalize_requested_path(raw: str) -> str:
    """Restore path characters that Markdown commonly rewrites while copying.

    A filename such as ``__init__.py`` can be rendered as bold text and copied
    back as ``**init**.py``.  Converting paired Markdown bold markers back to
    double underscores is deterministic and preserves the intended filename;
    no globbing or fuzzy filesystem lookup is performed.
    """
    value = raw.strip().strip("`\"'")
    return MARKDOWN_BOLD_PATTERN.sub(r"__\1__", value)


def _unwrapped_line(line: str) -> str:
    """Strip one layer of list/quote markers and one layer of symmetric
    Markdown wrapping from a single line, repeatedly, until nothing more can
    be removed. This never touches the interior of the line."""
    working = (line or "").strip()
    changed = True
    while changed and working:
        changed = False
        # Check symmetric wrapping (e.g. "**...**") before the leading list
        # marker pattern: the latter also matches "*"/"-" and would otherwise
        # eat one side of a bold-wrapped line, leaving a stray marker behind.
        for mark in _WRAP_MARKS:
            edge = len(mark)
            if len(working) > edge * 2 and working.startswith(mark) and working.endswith(mark):
                working = working[edge:-edge].strip()
                changed = True
                break
        if changed:
            continue
        without_markup = _LEADING_MARKUP_PATTERN.sub("", working, count=1)
        if without_markup != working:
            working = without_markup.strip()
            changed = True
    return working


def _looks_like_listed_path(cleaned_line: str) -> bool:
    if not cleaned_line:
        return False
    if cleaned_line.startswith("#"):
        return False
    if re.match(r"(?i)^https?://", cleaned_line):
        return False
    return True


def parse_download_requests(text: str) -> list[str]:
    requested: list[str] = []
    lines = (text or "").splitlines()
    index = 0
    while index < len(lines):
        cleaned = _unwrapped_line(lines[index])
        inline_match = _DOWNLOAD_INLINE_PATTERN.match(cleaned)
        if inline_match:
            for raw in inline_match.group(1).split(","):
                value = _normalize_requested_path(raw)
                if value and value not in requested:
                    requested.append(value)
            index += 1
            continue
        if _DOWNLOAD_HEADER_PATTERN.match(cleaned):
            index += 1
            while index < len(lines):
                candidate = _unwrapped_line(lines[index])
                if not _looks_like_listed_path(candidate):
                    break
                for raw in candidate.split(","):
                    value = _normalize_requested_path(raw)
                    if value and value not in requested:
                        requested.append(value)
                index += 1
            continue
        index += 1
    return requested


def _export_settings(settings: AppSettings | None) -> AppSettings:
    return settings if settings is not None else SettingsStore().load()


def _resolve_requested_file(
    workspace: Path,
    relative: str,
    settings: AppSettings | None,
) -> tuple[str, Path]:
    if parse_external_context_reference(relative) is not None:
        external_file = resolve_external_context_file(
            workspace,
            _export_settings(settings),
            relative,
        )
        return external_file.archive_name, external_file.path

    path = resolve_workspace_target(workspace, relative, allow_missing=False)
    return Path(relative.replace("\\", "/")).as_posix(), path


def _project_metadata(workspace: Path) -> dict[str, object]:
    metadata = project_identity(workspace)
    metadata["instructions"] = (
        "Copy this file unchanged into every update ZIP returned for this project. "
        "BridgAI uses it to reject updates prepared for a different workspace. "
        "Files under __bridgai_external_contexts__/ are read-only reference material from "
        "additional contexts and must not be included as targets in update ZIPs."
    )
    return metadata


def validate_requested_files(
    workspace: Path,
    requested: list[str],
    *,
    settings: AppSettings | None = None,
) -> list[tuple[str, Path]]:
    if not requested:
        raise ValueError("Nessun comando #scarica rilevato.")
    valid: list[tuple[str, Path]] = []
    errors: list[str] = []
    for relative in requested:
        try:
            valid.append(_resolve_requested_file(workspace, relative, settings))
        except (SafetyError, ValueError) as exc:
            errors.append(f"{relative}: {exc}")
    if errors:
        raise ValueError("Richieste non valide:\n" + "\n".join(errors))
    return valid


def create_export_zip(
    workspace: Path,
    requested: list[str],
    destination: Path,
    *,
    settings: AppSettings | None = None,
) -> Path:
    valid = validate_requested_files(workspace, requested, settings=settings)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            PROJECT_METADATA_NAME,
            json.dumps(_project_metadata(workspace), ensure_ascii=False, indent=2),
        )
        for relative, path in valid:
            archive.write(path, arcname=relative)
    return destination


def validate_requested_files_resilient(
    workspace: Path,
    requested: list[str],
    *,
    settings: AppSettings | None = None,
) -> tuple[list[tuple[str, Path]], list[str]]:
    if not requested:
        raise ValueError("Nessun comando #scarica rilevato.")
    valid: list[tuple[str, Path]] = []
    errors: list[str] = []
    for relative in requested:
        try:
            valid.append(_resolve_requested_file(workspace, relative, settings))
        except Exception as exc:
            errors.append(f"{relative} (Errore: {exc})")
    return valid, errors


def create_export_zip_resilient(
    workspace: Path,
    requested: list[str],
    destination: Path,
    *,
    settings: AppSettings | None = None,
) -> tuple[Path, list[str], list[str]]:
    valid, errors = validate_requested_files_resilient(workspace, requested, settings=settings)
    if not valid:
        joined_errors = ", ".join(errors)
        raise ValueError(f"Nessuno dei file richiesti è stato trovato o è accessibile nel workspace: {joined_errors}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            PROJECT_METADATA_NAME,
            json.dumps(_project_metadata(workspace), ensure_ascii=False, indent=2),
        )
        for relative, path in valid:
            archive.write(path, arcname=relative)
    zipped_files = [item[0] for item in valid]
    missing_files = []
    requested_arc_names = []
    for relative in requested:
        try:
            requested_arc_names.append(_resolve_requested_file(workspace, relative, settings)[0])
        except Exception:
            requested_arc_names.append(relative)
    for relative, arc_name in zip(requested, requested_arc_names):
        if arc_name not in zipped_files:
            missing_files.append(relative)
    return destination, zipped_files, missing_files
