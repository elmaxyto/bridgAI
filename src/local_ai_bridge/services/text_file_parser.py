from __future__ import annotations

from local_ai_bridge.services.text_file_models import (
    RawBlock,
    TextFileOperation,
    TextFileOperationsDocument,
    TextFileOperationsParseError,
    _parse_error,
)
from local_ai_bridge.services.text_utils import strip_scalar_markup

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


def _normalize_operation(raw: str, line_number: int) -> str:
    value = strip_scalar_markup(raw).strip().upper()
    operation = _OPERATION_ALIASES.get(value)
    if operation is None:
        raise _parse_error(
            line_number,
            "operazione non valida. Usa un solo valore: CREATE, REPLACE oppure DELETE.",
        )
    return operation


def _normalize_final_newline(raw: str, line_number: int) -> bool:
    value = strip_scalar_markup(raw).strip().upper()
    result = _FINAL_NEWLINE_ALIASES.get(value)
    if result is None:
        raise _parse_error(
            line_number,
            "FINAL_NEWLINE non valido. Usa un solo valore: YES oppure NO.",
        )
    return result


def parse_operations_from_tokens(blocks: list[RawBlock]) -> TextFileOperationsDocument:
    """Convert lexer blocks into normalized text-file operations."""
    operations: list[TextFileOperation] = []
    normalizations: list[str] = []
    seen: set[str] = set()

    for block in blocks:
        key = block.target.casefold()
        if key in seen:
            raise _parse_error(block.declaration_line, f"target duplicato: {block.target}.")
        seen.add(key)

        operation_raw = block.operation_raw
        if operation_raw == "AUTO":
            operation = "AUTO"
        elif operation_raw is None:
            raise _parse_error(
                block.declaration_line,
                "manca OPERATION: CREATE, REPLACE oppure DELETE.",
            )
        else:
            operation = _normalize_operation(
                operation_raw,
                block.operation_line or block.declaration_line,
            )

        final_newline: bool | None = None
        if block.final_newline_raw is not None:
            final_newline = _normalize_final_newline(
                block.final_newline_raw,
                block.final_newline_line or block.declaration_line,
            )

        content = None if block.content_lines is None else "\n".join(block.content_lines)
        operations.append(
            TextFileOperation(
                operation,
                block.target,
                content,
                block.declaration_line,
                final_newline,
            )
        )
        normalizations.extend(block.normalizations)

    if not operations:
        raise TextFileOperationsParseError(
            "Nessuna operazione file completa rilevata. "
            "Usa BEGIN_FILE, OPERATION, PATH, CONTENT ed END_FILE."
        )
    return TextFileOperationsDocument(tuple(operations), (), tuple(normalizations))
