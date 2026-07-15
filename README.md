# BridgAI

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

**BridgAI is a local-first, reviewable bridge between web AI assistants and local development workspaces.**

It lets you prepare project context for an AI assistant, export only the requested files, inspect proposed ZIP or patch changes, review the diff, apply changes transactionally, run detected tests, and roll back when needed.

BridgAI does **not** give a browser or a web AI service direct access to your computer.

[Italiano](README.it.md)

---

## Why BridgAI?

Using a web AI assistant for local development often requires manually copying files, instructions, patches, and results between the browser and the filesystem.

BridgAI keeps that workflow explicit and controlled:

1. select a local project;
2. generate a structured Super-Report;
3. send the report to a web AI assistant;
4. export only the files explicitly requested by the assistant;
5. import the returned ZIP, patch, or complete file;
6. inspect the diff before writing anything;
7. apply the change with persistent recovery data;
8. run detected project checks;
9. roll back explicitly when necessary.

## Developed through its own workflow

BridgAI has been developed iteratively using BridgAI itself. The early 0.1 version supplied the report, controlled export, review, and apply workflow that was then used to implement subsequent versions up to 1.1.1, including the current Git commit-message workflow, superpowers, project notes, and browser-extension workflow refinements.

This provides practical end-to-end validation of the application's core use case. It complements, rather than replaces, repeatable automated tests.

## Safety model

BridgAI is designed around human approval and local authority.

- The local application is the only component allowed to access the filesystem.
- Web AI assistants never receive direct filesystem access.
- Archive paths and target paths are validated before use.
- Sensitive paths such as environment and credential files are blocked.
- ZIP files are checked for traversal and unsafe archive entries.
- Changes are inspected before they are written.
- Apply operations are transactional and create persistent recovery data.
- Rollback is explicit.
- Git staging, commits, pulls, merges, and pushes are never performed automatically.

Review every proposed change before applying it. BridgAI reduces risk, but it cannot guarantee that AI-generated code is correct or safe.

## Main features

- Desktop interface built with PySide6
- Localhost web interface
- Optional browser extension for controlled browser-assisted exchanges
- Operational missions with persisted history, execution results, and artifacts
- Configurable local and cloud AI assistant providers
- Global and per-project prompts and report exclusions
- ZIP, Markdown, and complete textual file-operation workflows
- Optional TOTP two-factor authentication for remote Web access
- Persistent Web language, theme, and voice-dictation controls
- Structured Super-Report generation
- Controlled `#scarica` file export workflow
- ZIP inspection and unified diff preview
- Legacy SEARCH/REPLACE patch compatibility
- Complete-file replacement support
- Transactional apply operations
- Persistent backups and rollback
- Project test detection and execution
- Session history with post-apply test results
- Optional `commit-message.md` metadata in AI-generated ZIP archives
- Commit drafts based on actual Git changes and applied-session notes
- Explicitly reviewed and confirmed staging and commit creation
- Local Git status, diff, remote, and initialization tools
- Optional GitHub CLI integration
- Optional Google Drive workflow support
- Italian and English interface
- Light and dark themes
- Windows, Linux, and macOS launch scripts

## Requirements

- Python 3.11 or newer
- A supported desktop environment for the PySide6 interface
- Internet access during the first dependency installation
- Optional: [GitHub CLI](https://cli.github.com/) for GitHub account and repository operations

Audio dictation availability depends on the operating system, microphone permissions, and local audio libraries.

## Quick start

### Windows

```bat
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe run.py
```

The repository also includes:

```text
Avvia_BridgAI.bat
start_bridgai_windows.bat
```

### Linux and macOS

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python run.py
```

The repository also includes:

```text
start_bridgai_linux_mac.sh
```

### Installed entry points

After installation:

```bash
local-ai-bridge
local-ai-bridge-web
```

The historical Python package and entry-point names are preserved for backward compatibility. The public application name is **BridgAI**.

## Typical workflow

1. Use **Set Project** and select the workspace BridgAI may inspect.
2. Describe the task and generate the Super-Report.
3. Send the report to the selected web AI assistant.
4. Export only explicitly requested files, for example:

```text
#scarica src/example.py, tests/test_example.py
```

5. Import the returned ZIP, which may include a root `commit-message.md` metadata file, or prepare a supported patch/full-file response.
6. Review the generated change plan and diff. The commit metadata is not applied to the workspace.
7. Apply the plan only after review, then run detected tests.
8. When ready, generate and edit a commit draft based on the actual Git working tree and applied-session notes.
9. Confirm staging and commit creation explicitly.
10. Push separately after reviewing the resulting repository state, or use explicit rollback when necessary.

## Web interface

The local web interface can be started with:

```bash
local-ai-bridge-web
```

or:

```bash
python -m local_ai_bridge.web
```

The server is intended for localhost use. Do not expose it directly to an untrusted network.

## Git and GitHub integration

BridgAI can initialize a local Git repository, show status/diff/remotes, read commit suggestions from imported ZIP metadata, and generate an editable commit draft from the actual working tree and applied-session notes. After a separate confirmation, it can stage the current changes and create the commit.

GitHub CLI integration can create or connect a repository and push the current branch after explicit confirmation. BridgAI does not stage, commit, pull, merge, or push without a deliberate user action.

## Development setup

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest
```

## Tests

```bash
python -m compileall -q src tests run.py
python -m pytest -q
```

Report diagnostic:

```bash
python run.py --check-report .
```

Save the diagnostic report:

```bash
python run.py --check-report . --output REPORT_DIAGNOSTIC.md
```

## Project structure

```text
src/local_ai_bridge/
├── core/       # models, settings, safety, sessions and local I/O
├── resources/  # icons and translation catalogs
├── services/   # reports, archives, patches, Git, GitHub and testing
├── skills/     # built-in internal skills
├── ui/         # PySide6 desktop interface
└── web/        # localhost web interface

tests/          # automated test suite
```

## Privacy

BridgAI operates locally. Data leaves the machine only when the user deliberately copies or uploads it to an external service.

Before sharing a report or an exported archive, inspect its contents and never share secrets, credentials, tokens, personal data, or confidential source code unintentionally.

## Known limitations

- The workflow is intentionally supervised rather than fully autonomous.
- Visual desktop behavior requires platform-specific manual testing.
- Audio dictation support varies by system configuration.
- Source installation is currently the primary distribution method.
- External integrations depend on their respective local clients and authentication tools.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Security

Do not report vulnerabilities in a public issue. Read [SECURITY.md](SECURITY.md) and use GitHub's private vulnerability reporting workflow when available.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) and the historical `AGGIORNAMENTO_*.md` release notes.

## License

BridgAI is released under the [MIT License](LICENSE).

## Project-local report exclusions

Create `.bridgai/ignore` in a workspace to omit noisy project files from the Super-Report without changing `.gitignore`. Use one glob per line; blank lines and lines beginning with `#` are ignored. Examples:

```text
dist/
*.sqlite
docs/generated/**
```

These rules affect only scanner/report context, including the tree, summaries, task candidates, and priority notes. They do not weaken sensitive-path checks and do not change ZIP, patch, apply, or filesystem safety behavior.


### Global and per-project prompts

The **Settings** tab can store persistent instructions for inclusion in the Super-Report. The global prompt applies to every workspace, while the current project prompt is stored in `.bridgai/project.json`. A toggle can temporarily omit both prompts from reports without deleting them.

Custom instructions and the `.bridgai/ignore` editor are available in the **Advanced** tab. Saved settings continue to apply while the interface is in super simple mode, but they cannot be edited from that workflow.
