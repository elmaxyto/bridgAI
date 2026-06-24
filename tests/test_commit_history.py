from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from local_ai_bridge.core.skills import SkillContext, SkillRegistry
from local_ai_bridge.services import commit_history, reporting_git
from local_ai_bridge.skills.builtins import register_builtin_skills


def _git_log_payload() -> str:
    field_separator = "\x1f"
    record_separator = "\x1e"
    return (
        f"abc1234{field_separator}2026-06-22{field_separator}"
        f"Alice{field_separator}feat: add report history{field_separator}"
        f"Include every commit message\nAdd tests{record_separator}\n"
        f"def5678{field_separator}2026-06-21{field_separator}"
        f"Bob{field_separator}fix: stabilize export{field_separator}"
        f"{record_separator}\n"
    )


def test_read_commit_history_parses_all_messages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        commit_history,
        "_git_log_output",
        lambda workspace: _git_log_payload(),
    )

    entries = commit_history.read_commit_history(tmp_path)

    assert [entry.commit_hash for entry in entries] == [
        "abc1234",
        "def5678",
    ]
    assert entries[0].subject == "feat: add report history"
    assert entries[0].body == "Include every commit message\nAdd tests"


def test_commit_history_markdown_combines_subjects_and_bodies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        commit_history,
        "_git_log_output",
        lambda workspace: _git_log_payload(),
    )

    changelog = commit_history.commit_history_markdown(tmp_path)

    assert "Cronologia completa: **2 commit**" in changelog
    assert (
        "2026-06-22 — feat: add report history (`abc1234`)"
        in changelog
    )
    assert "- Include every commit message" in changelog
    assert (
        "2026-06-21 — fix: stabilize export (`def5678`)"
        in changelog
    )


def test_commit_history_handles_workspace_without_repository(
    tmp_path: Path,
) -> None:
    assert (
        commit_history.commit_history_markdown(tmp_path)
        == "_Repository Git non rilevato._"
    )
    assert (
        commit_history.commit_history_text(tmp_path)
        == "Repository Git non rilevato."
    )


def test_commit_history_handles_repository_without_commits(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        commit_history,
        "_git_log_output",
        lambda workspace: "",
    )

    assert (
        commit_history.commit_history_markdown(tmp_path)
        == "_Nessun commit presente nel repository._"
    )
    assert (
        commit_history.commit_history_text(tmp_path)
        == "Nessun commit presente nel repository."
    )


def test_git_snapshot_includes_commit_changelog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        reporting_git.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="## main\n M src/app.py\n",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        reporting_git,
        "commit_history_text",
        lambda workspace: (
            "Cronologia commit: 1 commit\n\n"
            "[2026-06-22] feat: history (abc1234) — Alice"
        ),
    )

    snapshot = reporting_git.git_snapshot(tmp_path)

    assert "M src/app.py" in snapshot
    assert "--- Changelog dai commit ---" in snapshot
    assert "feat: history" in snapshot


def test_builtin_registry_exposes_git_changelog_skill(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        "local_ai_bridge.skills.builtins.commit_history_markdown",
        lambda workspace: "generated changelog",
    )

    registry = SkillRegistry()
    register_builtin_skills(registry)

    result = registry.execute(
        "git.changelog",
        SkillContext(workspace=tmp_path),
    )

    assert result.ok
    assert result.message == "Changelog Git generato."
    assert result.data == "generated changelog"
    assert "git.changelog" in {
        spec.skill_id for spec in registry.list_specs()
    }
