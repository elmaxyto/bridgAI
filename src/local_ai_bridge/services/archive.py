from __future__ import annotations

import difflib
import json
import zipfile
from pathlib import Path
from typing import Any

from local_ai_bridge.core.io import sha256_bytes, sha256_file
from local_ai_bridge.core.models import ChangePlan, FileChange
from local_ai_bridge.core.safety import project_identity, resolve_workspace_target, validate_archive


MANIFEST_NAMES = ("applymanifest.json", "apply_manifest.json", "_apply_manifest.json")
COMMIT_MESSAGE_NAMES = (
    "commit-message.md", "commit_message.md", "commit-message.txt", "commit_message.txt",
    "commit-message.json", "commit_message.json",
)
MAX_COMMIT_MESSAGE_LENGTH = 10_000
PROJECT_METADATA_NAMES = ("bridgai-project.json", "_bridgai-project.json")


def _decode_for_diff(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _unified_diff(relative: str, old_data: bytes, new_data: bytes) -> str:
    old = _decode_for_diff(old_data)
    new = _decode_for_diff(new_data)
    if old is None or new is None:
        return f"--- {relative} ---\n[File binario: {len(old_data)} → {len(new_data)} byte]\n"
    lines = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(), fromfile=f"a/{relative}", tofile=f"b/{relative}", lineterm="",
    ))
    return "\n".join(lines)


def _delete_diff(relative: str, old_data: bytes) -> str:
    old = _decode_for_diff(old_data)
    if old is None:
        return f"--- a/{relative}\n+++ /dev/null\n[File binario eliminato: {len(old_data)} byte]"
    lines = list(difflib.unified_diff(
        old.splitlines(), [], fromfile=f"a/{relative}", tofile="/dev/null", lineterm="",
    ))
    return "\n".join(lines) or f"--- a/{relative}\n+++ /dev/null\n[File vuoto eliminato]"


def _load_manifest(zf: zipfile.ZipFile, member_info: dict[str, zipfile.ZipInfo]) -> tuple[dict[str, Any] | None, str | None]:
    by_name = {name.casefold(): name for name in member_info}
    for candidate in MANIFEST_NAMES:
        actual = by_name.get(candidate.casefold())
        if actual:
            try:
                value = json.loads(zf.read(member_info[actual]).decode("utf-8"))
            except Exception as exc:
                raise ValueError(f"Manifest non leggibile: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError("Il manifest deve essere un oggetto JSON.")
            return value, actual
    return None, None



def _load_project_metadata(
    zf: zipfile.ZipFile, member_info: dict[str, zipfile.ZipInfo]
) -> tuple[dict[str, Any] | None, str | None]:
    by_name = {name.casefold(): name for name in member_info}
    for candidate in PROJECT_METADATA_NAMES:
        actual = by_name.get(candidate.casefold())
        if not actual:
            continue
        try:
            value = json.loads(zf.read(member_info[actual]).decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"Identità progetto non leggibile: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("L'identità progetto deve essere un oggetto JSON.")
        identity = value.get("identity")
        if not isinstance(identity, str) or len(identity) != 64:
            raise ValueError("Identità progetto mancante o non valida.")
        return value, actual
    return None, None


def _validate_project_metadata(workspace: Path, metadata: dict[str, Any] | None) -> None:
    if metadata is None:
        return
    current = project_identity(workspace)
    if metadata.get("schema") != current["schema"] or metadata.get("identity") != current["identity"]:
        source_name = metadata.get("name") or metadata.get("directory") or "progetto sconosciuto"
        raise ValueError(
            f"ZIP destinato a un altro progetto ({source_name}). "
            f"Workspace corrente: {current['name']} ({current['directory']})."
        )


def _load_commit_message(
    zf: zipfile.ZipFile,
    member_info: dict[str, zipfile.ZipInfo],
    manifest: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    value: Any = manifest.get("commit_message") if manifest else None
    source_name: str | None = "manifest" if value is not None else None
    if value is None:
        by_name = {name.casefold(): name for name in member_info}
        for candidate in COMMIT_MESSAGE_NAMES:
            actual = by_name.get(candidate.casefold())
            if not actual:
                continue
            source_name = actual
            raw = zf.read(member_info[actual])
            if actual.casefold().endswith(".json"):
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except Exception as exc:
                    raise ValueError(f"Messaggio commit JSON non leggibile: {exc}") from exc
                if isinstance(parsed, str):
                    value = parsed
                elif isinstance(parsed, dict):
                    title = parsed.get("title", "")
                    summary = parsed.get("summary", [])
                    if not isinstance(title, str) or not isinstance(summary, list) or not all(isinstance(x, str) for x in summary):
                        raise ValueError("Messaggio commit JSON: title deve essere testo e summary una lista di testi.")
                    value = title.strip()
                    bullets = [item.strip() for item in summary if item.strip()]
                    if bullets:
                        value += ("\n\n" if value else "") + "\n".join(f"- {item}" for item in bullets)
                else:
                    raise ValueError("Messaggio commit JSON non valido.")
            else:
                try:
                    value = raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError("Il messaggio commit deve essere UTF-8.") from exc
            break
    if value is None:
        return None, None
    if not isinstance(value, str):
        raise ValueError("Il messaggio commit deve essere una stringa.")
    normalized = value.replace("\r\n", "\n").strip()
    if not normalized:
        return None, source_name
    if len(normalized) > MAX_COMMIT_MESSAGE_LENGTH:
        raise ValueError(f"Messaggio commit troppo lungo: massimo {MAX_COMMIT_MESSAGE_LENGTH} caratteri.")
    return normalized, source_name


def _mappings(manifest: dict[str, Any] | None, manifest_name: str | None, members: list[str]) -> list[dict[str, Any]]:
    reserved = {name.casefold() for name in COMMIT_MESSAGE_NAMES + PROJECT_METADATA_NAMES}
    file_members = [name for name in members if name != manifest_name and name.casefold() not in reserved]
    if manifest is None:
        return [{"source": name, "target": name, "expected_sha256": None} for name in file_members]
    items = manifest.get("files", [])
    if not isinstance(items, list):
        raise ValueError("Manifest: 'files' deve essere una lista.")
    available = set(file_members)
    output: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Manifest: elemento files {index} non valido.")
        source = item.get("source") or item.get("path")
        target = item.get("target") or item.get("path")
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError(f"Manifest: source/target mancanti nell'elemento files {index}.")
        source = source.replace("\\", "/")
        if source not in available:
            raise ValueError(f"Manifest: source non presente nello ZIP: {source}")
        if source in used_sources:
            raise ValueError(f"Manifest: source duplicato: {source}")
        used_sources.add(source)
        output.append({
            "source": source,
            "target": target,
            "expected_sha256": item.get("sha256") or item.get("original_sha256"),
        })
    undeclared = available - used_sources
    if undeclared:
        raise ValueError("Manifest incoerente: file non dichiarati: " + ", ".join(sorted(undeclared)))
    return output


def _deletions(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    if manifest is None:
        return []
    items = manifest.get("delete", [])
    if not isinstance(items, list):
        raise ValueError("Manifest: 'delete' deve essere una lista.")
    output: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            target = item
            expected = None
        elif isinstance(item, dict):
            target = item.get("target") or item.get("path")
            expected = item.get("sha256") or item.get("original_sha256")
        else:
            raise ValueError(f"Manifest: elemento delete {index} non valido.")
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f"Manifest: target mancante nell'elemento delete {index}.")
        output.append({"target": target, "expected_sha256": expected})
    return output


def _check_expected_hash(relative: str, target_path: Path, expected: Any) -> str | None:
    if not target_path.exists():
        if expected:
            raise ValueError(f"Hash dichiarato per un file inesistente: {relative}")
        return None
    old_hash = sha256_file(target_path)
    if expected:
        expected_text = str(expected).lower().strip()
        if not old_hash.lower().startswith(expected_text):
            raise ValueError(f"Conflitto hash per {relative}: atteso {expected_text}, attuale {old_hash}.")
    return old_hash


def inspect_zip(workspace: Path, zip_path: Path) -> ChangePlan:
    workspace = workspace.expanduser().resolve(strict=True)
    zip_path = zip_path.expanduser().resolve(strict=True)
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Il file selezionato non è uno ZIP valido.")
    changes: list[FileChange] = []
    contents: dict[str, bytes] = {}
    diffs: list[str] = []
    warnings: list[str] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        safe_members = validate_archive(zf)
        member_info = {
            Path(info.filename.replace("\\", "/")).as_posix(): info
            for info in zf.infolist() if not info.is_dir()
        }
        manifest, manifest_name = _load_manifest(zf, member_info)
        project_metadata, project_metadata_name = _load_project_metadata(zf, member_info)
        _validate_project_metadata(workspace, project_metadata)
        commit_message, commit_message_source = _load_commit_message(zf, member_info, manifest)
        mappings = _mappings(manifest, manifest_name, safe_members)
        deletions = _deletions(manifest)
        if project_metadata is None:
            warnings.append("ZIP senza identità progetto: compatibilità legacy, verificare manualmente il workspace.")
        seen_targets: set[str] = set()
        for item in mappings:
            source = item["source"]
            target_path = resolve_workspace_target(workspace, item["target"], allow_missing=True)
            relative = target_path.relative_to(workspace).as_posix()
            target_key = relative.casefold()
            if target_key in seen_targets:
                raise ValueError(f"Target duplicato nel manifest: {relative}")
            seen_targets.add(target_key)
            new_data = zf.read(member_info[source])
            if relative.lower().endswith(".py"):
                try:
                    compile(new_data.decode("utf-8"), relative, "exec")
                except (UnicodeDecodeError, SyntaxError) as exc:
                    raise ValueError(f"Python non valido in {source}: {exc}") from exc
            expected = item.get("expected_sha256")
            existed = target_path.exists()
            old_data = target_path.read_bytes() if existed else b""
            old_hash = _check_expected_hash(relative, target_path, expected)
            new_hash = sha256_bytes(new_data)
            kind = "modify" if existed else "create"
            if _decode_for_diff(new_data) is None:
                kind = "binary"
            changes.append(FileChange(
                source=source, target=relative, kind=kind, old_sha256=old_hash,
                new_sha256=new_hash, expected_sha256=str(expected) if expected else None, size=len(new_data),
            ))
            contents[relative] = new_data
            diff = _unified_diff(relative, old_data, new_data)
            if diff:
                diffs.append(f"\n### {relative}\n{diff}")
            else:
                warnings.append(f"{relative}: contenuto identico al file esistente.")
        for item in deletions:
            target_path = resolve_workspace_target(workspace, item["target"], allow_missing=True)
            relative = target_path.relative_to(workspace).as_posix()
            target_key = relative.casefold()
            if target_key in seen_targets:
                raise ValueError(f"Target duplicato nel manifest: {relative}")
            seen_targets.add(target_key)
            expected = item.get("expected_sha256")
            old_hash = _check_expected_hash(relative, target_path, expected)
            if not target_path.exists():
                warnings.append(f"{relative}: file già assente; cancellazione ignorata in modo idempotente.")
                old_data = b""
            else:
                old_data = target_path.read_bytes()
                diffs.append(f"\n### ELIMINA {relative}\n{_delete_diff(relative, old_data)}")
            changes.append(FileChange(
                source="", target=relative, kind="delete", old_sha256=old_hash,
                new_sha256=None, expected_sha256=str(expected) if expected else None, size=0,
            ))
    if not changes:
        raise ValueError("Lo ZIP non contiene file applicabili.")
    return ChangePlan(
        plan_type="zip", workspace=workspace, source_path=zip_path, changes=changes,
        diff="\n".join(diffs) or "Nessuna differenza testuale rilevata.", warnings=warnings,
        metadata={
            "contents": contents, "manifest": manifest, "manifest_name": manifest_name,
            "commit_message": commit_message, "commit_message_source": commit_message_source,
            "project_metadata": project_metadata, "project_metadata_name": project_metadata_name,
        },
    )
