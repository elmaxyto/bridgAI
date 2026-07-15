from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_SUPERPOWER_BYTES = 100_000
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class SuperpowerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MarkdownSuperpower:
    superpower_id: str
    title: str
    description: str
    category: str
    usage_mode: str
    operational_sectors: tuple[str, ...]
    includes: tuple[str, ...]
    instructions: str
    scope: str
    path: Path


def normalize_superpower_id(value: object) -> str:
    candidate = value.strip().lower() if isinstance(value, str) else ""
    if not _ID_PATTERN.fullmatch(candidate):
        raise SuperpowerError(
            "L'identificatore deve usare 1-64 caratteri tra lettere minuscole, "
            "numeri, punto, trattino e underscore."
        )
    return candidate


def parse_superpower_front_matter(text: str, path: Path, scope: str) -> MarkdownSuperpower:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        raise SuperpowerError(f"Front matter mancante in {path.name}.")
    try:
        closing = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise SuperpowerError(f"Front matter non chiuso in {path.name}.") from exc

    metadata: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise SuperpowerError(f"Metadato non valido in {path.name}: {line}")
        metadata[key.strip().lower()] = value.strip()

    superpower_id = normalize_superpower_id(metadata.get("id", path.stem))
    if path.stem.casefold() != superpower_id.casefold():
        raise SuperpowerError(
            f"Il file {path.name} deve avere lo stesso nome dell'id {superpower_id}."
        )
    title = metadata.get("title", "").strip()
    if not title:
        raise SuperpowerError(f"Titolo mancante in {path.name}.")
    description = metadata.get("description", "").strip()
    category = metadata.get("category", "Generale").strip() or "Generale"
    usage_mode = metadata.get("mode", "shared").strip().lower() or "shared"
    if usage_mode not in {"development", "operational", "shared"}:
        usage_mode = "shared"
    operational_sectors = tuple(
        value.strip() for value in metadata.get("operational_sectors", "").split(",") if value.strip()
    )
    includes = tuple(
        normalize_superpower_id(value.strip()) for value in metadata.get("includes", "").split(",") if value.strip()
    )
    instructions = "\n".join(lines[closing + 1 :]).strip()
    if not instructions:
        raise SuperpowerError(f"Istruzioni mancanti in {path.name}.")
    return MarkdownSuperpower(
        superpower_id=superpower_id,
        title=title[:200],
        description=description[:500],
        category=category[:80],
        usage_mode=usage_mode,
        operational_sectors=operational_sectors,
        includes=includes,
        instructions=instructions,
        scope=scope,
        path=path,
    )


def load_superpower(path: Path, scope: str) -> MarkdownSuperpower:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SuperpowerError(f"Impossibile leggere {path.name}: {exc}") from exc
    if size > MAX_SUPERPOWER_BYTES:
        raise SuperpowerError(f"{path.name} supera il limite di {MAX_SUPERPOWER_BYTES} byte.")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SuperpowerError(f"{path.name} non è un file Markdown UTF-8 valido.") from exc
    return parse_superpower_front_matter(text, path, scope)


def superpower_payload(item: MarkdownSuperpower) -> dict[str, object]:
    return {
        "id": item.superpower_id, "title": item.title, "description": item.description,
        "category": item.category, "mode": item.usage_mode,
        "operational_sectors": list(item.operational_sectors),
        "includes": list(item.includes),
        "markdown": item.instructions, "scope": item.scope,
    }
