from __future__ import annotations

import codecs
import difflib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from local_ai_bridge.core.io import sha256_bytes, sha256_file
from local_ai_bridge.core.models import ChangePlan, FileChange
from local_ai_bridge.core.safety import resolve_workspace_target


_FIELD_SEPARATOR = r"\s*(?::|=|：)\s*"
BEGIN_FILE_MARKER = re.compile(
    r"^(?:BEGIN[ _-]?FILE|FILE[ _-]?BEGIN|INIZIO[ _-]?FILE)\s*:?[\s]*$",
    re.IGNORECASE,
)
END_FILE_MARKER = re.compile(
    r"^(?:END[ _-]?FILE|FILE[ _-]?END|FINE[ _-]?FILE)\s*:?[\s]*$",
    re.IGNORECASE,
)
OPERATION_LINE = re.compile(
    rf"^(?:OPERATION|OPERAZIONE){_FIELD_SEPARATOR}(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
PATH_LINE = re.compile(
    rf"^(?:PATH|FILE[ _-]?PATH|TARGET|FILE|PERCORSO){_FIELD_SEPARATOR}(?P<path>.*?)\s*$",
    re.IGNORECASE,
)
FINAL_NEWLINE_LINE = re.compile(
    rf"^(?:FINAL[ _-]?NEWLINE|TRAILING[ _-]?NEWLINE|"
    rf"NEWLINE[ _-]?FINALE|NUOVA[ _-]?RIGA[ _-]?FINALE)"
    rf"{_FIELD_SEPARATOR}(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
CONTENT_LINE = re.compile(r"^(?:CONTENT|CONTENUTO)\s*:?[\s]*$", re.IGNORECASE)
CODE_FENCE_LINE = re.compile(r"^(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$")

_OPERATION_ALIASES = {
    "CREATE": "CREATE",
    "ADD": "CREATE",
    "NEW": "CREATE",
    "CREA": "CREATE",
    "REPLACE": "REPLACE",
    "UPDATE": "REPLACE",
    "MODIFY": "REPLACE",
    "OVERWRITE": "REPLACE",
    "SOSTITUISCI": "REPLACE",
    "AGGIORNA": "REPLACE",
    "MODIFICA": "REPLACE",
    "DELETE": "DELETE",
    "REMOVE": "DELETE",
    "ELIMINA": "DELETE",
    "RIMUOVI": "DELETE",
}
_FINAL_NEWLINE_ALIASES = {
    "YES": True,
    "Y": True,
    "TRUE": True,
    "SI": True,
    "SÌ": True,
    "NO": False,
    "N": False,
    "FALSE": False,
}


@dataclass(slots=True, frozen=True)
class TextFileOperation:
    operation: str
    target: str
    content: str | None
    declaration_line: int
    final_newline: bool | None = None


@dataclass(slots=True, frozen=True)
class TextFileOperationsDocument:
    operations: tuple[TextFileOperation, ...]
    ignored_lines: tuple[int, ...] = ()
    normalizations: tuple[str, ...] = ()


class TextFileOperationsParseError(ValueError):
    """Raised when a structured full-file response is malformed."""


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_error(line_number: int, message: str) -> TextFileOperationsParseError:
    return TextFileOperationsParseError(f"Riga {line_number}: {message}")


def _strip_scalar_markup(value: str) -> str:
    candidate = value.strip()
    wrappers = (("**", "**"), ("__", "__"), ("`", "`"), ('"', '"'), ("'", "'"))
    changed = True
    while changed and candidate:
        changed = False
        for opening, closing in wrappers:
            if (
                candidate.startswith(opening)
                and candidate.endswith(closing)
                and len(candidate) >= len(opening) + len(closing)
            ):
                candidate = candidate[len(opening):-len(closing)].strip()
                changed = True
                break
    return candidate


def _control_text(line: str) -> str:
    candidate = line.strip().lstrip("\ufeff")
    while candidate.startswith(">"):
        candidate = candidate[1:].lstrip()
    candidate = re.sub(r"^(?:#{1,6}\s+|[-+*]\s+)", "", candidate)
    return _strip_scalar_markup(candidate)


def _normalize_operation(raw: str, line_number: int) -> str:
    value = _strip_scalar_markup(raw).strip().upper()
    operation = _OPERATION_ALIASES.get(value)
    if operation is None:
        raise _parse_error(
            line_number,
            "operazione non valida. Usa un solo valore: CREATE, REPLACE oppure DELETE.",
        )
    return operation


def _normalize_final_newline(raw: str, line_number: int) -> bool:
    value = _strip_scalar_markup(raw).strip().upper()
    result = _FINAL_NEWLINE_ALIASES.get(value)
    if result is None:
        raise _parse_error(
            line_number,
            "FINAL_NEWLINE non valido. Usa un solo valore: YES oppure NO.",
        )
    return result


def _normalize_relative_path(raw: str) -> str | None:
    candidate = _strip_scalar_markup(raw).replace("\\", "/")
    if candidate.startswith("./"):
        candidate = candidate[2:]
    if not candidate or candidate.startswith(("/", "~/", "//")) or "://" in candidate:
        return None
    if re.match(r"^[A-Za-z]:/", candidate):
        return None
    if any(char in candidate for char in "<>|?*\x00") or candidate.endswith("/"):
        return None

    path = PurePosixPath(candidate)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if any(":" in part for part in path.parts):
        return None
    return path.as_posix()


def _is_closing_fence(line: str, opening_fence: str) -> bool:
    candidate = line.strip()
    return (
        len(candidate) >= len(opening_fence)
        and candidate
        and set(candidate) == {opening_fence[0]}
        and candidate[0] == opening_fence[0]
    )


def _is_orphan_control_line(line: str) -> bool:
    return bool(
        END_FILE_MARKER.match(line)
        or OPERATION_LINE.match(line)
        or PATH_LINE.match(line)
        or FINAL_NEWLINE_LINE.match(line)
        or CONTENT_LINE.match(line)
    )


def parse_text_file_operations(text: str) -> TextFileOperationsDocument:
    """Parse complete text-file operations while tolerating harmless Markdown wrappers."""
    lines = _normalize(text).split("\n")
    operations: list[TextFileOperation] = []
    ignored_lines: list[int] = []
    normalizations: list[str] = []
    seen: set[str] = set()
    index = 0

    while index < len(lines):
        control = _control_text(lines[index])
        if not control:
            index += 1
            continue
        if not BEGIN_FILE_MARKER.match(control):
            if _is_orphan_control_line(control):
                raise _parse_error(
                    index + 1,
                    "marcatore o campo strutturato trovato fuori da un blocco "
                    "BEGIN_FILE / END_FILE.",
                )
            ignored_lines.append(index + 1)
            index += 1
            continue

        declaration_line = index + 1
        index += 1
        fields: dict[str, object] = {}
        while index < len(lines):
            current = _control_text(lines[index])
            if not current:
                index += 1
                continue
            operation_match = OPERATION_LINE.match(current)
            path_match = PATH_LINE.match(current)
            newline_match = FINAL_NEWLINE_LINE.match(current)
            if operation_match:
                if "operation" in fields:
                    raise _parse_error(index + 1, "OPERATION dichiarata più di una volta.")
                fields["operation"] = _normalize_operation(
                    operation_match.group("value"),
                    index + 1,
                )
                index += 1
                continue
            if path_match:
                if "path" in fields:
                    raise _parse_error(index + 1, "PATH dichiarato più di una volta.")
                target = _normalize_relative_path(path_match.group("path"))
                if target is None:
                    raise _parse_error(index + 1, "percorso relativo non valido.")
                fields["path"] = target
                index += 1
                continue
            if newline_match:
                if "final_newline" in fields:
                    raise _parse_error(index + 1, "FINAL_NEWLINE dichiarato più di una volta.")
                fields["final_newline"] = _normalize_final_newline(
                    newline_match.group("value"),
                    index + 1,
                )
                index += 1
                continue
            break

        operation = fields.get("operation")
        target = fields.get("path")
        if operation is None:
            raise _parse_error(
                declaration_line,
                "manca OPERATION: CREATE, REPLACE oppure DELETE.",
            )
        if target is None:
            raise _parse_error(
                declaration_line,
                "manca PATH: percorso/relativo/file.ext.",
            )
        assert isinstance(operation, str)
        assert isinstance(target, str)

        key = target.casefold()
        if key in seen:
            raise _parse_error(declaration_line, f"target duplicato: {target}.")
        seen.add(key)

        if operation == "DELETE":
            if "final_newline" in fields:
                raise _parse_error(
                    declaration_line,
                    "DELETE non deve dichiarare FINAL_NEWLINE.",
                )
            if index >= len(lines) or not END_FILE_MARKER.match(
                _control_text(lines[index])
            ):
                if index < len(lines) and CONTENT_LINE.match(_control_text(lines[index])):
                    raise _parse_error(index + 1, "DELETE non deve contenere CONTENT.")
                raise _parse_error(declaration_line, f"manca END_FILE per {target}.")
            operations.append(
                TextFileOperation(operation, target, None, declaration_line)
            )
            index += 1
            continue

        if index >= len(lines) or not CONTENT_LINE.match(_control_text(lines[index])):
            unexpected = _control_text(lines[index]) if index < len(lines) else ""
            if unexpected:
                raise _parse_error(
                    index + 1,
                    f"campo non riconosciuto prima di CONTENT per {target}: {unexpected!r}.",
                )
            raise _parse_error(declaration_line, f"manca CONTENT per {target}.")
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            raise _parse_error(
                declaration_line,
                f"contenuto completo mancante per {target}.",
            )

        fence_match = CODE_FENCE_LINE.match(lines[index].strip())
        content_lines: list[str] = []
        if fence_match is None:
            content_start_line = index + 1
            while index < len(lines) and not END_FILE_MARKER.match(
                _control_text(lines[index])
            ):
                content_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                raise _parse_error(
                    content_start_line,
                    "CONTENT senza fence Markdown: manca END_FILE per chiudere il contenuto.",
                )
            normalizations.append(
                f"{target}: contenuto accettato senza fence Markdown "
                f"a partire dalla riga {content_start_line}."
            )
            index += 1
        else:
            opening_fence = fence_match.group("fence")
            index += 1
            while index < len(lines) and not _is_closing_fence(
                lines[index],
                opening_fence,
            ):
                content_lines.append(lines[index])
                index += 1
            if index >= len(lines):
                raise _parse_error(
                    declaration_line,
                    f"blocco di codice non chiuso per {target}.",
                )
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            if index >= len(lines) or not END_FILE_MARKER.match(
                _control_text(lines[index])
            ):
                raise _parse_error(declaration_line, f"manca END_FILE per {target}.")
            index += 1

        content = "\n".join(content_lines)
        final_newline = fields.get("final_newline")
        assert final_newline is None or isinstance(final_newline, bool)
        operations.append(
            TextFileOperation(
                operation,
                target,
                content,
                declaration_line,
                final_newline,
            )
        )

    if not operations:
        raise TextFileOperationsParseError(
            "Nessuna operazione file completa rilevata. "
            "Usa BEGIN_FILE, OPERATION, PATH, CONTENT ed END_FILE."
        )
    return TextFileOperationsDocument(
        tuple(operations),
        tuple(ignored_lines),
        tuple(normalizations),
    )


def _diff(relative: str, old: str, new: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
            lineterm="",
        )
    )


def _delete_diff(relative: str, old_bytes: bytes) -> str:
    try:
        old = old_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return f"File binario eliminato: {relative}"
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            [],
            fromfile=f"a/{relative}",
            tofile="/dev/null",
            lineterm="",
        )
    )


def _decode_existing_text(relative: str, data: bytes) -> tuple[str, bool]:
    has_utf8_bom = data.startswith(codecs.BOM_UTF8)
    try:
        return data.decode("utf-8-sig" if has_utf8_bom else "utf-8"), has_utf8_bom
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"File {relative}: il contenuto esistente non è UTF-8 e non può essere "
            "sostituito tramite un file Markdown di aggiornamento."
        ) from exc


def _existing_newline_style(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def _encode_replacement_content(content: str, old_text: str, has_utf8_bom: bool) -> bytes:
    newline = _existing_newline_style(old_text)
    normalized = content if newline == "\n" else content.replace("\n", newline)
    encoded = normalized.encode("utf-8")
    return codecs.BOM_UTF8 + encoded if has_utf8_bom else encoded


def _with_final_newline(content: str, final_newline: bool) -> str:
    if final_newline:
        return content if content.endswith("\n") else content + "\n"
    return content.rstrip("\n")


def _materialize_content(
    entry: TextFileOperation,
    *,
    existing_text: str | None = None,
) -> tuple[str, bool]:
    assert entry.content is not None
    inferred = entry.final_newline is None
    final_newline = entry.final_newline
    if final_newline is None:
        final_newline = (
            existing_text.endswith(("\n", "\r"))
            if existing_text is not None
            else True
        )
    return _with_final_newline(entry.content, final_newline), inferred


def inspect_text_file_operations(workspace: Path, text: str) -> ChangePlan:
    """Build one reviewable plan from complete text-file operations."""
    document = parse_text_file_operations(text)
    resolved_workspace = workspace.resolve()
    changes: list[FileChange] = []
    contents: dict[str, bytes] = {}
    diff_parts: list[str] = []
    targets: list[str] = []
    inferred_final_newline: list[str] = []

    for entry in document.operations:
        allow_missing = entry.operation == "CREATE"
        target = resolve_workspace_target(
            workspace,
            entry.target,
            allow_missing=allow_missing,
        )
        relative = target.relative_to(resolved_workspace).as_posix()
        targets.append(relative)

        if entry.operation == "CREATE":
            if target.exists():
                raise ValueError(
                    f"File {relative} (riga {entry.declaration_line}): "
                    "CREATE richiede un file inesistente."
                )
            content, inferred = _materialize_content(entry)
            if inferred:
                inferred_final_newline.append(relative)
            new_bytes = content.encode("utf-8")
            if target.suffix.casefold() == ".py":
                compile(content, relative, "exec")
            changes.append(
                FileChange(
                    relative,
                    relative,
                    "create",
                    None,
                    sha256_bytes(new_bytes),
                    size=len(new_bytes),
                )
            )
            contents[relative] = new_bytes
            diff_parts.append(_diff(relative, "", content))
            continue

        if not target.exists() or not target.is_file():
            raise ValueError(
                f"File {relative} (riga {entry.declaration_line}): "
                f"{entry.operation} richiede un file esistente."
            )
        old_bytes = target.read_bytes()
        old_hash = sha256_file(target)

        if entry.operation == "DELETE":
            changes.append(
                FileChange(relative, relative, "delete", old_hash, None, size=0)
            )
            diff_parts.append(_delete_diff(relative, old_bytes))
            continue

        old_text, has_utf8_bom = _decode_existing_text(relative, old_bytes)
        content, inferred = _materialize_content(entry, existing_text=old_text)
        if inferred:
            inferred_final_newline.append(relative)
        new_bytes = _encode_replacement_content(
            content,
            old_text,
            has_utf8_bom,
        )
        if new_bytes == old_bytes:
            raise ValueError(
                f"File {relative} (riga {entry.declaration_line}): "
                "REPLACE non modifica il contenuto esistente."
            )
        if target.suffix.casefold() == ".py":
            compile(content, relative, "exec")
        diff_parts.append(_diff(relative, old_text, content))
        changes.append(
            FileChange(
                relative,
                relative,
                "modify",
                old_hash,
                sha256_bytes(new_bytes),
                size=len(new_bytes),
            )
        )
        contents[relative] = new_bytes

    combined_diff = "\n\n".join(part.rstrip() for part in diff_parts if part)
    if combined_diff:
        combined_diff += "\n"
    counts = {
        name.lower(): sum(
            1 for item in document.operations if item.operation == name
        )
        for name in ("CREATE", "REPLACE", "DELETE")
    }
    warnings: list[str] = []
    if document.ignored_lines:
        warnings.append(
            "Sono state ignorate righe esterne ai blocchi strutturati: "
            + ", ".join(str(item) for item in document.ignored_lines)
            + ". Verifica che non contengano istruzioni o omissioni importanti."
        )
    if document.normalizations:
        warnings.append(
            "La risposta conteneva formattazione incompleta o rimossa dalla chat. "
            "BridgAI ha normalizzato: "
            + " ".join(document.normalizations)
            + " Verifica attentamente il diff prima di applicare."
        )
    if inferred_final_newline:
        warnings.append(
            "FINAL_NEWLINE assente per: "
            + ", ".join(inferred_final_newline)
            + ". BridgAI ha usato una scelta conservativa basata sul file esistente "
            "oppure YES per i file nuovi."
        )
    return ChangePlan(
        plan_type="full_file",
        workspace=resolved_workspace,
        source_path=None,
        changes=changes,
        diff=combined_diff,
        warnings=warnings,
        metadata={
            "contents": contents,
            "provider": "text_file_operations",
            "targets": targets,
            "operations": counts,
            "ignored_text_lines": list(document.ignored_lines),
            "normalized_text_formatting": list(document.normalizations),
            "inferred_final_newline": inferred_final_newline,
            "import_summary": {
                "files": len(changes),
                "blocks": len(document.operations),
                "targets": targets,
                **counts,
            },
        },
    )
