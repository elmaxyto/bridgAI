from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_bridge.services import git as git_service
from local_ai_bridge.services import github as github_service
from local_ai_bridge.services import gitignore as gitignore_service


def test_publish_gitignore_is_created_for_node_projects(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    result = gitignore_service.ensure_publish_gitignore(tmp_path, untrack=False)

    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert result.created is True
    assert result.changed is True
    assert result.detected_stacks == ("node",)
    assert "node_modules/" in content
    assert ".next/" in content
    assert ".env" in content
    assert gitignore_service.gitignore_update_needed(tmp_path) is False


def test_publish_gitignore_preserves_custom_rules_and_updates_one_managed_block(
    tmp_path: Path,
) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("custom-output/\n", encoding="utf-8")
    gitignore_service.ensure_publish_gitignore(tmp_path, untrack=False)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    result = gitignore_service.ensure_publish_gitignore(tmp_path, untrack=False)

    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert result.created is False
    assert result.changed is True
    assert "custom-output/\n" in content
    assert content.index(gitignore_service.MANAGED_START) < content.index("custom-output/")
    assert content.count(gitignore_service.MANAGED_START) == 1
    assert "*.egg-info/" in content


def test_publish_gitignore_untracks_only_known_generated_paths(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        gitignore_service,
        "_tracked_files",
        lambda workspace: (
            "node_modules/pkg/index.js",
            "dist/app.js",
            ".env",
            ".env.example",
            "src/app.js",
            "docs/build-guide.md",
        ),
    )
    managed_candidates: list[str] = []
    monkeypatch.setattr(
        gitignore_service,
        "_effectively_ignored_paths",
        lambda workspace, paths: managed_candidates.extend(paths) or paths,
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        gitignore_service,
        "_run_command",
        lambda command, **kwargs: commands.append(command) or "ok",
    )

    result = gitignore_service.ensure_publish_gitignore(tmp_path)

    assert managed_candidates == ["node_modules/pkg/index.js", "dist/app.js", ".env"]
    assert result.untracked_paths == ("node_modules/pkg/index.js", "dist/app.js", ".env")
    assert "segreti già pubblicati" in result.summary
    assert commands == [[
        "git",
        "rm",
        "-r",
        "--cached",
        "--ignore-unmatch",
        "-f",
        "--",
        "node_modules/pkg/index.js",
        "dist/app.js",
        ".env",
    ]]


def test_publish_gitignore_rejects_an_incomplete_managed_block(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(
        gitignore_service.MANAGED_START + "\nnode_modules/\n",
        encoding="utf-8",
    )

    with pytest.raises(git_service.GitIntegrationError, match="incompleto o duplicato"):
        gitignore_service.ensure_publish_gitignore(tmp_path, untrack=False)


def test_simple_github_status_reports_pending_gitignore_update(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(github_service, "git_available", lambda: True)
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(
        github_service,
        "git_remote_url",
        lambda workspace, remote_name="origin": "https://github.com/alice/demo.git",
    )
    monkeypatch.setattr(github_service, "_current_changes", lambda workspace: [])

    status = github_service.simple_github_status(tmp_path)

    assert status["gitignore_update_pending"] is True
    assert status["has_changes"] is True
    assert status["change_count"] == 1


def test_publish_or_update_runs_gitignore_protection_before_commit(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[str] = []
    remote = {"value": "https://github.com/alice/demo.git"}
    monkeypatch.setattr(github_service, "git_available", lambda: True)
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(github_service, "list_github_accounts", lambda: ["alice"])
    monkeypatch.setattr(
        github_service,
        "ensure_publish_gitignore",
        lambda workspace: calls.append("protect")
        or gitignore_service.GitIgnoreUpdate(created=True, changed=True),
    )
    monkeypatch.setattr(
        github_service,
        "_current_changes",
        lambda workspace: calls.append("changes") or [("create", ".gitignore")],
    )
    monkeypatch.setattr(
        github_service,
        "generate_commit_message",
        lambda workspace, session_manager=None: "chore: add gitignore",
    )
    monkeypatch.setattr(
        github_service,
        "create_commit",
        lambda workspace, message: calls.append("commit") or "committed",
    )
    monkeypatch.setattr(github_service, "git_has_commits", lambda workspace: True)
    monkeypatch.setattr(
        github_service,
        "git_remote_url",
        lambda workspace, remote_name="origin": remote["value"],
    )
    monkeypatch.setattr(
        github_service,
        "push_current_branch",
        lambda workspace: calls.append("push") or "pushed",
    )

    result = github_service.publish_or_update_github(tmp_path)

    assert calls == ["protect", "changes", "commit", "push"]
    assert result["gitignore_created"] is True
    assert result["gitignore_updated"] is True
    assert result["untracked_generated_count"] == 0
