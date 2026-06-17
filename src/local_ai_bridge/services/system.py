from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class RestartCommand:
    """Command used to start a fresh Local AI Bridge process."""

    program: str
    arguments: list[str]
    working_directory: str


def build_restart_command(
    *,
    argv: Sequence[str] | None = None,
    executable: str | None = None,
    frozen: bool | None = None,
    cwd: str | Path | None = None,
) -> RestartCommand:
    """Build a cross-platform restart command for source and packaged runs.

    Source runs reuse the current Python interpreter and the resolved ``run.py``
    path. Packaged builds relaunch the executable directly. Console-script or
    module-style runs fall back to ``python -m local_ai_bridge``.
    """

    current_argv = list(argv if argv is not None else sys.argv)
    if not current_argv:
        current_argv = ["local-ai-bridge"]

    program = str(executable or sys.executable)
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    current_cwd = Path(cwd or Path.cwd()).expanduser().resolve()

    if is_frozen:
        executable_path = Path(program).expanduser().resolve()
        return RestartCommand(
            program=str(executable_path),
            arguments=current_argv[1:],
            working_directory=str(executable_path.parent),
        )

    entry = Path(current_argv[0]).expanduser()
    if not entry.is_absolute():
        entry = current_cwd / entry
    entry = entry.resolve()

    if entry.suffix.lower() in {".py", ".pyw"} and entry.is_file():
        return RestartCommand(
            program=program,
            arguments=[str(entry), *current_argv[1:]],
            working_directory=str(entry.parent),
        )

    return RestartCommand(
        program=program,
        arguments=["-m", "local_ai_bridge", *current_argv[1:]],
        working_directory=str(current_cwd),
    )
