from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from local_ai_bridge.core.io import sha256_bytes, sha256_file
from local_ai_bridge.core.models import ChangePlan, FileChange
from local_ai_bridge.core.safety import resolve_workspace_target


PATCH_PATTERN = re.compile(
    r"<{7}\s*SEARCH\s*\r?\n(.*?)\r?\n={7}\s*\r?\n(.*?)\r?\n>{7}\s*REPLACE",
    re.DOTALL | re.IGNORECASE,
)
FENCE_PATTERN = re.compile(r"^\s*```(?:[\w.+-]+)?\s*\n(.*)\n```\s*$", re.DOTALL)
SEARCH_MARKER = re.compile(r"^<{7,}\s*SEARCH\s*$", re.IGNORECASE)
SEPARATOR_MARKER = re.compile(r"^={7,}\s*$")
REPLACE_MARKER = re.compile(r"^>{7,}\s*REPLACE\s*$", re.IGNORECASE)
END_FILE_MARKER = re.compile(r"^END_FILE\s*$", re.IGNORECASE)
PATH_PREFIX = re.compile(
    r"^(?P<label>BEGIN_FILE|FILE(?:\s+TARGET)?|PERCORSO(?:\s+FILE)?|PATH|TARGET)\s*:\s*(?P<path>.*?)\s*$",
    re.IGNORECASE,
)
MARKDOWN_PREFIX = re.compile(r"^(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)")
MARKER_HINT = re.compile(
    r"^(?:<+\s*SEARCH\b|>+\s*REPLACE\b|={5,}\s*$)",
    re.IGNORECASE,
)


def _newline_style(text: str) -> str:
    return "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_outer_fence(text: str) -> str:
    match = FENCE_PATTERN.match(text)
    return match.group(1) if match else text


@dataclass(slots=True)
class PatchApplication:
    new_text: str
    block_count: int


@dataclass(slots=True, frozen=True)
class GeminiFilePatch:
    target: str
    patch_text: str
    block_count: int
    first_block_line: int
    block_lines: tuple[int, ...]


@dataclass(slots=True, frozen=True)
class GeminiPatchDocument:
    files: tuple[GeminiFilePatch, ...]
    block_count: int
    ignored_block_count: int = 0

    def as_pairs(self) -> list[tuple[str, str]]:
        return [(item.target, item.patch_text) for item in self.files]


class GeminiPatchParseError(ValueError):
    """Raised when a Gemini patch response is incomplete or ambiguous."""


def apply_search_replace(original: str, patch_text: str) -> PatchApplication:
    matches = list(PATCH_PATTERN.finditer(patch_text))
    if not matches:
        raise ValueError("Nessun blocco SEARCH/REPLACE valido rilevato.")
    style = _newline_style(original)
    current = _normalize(original)
    for index, match in enumerate(matches, start=1):
        search = _normalize(match.group(1))
        replacement = _normalize(match.group(2))
        occurrences = current.count(search)
        if occurrences == 0:
            raise ValueError(f"Blocco {index}: testo SEARCH non trovato.")
        if occurrences > 1:
            raise ValueError(f"Blocco {index}: testo SEARCH ambiguo ({occurrences} corrispondenze).")
        current = current.replace(search, replacement, 1)
    if style != "\n":
        current = current.replace("\n", style)
    return PatchApplication(current, len(matches))


def _diff(relative: str, old: str, new: str) -> str:
    return "\n".join(difflib.unified_diff(
        old.splitlines(), new.splitlines(), fromfile=f"a/{relative}", tofile=f"b/{relative}", lineterm="",
    ))


def _parse_error(line_number: int, message: str) -> GeminiPatchParseError:
    return GeminiPatchParseError(f"Riga {line_number}: {message}")


def _normalize_gemini_path(raw: str, *, explicit: bool) -> str | None:
    candidate = raw.strip().replace("**", "").replace("__", "").strip()
    candidate = candidate.strip("`\"'").rstrip(":,;").replace("\\", "/")
    if candidate.startswith("./"):
        candidate = candidate[2:]
    if not candidate or candidate.startswith(("/", "~/", "//")) or "://" in candidate:
        return None
    if re.match(r"^[A-Za-z]:/", candidate):
        return None
    if any(char in candidate for char in "<>|?*\x00"):
        return None
    if candidate.endswith("/"):
        return None
    if any(char.isspace() for char in candidate) and not explicit:
        return None

    path = PurePosixPath(candidate)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if any(":" in part for part in path.parts):
        return None
    if not explicit and "/" not in candidate and "." not in path.name:
        return None
    return path.as_posix()


def _gemini_path_declaration(line: str, line_number: int) -> tuple[str, bool] | None:
    raw = line.strip()
    if not raw or raw.startswith("```"):
        return None

    cleaned = MARKDOWN_PREFIX.sub("", raw).strip()
    cleaned = cleaned.replace("**", "").replace("__", "").strip()
    match = PATH_PREFIX.match(cleaned)
    if match:
        path = _normalize_gemini_path(match.group("path"), explicit=True)
        if path is None:
            raise _parse_error(
                line_number,
                "percorso FILE non valido: usa un percorso relativo interno al workspace, senza .. o unità disco.",
            )
        return path, True

    inline_match = re.fullmatch(r"`([^`]+)`\s*:?\s*", cleaned)
    if inline_match:
        path = _normalize_gemini_path(inline_match.group(1), explicit=True)
        return (path, False) if path else None

    path = _normalize_gemini_path(cleaned, explicit=False)
    return (path, False) if path else None


def _is_fence_line(line: str) -> bool:
    return line.strip().startswith("```")


def _raise_if_malformed_marker(line: str, line_number: int) -> None:
    stripped = line.strip()
    if MARKER_HINT.match(stripped):
        raise _parse_error(
            line_number,
            "marcatore patch non valido. Usa esattamente <<<<<<< SEARCH, ======= e >>>>>>> REPLACE.",
        )


def _canonical_patch_block(search_lines: list[str], replacement_lines: list[str]) -> str:
    return (
        "<<<<<<< SEARCH\n"
        + "\n".join(search_lines)
        + "\n=======\n"
        + "\n".join(replacement_lines)
        + "\n>>>>>>> REPLACE"
    )


def parse_gemini_patch_document(text: str) -> GeminiPatchDocument:
    """Parse all Gemini SEARCH/REPLACE blocks without silently ignoring malformed ones."""
    lines = _normalize(text).split("\n")
    grouped_blocks: dict[str, list[str]] = {}
    grouped_lines: dict[str, list[int]] = {}
    current_path: str | None = None
    current_path_explicit = False
    pending_explicit_line: int | None = None
    pending_explicit_has_block = False
    soft_path_usable = False
    index = 0

    def finish_pending_declaration() -> None:
        if pending_explicit_line is not None and not pending_explicit_has_block:
            raise _parse_error(
                pending_explicit_line,
                "il percorso FILE dichiarato non contiene alcun blocco SEARCH/REPLACE.",
            )

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        line_number = index + 1

        if SEARCH_MARKER.match(stripped):
            if current_path is None or not soft_path_usable:
                raise _parse_error(
                    line_number,
                    "ogni blocco SEARCH/REPLACE deve essere preceduto da FILE: percorso/relativo.ext.",
                )

            search_lines: list[str] = []
            replacement_lines: list[str] = []
            separator_seen = False
            block_start_line = line_number
            index += 1

            while index < len(lines):
                block_line = lines[index]
                block_stripped = block_line.strip()
                block_line_number = index + 1

                if SEARCH_MARKER.match(block_stripped):
                    raise _parse_error(block_line_number, "trovato un nuovo SEARCH prima della chiusura del blocco precedente.")
                if SEPARATOR_MARKER.match(block_stripped):
                    if separator_seen:
                        raise _parse_error(block_line_number, "il blocco contiene più di un separatore =======.")
                    separator_seen = True
                    index += 1
                    continue
                if REPLACE_MARKER.match(block_stripped):
                    if not separator_seen:
                        raise _parse_error(block_line_number, "marcatore REPLACE trovato prima del separatore =======.")
                    break

                _raise_if_malformed_marker(block_line, block_line_number)
                if separator_seen:
                    replacement_lines.append(block_line)
                else:
                    search_lines.append(block_line)
                index += 1
            else:
                raise _parse_error(block_start_line, "blocco SEARCH/REPLACE incompleto: manca >>>>>>> REPLACE.")

            if not separator_seen:
                raise _parse_error(block_start_line, "blocco SEARCH/REPLACE senza separatore =======.")
            if not "\n".join(search_lines):
                raise _parse_error(block_start_line, "il contenuto SEARCH è vuoto e non può essere applicato in sicurezza.")

            grouped_blocks.setdefault(current_path, []).append(
                _canonical_patch_block(search_lines, replacement_lines)
            )
            grouped_lines.setdefault(current_path, []).append(block_start_line)
            if current_path_explicit:
                pending_explicit_has_block = True
            soft_path_usable = True
            index += 1
            continue

        if SEPARATOR_MARKER.match(stripped):
            raise _parse_error(line_number, "separatore ======= trovato fuori da un blocco SEARCH/REPLACE.")
        if REPLACE_MARKER.match(stripped):
            raise _parse_error(line_number, "marcatore REPLACE trovato senza un blocco SEARCH aperto.")
        _raise_if_malformed_marker(line, line_number)

        if END_FILE_MARKER.match(stripped):
            finish_pending_declaration()
            current_path = None
            current_path_explicit = False
            pending_explicit_line = None
            pending_explicit_has_block = False
            soft_path_usable = False
            index += 1
            continue

        declaration = _gemini_path_declaration(line, line_number)
        if declaration is not None:
            finish_pending_declaration()
            current_path, current_path_explicit = declaration
            pending_explicit_line = line_number if current_path_explicit else None
            pending_explicit_has_block = False
            soft_path_usable = True
            index += 1
            continue

        if stripped and not _is_fence_line(line):
            soft_path_usable = False
        index += 1

    finish_pending_declaration()

    if not grouped_blocks:
        raise GeminiPatchParseError("Nessun blocco SEARCH/REPLACE trovato nella risposta di Gemini.")

    files = tuple(
        GeminiFilePatch(
            target=target,
            patch_text="\n\n".join(blocks),
            block_count=len(blocks),
            first_block_line=grouped_lines[target][0],
            block_lines=tuple(grouped_lines[target]),
        )
        for target, blocks in grouped_blocks.items()
    )
    return GeminiPatchDocument(
        files=files,
        block_count=sum(item.block_count for item in files),
        ignored_block_count=0,
    )


def parse_gemini_patch_response(text: str) -> list[tuple[str, str]]:
    """Compatibility API returning target/patch pairs from a Gemini response."""
    return parse_gemini_patch_document(text).as_pairs()


def combine_patch_plans(
    workspace: Path,
    plans: list[ChangePlan],
    *,
    metadata: dict | None = None,
) -> ChangePlan:
    """Combine validated single-file patch plans into one applicable plan."""
    if not plans:
        raise ValueError("Nessun piano patch da combinare.")

    resolved_workspace = workspace.resolve()
    changes: list[FileChange] = []
    diff_parts: list[str] = []
    warnings: list[str] = []
    contents: dict[str, bytes] = {}
    total_blocks = 0

    for plan in plans:
        if plan.plan_type != "patch":
            raise ValueError("È possibile combinare soltanto piani di tipo patch.")
        if plan.workspace.resolve() != resolved_workspace:
            raise ValueError("I piani patch appartengono a workspace differenti.")

        plan_contents = plan.metadata.get("contents")
        if not isinstance(plan_contents, dict):
            raise ValueError("Un piano patch non contiene dati applicabili.")

        for change in plan.changes:
            if change.target in contents:
                raise ValueError(f"Target duplicato nel piano patch: {change.target}")
            data = plan_contents.get(change.target)
            if not isinstance(data, bytes):
                raise ValueError(f"Contenuto mancante per {change.target}")
            contents[change.target] = data
            changes.append(change)

        if plan.diff:
            diff_parts.append(plan.diff.rstrip())
        warnings.extend(plan.warnings)
        blocks = plan.metadata.get("blocks", 0)
        if isinstance(blocks, int):
            total_blocks += blocks

    combined_metadata = dict(metadata or {})
    combined_metadata["contents"] = contents
    combined_metadata["blocks"] = total_blocks
    combined_diff = "\n\n".join(diff_parts)
    if combined_diff:
        combined_diff += "\n"

    return ChangePlan(
        plan_type="patch",
        workspace=resolved_workspace,
        source_path=None,
        changes=changes,
        diff=combined_diff,
        warnings=warnings,
        metadata=combined_metadata,
    )


def inspect_patch(workspace: Path, target_relative: str, patch_text: str) -> ChangePlan:
    target = resolve_workspace_target(workspace, target_relative, allow_missing=False)
    old_bytes = target.read_bytes()
    old = old_bytes.decode("utf-8")
    applied = apply_search_replace(old, patch_text)
    new_bytes = applied.new_text.encode("utf-8")
    relative = target.relative_to(workspace.resolve()).as_posix()
    return ChangePlan(
        plan_type="patch", workspace=workspace.resolve(), source_path=None,
        changes=[FileChange(relative, relative, "modify", sha256_file(target), sha256_bytes(new_bytes), size=len(new_bytes))],
        diff=_diff(relative, old, applied.new_text),
        metadata={"contents": {relative: new_bytes}, "blocks": applied.block_count},
    )


def inspect_gemini_response(workspace: Path, text: str) -> ChangePlan:
    """Build one reviewable and applicable plan from a complete Gemini response."""
    document = parse_gemini_patch_document(text)
    plans: list[ChangePlan] = []
    for item in document.files:
        try:
            plans.append(inspect_patch(workspace, item.target, item.patch_text))
        except Exception as exc:
            raise ValueError(
                f"File {item.target} (primo blocco alla riga {item.first_block_line}): {exc}"
            ) from exc

    targets = [item.target for item in document.files]
    return combine_patch_plans(
        workspace,
        plans,
        metadata={
            "provider": "gemini",
            "targets": targets,
            "import_summary": {
                "files": len(document.files),
                "blocks": document.block_count,
                "ignored_blocks": document.ignored_block_count,
                "targets": targets,
            },
        },
    )


def inspect_full_file(
    workspace: Path,
    target_relative: str,
    content: str,
    *,
    strip_fence: bool = True,
) -> ChangePlan:
    target = resolve_workspace_target(workspace, target_relative, allow_missing=True)
    clean = strip_outer_fence(content) if strip_fence else content
    new_bytes = clean.encode("utf-8")
    if target.suffix.lower() == ".py":
        compile(clean, target_relative, "exec")
    if target.exists():
        old_bytes = target.read_bytes()
        try:
            old = old_bytes.decode("utf-8")
            diff = _diff(target_relative, old, clean)
        except UnicodeDecodeError:
            diff = f"File binario sostituito: {target_relative}"
        kind = "modify"
        old_hash = sha256_file(target)
    else:
        diff = _diff(target_relative, "", clean)
        kind = "create"
        old_hash = None
    relative = target.relative_to(workspace.resolve()).as_posix()
    return ChangePlan(
        plan_type="full_file", workspace=workspace.resolve(), source_path=None,
        changes=[FileChange(relative, relative, kind, old_hash, sha256_bytes(new_bytes), size=len(new_bytes))],
        diff=diff,
        metadata={"contents": {relative: new_bytes}},
    )
