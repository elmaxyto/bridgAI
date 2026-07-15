from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RawBlock:
    target: str
    declaration_line: int
    operation_raw: str | None
    operation_line: int | None
    final_newline_raw: str | None
    final_newline_line: int | None
    content_lines: tuple[str, ...] | None
    normalizations: tuple[str, ...] = ()


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


def _parse_error(line_number: int, message: str) -> TextFileOperationsParseError:
    return TextFileOperationsParseError(f"Riga {line_number}: {message}")
