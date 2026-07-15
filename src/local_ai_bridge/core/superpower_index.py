from __future__ import annotations

import json
from pathlib import Path

from local_ai_bridge.core.superpower_models import (
    MarkdownSuperpower,
    SuperpowerError,
    normalize_superpower_id,
)


def summary_payload(item: MarkdownSuperpower) -> dict[str, object]:
    return {
        "id": item.superpower_id,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "mode": item.usage_mode,
        "operational_sectors": list(item.operational_sectors),
        "includes": list(item.includes),
        "file": item.path.name,
    }


def write_superpower_index(
    directory: Path,
    index_path: Path,
    version: int,
    items: list[MarkdownSuperpower],
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": version,
        "superpowers": [summary_payload(item) for item in items],
    }
    atomic_write_json(index_path, payload)
    return index_path


def read_index_payload(index_path: Path, version: int) -> dict[str, object] | None:
    if not index_path.is_file() or index_path.is_symlink():
        return None
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != version:
        return None
    if not isinstance(payload.get("superpowers"), list):
        return None
    return payload


def index_summaries(
    raw: dict[str, object],
    directory: Path,
) -> list[MarkdownSuperpower]:
    result: list[MarkdownSuperpower] = []
    for entry in raw.get("superpowers", []):
        if not isinstance(entry, dict):
            continue
        try:
            superpower_id = normalize_superpower_id(entry.get("id", ""))
        except SuperpowerError:
            continue
        filename = str(entry.get("file", f"{superpower_id}.md"))
        if Path(filename).name != filename or not filename.endswith(".md"):
            continue
        result.append(
            MarkdownSuperpower(
                superpower_id=superpower_id,
                title=str(entry.get("title", superpower_id))[:200],
                description=str(entry.get("description", ""))[:500],
                category=str(entry.get("category", "Generale"))[:80] or "Generale",
                usage_mode=str(entry.get("mode", "shared")),
                operational_sectors=tuple(
                    str(value) for value in entry.get("operational_sectors", [])
                    if isinstance(value, str) and value.strip()
                ),
                includes=tuple(
                    str(value) for value in entry.get("includes", [])
                    if isinstance(value, str) and value.strip()
                ),
                instructions="",
                scope="app",
                path=directory / filename,
            )
        )
    return result


def upsert_index_entry(
    payload: dict[str, object],
    item: MarkdownSuperpower,
) -> dict[str, object]:
    entries = [
        entry for entry in payload["superpowers"]
        if isinstance(entry, dict) and entry.get("id") != item.superpower_id
    ]
    entries.append(summary_payload(item))
    entries.sort(
        key=lambda entry: (
            str(entry.get("title", "")).casefold(),
            str(entry.get("id", "")),
        )
    )
    return {"version": payload["version"], "superpowers": entries}


def remove_index_entry(payload: dict[str, object], superpower_id: str) -> dict[str, object]:
    entries = [
        entry for entry in payload["superpowers"]
        if isinstance(entry, dict) and entry.get("id") != superpower_id
    ]
    return {"version": payload["version"], "superpowers": entries}


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
