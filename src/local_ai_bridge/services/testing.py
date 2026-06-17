from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from local_ai_bridge.core.models import TestResult


MAX_OUTPUT = 30_000


def _has_pytest_suite(workspace: Path) -> bool:
    if (workspace / "tests").is_dir():
        return True
    if any((workspace / name).exists() for name in ("pytest.ini", "conftest.py")):
        return True
    pyproject = workspace / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        return "pytest" in pyproject.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _run(name: str, command: list[str], cwd: Path, timeout: int = 120, env: dict[str, str] | None = None) -> TestResult:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            check=False, env=env,
        )
        output = ((result.stdout or "") + (result.stderr or ""))[-MAX_OUTPUT:]
        return TestResult(
            name=name, command=command, status="passed" if result.returncode == 0 else "failed",
            returncode=result.returncode, output=output, duration_seconds=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + (exc.stderr or ""))[-MAX_OUTPUT:] if isinstance(exc.stdout, str) else ""
        return TestResult(name, command, "timeout", None, output, time.monotonic() - started)
    except FileNotFoundError as exc:
        return TestResult(name, command, "unavailable", None, str(exc), time.monotonic() - started)
    except Exception as exc:
        return TestResult(name, command, "error", None, str(exc), time.monotonic() - started)


def detect_test_commands(workspace: Path) -> list[tuple[str, list[str], int, dict[str, str] | None]]:
    commands: list[tuple[str, list[str], int, dict[str, str] | None]] = []
    has_python = any(workspace.rglob("*.py"))
    if has_python:
        commands.append(("Python compileall", [sys.executable, "-m", "compileall", "-q", "."], 120, None))
        pyproject = workspace / "pyproject.toml"
        if _has_pytest_suite(workspace) and _module_available("pytest"):
            commands.append(("Pytest", [sys.executable, "-m", "pytest", "-q"], 180, None))
        if shutil.which("ruff"):
            commands.append(("Ruff", ["ruff", "check", "."], 120, None))
        if shutil.which("mypy") and pyproject.exists():
            commands.append(("Mypy", ["mypy", "."], 180, None))
    package = workspace / "package.json"
    if package.exists() and shutil.which("npm"):
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})} if isinstance(data, dict) else {}
        except Exception:
            scripts, deps = {}, {}
        env = os.environ.copy()
        env["CI"] = "1"
        if "lint" in scripts:
            commands.append(("npm lint", ["npm", "run", "lint"], 180, env))
        if "build" in scripts:
            commands.append(("npm build", ["npm", "run", "build"], 240, env))
        if "test" in scripts:
            if "vitest" in deps:
                command = ["npm", "test", "--", "--run"]
            elif "jest" in deps:
                command = ["npm", "test", "--", "--runInBand"]
            else:
                command = ["npm", "test", "--", "--watch=false"]
            commands.append(("npm test", command, 240, env))
        if (workspace / "tsconfig.json").exists() and shutil.which("npx"):
            commands.append(("TypeScript", ["npx", "tsc", "--noEmit"], 180, env))
    return commands


def run_detected_tests(workspace: Path) -> list[TestResult]:
    workspace = workspace.expanduser().resolve(strict=True)
    commands = detect_test_commands(workspace)
    if not commands:
        return [TestResult("Rilevamento test", [], "unavailable", None, "Nessun test rilevato.", 0.0)]
    results = [_run(name, command, workspace, timeout, env) for name, command, timeout, env in commands]
    if _has_pytest_suite(workspace) and not _module_available("pytest"):
        results.append(
            TestResult(
                "Pytest",
                [sys.executable, "-m", "pytest", "-q"],
                "unavailable",
                None,
                "Pytest non è installato nell'ambiente Python corrente; suite non eseguita.",
                0.0,
            )
        )
    return results


def format_test_results(results: list[TestResult]) -> str:
    chunks: list[str] = []
    icons = {"passed": "✅", "failed": "❌", "unavailable": "⚪", "timeout": "⏱️", "error": "⚠️"}
    for result in results:
        chunks.append(
            f"{icons[result.status]} {result.name} — {result.status} ({result.duration_seconds:.1f}s)\n"
            f"Comando: {' '.join(result.command) if result.command else '-'}\n"
            f"{result.output.strip() or '[nessun output]'}"
        )
    return "\n\n".join(chunks)


def test_results_to_dicts(results: list[TestResult]) -> list[dict]:
    return [
        {
            "name": result.name,
            "command": list(result.command),
            "status": result.status,
            "returncode": result.returncode,
            "output": result.output,
            "duration_seconds": result.duration_seconds,
        }
        for result in results
    ]


def test_summary(results: list[TestResult]) -> str:
    passed = sum(result.status == "passed" for result in results)
    failed = sum(result.status in {"failed", "timeout", "error"} for result in results)
    unavailable = sum(result.status == "unavailable" for result in results)
    return f"{passed} superati, {failed} non superati, {unavailable} non disponibili"
