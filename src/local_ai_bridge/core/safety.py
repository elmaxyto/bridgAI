from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


BLOCKED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "venv", ".venv", "dist", "build",
    ".ssh", ".aws", ".gnupg",
}
BLOCKED_EXACT_NAMES = {
    ".env", "id_rsa", "id_dsa", "id_ed25519", "credentials.json",
    "secrets.json", "secrets.yaml", "secrets.yml", "secret.json", "api_keys.json",
}
BLOCKED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt"}
WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")


class SafetyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_members: int = 2_000
    max_single_file: int = 20 * 1024 * 1024
    max_uncompressed: int = 250 * 1024 * 1024
    max_compression_ratio: float = 200.0


def project_identity(workspace: Path) -> dict[str, str]:
    """Return a stable logical identity without depending on the absolute path."""
    workspace = workspace.expanduser().resolve(strict=True)
    if not workspace.is_dir():
        raise SafetyError("Il workspace non è una cartella valida.")

    kind = "directory"
    project_name = workspace.name
    pyproject = workspace / "pyproject.toml"
    package_json = workspace / "package.json"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            value = data.get("project", {}).get("name")
            if isinstance(value, str) and value.strip():
                project_name = value.strip()
                kind = "python"
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            pass
    elif package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            value = data.get("name") if isinstance(data, dict) else None
            if isinstance(value, str) and value.strip():
                project_name = value.strip()
                kind = "node"
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass

    canonical = f"bridgai-project-v1\n{kind.casefold()}\n{project_name.casefold()}\n{workspace.name.casefold()}"
    return {
        "schema": "bridgai-project-v1",
        "kind": kind,
        "name": project_name,
        "directory": workspace.name,
        "identity": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def _normalized_parts(raw_path: str) -> tuple[str, ...]:
    value = raw_path.replace("\\", "/").strip()
    if not value or value.startswith("/") or WINDOWS_DRIVE_RE.match(value):
        raise SafetyError(f"Percorso assoluto o vuoto non consentito: {raw_path}")
    path = PurePosixPath(value)
    parts = tuple(part for part in path.parts if part not in ("", "."))
    if not parts or any(part == ".." for part in parts):
        raise SafetyError(f"Path traversal non consentito: {raw_path}")
    return parts


def is_sensitive_relative_path(raw_path: str) -> bool:
    try:
        parts = _normalized_parts(raw_path)
    except SafetyError:
        return True
    lowered = tuple(part.lower() for part in parts)
    if any(part in BLOCKED_DIRS for part in lowered):
        return True
    name = lowered[-1]
    if name in BLOCKED_EXACT_NAMES or name.startswith(".env."):
        return True
    if any(name.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        return True
    return False


def resolve_workspace_target(workspace: Path, raw_path: str, *, allow_missing: bool = True) -> Path:
    workspace = workspace.expanduser().resolve(strict=True)
    if not workspace.is_dir():
        raise SafetyError("Il workspace non è una cartella valida.")
    parts = _normalized_parts(raw_path)
    relative = Path(*parts)
    if is_sensitive_relative_path(relative.as_posix()):
        raise SafetyError(f"Percorso sensibile o escluso: {raw_path}")
    candidate = workspace.joinpath(relative)
    resolved_parent = candidate.parent.resolve(strict=False)
    try:
        resolved_parent.relative_to(workspace)
    except ValueError as exc:
        raise SafetyError(f"Percorso esterno al workspace: {raw_path}") from exc
    if candidate.exists() or candidate.is_symlink():
        if candidate.is_symlink():
            raise SafetyError(f"Link simbolico non consentito: {raw_path}")
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(workspace)
        except ValueError as exc:
            raise SafetyError(f"Percorso risolto fuori dal workspace: {raw_path}") from exc
        if not resolved.is_file():
            raise SafetyError(f"Il target non è un file regolare: {raw_path}")
        return resolved
    if not allow_missing:
        raise SafetyError(f"File non trovato: {raw_path}")
    return candidate


def validate_zip_info(info: zipfile.ZipInfo, limits: ArchiveLimits) -> str | None:
    if info.is_dir():
        return None
    parts = _normalized_parts(info.filename)
    relative = PurePosixPath(*parts).as_posix()
    if is_sensitive_relative_path(relative):
        raise SafetyError(f"Elemento ZIP sensibile o escluso: {info.filename}")
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if file_type and file_type not in (stat.S_IFREG, stat.S_IFDIR):
        raise SafetyError(f"Elemento ZIP non regolare o link: {info.filename}")
    if info.file_size > limits.max_single_file:
        raise SafetyError(f"File ZIP troppo grande: {info.filename}")
    compressed = max(info.compress_size, 1)
    if info.file_size / compressed > limits.max_compression_ratio:
        raise SafetyError(f"Rapporto di compressione sospetto: {info.filename}")
    return relative


def validate_archive(zf: zipfile.ZipFile, limits: ArchiveLimits | None = None) -> list[str]:
    limits = limits or ArchiveLimits()
    infos = zf.infolist()
    if len(infos) > limits.max_members:
        raise SafetyError(f"Archivio con troppi elementi: {len(infos)}")
    total = sum(info.file_size for info in infos)
    if total > limits.max_uncompressed:
        raise SafetyError("Archivio troppo grande dopo la decompressione.")
    safe: list[str] = []
    seen: set[str] = set()
    for info in infos:
        relative = validate_zip_info(info, limits)
        if relative is None:
            continue
        key = relative.casefold()
        if key in seen:
            raise SafetyError(f"Elemento duplicato nello ZIP: {relative}")
        seen.add(key)
        safe.append(relative)
    return safe
