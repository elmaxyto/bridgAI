from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from local_ai_bridge.core.settings import app_data_dir


MANAGED_DIR_NAME = "LocalAIBridgeTemp"
MARKER_NAME = ".local_ai_bridge_temp"


@dataclass(frozen=True, slots=True)
class CleanupResult:
    files_removed: int
    directories_removed: int
    bytes_removed: int


def configured_temp_root(configured: str | Path | None) -> Path:
    if configured:
        base = Path(configured).expanduser()
        if base.name == MANAGED_DIR_NAME:
            root = base
        else:
            root = base / MANAGED_DIR_NAME
    else:
        root = app_data_dir() / "temp"
    root.mkdir(parents=True, exist_ok=True)
    marker = root / MARKER_NAME
    marker.touch(exist_ok=True)
    for name in ("exports", "imports", "patches", "ai_models"):
        (root / name).mkdir(exist_ok=True)
    return root.resolve()


def managed_subdir(configured: str | Path | None, name: str) -> Path:
    if name not in {"exports", "imports", "patches", "ai_models"}:
        raise ValueError(f"Sottocartella temporanea non consentita: {name}")
    path = configured_temp_root(configured) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _latest_file_with_suffixes(
    directory: str | Path | None,
    suffixes: set[str],
) -> Path | None:
    if not directory:
        return None
    folder = Path(directory).expanduser()
    if not folder.is_dir():
        return None
    normalized = {suffix.casefold() for suffix in suffixes}
    candidates = [
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.casefold() in normalized
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name.casefold()))


def latest_zip_file(directory: str | Path | None) -> Path | None:
    return _latest_file_with_suffixes(directory, {".zip"})


def latest_markdown_file(directory: str | Path | None) -> Path | None:
    return _latest_file_with_suffixes(directory, {".md", ".markdown"})


def stage_import_zip(source: Path, configured: str | Path | None) -> Path:
    source = source.expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".zip":
        raise ValueError("Il file selezionato non è uno ZIP valido.")
    imports = managed_subdir(configured, "imports")
    try:
        source.relative_to(imports)
        return source
    except ValueError:
        pass
    target = imports / source.name
    counter = 1
    while target.exists():
        if target.stat().st_size == source.stat().st_size and target.read_bytes() == source.read_bytes():
            return target
        target = imports / f"{source.stem}_{counter}{source.suffix}"
        counter += 1
    shutil.copy2(source, target)
    return target


def clean_managed_temp(configured: str | Path | None) -> CleanupResult:
    root = configured_temp_root(configured)
    marker = root / MARKER_NAME
    if not marker.is_file():
        raise RuntimeError("Pulizia rifiutata: cartella temporanea non riconosciuta.")
    files = directories = total_bytes = 0
    for child in list(root.iterdir()):
        if child.name == MARKER_NAME:
            continue
        if child.is_symlink():
            child.unlink()
            files += 1
            continue
        if child.is_file():
            try:
                total_bytes += child.stat().st_size
            except OSError:
                pass
            child.unlink()
            files += 1
            continue
        for nested in child.rglob("*"):
            if nested.is_file() and not nested.is_symlink():
                files += 1
                try:
                    total_bytes += nested.stat().st_size
                except OSError:
                    pass
            elif nested.is_dir():
                directories += 1
        shutil.rmtree(child)
        directories += 1
    for name in ("exports", "imports", "patches", "ai_models"):
        (root / name).mkdir(exist_ok=True)
    return CleanupResult(files, directories, total_bytes)
