from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from local_ai_bridge.core.io import atomic_write
from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.core.safety import SafetyError, project_identity, resolve_workspace_target
from local_ai_bridge.services.exporting import validate_requested_files
from local_ai_bridge.services.patching import combine_patch_plans, inspect_full_file

FORMAT_MARKER = "<!-- BRIDGAI:MARKDOWN-EXCHANGE 1 -->"
FILE_MARKER = re.compile(r"^\s*<!--\s*BRIDGAI:FILE\s+(.+?)\s*-->\s*$", re.IGNORECASE)
PROJECT_MARKER = re.compile(r"^\s*<!--\s*BRIDGAI:PROJECT\s+(.+?)\s*-->\s*$", re.IGNORECASE)
TEXT_MARKER = re.compile(r"^\s*<!--\s*BRIDGAI:TEXT\s+final-newline=(0|1)\s*-->\s*$", re.IGNORECASE)
BINARY_MARKER = re.compile(r"^\s*<!--\s*BRIDGAI:BINARY\b.*-->\s*$", re.IGNORECASE)
FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})([^\r\n]*)$")

LANGUAGES = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "jsx",
    ".ts": "typescript", ".tsx": "tsx", ".json": "json", ".md": "markdown",
    ".html": "html", ".css": "css", ".scss": "scss", ".xml": "xml",
    ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".ini": "ini",
    ".sh": "bash", ".bash": "bash", ".ps1": "powershell", ".sql": "sql",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".java": "java",
    ".rs": "rust", ".go": "go", ".rb": "ruby", ".php": "php",
}


class MarkdownExchangeError(ValueError):
    """Raised when a Markdown Exchange document is present but invalid."""


class MarkdownExchangeNotFound(MarkdownExchangeError):
    """Raised when the text does not contain Markdown Exchange markers."""


def _line_text(line: str) -> str:
    return line.rstrip("\r\n")


def _fence_for(content: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def _is_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def encode_files_to_markdown(workspace: Path, requested: list[str]) -> str:
    valid = validate_requested_files(workspace, requested)
    identity = json.dumps(project_identity(workspace), ensure_ascii=False, separators=(",", ":"))
    parts = [FORMAT_MARKER, f"<!-- BRIDGAI:PROJECT {identity} -->", ""]
    for relative, path in valid:
        data = path.read_bytes()
        parts.append(f"<!-- BRIDGAI:FILE {relative} -->")
        if _is_binary(data):
            digest = hashlib.sha256(data).hexdigest()
            parts.extend((f"<!-- BRIDGAI:BINARY size={len(data)} sha256={digest} -->", ""))
            continue
        content = data.decode("utf-8")
        final_newline = int(content.endswith(("\n", "\r")))
        fence = _fence_for(content)
        parts.append(f"<!-- BRIDGAI:TEXT final-newline={final_newline} -->")
        parts.append(f"{fence}{LANGUAGES.get(path.suffix.lower(), 'text')}")
        parts.append(content + ("" if final_newline else "\n") + fence)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def markdown_export_path(workspace: Path, directory: Path) -> Path:
    """Return the stable per-project Markdown Exchange export path."""
    workspace = workspace.expanduser().resolve(strict=True)
    directory = directory.expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{workspace.name}_ai_context.md"


def export_files_to_markdown(workspace: Path, requested: list[str], directory: Path) -> Path:
    """Create or replace the single Markdown Exchange document for a project."""
    document = encode_files_to_markdown(workspace, requested)
    destination = markdown_export_path(workspace, directory)
    atomic_write(destination, document.encode("utf-8"))
    return destination


def _validate_project(workspace: Path, lines: list[str]) -> None:
    for number, line in enumerate(lines, start=1):
        raw = _line_text(line)
        if "BRIDGAI:PROJECT" not in raw.upper():
            continue
        match = PROJECT_MARKER.match(raw)
        if not match:
            raise MarkdownExchangeError(f"Riga {number}: marcatore BRIDGAI:PROJECT non valido.")
        try:
            received = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise MarkdownExchangeError(f"Riga {number}: metadati progetto non validi.") from exc
        expected = project_identity(workspace)
        if not isinstance(received, dict) or received.get("identity") != expected["identity"]:
            raise SafetyError("Il documento Markdown appartiene a un workspace differente.")
        return


def _as_patch_plan(plan: ChangePlan) -> ChangePlan:
    return ChangePlan(
        plan_type="patch", workspace=plan.workspace, source_path=plan.source_path,
        changes=plan.changes, diff=plan.diff, warnings=plan.warnings,
        metadata={**plan.metadata, "blocks": 1},
    )


def parse_markdown_response(workspace: Path, text: str) -> ChangePlan:
    lines = (text or "").splitlines(keepends=True)
    marker_hint = any("BRIDGAI:FILE" in line.upper() for line in lines)
    if not marker_hint:
        raise MarkdownExchangeNotFound("Nessun marcatore Markdown Exchange rilevato.")

    warnings: list[str] = []
    _validate_project(workspace, lines)
    plans: list[ChangePlan] = []
    seen: set[str] = set()
    index = 0
    while index < len(lines):
        raw = _line_text(lines[index])
        match = FILE_MARKER.match(raw)
        if not match:
            if "BRIDGAI:FILE" in raw.upper():
                warnings.append(f"Riga {index + 1}: marcatore BRIDGAI:FILE non valido ignorato.")
            index += 1
            continue

        target = match.group(1).strip().strip("`\"'").replace("\\", "/")
        resolved_target = resolve_workspace_target(workspace, target, allow_missing=True)
        target = resolved_target.relative_to(workspace.resolve()).as_posix()
        index += 1
        while index < len(lines) and not _line_text(lines[index]).strip():
            index += 1
        if target.casefold() == "commit-message.md":
            warnings.append("commit-message.md ignorato: è un metadato, non un file del progetto.")
            continue
        if index < len(lines) and BINARY_MARKER.match(_line_text(lines[index])):
            warnings.append(f"File binario ignorato: {target}")
            index += 1
            continue

        final_newline: bool | None = None
        if index < len(lines):
            text_match = TEXT_MARKER.match(_line_text(lines[index]))
            if text_match:
                final_newline = text_match.group(1) == "1"
                index += 1
        if index >= len(lines):
            warnings.append(f"Blocco mancante per {target}.")
            continue
        opening = FENCE_OPEN.match(_line_text(lines[index]))
        if not opening:
            warnings.append(f"Code fence mancante per {target}.")
            continue

        fence = opening.group(1)
        fence_char = fence[0]
        index += 1
        start = index
        while index < len(lines):
            candidate = _line_text(lines[index]).strip()
            if candidate and set(candidate) == {fence_char} and len(candidate) == len(fence):
                break
            index += 1
        if index >= len(lines):
            warnings.append(f"Code fence non chiusa per {target}.")
            continue

        content = "".join(lines[start:index])
        if final_newline is False:
            content = re.sub(r"(?:\r\n|\r|\n)$", "", content, count=1)
        key = target.casefold()
        if key in seen:
            raise MarkdownExchangeError(f"Target duplicato nel documento Markdown: {target}")
        seen.add(key)
        try:
            plans.append(_as_patch_plan(inspect_full_file(workspace, target, content, strip_fence=False)))
        except (SafetyError, SyntaxError):
            raise
        except Exception as exc:
            raise MarkdownExchangeError(f"Contenuto non valido per {target}: {exc}") from exc
        index += 1

    if not plans:
        raise MarkdownExchangeError("Nessun file testuale applicabile trovato nel documento Markdown.")
    plan = combine_patch_plans(
        workspace,
        plans,
        metadata={"provider": "markdown_exchange", "format_version": 1, "targets": sorted(seen)},
    )
    plan.warnings.extend(warnings)
    return plan
