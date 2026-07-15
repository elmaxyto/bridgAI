from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from local_ai_bridge.core.default_superpowers import (
    DefaultSuperpowerInstallError, ensure_default_superpowers,
)
from local_ai_bridge.core.settings import app_data_dir
from local_ai_bridge.core.superpower_index import (
    atomic_write_json,
    index_summaries,
    read_index_payload,
    remove_index_entry,
    upsert_index_entry,
    write_superpower_index,
)
from local_ai_bridge.core.superpower_models import (
    MAX_SUPERPOWER_BYTES,
    MarkdownSuperpower,
    SuperpowerError,
    load_superpower,
    normalize_superpower_id,
    superpower_payload,
)

LEGACY_PROJECT_SUPERPOWERS_RELATIVE = ".bridgai/superpowers"
APP_SUPERPOWERS_DIRECTORY = "superpowers"
SUPERPOWER_INDEX_FILENAME = "index.json"
SUPERPOWER_INDEX_VERSION = 1
MAX_SUPERPOWERS = 100
_REFERENCE_PATTERN = re.compile(
    r"@(?:superpower|superpotere):(\*|[a-z0-9][a-z0-9._-]{0,63})",
    re.IGNORECASE,
)


def superpowers_directory() -> Path:
    """Return the application-wide Markdown superpower library directory."""
    return app_data_dir() / APP_SUPERPOWERS_DIRECTORY


def project_superpowers_directory(workspace: Path) -> Path:
    """Return the legacy project-local directory used before app-wide storage."""
    return workspace / LEGACY_PROJECT_SUPERPOWERS_RELATIVE


def superpowers_index_path() -> Path:
    return superpowers_directory() / SUPERPOWER_INDEX_FILENAME


def project_superpowers_index_path(workspace: Path | None = None) -> Path:
    """Backward-compatible alias for the application-wide index path."""
    del workspace
    return superpowers_index_path()


def superpower_index_exists(workspace: Path | None = None) -> bool:
    del workspace
    path = superpowers_index_path()
    return path.is_file() and not path.is_symlink()


def _ensure_default_superpowers() -> bool:
    try:
        changed = ensure_default_superpowers(
            superpowers_directory(),
            MAX_SUPERPOWER_BYTES,
        )
    except DefaultSuperpowerInstallError as exc:
        raise SuperpowerError(str(exc)) from exc
    if changed:
        clear_superpower_cache()
    return changed


def _write_superpower_index(workspace: Path | None, items: list[MarkdownSuperpower]) -> Path:
    del workspace
    return write_superpower_index(
        superpowers_directory(),
        superpowers_index_path(),
        SUPERPOWER_INDEX_VERSION,
        items,
    )


def rebuild_superpower_index(workspace: Path | None = None) -> Path:
    _ensure_default_superpowers()
    if workspace is not None:
        _migrate_legacy_project_superpowers(workspace)
    directory = superpowers_directory()
    items = sorted(
        _library(directory, "app").values(),
        key=lambda item: (item.title.casefold(), item.superpower_id),
    )
    return _write_superpower_index(workspace, items)


def _read_index_payload(workspace: Path | None = None) -> dict[str, object] | None:
    del workspace
    return read_index_payload(superpowers_index_path(), SUPERPOWER_INDEX_VERSION)


def _update_superpower_index_entry(workspace: Path | None, item: MarkdownSuperpower) -> Path:
    payload = _read_index_payload(workspace)
    if payload is None:
        return rebuild_superpower_index(workspace)
    superpowers_directory().mkdir(parents=True, exist_ok=True)
    atomic_write_json(superpowers_index_path(), upsert_index_entry(payload, item))
    return superpowers_index_path()


def _remove_superpower_index_entry(workspace: Path | None, superpower_id: str) -> Path:
    payload = _read_index_payload(workspace)
    if payload is None:
        return rebuild_superpower_index(workspace)
    atomic_write_json(superpowers_index_path(), remove_index_entry(payload, superpower_id))
    return superpowers_index_path()


def list_superpower_summaries(
    workspace: Path | None = None, *, rebuild_if_missing: bool = True
) -> list[MarkdownSuperpower]:
    defaults_changed = _ensure_default_superpowers()
    if workspace is not None:
        _migrate_legacy_project_superpowers(workspace)
    if defaults_changed:
        rebuild_superpower_index(workspace)
    raw = _read_index_payload(workspace)
    if raw is None:
        if not rebuild_if_missing:
            return []
        rebuild_superpower_index(workspace)
        raw = _read_index_payload(workspace)
    return index_summaries(raw or {"superpowers": []}, superpowers_directory())


def get_superpower(workspace: Path | None, superpower_id: str) -> MarkdownSuperpower | None:
    defaults_changed = _ensure_default_superpowers()
    if workspace is not None:
        _migrate_legacy_project_superpowers(workspace)
    if defaults_changed:
        rebuild_superpower_index(workspace)
    normalized_id = normalize_superpower_id(superpower_id)
    path = superpowers_directory() / f"{normalized_id}.md"
    if path.is_symlink() or not path.is_file():
        return None
    try:
        return load_superpower(path, "app")
    except SuperpowerError:
        return None


def _library(directory: Path, scope: str) -> dict[str, MarkdownSuperpower]:
    if not directory.is_dir() or directory.is_symlink():
        return {}
    result: dict[str, MarkdownSuperpower] = {}
    for path in sorted(directory.glob("*.md"), key=lambda item: item.name.casefold()):
        if len(result) >= MAX_SUPERPOWERS or path.is_symlink() or not path.is_file():
            continue
        try:
            item = load_superpower(path, scope)
        except SuperpowerError:
            continue
        result[item.superpower_id] = item
    return result


def _migrate_legacy_project_superpowers(workspace: Path) -> bool:
    """Copy valid legacy project superpowers into the app library once.

    Existing app-level IDs always win, so opening an older project cannot
    overwrite a superpower already edited in the shared library. Legacy files
    remain untouched to keep rollback and manual recovery possible.
    """
    legacy_directory = project_superpowers_directory(workspace)
    legacy_items = _library(legacy_directory, "project")
    if not legacy_items:
        return False

    directory = superpowers_directory()
    if directory.exists() and directory.is_symlink():
        raise SuperpowerError(
            "La cartella dei superpoteri dell’app non può essere un collegamento simbolico."
        )
    directory.mkdir(parents=True, exist_ok=True)
    existing = _library(directory, "app")
    copied = False
    for superpower_id, item in legacy_items.items():
        if superpower_id in existing:
            continue
        target = directory / f"{superpower_id}.md"
        try:
            content = item.path.read_bytes()
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(content)
            temporary.replace(target)
        except OSError as exc:
            raise SuperpowerError(
                f"Impossibile migrare il superpotere {superpower_id}: {exc}"
            ) from exc
        copied = True
    if copied:
        clear_superpower_cache()
        items = sorted(
            _library(directory, "app").values(),
            key=lambda current: (current.title.casefold(), current.superpower_id),
        )
        _write_superpower_index(None, items)
    return copied


def _library_signature(directory: Path) -> tuple[tuple[str, int, int], ...]:
    if not directory.is_dir() or directory.is_symlink():
        return ()
    signature: list[tuple[str, int, int]] = []
    for path in sorted(directory.glob("*.md"), key=lambda item: item.name.casefold()):
        if len(signature) >= MAX_SUPERPOWERS or path.is_symlink() or not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((path.name, stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


@lru_cache(maxsize=32)
def _cached_app_library(
    directory_text: str,
    signature: tuple[tuple[str, int, int], ...],
) -> tuple[MarkdownSuperpower, ...]:
    del signature
    items = _library(Path(directory_text), "app")
    return tuple(
        sorted(
            items.values(),
            key=lambda item: (item.title.casefold(), item.superpower_id),
        )
    )


def clear_superpower_cache() -> None:
    _cached_app_library.cache_clear()


def list_superpowers(workspace: Path | None = None) -> list[MarkdownSuperpower]:
    defaults_changed = _ensure_default_superpowers()
    if workspace is not None:
        _migrate_legacy_project_superpowers(workspace)
    if defaults_changed:
        rebuild_superpower_index(workspace)
    directory = superpowers_directory()
    return list(_cached_app_library(str(directory.resolve()), _library_signature(directory)))


def referenced_superpower_ids(task: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in _REFERENCE_PATTERN.finditer(task):
        value = match.group(1).lower()
        if value not in found:
            found.append(value)
    return tuple(found)


def resolve_superpowers(workspace: Path, task: str) -> tuple[list[MarkdownSuperpower], list[str]]:
    library = {item.superpower_id: item for item in list_superpowers(workspace)}
    requested = list(referenced_superpower_ids(task))
    if "*" in requested:
        return list(library.values()), []

    selected: list[MarkdownSuperpower] = []
    missing: list[str] = []
    visited: set[str] = set()

    queue = requested.copy()
    while queue:
        superpower_id = queue.pop(0)
        if superpower_id in visited:
            continue
        visited.add(superpower_id)

        item = library.get(superpower_id)
        if item is None:
            if superpower_id in requested:
                missing.append(superpower_id)
        else:
            selected.append(item)
            for inc in item.includes:
                if inc not in visited:
                    queue.append(inc)

    return selected, missing


def save_superpower(
    superpower_id: str,
    title: str,
    instructions: str,
    *,
    workspace: Path | None = None,
    description: str = "",
    category: str = "Generale",
    usage_mode: str = "shared",
    operational_sectors: tuple[str, ...] = (),
    includes: tuple[str, ...] = (),
) -> Path:
    normalized_id = normalize_superpower_id(superpower_id)
    normalized_title = title.strip()
    normalized_instructions = instructions.strip()
    normalized_category = category.strip() or "Generale"
    normalized_mode = usage_mode.strip().lower()
    if normalized_mode not in {"development", "operational", "shared"}:
        raise SuperpowerError("La modalità deve essere development, operational o shared.")
    normalized_sectors = tuple(value.strip() for value in operational_sectors if value.strip())
    normalized_includes = tuple(normalize_superpower_id(value.strip()) for value in includes if value.strip())

    if not normalized_title:
        raise SuperpowerError("Il titolo è obbligatorio.")
    if not normalized_instructions:
        raise SuperpowerError("Le istruzioni sono obbligatorie.")
    directory = superpowers_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{normalized_id}.md"
    content = (
        "---\n"
        f"id: {normalized_id}\n"
        f"title: {normalized_title[:200]}\n"
        f"description: {description.strip()[:500]}\n"
        f"category: {normalized_category[:80]}\n"
        f"mode: {normalized_mode}\n"
        + (f"operational_sectors: {', '.join(normalized_sectors)}\n" if normalized_sectors else "")
        + (f"includes: {', '.join(normalized_includes)}\n" if normalized_includes else "")
        + "---\n\n"
        f"{normalized_instructions}\n"
    )
    if len(content.encode("utf-8")) > MAX_SUPERPOWER_BYTES:
        raise SuperpowerError(f"Il superpotere supera il limite di {MAX_SUPERPOWER_BYTES} byte.")
    temporary = target.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(target)
    clear_superpower_cache()
    _update_superpower_index_entry(
        workspace,
        MarkdownSuperpower(
            superpower_id=normalized_id,
            title=normalized_title[:200],
            description=description.strip()[:500],
            category=normalized_category[:80],
            usage_mode=normalized_mode,
            operational_sectors=normalized_sectors,
            includes=normalized_includes,
            instructions=normalized_instructions,
            scope="app",
            path=target,
        ),
    )
    return target


def delete_superpower(superpower_id: str, *, workspace: Path | None = None) -> Path:
    normalized_id = normalize_superpower_id(superpower_id)
    directory = superpowers_directory()
    target = directory / f"{normalized_id}.md"
    if target.is_symlink():
        raise SuperpowerError("I collegamenti simbolici non sono consentiti.")
    if not target.is_file():
        raise SuperpowerError(f"Superpotere non trovato: {normalized_id}.")
    target.unlink()
    clear_superpower_cache()
    _remove_superpower_index_entry(workspace, normalized_id)
    return target


def superpowers_markdown(workspace: Path, task: str) -> str:
    selected, missing = resolve_superpowers(workspace, task)
    available = list_superpowers(workspace)
    chunks = [
        "Richiamo: usa `@superpower:id` (o `@superpotere:id`) nel task. "
        "Usa `@superpower:*` per richiamare tutta la libreria.",
        "Tutti i superpoteri risiedono nella cartella dati di BridgAI e restano "
        "disponibili quando cambi progetto.",
    ]
    if available:
        chunks.append(
            "Disponibili: "
            + ", ".join(
                f"`{item.superpower_id}` ({item.scope})" for item in available
            )
            + "."
        )
    else:
        chunks.append("Nessun superpotere Markdown configurato.")
    if missing:
        chunks.append("Non trovati: " + ", ".join(f"`{item}`" for item in missing) + ".")
    for item in selected:
        heading = f"### {item.title} (`{item.superpower_id}`, {item.scope})"
        if item.description:
            heading += f"\n\n_{item.description}_"
        chunks.append(f"{heading}\n\n{item.instructions}")
    return "\n\n".join(chunks)
