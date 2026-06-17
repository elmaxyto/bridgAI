# Contributing to BridgAI

Thank you for considering a contribution.

BridgAI handles local files and applies code changes, so correctness, explicit behavior, and safety are more important than convenience or hidden automation.

## Before opening an issue

- Search existing issues.
- Reproduce the problem with the latest code.
- Remove credentials, personal data, private source code, and local filesystem paths from logs.
- Include the operating system, Python version, launch method, and relevant error output.

Security vulnerabilities must not be reported in public issues. Follow [SECURITY.md](SECURITY.md).

## Development setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest
```

## Running checks

```bash
python -m compileall -q src tests run.py
python -m pytest -q
```

For report-generation changes:

```bash
python run.py --check-report .
```

GUI changes should also be tested manually on at least one supported desktop platform.

## Architecture guidelines

- Keep filesystem authority inside the local application.
- Do not add direct browser access to the workspace.
- Separate UI, core logic, filesystem access, providers, and integrations.
- Avoid adding new monolithic modules.
- Prefer focused modules when a file approaches 300–350 lines.
- Preserve backward compatibility unless a breaking change is explicitly approved.
- Do not read or modify `.env`, credentials, keys, `.git`, or files outside the selected workspace.
- Do not introduce destructive or implicit Git operations.
- Keep rollback and user approval explicit.

## Tests

Add or update tests for every behavior change when practical. Security-sensitive changes should include regression tests for paths, archives, transaction failures, rollback conflicts, secret exposure, and command construction.

Tests must not require real GitHub, Google, microphone, or browser credentials.

## Pull requests

A pull request should explain the problem, describe the solution, list changed behavior, include tests, mention platform-specific effects, avoid unrelated refactors, and contain no secrets or generated local data.

## License

By contributing, you agree that your contribution may be distributed under the MIT License used by this repository.
