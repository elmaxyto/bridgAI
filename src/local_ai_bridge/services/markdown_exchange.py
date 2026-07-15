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
FILE_MARKER = re.compile(r"^\s*(?:<!--\s*)?BRIDGAI:FILE\s+(.+?)(?:\s*-->)?\s*$", re.IGNORECASE)
PROJECT_MARKER = re.compile(r"^\s*(?:<!--\s*)?BRIDGAI:PROJECT\s+(.+?)(?:\s*-->)?\s*$", re.IGNORECASE)
TEXT_MARKER = re.compile(r"^\s*(?:<!--\s*)?BRIDGAI:TEXT\s+final-newline=(0|1)(?:\s*-->)?\s*$", re.IGNORECASE)
BINARY_MARKER = re.compile(r"^\s*(?:<!--\s*)?BRIDGAI:BINARY\b.*(?:\s*-->)?\s*$", re.IGNORECASE)
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

_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _stronger_severity(current: str, candidate: str) -> str:
    return candidate if _SEVERITY_RANK[candidate] > _SEVERITY_RANK[current] else current


def _recovery_action(action: str, severity: str, detail: str, target: str = "") -> dict[str, str]:
    item = {"action": action, "severity": severity, "detail": detail}
    if target:
        item["target"] = target
    return item


class MarkdownExchangeError(ValueError):
    """Raised when a Markdown Exchange document is present but invalid."""


class MarkdownExchangeNotFound(MarkdownExchangeError):
    """Raised when the text does not contain Markdown Exchange markers."""


def _line_text(line: str) -> str:
    return line.rstrip("\r\n")


def _is_closing_fence(line: str, opening_fence: str) -> bool:
    candidate = _line_text(line).strip()
    return (
        bool(candidate)
        and set(candidate) == {opening_fence[0]}
        and len(candidate) >= len(opening_fence)
    )


def _normalized_marker_target(raw: str) -> str:
    target = raw.strip().strip("`\"'").replace("\\", "/")
    while target.startswith("./"):
        target = target[2:]
    return target


def extract_commit_message_metadata(text: str) -> tuple[str, str | None]:
    """Remove and return the optional root ``commit-message.md`` metadata block.

    Markdown updates use the same metadata name as ZIP updates, represented as a
    Markdown Exchange file block. The block is never applied to the workspace.
    Keeping extraction here lets desktop, Web uploads, pasted updates, and direct
    Markdown Exchange parsing share one strict implementation.
    """
    lines = (text or "").splitlines(keepends=True)
    output: list[str] = []
    commit_message: str | None = None
    active_fence: str | None = None
    index = 0

    while index < len(lines):
        raw = _line_text(lines[index])
        if active_fence is not None:
            output.append(lines[index])
            if _is_closing_fence(lines[index], active_fence):
                active_fence = None
            index += 1
            continue

        opening = FENCE_OPEN.match(raw)
        if opening:
            active_fence = opening.group(1)
            output.append(lines[index])
            index += 1
            continue

        match = FILE_MARKER.match(raw)
        target = _normalized_marker_target(match.group(1)) if match else ""
        if target.casefold() != "commit-message.md":
            output.append(lines[index])
            index += 1
            continue

        if commit_message is not None:
            raise MarkdownExchangeError(
                "commit-message.md compare più di una volta nel documento Markdown."
            )
        marker_line = index + 1
        index += 1
        while index < len(lines) and not _line_text(lines[index]).strip():
            index += 1

        final_newline: bool | None = None
        if index < len(lines):
            text_match = TEXT_MARKER.match(_line_text(lines[index]))
            if text_match:
                final_newline = text_match.group(1) == "1"
                index += 1
                while index < len(lines) and not _line_text(lines[index]).strip():
                    index += 1

        if index < len(lines) and BINARY_MARKER.match(_line_text(lines[index])):
            raise MarkdownExchangeError(
                f"Riga {marker_line}: commit-message.md deve essere testo UTF-8."
            )
        if index >= len(lines):
            raise MarkdownExchangeError(
                f"Riga {marker_line}: contenuto commit-message.md mancante."
            )
        opening = FENCE_OPEN.match(_line_text(lines[index]))
        if not opening:
            raise MarkdownExchangeError(
                f"Riga {marker_line}: code fence mancante per commit-message.md."
            )

        fence = opening.group(1)
        index += 1
        start = index
        while index < len(lines) and not _is_closing_fence(lines[index], fence):
            index += 1
        if index >= len(lines):
            raise MarkdownExchangeError(
                f"Riga {marker_line}: code fence non chiusa per commit-message.md."
            )

        content = "".join(lines[start:index])
        if final_newline is False:
            content = re.sub(r"(?:\r\n|\r|\n)$", "", content, count=1)
        commit_message = content.strip()
        if not commit_message:
            raise MarkdownExchangeError(
                f"Riga {marker_line}: commit-message.md è vuoto."
            )
        index += 1

    return "".join(output), commit_message


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


def encode_files_to_markdown_resilient(workspace: Path, requested: list[str]) -> tuple[str, list[str], list[str]]:
    from local_ai_bridge.services.exporting import validate_requested_files_resilient
    valid, errors = validate_requested_files_resilient(workspace, requested)
    if not valid:
        joined_errors = ", ".join(errors)
        raise ValueError(f"Nessuno dei file richiesti è stato trovato o è accessibile nel workspace: {joined_errors}")
    identity = json.dumps(project_identity(workspace), ensure_ascii=False, separators=(",", ":"))
    parts = [FORMAT_MARKER, f"<!-- BRIDGAI:PROJECT {identity} -->", ""]
    zipped_files = []
    for relative, path in valid:
        data = path.read_bytes()
        parts.append(f"<!-- BRIDGAI:FILE {relative} -->")
        zipped_files.append(relative)
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
    missing_files = []
    for relative in requested:
        normalized = Path(relative.replace("\\", "/")).as_posix()
        if normalized not in zipped_files:
            missing_files.append(relative)
    return "\n".join(parts).rstrip() + "\n", zipped_files, missing_files


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
    text, commit_message = extract_commit_message_metadata(text)
    lines = text.splitlines(keepends=True)
    marker_hint = any("BRIDGAI:FILE" in line.upper() for line in lines)
    if not marker_hint:
        raise MarkdownExchangeNotFound("Nessun marcatore Markdown Exchange rilevato.")

    warnings: list[str] = []
    recovery_actions: list[dict[str, str]] = []
    recovery_severity = "none"
    _validate_project(workspace, lines)
    plans: list[ChangePlan] = []
    seen: set[str] = set()
    index = 0
    while index < len(lines):
        raw = _line_text(lines[index])
        match = FILE_MARKER.match(raw)
        if not match:
            if "BRIDGAI:FILE" in raw.upper():
                detail = f"Riga {index + 1}: marcatore BRIDGAI:FILE non valido ignorato."
                warnings.append(detail)
                recovery_actions.append(_recovery_action("invalid_file_marker_ignored", "low", detail))
                recovery_severity = _stronger_severity(recovery_severity, "low")
            index += 1
            continue

        if not raw.lstrip().startswith("<!--"):
            detail = f"Riga {index + 1}: marker BRIDGAI:FILE senza commento HTML accettato."
            recovery_actions.append(_recovery_action("plain_file_marker", "low", detail))
            recovery_severity = _stronger_severity(recovery_severity, "low")
        target = match.group(1).strip().strip("`\"'").replace("\\", "/")
        resolved_target = resolve_workspace_target(workspace, target, allow_missing=True)
        target = resolved_target.relative_to(workspace.resolve()).as_posix()
        if target.casefold() == "commit-message.md":
            raise MarkdownExchangeError(
                "commit-message.md deve essere dichiarato come metadato root con "
                "il percorso canonico esatto."
            )
        index += 1
        while index < len(lines) and not _line_text(lines[index]).strip():
            index += 1
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
        closed_fence = False
        while index < len(lines):
            candidate = _line_text(lines[index]).strip()
            if candidate and set(candidate) == {fence_char} and len(candidate) >= len(fence):
                closed_fence = True
                break
            if FILE_MARKER.match(_line_text(lines[index])) and index > start:
                detail = f"Code fence non chiusa per {target}: chiusura inferita prima del file successivo."
                warnings.append(detail)
                recovery_actions.append(_recovery_action("missing_code_fence", "high", detail, target))
                recovery_severity = _stronger_severity(recovery_severity, "high")
                break
            index += 1
        if not closed_fence and index >= len(lines):
            detail = f"Code fence non chiusa per {target}: chiusura inferita a fine documento."
            warnings.append(detail)
            recovery_actions.append(_recovery_action("missing_code_fence_at_eof", "high", detail, target))
            recovery_severity = _stronger_severity(recovery_severity, "high")

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
        if closed_fence:
            index += 1

    if not plans:
        raise MarkdownExchangeError("Nessun file testuale applicabile trovato nel documento Markdown.")
    metadata = {
        "provider": "markdown_exchange",
        "format_version": 1,
        "targets": sorted(seen),
    }
    if commit_message is not None:
        metadata["commit_message"] = commit_message
    plan = combine_patch_plans(
        workspace,
        plans,
        metadata=metadata,
    )
    plan.warnings.extend(warnings)
    plan.metadata["recovery_actions"] = recovery_actions
    plan.metadata["recovery_severity"] = recovery_severity
    plan.metadata["requires_explicit_confirmation"] = recovery_severity == "high"
    if plan.metadata["requires_explicit_confirmation"]:
        plan.warnings.append(
            "Il documento Markdown Exchange richiede recuperi ad alta severità: "
            "controlla attentamente il diff prima di applicare."
        )
    return plan
