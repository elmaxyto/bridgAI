from __future__ import annotations

import codecs
import difflib
import re
from pathlib import PurePosixPath

def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

def strip_scalar_markup(value: str) -> str:
    candidate = value.strip()
    wrappers = (("**", "**"), ("__", "__"), ("`", "`"), ('"', '"'), ("'", "'"))
    changed = True
    while changed and candidate:
        changed = False
        for opening, closing in wrappers:
            if (
                candidate.startswith(opening)
                and candidate.endswith(closing)
                and len(candidate) >= len(opening) + len(closing)
            ):
                candidate = candidate[len(opening):-len(closing)].strip()
                changed = True
                break
    return candidate

def normalize_relative_path(raw: str) -> str | None:
    candidate = strip_scalar_markup(raw).replace("\\", "/")
    if candidate.startswith("./"):
        candidate = candidate[2:]
    if not candidate or candidate.startswith(("/", "~/", "//")) or "://" in candidate:
        return None
    if re.match(r"^[A-Za-z]:/", candidate):
        return None
    if any(char in candidate for char in "<>|?*\x00") or candidate.endswith("/"):
        return None

    path = PurePosixPath(candidate)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if any(":" in part for part in path.parts):
        return None
    return path.as_posix()

def generate_unified_diff(relative: str, old: str, new: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
            lineterm="",
        )
    )

def generate_delete_diff(relative: str, old_bytes: bytes) -> str:
    try:
        old = old_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return f"File binario eliminato: {relative}"
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            [],
            fromfile=f"a/{relative}",
            tofile="/dev/null",
            lineterm="",
        )
    )

def decode_existing_text(relative: str, data: bytes) -> tuple[str, bool]:
    has_utf8_bom = data.startswith(codecs.BOM_UTF8)
    try:
        return data.decode("utf-8-sig" if has_utf8_bom else "utf-8"), has_utf8_bom
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"File {relative}: il contenuto esistente non è UTF-8 e non può essere "
            "sostituito tramite un file Markdown di aggiornamento."
        ) from exc

    return data.decode("utf-8-sig" if has_utf8_bom else "utf-8"), has_utf8_bom

def existing_newline_style(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"

def encode_replacement_content(content: str, old_text: str, has_utf8_bom: bool) -> bytes:
    newline = existing_newline_style(old_text)
    normalized = content if newline == "\n" else content.replace("\n", newline)
    encoded = normalized.encode("utf-8")
    return codecs.BOM_UTF8 + encoded if has_utf8_bom else encoded

def with_final_newline(content: str, final_newline: bool) -> str:
    if final_newline:
        return content if content.endswith("\n") else content + "\n"
    return content.rstrip("\n")
