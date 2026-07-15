from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re

from local_ai_bridge.core.models import ChangePlan
from local_ai_bridge.core.safety import SafetyError
from local_ai_bridge.services.markdown_exchange import (
    MarkdownExchangeError,
    MarkdownExchangeNotFound,
    extract_commit_message_metadata,
    parse_markdown_response,
)
from local_ai_bridge.services.text_file_operations import inspect_text_file_operations


class TextUpdateImportError(ValueError):
    """Raised when no supported textual update format can be parsed."""


_TEXT_OPERATION_HINT = re.compile(
    r"^\s*(?:>\s*)?(?:#{1,6}\s+|[-+*]\s+)?"
    r"(?:[*_`~]+)?(?:BEGIN[ _-]?FILE|FILE[ _-]?BEGIN|INIZIO[ _-]?FILE)\b",
    re.IGNORECASE,
)
_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _looks_like_markdown_exchange(text: str) -> bool:
    return any("BRIDGAI:FILE" in line.upper() for line in text.splitlines())


def _looks_like_text_operations(text: str) -> bool:
    return any(_TEXT_OPERATION_HINT.search(line) for line in text.splitlines())


def _stronger_severity(current: str, candidate: str) -> str:
    return candidate if _SEVERITY_RANK[candidate] > _SEVERITY_RANK[current] else current


def _add_recovery_action(
    plan: ChangePlan,
    action: str,
    severity: str,
    detail: str,
) -> None:
    actions = list(plan.metadata.get("recovery_actions", []))
    actions.append({"action": action, "severity": severity, "detail": detail})
    plan.metadata["recovery_actions"] = actions
    current = str(plan.metadata.get("recovery_severity", "none"))
    plan.metadata["recovery_severity"] = _stronger_severity(current, severity)
    if plan.metadata["recovery_severity"] == "high":
        plan.metadata["requires_explicit_confirmation"] = True


def _is_format_not_found(label: str, error: Exception) -> bool:
    if label == "Markdown Exchange":
        return isinstance(error, MarkdownExchangeNotFound)
    return "Nessuna operazione file completa rilevata" in str(error)


def _candidate_parsers(
    text: str,
    preferred: str,
) -> tuple[tuple[str, Callable[[Path, str], ChangePlan]], ...]:
    text_operations = ("file Markdown di aggiornamento", inspect_text_file_operations)
    markdown_exchange = ("Markdown Exchange", parse_markdown_response)

    if preferred == "text_file_operations":
        return (text_operations, markdown_exchange)
    if preferred == "markdown_exchange":
        return (markdown_exchange, text_operations)
    if preferred != "auto":
        raise ValueError(
            "preferred deve essere 'auto', 'text_file_operations' "
            "oppure 'markdown_exchange'."
        )

    if _looks_like_markdown_exchange(text) and not _looks_like_text_operations(text):
        return (markdown_exchange, text_operations)
    if _looks_like_text_operations(text) and not _looks_like_markdown_exchange(text):
        return (text_operations, markdown_exchange)
    return (text_operations, markdown_exchange)



def _ensure_import_summary(plan: ChangePlan) -> None:
    counts = {
        "create": sum(1 for item in plan.changes if item.kind == "create"),
        "replace": sum(1 for item in plan.changes if item.kind == "modify"),
        "delete": sum(1 for item in plan.changes if item.kind == "delete"),
    }
    targets = [item.target for item in plan.changes]
    plan.metadata.setdefault(
        "import_summary",
        {
            "files": len(plan.changes),
            "targets": targets,
            **counts,
        },
    )


def inspect_text_update_response(
    workspace: Path,
    text: str,
    *,
    preferred: str = "auto",
) -> ChangePlan:
    """Parse any supported textual update format into a reviewable ChangePlan.

    The Web/desktop UI has two historical entry points: Markdown Exchange and
    full-file text operations. Web AI providers often return the right content
    through the wrong upload/copy path, so this adapter tries the most likely
    parser first and falls back to the other one without weakening safety checks.

    Fallback is intentionally conservative: if a parser sees markers for its
    own format and then fails, BridgAI keeps that error instead of silently
    recovering a partial plan with the other parser.
    """

    try:
        parser_text, commit_message = extract_commit_message_metadata(text)
    except MarkdownExchangeError as exc:
        raise TextUpdateImportError(
            f"Metadati commit-message.md non validi: {exc}"
        ) from exc

    markdown_hint = _looks_like_markdown_exchange(parser_text)
    text_operations_hint = _looks_like_text_operations(parser_text)
    if preferred == "auto" and markdown_hint and text_operations_hint:
        raise TextUpdateImportError(
            "Formato testuale ambiguo: la risposta contiene sia marker "
            "BEGIN_FILE sia marker BRIDGAI:FILE. Usa un solo formato oppure "
            "seleziona esplicitamente il percorso di import corretto."
        )

    errors: list[tuple[str, Exception]] = []
    for label, parser in _candidate_parsers(parser_text, preferred):
        own_marker_detected = (
            markdown_hint if label == "Markdown Exchange" else text_operations_hint
        )
        try:
            plan = parser(workspace, parser_text)
        except (SafetyError, SyntaxError):
            raise
        except Exception as exc:
            errors.append((label, exc))
            if own_marker_detected and not _is_format_not_found(label, exc):
                raise TextUpdateImportError(
                    f"Il formato {label} è stato rilevato ma non è valido. "
                    "Per evitare recuperi parziali o ambigui, BridgAI non proverà "
                    f"parser alternativi. Dettaglio: {exc}"
                ) from exc
            continue

        plan.metadata.setdefault("text_update_format", label)
        if commit_message is not None:
            plan.metadata["commit_message"] = commit_message
        _ensure_import_summary(plan)
        if errors:
            attempted = "; ".join(f"{name}: {error}" for name, error in errors)
            warning = (
                f"Formato riconosciuto come {label} dopo un tentativo non riuscito "
                f"con l'altro parser ({attempted}). Verifica attentamente il diff."
            )
            plan.warnings.append(warning)
            _add_recovery_action(
                plan,
                "fallback_parser_used",
                "high",
                warning,
            )
            plan.warnings.append(
                "Il parser alternativo è stato usato come recupero ad alta severità: "
                "controlla che l'intera risposta sia stata interpretata nel formato atteso."
            )
        return plan

    details = "\n".join(f"- {name}: {error}" for name, error in errors)
    raise TextUpdateImportError(
        "Nessun formato testuale applicabile riconosciuto. "
        "Puoi usare un file Markdown di aggiornamento BEGIN_FILE/END_FILE "
        "oppure un documento Markdown Exchange BridgAI.\n"
        f"Dettagli:\n{details}"
    )
