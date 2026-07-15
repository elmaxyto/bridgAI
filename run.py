from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


_DESKTOP_LOG_STREAM: TextIO | None = None


def _missing_dependencies() -> list[str]:
    required = {
        "PySide6": "PySide6",
        "platformdirs": "platformdirs",
    }
    return [package for module, package in required.items() if importlib.util.find_spec(module) is None]


def _print_setup_help(missing: list[str]) -> None:
    joined = ", ".join(missing)
    print(
        "Impossibile avviare BridgAI: mancano le dipendenze: " + joined + "\n\n"
        "Su Windows non avviare direttamente run.py. Esegui invece:\n"
        "  start_windows.bat\n\n"
        "Oppure, da questa cartella:\n"
        "  py -3 -m venv .venv\n"
        "  .venv\\Scripts\\python.exe -m pip install -r requirements.txt\n"
        "  .venv\\Scripts\\python.exe run.py\n",
        file=sys.stderr,
    )


def _configure_desktop_log() -> None:
    """Redirect a hidden Windows launch to the persistent desktop log."""
    global _DESKTOP_LOG_STREAM
    raw_path = os.environ.get("BRIDGAI_DESKTOP_LOG", "").strip()
    if not raw_path:
        return
    try:
        path = Path(raw_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open("a", encoding="utf-8", buffering=1)
    except OSError:
        return
    _DESKTOP_LOG_STREAM = stream
    sys.stdout = stream
    sys.stderr = stream
    print(f"\n[{datetime.now().isoformat(timespec='seconds')}] Avvio BridgAI desktop")


def _windows_launch_mode() -> int:
    from local_ai_bridge.core.settings import SettingsStore

    settings = SettingsStore().load()
    print("console" if settings.windows_show_diagnostic_consoles else "hidden")
    return 0


def _run_web_server() -> int:
    """Start the web entry point after the source directory is on sys.path."""
    from local_ai_bridge.web.server import main as web_main

    original_argv = sys.argv
    try:
        forwarded = [
            arg for arg in original_argv[1:] if arg != "--web-server"
        ]
        sys.argv = [original_argv[0], *forwarded]
        return web_main()
    finally:
        sys.argv = original_argv


def _check_report(workspace: str, output: str | None) -> int:
    from local_ai_bridge.services.reporting import build_super_report

    root = Path(workspace).expanduser().resolve(strict=True)
    report = build_super_report(root, "Diagnostica generazione Super-Report")
    if output:
        destination = Path(output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report, encoding="utf-8")
        print(f"Super-Report diagnostico creato: {destination}")
    else:
        print(f"Super-Report generato correttamente: {len(report)} caratteri, {report.count(chr(10)) + 1} righe.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--check-report",
        metavar="WORKSPACE",
        help="Genera il report senza avviare la GUI, utile per la diagnostica.",
    )
    parser.add_argument(
        "--output",
        help="File Markdown opzionale usato insieme a --check-report.",
    )
    parser.add_argument(
        "--windows-launch-mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


if __name__ == "__main__":
    if "--web-server" in sys.argv[1:]:
        raise SystemExit(_run_web_server())

    args = _parse_args()
    if args.windows_launch_mode:
        raise SystemExit(_windows_launch_mode())

    _configure_desktop_log()

    if args.check_report:
        try:
            raise SystemExit(_check_report(args.check_report, args.output))
        except Exception as exc:
            print(f"Diagnostica report fallita: {type(exc).__name__}: {exc}", file=sys.stderr)
            raise

    missing = _missing_dependencies()
    if missing:
        _print_setup_help(missing)
        raise SystemExit(2)

    from local_ai_bridge.app import main

    raise SystemExit(main())
