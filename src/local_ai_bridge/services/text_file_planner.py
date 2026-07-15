from __future__ import annotations

from pathlib import Path

from local_ai_bridge.core.io import sha256_bytes, sha256_file
from local_ai_bridge.core.models import ChangePlan, FileChange
from local_ai_bridge.core.safety import resolve_workspace_target
from local_ai_bridge.services.text_file_models import TextFileOperation, TextFileOperationsDocument
from local_ai_bridge.services.text_utils import (
    decode_existing_text,
    encode_replacement_content,
    generate_delete_diff,
    generate_unified_diff,
    with_final_newline,
)

_SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}


def _stronger_severity(current: str, candidate: str) -> str:
    return candidate if _SEVERITY_RANK[candidate] > _SEVERITY_RANK[current] else current


def _normalization_target(detail: str) -> str:
    prefix, separator, _rest = detail.partition(":")
    return prefix.strip() if separator else ""


def _classify_normalization(detail: str) -> tuple[str, str, str]:
    target = _normalization_target(detail)
    if "fence Markdown non chiusa" in detail:
        return "missing_code_fence", "high", target
    if "contenuto accettato senza fence" in detail:
        return "unfenced_content", "high", target
    if "END_FILE assente" in detail:
        return "missing_end_file", "medium", target
    if "CONTENT assente" in detail:
        return "missing_content_marker", "medium", target
    return "format_normalized", "low", target


def _recovery_action(
    action: str,
    severity: str,
    *,
    target: str = "",
    detail: str = "",
) -> dict[str, str]:
    item = {"action": action, "severity": severity}
    if target:
        item["target"] = target
    if detail:
        item["detail"] = detail
    return item


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
    return with_final_newline(entry.content, final_newline), inferred


def _record_python_syntax_check(
    content: str,
    relative: str,
    syntax_error_targets: list[str],
    recovery_actions: list[dict[str, str]],
    recovery_severity: str,
) -> str:
    try:
        compile(content, relative, "exec")
    except SyntaxError as exc:
        detail = (
            f"{relative}: sintassi Python non valida "
            f"({exc.msg}, riga {exc.lineno})."
        )
        syntax_error_targets.append(relative)
        recovery_actions.append(
            _recovery_action(
                "python_syntax_error",
                "high",
                target=relative,
                detail=detail,
            )
        )
        return _stronger_severity(recovery_severity, "high")
    return recovery_severity


def plan_from_operations(workspace: Path, document: TextFileOperationsDocument) -> ChangePlan:
    """Build one reviewable plan from normalized text-file operations."""
    resolved_workspace = workspace.resolve()
    changes: list[FileChange] = []
    contents: dict[str, bytes] = {}
    diff_parts: list[str] = []
    targets: list[str] = []
    inferred_final_newline: list[str] = []
    inferred_operations: list[str] = []
    syntax_error_targets: list[str] = []
    effective_operations: list[str] = []
    recovery_actions: list[dict[str, str]] = []
    recovery_severity = "none"

    for detail in document.normalizations:
        action, severity, target = _classify_normalization(detail)
        recovery_actions.append(
            _recovery_action(action, severity, target=target, detail=detail)
        )
        recovery_severity = _stronger_severity(recovery_severity, severity)
    if document.ignored_lines:
        recovery_actions.append(
            _recovery_action(
                "ignored_outer_text",
                "low",
                detail=", ".join(str(item) for item in document.ignored_lines),
            )
        )
        recovery_severity = _stronger_severity(recovery_severity, "low")

    for entry in document.operations:
        operation = entry.operation
        allow_missing = operation in {"CREATE", "AUTO"}
        target = resolve_workspace_target(
            workspace,
            entry.target,
            allow_missing=allow_missing,
        )
        relative = target.relative_to(resolved_workspace).as_posix()
        if relative.casefold() == "commit-message.md":
            raise ValueError(
                "commit-message.md è un metadato BridgAI e non può essere "
                "creato, sostituito o eliminato come file del progetto. Usa il "
                "blocco BRIDGAI:FILE commit-message.md previsto dal protocollo."
            )
        targets.append(relative)

        if operation == "AUTO":
            operation = "REPLACE" if target.exists() else "CREATE"
            inferred_operations.append(f"{relative}: {operation}")
            action = (
                "create_inferred_for_missing_target"
                if operation == "CREATE"
                else "replace_inferred_for_existing_target"
            )
            recovery_actions.append(
                _recovery_action(
                    action,
                    "high",
                    target=relative,
                    detail=(
                        f"OPERATION assente per {relative}; BridgAI ha inferito "
                        f"{operation} dallo stato locale del file."
                    ),
                )
            )
            recovery_severity = _stronger_severity(recovery_severity, "high")
        effective_operations.append(operation)

        if operation == "CREATE":
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
                recovery_severity = _record_python_syntax_check(
                    content,
                    relative,
                    syntax_error_targets,
                    recovery_actions,
                    recovery_severity,
                )
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
            diff_parts.append(generate_unified_diff(relative, "", content))
            continue

        if not target.exists() or not target.is_file():
            raise ValueError(
                f"File {relative} (riga {entry.declaration_line}): "
                f"{operation} richiede un file esistente."
            )
        old_bytes = target.read_bytes()
        old_hash = sha256_file(target)

        if operation == "DELETE":
            changes.append(
                FileChange(relative, relative, "delete", old_hash, None, size=0)
            )
            diff_parts.append(generate_delete_diff(relative, old_bytes))
            continue

        old_text, has_utf8_bom = decode_existing_text(relative, old_bytes)
        content, inferred = _materialize_content(entry, existing_text=old_text)
        if inferred:
            inferred_final_newline.append(relative)
        new_bytes = encode_replacement_content(
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
            recovery_severity = _record_python_syntax_check(
                content,
                relative,
                syntax_error_targets,
                recovery_actions,
                recovery_severity,
            )
        diff_parts.append(generate_unified_diff(relative, old_text, content))
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

    for relative in inferred_final_newline:
        recovery_actions.append(
            _recovery_action(
                "final_newline_inferred",
                "low",
                target=relative,
                detail="FINAL_NEWLINE assente; scelta conservativa usata da BridgAI.",
            )
        )
        recovery_severity = _stronger_severity(recovery_severity, "low")

    requires_explicit_confirmation = recovery_severity == "high"

    combined_diff = "\n\n".join(part.rstrip() for part in diff_parts if part)
    if combined_diff:
        combined_diff += "\n"
    counts = {
        name.lower(): sum(
            1 for item in effective_operations if item == name
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
    if inferred_operations:
        warnings.append(
            "OPERATION assente per: "
            + ", ".join(inferred_operations)
            + ". BridgAI ha inferito CREATE/REPLACE dallo stato locale del file. "
            "Verifica attentamente percorsi e diff prima di applicare."
        )
    if syntax_error_targets:
        warnings.append(
            "Sintassi Python non valida rilevata per: "
            + ", ".join(syntax_error_targets)
            + ". Il diff resta disponibile, ma l'applicazione richiede conferma esplicita."
        )
    if requires_explicit_confirmation:
        warnings.append(
            "Il piano contiene recuperi ad alta severità. Controlla percorsi, "
            "contenuti e diff con attenzione prima di confermare l'applicazione."
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
            "inferred_operations": inferred_operations,
            "syntax_error_targets": syntax_error_targets,
            "import_summary": {
                "files": len(changes),
                "blocks": len(document.operations),
                "targets": targets,
                **counts,
            },
            "recovery_actions": recovery_actions,
            "recovery_severity": recovery_severity,
            "requires_explicit_confirmation": requires_explicit_confirmation,
        },
    )
