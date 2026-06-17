from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_LANGUAGE = "it"
_language = _DEFAULT_LANGUAGE
_catalog: dict[str, str] = {}


def available_languages() -> tuple[tuple[str, str], ...]:
    return (("it", "Italiano"), ("en", "English"))


def normalize_language(value: str | None) -> str:
    return value if value in {"it", "en"} else _DEFAULT_LANGUAGE


def configure_language(value: str | None) -> str:
    global _language, _catalog
    _language = normalize_language(value)
    path = Path(__file__).resolve().parent / "resources" / f"i18n_{_language}.json"
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
        _catalog = data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        _catalog = {}
    return _language


def current_language() -> str:
    return _language


def translate(text: str) -> str:
    return _catalog.get(text, text)


def tr(text: str) -> str:
    return translate(text)
