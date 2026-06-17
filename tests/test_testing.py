from __future__ import annotations

from pathlib import Path

from local_ai_bridge.services import testing


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
    assert "non è installato" in pytest_result.output
    assert testing.test_summary(results) == "1 superati, 0 non superati, 1 non disponibili"
