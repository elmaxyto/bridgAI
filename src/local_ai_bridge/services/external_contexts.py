from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from local_ai_bridge.core.safety import is_sensitive_relative_path
from local_ai_bridge.core.settings import AppSettings, normalize_external_context_paths


EXTERNAL_CONTEXT_ARCHIVE_ROOT = "__bridgai_external_contexts__"


@dataclass(slots=True)
class ExternalContextRoot:
    """A project or folder made visible to reports without becoming writable."""

    index: int
    path: Path

    @property
    def label(self) -> str:
        return f"context-{self.index}"


@dataclass(slots=True)
class ExternalContextFile:
    """A single read-only file requested from an additional context root."""

    context: ExternalContextRoot
    requested: str
    relative: str
    path: Path

    @property
    def archive_name(self) -> str:
        return f"{EXTERNAL_CONTEXT_ARCHIVE_ROOT}/{self.context.label}/{self.relative}"


def _paths_overlap(first: Path, second: Path) -> bool:
    """Return whether two resolved paths are equal or one contains the other."""
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def resolve_external_context_roots(
    workspace: Path,
    settings: AppSettings,
) -> tuple[list[ExternalContextRoot], list[str]]:
    """Resolve configured extra context roots and collect non-fatal diagnostics."""
    workspace = workspace.expanduser().resolve(strict=True)
    roots: list[ExternalContextRoot] = []
    diagnostics: list[str] = []
    seen = {workspace}

    for raw in normalize_external_context_paths(settings.external_context_paths):
        candidate = Path(raw).expanduser()
        if candidate.is_symlink():
            diagnostics.append(
                f"Contesto aggiuntivo ignorato `{raw}`: i link simbolici non sono consentiti."
            )
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            diagnostics.append(f"Contesto aggiuntivo non disponibile `{raw}`: {exc}")
            continue
        if not resolved.is_dir():
            diagnostics.append(f"Contesto aggiuntivo ignorato `{resolved}`: non è una cartella.")
            continue
        if any(_paths_overlap(resolved, existing) for existing in seen):
            diagnostics.append(
                f"Contesto aggiuntivo ignorato `{resolved}`: si sovrappone al workspace corrente "
                "o a un contesto già incluso."
            )
            continue
        seen.add(resolved)
        roots.append(ExternalContextRoot(index=len(roots) + 1, path=resolved))
    return roots, diagnostics


def parse_external_context_reference(value: str) -> tuple[str, str] | None:
    """Return ``(context_label, relative_path)`` for ``@context-N:path`` references."""
    raw = (value or "").strip()
    if not raw.startswith("@context-"):
        return None
    label, separator, relative = raw[1:].partition(":")
    if not separator or not relative.strip():
        return None
    if not label.startswith("context-") or not label.removeprefix("context-").isdigit():
        return None
    return label, relative.strip()


def _safe_relative_path(raw: str) -> str:
    normalized = raw.replace("\\", "/").strip()
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or relative.is_absolute()
        or normalized.startswith("/")
        or (relative.parts and ":" in relative.parts[0])
    ):
        raise ValueError("il percorso del contesto deve essere relativo")
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("il percorso del contesto non può contenere segmenti vuoti, `.` o `..`")
    return relative.as_posix()


def resolve_external_context_file(
    workspace: Path,
    settings: AppSettings,
    reference: str,
) -> ExternalContextFile:
    """Resolve a read-only ``@context-N:path`` file request safely."""
    parsed = parse_external_context_reference(reference)
    if parsed is None:
        raise ValueError(
            "usa la forma `@context-N:percorso/relativo.ext` per i file dei contesti aggiuntivi"
        )
    label, raw_relative = parsed
    relative = _safe_relative_path(raw_relative)
    if is_sensitive_relative_path(relative):
        raise ValueError("il percorso richiesto è escluso perché può contenere dati sensibili")

    contexts, diagnostics = resolve_external_context_roots(workspace, settings)
    by_label = {context.label: context for context in contexts}
    context = by_label.get(label)
    if context is None:
        available = ", ".join(sorted(by_label)) or "nessun contesto disponibile"
        diagnostic_text = f" Diagnostica: {'; '.join(diagnostics)}" if diagnostics else ""
        raise ValueError(
            f"contesto `{label}` non disponibile; contesti validi: {available}.{diagnostic_text}"
        )

    candidate = context.path / relative
    if candidate.is_symlink():
        raise ValueError("i link simbolici nei contesti aggiuntivi non sono scaricabili")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"file non disponibile nel contesto `{label}`: {exc}") from exc
    if not resolved.is_relative_to(context.path):
        raise ValueError("il percorso richiesto esce dal contesto aggiuntivo")
    if not resolved.is_file():
        raise ValueError("il percorso richiesto nel contesto aggiuntivo non è un file")

    return ExternalContextFile(
        context=context,
        requested=reference,
        relative=relative,
        path=resolved,
    )
