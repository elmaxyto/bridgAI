from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from local_ai_bridge.core.settings import AppSettings, SettingsStore


_DOWNLOAD_DIRECTORY_PROBE_PREFIX = ".bridgai-download-directory-"
_DOWNLOAD_DIRECTORY_PROBE_SUFFIX = ".tmp"
_DOWNLOAD_DIRECTORY_PROBE_CONTENT = b"BridgAI download directory probe\n"
_DOWNLOAD_DIRECTORY_PROBE_MAX_AGE = 120.0


def _save_update_directory(settings: AppSettings, value: str) -> None:
    store = SettingsStore()
    current = store.load()
    current.update_zip_directory = value
    store.save(current)
    settings.update_zip_directory = value


def _download_directory_probe(raw_path: object) -> Path:
    value = str(raw_path or "").strip()
    if not value or "\x00" in value:
        raise ValueError("Chrome non ha comunicato una cartella Download valida.")
    supplied = Path(value).expanduser()
    if supplied.is_symlink() or supplied.parent.is_symlink():
        raise ValueError("La cartella Download dell’estensione non può usare link simbolici.")
    probe = supplied.resolve(strict=True)
    if not probe.is_file():
        raise ValueError("Il file di verifica della cartella Download non è valido.")
    if not (
        probe.name.startswith(_DOWNLOAD_DIRECTORY_PROBE_PREFIX)
        and probe.name.endswith(_DOWNLOAD_DIRECTORY_PROBE_SUFFIX)
    ):
        raise ValueError("Il file di verifica della cartella Download non è riconosciuto.")
    stat = probe.stat()
    if stat.st_size > 128 or time.time() - stat.st_mtime > _DOWNLOAD_DIRECTORY_PROBE_MAX_AGE:
        raise ValueError("Il file di verifica della cartella Download è scaduto o non valido.")
    if probe.read_bytes() != _DOWNLOAD_DIRECTORY_PROBE_CONTENT:
        raise ValueError("Il contenuto di verifica della cartella Download non è valido.")
    return probe


def configure_download_directory(
    settings: AppSettings,
    body: dict[str, Any],
) -> dict[str, Any]:
    enabled = bool(body.get("enabled"))
    raw_path = body.get("path")
    if not enabled or not str(raw_path or "").strip():
        _save_update_directory(settings, "")
        return {
            "action": "download_directory_reset",
            "update_directory": "",
        }

    probe = _download_directory_probe(raw_path)
    directory = probe.parent.resolve(strict=True)
    try:
        _save_update_directory(settings, str(directory))
    finally:
        probe.unlink(missing_ok=True)
    return {
        "action": "download_directory_ready",
        "update_directory": str(directory),
    }
