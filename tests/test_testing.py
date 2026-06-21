from __future__ import annotations

import sys
from pathlib import Path

from local_ai_bridge.services import testing


def test_compileall_targets_project_sources_not_workspace_artifacts(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src" / "example").mkdir(parents=True)
    (tmp_path / "src" / "example" / "__init__.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_example.py").write_text("def test_value(): pass\n", encoding="utf-8")
    (tmp_path / "run.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "invalid.py").write_text("{% template %}\n", encoding="utf-8")
    (tmp_path / "backups" / "old" / "tests").mkdir(parents=True)
    (tmp_path / "backups" / "old" / "tests" / "test_example.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(testing, "_module_available", lambda name: False)
    monkeypatch.setattr(testing.shutil, "which", lambda name: None)

    commands = testing.detect_test_commands(tmp_path)

    compile_command = next(command for name, command, *_ in commands if name == "Python compileall")
    assert compile_command == [sys.executable, "-m", "compileall", "-q", "src", "tests", "run.py"]
    assert "." not in compile_command
    assert ".venv" not in compile_command
    assert "backups" not in compile_command


def test_pytest_targets_tests_directory_when_present(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(testing, "_module_available", lambda name: name == "pytest")
    monkeypatch.setattr(testing.shutil, "which", lambda name: None)

    commands = testing.detect_test_commands(tmp_path)

    pytest_command = next(command for name, command, *_ in commands if name == "Pytest")
    assert pytest_command == [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]


def test_pytest_is_not_scheduled_when_module_is_missing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(testing, "_module_available", lambda name: False if name == "pytest" else True)

    commands = testing.detect_test_commands(tmp_path)

    assert all(name != "Pytest" for name, *_ in commands)


def test_missing_pytest_is_reported_as_unavailable_not_failed(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(testing, "_module_available", lambda name: False if name == "pytest" else True)
    monkeypatch.setattr(
        testing,
        "_run",
        lambda name, command, cwd, timeout=120, env=None: testing.TestResult(
            name, command, "passed", 0, "", 0.01
        ),
    )

    results = testing.run_detected_tests(tmp_path)

    pytest_result = next(result for result in results if result.name == "Pytest")
    assert pytest_result.status == "unavailable"
    assert pytest_result.command == [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    assert "non è installato" in pytest_result.output
    assert testing.test_summary(results) == "1 superati, 0 non superati, 1 non disponibili"


def test_partial_pytest_run_is_explained_without_hiding_failures() -> None:
    results = [
        testing.TestResult("Python compileall", ["python", "-m", "compileall"], "passed", 0, "", 0.1),
        testing.TestResult(
            "Pytest",
            ["python", "-m", "pytest"],
            "failed",
            1,
            "5 failed, 201 passed in 7.53s",
            7.53,
        ),
    ]

    interpretation = testing.interpret_test_results(results)
    formatted = testing.format_test_results(results)

    assert interpretation["level"] == "warning"
    assert interpretation["pytest"]["passed"] == 201
    assert interpretation["pytest"]["failed"] == 5
    assert interpretation["automatic_rollback"] is False
    assert "Verifica parziale" in formatted
    assert "201 test superati e 5 non superati" in formatted
    assert "5 failed, 201 passed" in formatted


def test_compile_failure_is_reported_as_structural_problem() -> None:
    results = [
        testing.TestResult(
            "Python compileall",
            ["python", "-m", "compileall"],
            "failed",
            1,
            "SyntaxError",
            0.2,
        )
    ]

    interpretation = testing.interpret_test_results(results)

    assert interpretation["level"] == "error"
    assert interpretation["structural_failures"] == ["Python compileall"]
    assert "Controllo strutturale" in testing.format_test_results(results)


def test_successful_checks_receive_clear_success_interpretation() -> None:
    results = [
        testing.TestResult("Python compileall", ["python"], "passed", 0, "", 0.1),
        testing.TestResult("Pytest", ["pytest"], "passed", 0, "206 passed in 7.1s", 7.1),
    ]

    interpretation = testing.interpret_test_results(results)

    assert interpretation["level"] == "ok"
    assert interpretation["pytest"]["passed"] == 206
    assert "Verifiche completate con successo" in testing.format_test_results(results)



def test_python_checks_use_cache_outside_workspace(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "app.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(testing, "_module_available", lambda name: False)
    monkeypatch.setattr(testing.shutil, "which", lambda name: None)
    captured_envs: list[dict[str, str] | None] = []

    def fake_run(name, command, cwd, timeout=120, env=None):
        captured_envs.append(env)
        return testing.TestResult(name, command, "passed", 0, "", 0.01)

    monkeypatch.setattr(testing, "_run", fake_run)

    results = testing.run_detected_tests(tmp_path)

    assert results[0].status == "passed"
    assert captured_envs and captured_envs[0] is not None
    cache_path = Path(captured_envs[0]["PYTHONPYCACHEPREFIX"])
    assert not cache_path.is_relative_to(tmp_path)
    assert not cache_path.exists()


def test_compileall_permission_error_is_inconclusive_not_structural() -> None:
    results = [
        testing.TestResult(
            "Python compileall",
            ["python", "-m", "compileall"],
            "failed",
            1,
            "PermissionError: [WinError 5] Accesso negato: '__pycache__'",
            0.2,
        )
    ]

    interpretation = testing.interpret_test_results(results)
    formatted = testing.format_test_results(results)

    assert interpretation["level"] == "warning"
    assert interpretation["failed_checks"] == 0
    assert interpretation["unavailable_checks"] == 1
    assert interpretation["structural_failures"] == []
    assert "Nessun errore della patch è stato confermato" in interpretation["summary"]
    assert "⚪ Python compileall — non disponibile" in formatted
    assert "❌ Python compileall" not in formatted
    assert "Nessun errore strutturale del codice è stato confermato" in formatted


def test_timeout_is_reported_as_incomplete_not_structural() -> None:
    results = [
        testing.TestResult(
            "Python compileall",
            ["python", "-m", "compileall"],
            "timeout",
            None,
            "",
            120.0,
        )
    ]

    interpretation = testing.interpret_test_results(results)

    assert interpretation["level"] == "warning"
    assert interpretation["structural_failures"] == []
    assert interpretation["inconclusive_checks"] == 1
    assert "Verifica incompleta" in testing.format_test_results(results)


def test_serialized_results_normalize_environment_failures() -> None:
    results = [
        testing.TestResult(
            "Python compileall",
            ["python", "-m", "compileall"],
            "failed",
            1,
            "PermissionError: [WinError 5] Accesso negato",
            0.2,
        )
    ]

    serialized = testing.test_results_to_dicts(results)

    assert serialized[0]["status"] == "unavailable"
    assert testing.test_summary(results) == "0 superati, 0 non superati, 1 non disponibili"
