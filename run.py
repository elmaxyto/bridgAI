from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
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
