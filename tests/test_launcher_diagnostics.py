from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_ROOT / "run.py"


def test_report_diagnostic_cli(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def hello():\n    return 'ok'\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--check-report", str(tmp_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Super-Report generato correttamente" in result.stdout


def test_report_diagnostic_can_write_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    output = tmp_path / "diagnostic.md"
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--check-report",
            str(workspace),
            "--output",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert "# Super-Report" in output.read_text(encoding="utf-8")
