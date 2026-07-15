from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_github_commit_identity_uses_active_account_and_id_noreply(monkeypatch) -> None:
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(
        github_service,
        "_run_command",
        lambda command, **kwargs: '{"login":"octocat","name":"The Octocat","id":583231}',
    )

    assert github_service._github_commit_identity() == (
        "The Octocat",
        "583231+octocat@users.noreply.github.com",
    )


def test_ensure_git_author_identity_only_fills_missing_fields(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        git_service,
        "git_author_identity",
        lambda workspace: (None, "configured@example.com"),
    )
    monkeypatch.setattr(
        git_service,
        "_run_command",
        lambda command, **kwargs: calls.append(command) or "ok",
    )

    output = git_service.ensure_git_author_identity(
        tmp_path,
        name="Octocat",
        email="583231+octocat@users.noreply.github.com",
    )

    assert calls == [["git", "config", "--local", "user.name", "Octocat"]]
    assert output == "Identità autore Git configurata localmente: nome."


def test_ensure_github_commit_identity_preserves_existing_git_identity(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        github_service,
        "git_author_identity",
        lambda workspace: ("Existing Author", "existing@example.com"),
    )
    monkeypatch.setattr(
        github_service,
        "_github_commit_identity",
        lambda: pytest.fail("GitHub profile must not be queried"),
    )

    assert github_service.ensure_github_commit_identity(tmp_path) == ""


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



def test_simple_github_status_reports_publish_or_update(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(github_service, "git_available", lambda: True)
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(github_service, "git_remote_url", lambda workspace, remote_name="origin": "https://github.com/alice/demo.git")
    monkeypatch.setattr(github_service, "_current_changes", lambda workspace: [("modify", "src/app.py")])
    status = github_service.simple_github_status(tmp_path)
    assert status["published"] is True
    assert status["action"] == "update"
    assert status["change_count"] == 1
    assert status["repository_name"] == "alice/demo"
    assert status["suggested_repository_name"] == tmp_path.name
    assert status["repository_url"] == "https://github.com/alice/demo"


def test_simple_github_status_suggests_workspace_name_before_first_publish(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(github_service, "git_available", lambda: True)
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(github_service, "git_remote_url", lambda workspace, remote_name="origin": None)
    monkeypatch.setattr(github_service, "_current_changes", lambda workspace: [])

    status = github_service.simple_github_status(tmp_path)

    assert status["published"] is False
    assert status["repository_name"] is None
    assert status["suggested_repository_name"] == tmp_path.name


def test_publish_or_update_creates_commit_repository_and_pushes(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    remote = {"value": None}
    calls: list[str] = []
    monkeypatch.setattr(github_service, "git_available", lambda: True)
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(github_service, "list_github_accounts", lambda: ["alice"])
    monkeypatch.setattr(github_service, "_current_changes", lambda workspace: [("modify", "src/app.py")])
    monkeypatch.setattr(github_service, "generate_commit_message", lambda workspace, session_manager=None: "feat: update app")
    monkeypatch.setattr(
        github_service,
        "ensure_github_commit_identity",
        lambda workspace: calls.append("identity") or "identity configured",
    )
    monkeypatch.setattr(github_service, "create_commit", lambda workspace, message: calls.append("commit") or "ok")
    monkeypatch.setattr(github_service, "git_has_commits", lambda workspace: True)
    monkeypatch.setattr(github_service, "git_remote_url", lambda workspace, remote_name="origin": remote["value"])
    def create_repo(workspace, name, **kwargs):
        calls.append("create")
        remote["value"] = "https://github.com/alice/demo.git"
        return "created"
    monkeypatch.setattr(github_service, "create_github_repository", create_repo)
    monkeypatch.setattr(
        github_service,
        "github_setup_git",
        lambda: calls.append("credentials") or "credentials configured",
    )
    monkeypatch.setattr(github_service, "push_current_branch", lambda workspace: calls.append("push") or "pushed")
    result = github_service.publish_or_update_github(tmp_path, repository_name="demo")
    assert calls == ["identity", "commit", "create", "credentials", "push"]
    assert result["repository_created"] is True
    assert result["repository_url"] == "https://github.com/alice/demo"
    assert "identity configured" in result["output"]
    assert "credentials configured" in result["output"]


def test_publish_from_uninitialized_workspace_initializes_git_before_commit(
    tmp_path: Path, monkeypatch
) -> None:
    repository = {"initialized": False, "remote": None}
    calls: list[str] = []
    protection = SimpleNamespace(
        summary="",
        created=False,
        changed=False,
        untracked_paths=(),
    )
    monkeypatch.setattr(github_service, "git_available", lambda: True)
    monkeypatch.setattr(github_service, "github_cli_available", lambda: True)
    monkeypatch.setattr(github_service, "list_github_accounts", lambda: ["alice"])
    monkeypatch.setattr(
        github_service,
        "is_git_repository",
        lambda workspace: repository["initialized"],
    )

    def initialize(workspace):
        calls.append("init")
        repository["initialized"] = True
        return "initialized"

    monkeypatch.setattr(github_service, "git_init", initialize)
    monkeypatch.setattr(github_service, "ensure_publish_gitignore", lambda workspace: protection)
    monkeypatch.setattr(github_service, "_current_changes", lambda workspace: [("create", "README.md")])
    monkeypatch.setattr(
        github_service,
        "ensure_github_commit_identity",
        lambda workspace: calls.append("identity") or "identity configured",
    )
    monkeypatch.setattr(
        github_service,
        "generate_commit_message",
        lambda workspace, session_manager=None: "chore: initial commit",
    )
    monkeypatch.setattr(
        github_service,
        "create_commit",
        lambda workspace, message: calls.append("commit") or "committed",
    )
    monkeypatch.setattr(github_service, "git_has_commits", lambda workspace: "commit" in calls)
    monkeypatch.setattr(
        github_service,
        "git_remote_url",
        lambda workspace, remote_name="origin": repository["remote"],
    )

    def create_repo(workspace, name, **kwargs):
        calls.append("create")
        repository["remote"] = "https://github.com/alice/demo.git"
        return "created"

    monkeypatch.setattr(github_service, "create_github_repository", create_repo)
    monkeypatch.setattr(
        github_service,
        "github_setup_git",
        lambda: calls.append("credentials") or "credentials configured",
    )
    monkeypatch.setattr(
        github_service,
        "push_current_branch",
        lambda workspace: calls.append("push") or "pushed",
    )

    result = github_service.publish_or_update_github(tmp_path, repository_name="demo")

    assert calls == ["init", "identity", "commit", "create", "credentials", "push"]
    assert result["repository_created"] is True
    assert result["commit_created"] is True
