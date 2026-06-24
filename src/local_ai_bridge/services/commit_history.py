from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


_RECORD_SEPARATOR = "\x1e"
_FIELD_SEPARATOR = "\x1f"


@dataclass(frozen=True, slots=True)
class CommitHistoryEntry:
    commit_hash: str
    committed_at: str
    author: str
    subject: str
    body: str


def _git_log_output(workspace: Path, timeout: int = 20) -> str:
    if not (workspace / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--date=short",
                "--format=%h%x1f%ad%x1f%an%x1f%s%x1f%b%x1e",
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def read_commit_history(workspace: Path) -> list[CommitHistoryEntry]:
    """Legge tutti i commit raggiungibili, dal più recente al più vecchio."""
    entries: list[CommitHistoryEntry] = []
    for raw_record in _git_log_output(workspace).split(_RECORD_SEPARATOR):
        record = raw_record.strip()
        if not record:
            continue

        fields = record.split(_FIELD_SEPARATOR, 4)
        if len(fields) != 5:
            continue

        commit_hash, committed_at, author, subject, body = fields
        entries.append(
            CommitHistoryEntry(
                commit_hash=commit_hash.strip(),
                committed_at=committed_at.strip(),
                author=author.strip(),
                subject=subject.strip() or "Commit senza titolo",
                body=body.strip(),
            )
        )
    return entries


def _body_lines(body: str) -> list[str]:
    rows: list[str] = []
    for line in body.splitlines():
        cleaned = line.strip().lstrip("-* ").strip()
        if cleaned and cleaned not in rows:
            rows.append(cleaned)
    return rows


def commit_history_markdown(workspace: Path) -> str:
    """Rende l'intera cronologia Git come changelog Markdown."""
    if not (workspace / ".git").exists():
        return "_Repository Git non rilevato._"

    entries = read_commit_history(workspace)
    if not entries:
        return "_Nessun commit presente nel repository._"

    lines = [
        f"Cronologia completa: **{len(entries)} commit** "
        "(dal più recente al più vecchio).",
        "",
    ]
    for entry in entries:
        lines.append(
            f"### {entry.committed_at} — {entry.subject} (`{entry.commit_hash}`)"
        )
        lines.append(f"Autore: {entry.author}")

        details = _body_lines(entry.body)
        if details:
            lines.append("")
            lines.extend(f"- {detail}" for detail in details)

        lines.append("")

    return "\n".join(lines).rstrip()


def commit_history_text(workspace: Path) -> str:
    """Rende l'intera cronologia Git in formato testuale per il Super-Report."""
    if not (workspace / ".git").exists():
        return "Repository Git non rilevato."

    entries = read_commit_history(workspace)
    if not entries:
        return "Nessun commit presente nel repository."

    lines = [
        f"Cronologia commit: {len(entries)} commit "
        "(dal più recente al più vecchio)."
    ]
    for entry in entries:
        lines.append("")
        lines.append(
            f"[{entry.committed_at}] {entry.subject} "
            f"({entry.commit_hash}) — {entry.author}"
        )
        lines.extend(f"  - {detail}" for detail in _body_lines(entry.body))

    return "\n".join(lines)
