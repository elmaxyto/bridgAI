from __future__ import annotations

import re

from local_ai_bridge.services.text_file_models import RawBlock, _parse_error
from local_ai_bridge.services.text_file_parser import _normalize_operation
from local_ai_bridge.services.text_utils import (
    normalize_newlines,
    normalize_relative_path,
    strip_scalar_markup,
)

_FIELD_SEPARATOR = r"\s*(?::|=|：)\s*"
BEGIN_FILE_MARKER = re.compile(
    r"^(?:BEGIN[ _-]?FILE|FILE[ _-]?BEGIN|INIZIO[ _-]?FILE)"
    r"(?:\s*(?::|=|：)\s*|\s+)?(?P<path>.*?)\s*$",
    re.IGNORECASE,
)
END_FILE_MARKER = re.compile(
    r"^(?:END[ _-]?FILE|FILE[ _-]?END|FINE[ _-]?FILE)"
    r"(?:\s*(?::|=|：)\s*|\s+)?(?P<path>.*?)\s*$",
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
_INLINE_FIELD_NAME = (
    r"OPERATION|OPERAZIONE|PATH|FILE[ _-]?PATH|TARGET|FILE|PERCORSO|"
    r"FINAL[ _-]?NEWLINE|TRAILING[ _-]?NEWLINE|"
    r"NEWLINE[ _-]?FINALE|NUOVA[ _-]?RIGA[ _-]?FINALE"
)
INLINE_FIELD = re.compile(
    rf"(?P<label>{_INLINE_FIELD_NAME}){_FIELD_SEPARATOR}",
    re.IGNORECASE,
)


def _control_text(line: str) -> str:
    candidate = line.strip().lstrip("\ufeff")
    while candidate.startswith(">"):
        candidate = candidate[1:].lstrip()
    candidate = re.sub(r"^(?:#{1,6}\s+|[-+*]\s+)", "", candidate)
    return strip_scalar_markup(candidate)


def _path_from_inline_value(raw: str, line_number: int) -> str:
    target = normalize_relative_path(raw)
    if target is None:
        raise _parse_error(line_number, "percorso relativo non valido nel marcatore BEGIN_FILE.")
    return target


def _inline_label_key(raw: str) -> str:
    value = re.sub(r"[ _-]+", "_", raw.strip().upper())
    if value in {"OPERATION", "OPERAZIONE"}:
        return "operation"
    if value in {"FINAL_NEWLINE", "TRAILING_NEWLINE", "NEWLINE_FINALE", "NUOVA_RIGA_FINALE"}:
        return "final_newline"
    return "path"


def _assign_inline_field(
    fields: dict[str, object],
    key: str,
    value: str,
    line_number: int,
) -> None:
    if key == "path":
        parsed: object = _path_from_inline_value(value, line_number)
    else:
        parsed = strip_scalar_markup(value).strip()
        if key == "operation":
            _normalize_operation(value, line_number)
    existing = fields.get(key)
    if existing is not None and existing != parsed:
        label = {"operation": "OPERATION", "final_newline": "FINAL_NEWLINE", "path": "PATH"}[key]
        raise _parse_error(line_number, f"{label} dichiarato più di una volta con valori diversi.")
    fields[key] = parsed
    if key != "path":
        fields[f"{key}_line"] = line_number


def _inline_marker_fields(match: re.Match[str], line_number: int) -> dict[str, object]:
    raw = (match.group("path") or "").strip()
    if not raw:
        return {}
    candidate = strip_scalar_markup(raw).strip()
    fields: dict[str, object] = {}

    labels = list(INLINE_FIELD.finditer(candidate))
    if labels:
        prefix = candidate[: labels[0].start()].strip()
        if prefix:
            fields["path"] = _path_from_inline_value(prefix, line_number)
        for position, field_match in enumerate(labels):
            value_start = field_match.end()
            value_end = labels[position + 1].start() if position + 1 < len(labels) else len(candidate)
            value = candidate[value_start:value_end].strip().strip(",;")
            if not value:
                raise _parse_error(line_number, "campo inline vuoto nel marcatore BEGIN_FILE.")
            _assign_inline_field(
                fields,
                _inline_label_key(field_match.group("label")),
                value,
                line_number,
            )
        return fields

    parts = candidate.rsplit(None, 1)
    if len(parts) == 2:
        try:
            _normalize_operation(parts[1], line_number)
        except Exception:
            pass
        else:
            return {
                "path": _path_from_inline_value(parts[0], line_number),
                "operation": strip_scalar_markup(parts[1]).strip(),
                "operation_line": line_number,
            }

    target = normalize_relative_path(candidate)
    if target is not None:
        return {"path": target}

    raise _parse_error(line_number, "percorso relativo non valido nel marcatore BEGIN_FILE.")


def _end_marker_path(match: re.Match[str], line_number: int) -> str | None:
    raw = (match.group("path") or "").strip()
    if not raw:
        return None
    return _path_from_inline_value(raw, line_number)


def _consume_end_file(
    lines: list[str],
    index: int,
    target: str,
) -> int | None:
    if index >= len(lines):
        return None
    match = END_FILE_MARKER.match(_control_text(lines[index]))
    if not match:
        return None
    declared_target = _end_marker_path(match, index + 1)
    if declared_target is not None and declared_target.casefold() != target.casefold():
        raise _parse_error(
            index + 1,
            f"END_FILE dichiara {declared_target}, ma il blocco aperto riguarda {target}.",
        )
    return index + 1


def _append_missing_end_normalization(
    normalizations: list[str],
    target: str,
    line_number: int,
) -> None:
    normalizations.append(
        f"{target}: END_FILE assente o spostato; chiusura inferita alla riga {line_number}."
    )


def _append_missing_fence_normalization(
    normalizations: list[str],
    target: str,
    line_number: int,
) -> None:
    normalizations.append(
        f"{target}: fence Markdown non chiusa; chiusura inferita prima della riga {line_number}."
    )


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


def _operation_kind(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    try:
        return _normalize_operation(raw, 0)
    except Exception:
        return None


def tokenize_text_file_operations(text: str) -> tuple[list[RawBlock], tuple[int, ...]]:
    """Tokenize complete text-file operations while tolerating Markdown wrappers."""
    lines = normalize_newlines(text).split("\n")
    blocks: list[RawBlock] = []
    ignored_lines: list[int] = []
    index = 0

    while index < len(lines):
        control = _control_text(lines[index])
        if not control:
            index += 1
            continue
        begin_match = BEGIN_FILE_MARKER.match(control)
        if not begin_match:
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
        block_normalizations: list[str] = []
        index += 1
        fields: dict[str, object] = _inline_marker_fields(begin_match, declaration_line)
        if fields:
            inline_target = fields.get("path")
            label = inline_target if isinstance(inline_target, str) else "blocco"
            block_normalizations.append(
                f"{label}: metadati letti dal marcatore BEGIN_FILE alla riga {declaration_line}."
            )
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
                value = operation_match.group("value")
                _normalize_operation(value, index + 1)
                fields["operation"] = value
                fields["operation_line"] = index + 1
                index += 1
                continue
            if path_match:
                target = normalize_relative_path(path_match.group("path"))
                if target is None:
                    raise _parse_error(index + 1, "percorso relativo non valido.")
                if "path" in fields:
                    if fields["path"] != target:
                        raise _parse_error(index + 1, "PATH dichiarato più di una volta con valori diversi.")
                    block_normalizations.append(
                        f"{target}: PATH duplicato coerente ignorato alla riga {index + 1}."
                    )
                    index += 1
                    continue
                fields["path"] = target
                index += 1
                continue
            if newline_match:
                if "final_newline" in fields:
                    raise _parse_error(index + 1, "FINAL_NEWLINE dichiarato più di una volta.")
                fields["final_newline"] = newline_match.group("value")
                fields["final_newline_line"] = index + 1
                index += 1
                continue
            break

        operation = fields.get("operation")
        target = fields.get("path")
        if target is None:
            raise _parse_error(
                declaration_line,
                "manca PATH: percorso/relativo/file.ext.",
            )
        assert isinstance(target, str)
        if operation is None:
            next_control = _control_text(lines[index]) if index < len(lines) else ""
            next_is_content = bool(CONTENT_LINE.match(next_control))
            next_is_fence = bool(index < len(lines) and CODE_FENCE_LINE.match(lines[index].strip()))
            if next_is_content or next_is_fence:
                operation = "AUTO"
                block_normalizations.append(
                    f"{target}: OPERATION assente; verrà inferita dal file locale alla riga {declaration_line}."
                )
            else:
                raise _parse_error(
                    declaration_line,
                    "manca OPERATION: CREATE, REPLACE oppure DELETE.",
                )
        assert isinstance(operation, str)

        if _operation_kind(operation) == "DELETE":
            if "final_newline" in fields:
                raise _parse_error(
                    declaration_line,
                    "DELETE non deve dichiarare FINAL_NEWLINE.",
                )
            consumed = _consume_end_file(lines, index, target)
            if consumed is None:
                if index < len(lines) and CONTENT_LINE.match(_control_text(lines[index])):
                    raise _parse_error(index + 1, "DELETE non deve contenere CONTENT.")
                _append_missing_end_normalization(
                    block_normalizations,
                    target,
                    min(index + 1, len(lines)),
                )
            else:
                index = consumed
            blocks.append(
                RawBlock(
                    target,
                    declaration_line,
                    operation,
                    int(fields.get("operation_line") or declaration_line),
                    None,
                    None,
                    None,
                    tuple(block_normalizations),
                )
            )
            continue

        if index < len(lines) and CONTENT_LINE.match(_control_text(lines[index])):
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
        else:
            probe = index
            while probe < len(lines) and not lines[probe].strip():
                probe += 1
            if probe < len(lines) and CODE_FENCE_LINE.match(lines[probe].strip()):
                block_normalizations.append(
                    f"{target}: CONTENT assente; contenuto letto dalla fence Markdown alla riga {probe + 1}."
                )
                index = probe
            else:
                unexpected = _control_text(lines[index]) if index < len(lines) else ""
                if unexpected:
                    raise _parse_error(
                        index + 1,
                        f"campo non riconosciuto prima di CONTENT per {target}: {unexpected!r}.",
                    )
                raise _parse_error(declaration_line, f"manca CONTENT per {target}.")
        if index >= len(lines):
            raise _parse_error(
                declaration_line,
                f"contenuto completo mancante per {target}.",
            )

        fence_match = CODE_FENCE_LINE.match(lines[index].strip())
        content_lines: list[str] = []
        if fence_match is None:
            content_start_line = index + 1
            while index < len(lines):
                current_control = _control_text(lines[index])
                if END_FILE_MARKER.match(current_control):
                    break
                if BEGIN_FILE_MARKER.match(current_control) and content_lines:
                    break
                content_lines.append(lines[index])
                index += 1
            block_normalizations.append(
                f"{target}: contenuto accettato senza fence Markdown "
                f"a partire dalla riga {content_start_line}."
            )
            consumed = _consume_end_file(lines, index, target)
            if consumed is not None:
                index = consumed
            elif index >= len(lines):
                raise _parse_error(
                    content_start_line,
                    "CONTENT senza fence Markdown: manca END_FILE.",
                )
            else:
                _append_missing_end_normalization(
                    block_normalizations,
                    target,
                    min(index + 1, len(lines)),
                )
        else:
            opening_fence = fence_match.group("fence")
            index += 1
            closed_fence = False
            while index < len(lines):
                if _is_closing_fence(lines[index], opening_fence):
                    closed_fence = True
                    break
                current_control = _control_text(lines[index])
                if END_FILE_MARKER.match(current_control) or BEGIN_FILE_MARKER.match(current_control):
                    break
                content_lines.append(lines[index])
                index += 1
            if closed_fence:
                index += 1
                while index < len(lines) and not lines[index].strip():
                    index += 1
                consumed = _consume_end_file(lines, index, target)
                if consumed is not None:
                    index = consumed
                else:
                    _append_missing_end_normalization(
                        block_normalizations,
                        target,
                        min(index + 1, len(lines)),
                    )
            else:
                _append_missing_fence_normalization(
                    block_normalizations,
                    target,
                    min(index + 1, len(lines)),
                )
                consumed = _consume_end_file(lines, index, target)
                if consumed is not None:
                    index = consumed
                else:
                    _append_missing_end_normalization(
                        block_normalizations,
                        target,
                        min(index + 1, len(lines)),
                    )

        blocks.append(
            RawBlock(
                target,
                declaration_line,
                operation,
                int(fields.get("operation_line") or declaration_line),
                fields.get("final_newline") if isinstance(fields.get("final_newline"), str) else None,
                int(fields.get("final_newline_line") or declaration_line) if "final_newline" in fields else None,
                tuple(content_lines),
                tuple(block_normalizations),
            )
        )

    return blocks, tuple(ignored_lines)
