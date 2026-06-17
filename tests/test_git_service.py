from __future__ import annotations

from pathlib import Path

import pytest

from local_ai_bridge.services import git as git_service
from local_ai_bridge.services import github as github_service


def test_normalize_github_repository_accepts_slug_and_urls() -> None:
    expected = ("octocat/Hello-World", "https://github.com/octocat/Hello-World.git")
    assert github_service.normalize_github_repository("octocat/Hello-World") == expected
    assert github_service.normalize_github_repository("https://github.com/octocat/Hello-World.git") == expected
    assert github_service.normalize_github_repository("git@github.com:octocat/Hello-World.git") == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "https://example.com/owner/repo",
        "owner/repo/issues",
        "owner name/repo",
        "-owner/repo",
    ],
)
def test_normalize_github_repository_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(github_service.GitIntegrationError):
        github_service.normalize_github_repository(value)


def test_connect_repository_adds_canonical_origin(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[tuple[list[str], Path | None]] = []

    monkeypatch.setattr(github_service, "git_available", lambda: True)
    monkeypatch.setattr(github_service, "git_remote_url", lambda workspace, remote_name="origin": None)

    def fake_run(command, *, cwd=None, timeout=60, check=True):
        calls.append((command, cwd))
        return "ok"

    monkeypatch.setattr(github_service, "_run_command", fake_run)
    output = github_service.connect_github_repository(tmp_path, "octocat/Hello-World")

    assert calls == [
        (["git", "remote", "add", "origin", "https://github.com/octocat/Hello-World.git"], tmp_path)
    ]
    assert "Nessun pull, merge o push" in output


def test_create_repository_builds_noninteractive_gh_command(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(github_service, "git_remote_url", lambda workspace, remote_name="origin": None)
    monkeypatch.setattr(github_service, "git_has_commits", lambda workspace: True)

    def fake_run(command, *, cwd=None, timeout=60, check=True):
        calls.append(command)
        assert cwd == tmp_path
        return "created"

    monkeypatch.setattr(github_service, "_run_command", fake_run)
    output = github_service.create_github_repository(
        tmp_path,
        "demo-project",
        visibility="private",
        description="Demo",
        push=True,
    )

    assert calls == [[
        "gh",
        "repo",
        "create",
        "demo-project",
        "--source",
        ".",
        "--remote",
        "origin",
        "--private",
        "--description",
        "Demo",
        "--push",
    ]]
    assert "Remote origin configurato" in output


def test_create_repository_refuses_push_without_commits(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(github_service, "git_remote_url", lambda workspace, remote_name="origin": None)
    monkeypatch.setattr(github_service, "git_has_commits", lambda workspace: False)

    with pytest.raises(git_service.GitIntegrationError, match="Non ci sono commit"):
        github_service.create_github_repository(tmp_path, "demo", push=True)


def test_push_uses_current_branch_and_never_stages_files(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    calls: list[list[str]] = []
    monkeypatch.setattr(git_service, "git_available", lambda: True)
    monkeypatch.setattr(git_service, "git_remote_url", lambda workspace, remote_name="origin": "https://github.com/a/b.git")
    monkeypatch.setattr(git_service, "git_has_commits", lambda workspace: True)
    monkeypatch.setattr(git_service, "git_current_branch", lambda workspace: "feature/test")

    def fake_run(command, *, cwd=None, timeout=60, check=True):
        calls.append(command)
        return "pushed"

    monkeypatch.setattr(git_service, "_run_command", fake_run)
    output = git_service.push_current_branch(tmp_path)

    assert calls == [["git", "push", "--set-upstream", "origin", "feature/test"]]
    assert "Branch feature/test inviato" in output


def test_application_icon_resource_exists() -> None:
    from local_ai_bridge.app import _icon_path

    assert _icon_path().is_file()


def test_list_github_accounts_uses_json_without_exposing_tokens(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)

    def fake_run(command, *, cwd=None, timeout=60, check=True):
        calls.append(command)
        return "alice\nbob\nalice\n"

    monkeypatch.setattr(github_service, "_run_command", fake_run)
    assert github_service.list_github_accounts() == ["alice", "bob"]
    assert "--show-token" not in calls[0]
    assert calls[0][-2:] == ["--jq", '.hosts["github.com"][].login']


def test_switch_github_account_is_noninteractive(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)

    def fake_run(command, *, cwd=None, timeout=60, check=True):
        calls.append(command)
        return "switched"

    monkeypatch.setattr(github_service, "_run_command", fake_run)
    assert github_service.github_switch_account("octocat") == "switched"
    assert calls == [[
        "gh",
        "auth",
        "switch",
        "--hostname",
        "github.com",
        "--user",
        "octocat",
    ]]


def test_generate_commit_message_uses_real_changes_and_session_note(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace
    from local_ai_bridge.services import git as git_service

    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(git_service, "git_available", lambda: True)
    monkeypatch.setattr(
        git_service,
        "_run_command",
        lambda command, **kwargs: " M src/app.py\n?? tests/test_app.py" if "status" in command else "ok",
    )

    class Sessions:
        def iter_for_workspace(self, workspace):
            yield tmp_path, SimpleNamespace(status="applied", commit_message="feat: improve app\n\n- update behavior")

    message = git_service.generate_commit_message(tmp_path, Sessions())
    assert message.startswith("feat: improve app")
    assert "Update src/app.py" in message
    assert "Add tests/test_app.py" in message


def test_create_commit_stages_only_after_explicit_call(tmp_path: Path, monkeypatch) -> None:
    from local_ai_bridge.services import git as git_service

    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(git_service, "git_available", lambda: True)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if "status" in command:
            return " M src/app.py"
        return "done"

    monkeypatch.setattr(git_service, "_run_command", fake_run)
    result = git_service.create_commit(tmp_path, "feat: update app")
    assert result == "done"
    assert commands[-2] == ["git", "add", "--all", "--", "."]
    assert commands[-1] == ["git", "commit", "-m", "feat: update app"]
