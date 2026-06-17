from __future__ import annotations

from pathlib import Path

from local_ai_bridge.services.system import build_restart_command


def test_restart_source_run_uses_same_interpreter_and_script(tmp_path: Path) -> None:
    runner = tmp_path / "run.py"
    runner.write_text("print('ok')\n", encoding="utf-8")

    command = build_restart_command(
        argv=[str(runner), "--check-report", "."],
        executable=str(tmp_path / "python.exe"),
        frozen=False,
        cwd=tmp_path,
    )

    assert command.program == str(tmp_path / "python.exe")
    assert command.arguments == [str(runner.resolve()), "--check-report", "."]
    assert command.working_directory == str(tmp_path.resolve())


def test_restart_frozen_relaunches_executable(tmp_path: Path) -> None:
    executable = tmp_path / "LocalAIBridge.exe"
    command = build_restart_command(
        argv=[str(executable), "--demo"],
        executable=str(executable),
        frozen=True,
        cwd=tmp_path,
    )

    assert command.program == str(executable.resolve())
    assert command.arguments == ["--demo"]
    assert command.working_directory == str(tmp_path.resolve())


def test_restart_console_script_falls_back_to_module(tmp_path: Path) -> None:
    command = build_restart_command(
        argv=["local-ai-bridge", "--demo"],
        executable="python",
        frozen=False,
        cwd=tmp_path,
    )

    assert command.program == "python"
    assert command.arguments == ["-m", "local_ai_bridge", "--demo"]
    assert command.working_directory == str(tmp_path.resolve())
