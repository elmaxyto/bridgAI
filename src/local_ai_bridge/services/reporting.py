from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from local_ai_bridge import __version__
from local_ai_bridge.core.safety import is_sensitive_relative_path
from local_ai_bridge.core.project_prompts import load_project_prompt
from local_ai_bridge.core.settings import AppSettings, SettingsStore, app_data_dir
from local_ai_bridge.services.project_scanner import (
    load_project_ignore,
    rank_task_candidates,
    scan_project,
)
from local_ai_bridge.services.reporting_git import git_snapshot


NOTE_FILES = (
    "AI_NOTES.md",
    "PROJECT_NOTES.md",
    "TODO.md",
    "general_rules.cline",
    ".context_snapshot.json",
)
MAX_NOTES_PER_FILE = 8_000


def _trace_report(message: str) -> None:
    """Append lightweight stage diagnostics for report generation."""
    try:
        log_dir = app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "report_generation.log").open("a", encoding="utf-8") as stream:
            stream.write(f"{datetime.now().isoformat(timespec='seconds')} | {message}\n")
    except OSError:
        pass


def _notes(root: Path) -> str:
    chunks: list[str] = []
    ignore = load_project_ignore(root)
    for name in NOTE_FILES:
        path = root / name
        if (
            path.is_file()
            and not is_sensitive_relative_path(name)
            and not ignore.matches(name)
        ):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:MAX_NOTES_PER_FILE]
            except OSError:
                continue
            chunks.append(f"### `{name}`\n```text\n{text}\n```")
    return "\n\n".join(chunks) if chunks else "_Nessuna nota locale prioritaria rilevata._"



def _custom_instructions(root: Path, settings: AppSettings | None = None) -> str:
    settings = settings or SettingsStore().load()
    if not settings.include_custom_prompts:
        return "_Inclusione disabilitata nelle impostazioni._"
    chunks: list[str] = []
    global_prompt = settings.global_prompt.strip()
    project_prompt = load_project_prompt(root).strip()
    if global_prompt:
        chunks.append(f"### Prompt globale\n\n{global_prompt}")
    if project_prompt:
        chunks.append(f"### Prompt del progetto\n\n{project_prompt}")
    return "\n\n".join(chunks) if chunks else "_Nessuna istruzione personalizzata configurata._"

def _candidate_section(root: Path, task: str) -> str:
    if not task.strip():
        return "_Nessun task specifico: impossibile stimare i file candidati._"
    candidates = rank_task_candidates(root, task)
    if not candidates:
        return "_Nessun file candidato individuato automaticamente. Usa `#scarica` dopo l’analisi del report._"
    return "\n".join(f"- `{relative}`" for relative in candidates)


def _diagnostics_text(scan) -> str:
    runtime = (
        "Import runtime: non verificati durante la generazione del report.\n"
        "Test del progetto: non eseguiti durante la generazione del report.\n"
        "Interfaccia grafica: non avviata durante la generazione del report."
    )
    informational_prefixes = ("Contesto sintetico:", "Limite adattivo del contesto:")
    informational = [
        item for item in scan.diagnostics
        if item.startswith(informational_prefixes)
    ]
    warnings = [
        item for item in scan.diagnostics
        if not item.startswith(informational_prefixes)
    ]

    rows = [
        "Scansione: completata con avvisi." if warnings else "Scansione: completata."
    ]
    if scan.python_files:
        if scan.python_syntax_errors:
            rows.append(
                f"Parsing AST Python: {scan.python_files} file analizzati, "
                f"{scan.python_syntax_errors} errori sintattici rilevati."
            )
        else:
            rows.append(
                f"Parsing AST Python: {scan.python_files} file analizzati, nessun errore sintattico."
            )
    else:
        rows.append("Parsing AST Python: nessun file Python incluso nel contesto sintetico.")

    if scan.javascript_files:
        rows.append(
            f"JavaScript/TypeScript: firme estratte euristicamente da "
            f"{scan.javascript_files} file; sintassi non validata durante il report."
        )

    rows.extend(informational)
    rows.extend(warnings[:100])
    rows.append(runtime)
    return "\n".join(rows)


def build_super_report(root: Path, task: str = "") -> str:
    started = time.monotonic()
    root = root.expanduser().resolve(strict=True)
    _trace_report(f"START workspace={root}")
    try:
        scan = scan_project(root, task=task)
        _trace_report(
            f"SCAN_DONE files={scan.scanned_files} skipped={scan.skipped_files} "
            f"elapsed={time.monotonic() - started:.2f}s"
        )
        workspace_is_empty = scan.discovered_files == 0 and not any(
            "Scansione filesystem interrotta" in item for item in scan.diagnostics
        )
        task_text = task.strip() or "Nessun task specifico fornito: analizzare il progetto e attendere istruzioni."
        if workspace_is_empty:
            task_text += (
                "\n\n**WORKSPACE VUOTO:** non esistono file da richiedere con `#scarica`. "
                "Prima di creare i file, valuta se il task contiene già requisiti sufficienti per "
                "definire il progetto senza introdurre assunzioni importanti.\n\n"
                "- Se il task è già sufficientemente specifico, procedi direttamente.\n"
                "- Se il task è generico, ambiguo o incompleto, chiedi prima esattamente:\n\n"
                "> **Il progetto è vuoto o appena iniziato. Vuoi che ti faccia alcune domande "
                "per definire meglio struttura e requisiti? Rispondi: No, Breve oppure Dettagliata.**\n\n"
                "Interpreta la scelta così:\n\n"
                "- **No:** procedi autonomamente con scelte ragionevoli, sicure e semplici, "
                "dichiarando brevemente le assunzioni principali.\n"
                "- **Breve:** poni in un unico elenco numerato al massimo 4 domande indispensabili.\n"
                "- **Dettagliata:** poni in un unico elenco numerato al massimo 8 domande mirate.\n\n"
                "Non chiedere informazioni già presenti nel task o nel report. Poni soltanto domande "
                "che possano cambiare concretamente l'implementazione e usa formulazioni comprensibili "
                "anche a utenti non tecnici. Dopo le risposte, riepiloga brevemente requisiti, assunzioni "
                "e scelte principali; non prolungare l'intervista quando le informazioni sono sufficienti.\n\n"
                "Quando puoi procedere, realizza direttamente il task creando da zero tutti i file "
                "necessari e restituisci un unico archivio ZIP applicabile. Lo ZIP deve contenere nella "
                "propria radice la struttura completa del nuovo progetto, senza cartella contenitore "
                "aggiuntiva. Dopo aver prodotto lo ZIP, indica esplicitamente all'utente di usare "
                "**Applica ZIP**."
            )
        project_version = scan.project_version or "non rilevata"
        candidate_text = (
            "_Workspace vuoto: non richiedere file con `#scarica`; crea direttamente lo ZIP completo._"
            if workspace_is_empty
            else _candidate_section(root, task)
        )
        output_guidance = (
            "Se il report dichiara **WORKSPACE VUOTO** e il task non è sufficientemente "
            "dettagliato, esegui prima l'intervista opzionale descritta nell'obiettivo corrente. "
            "In quel caso, nella prima risposta fermati alla domanda di scelta; riprendi il flusso "
            "seguente dopo la risposta dell'utente e le eventuali domande necessarie.\n\n"
            if workspace_is_empty
            else ""
        )
        git_text = git_snapshot(root)
        notes_text = _notes(root)
        custom_instructions = _custom_instructions(root)
        elapsed = time.monotonic() - started
        _trace_report(f"RENDER elapsed={elapsed:.2f}s")

        report = f"""# Super-Report — Ponte AI Web / Workspace Locale

**Progetto/cartella:** `{root.name}`  
**Versione progetto rilevata:** `{project_version}`  
**Generatore report:** `BridgAI {__version__}`  
**Workspace:** `{root}`  
**Generato:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Modalità scansione:** {scan.discovery_mode}  
**File riassunti:** {scan.scanned_files}  
**File indicizzati ma non espansi:** {scan.omitted_files}  
**Copertura `#scarica`:** tutti i file indicizzati restano richiedibili anche se non espansi nel report.  
**File saltati/troncati:** {scan.skipped_files}  
**Sottoalberi tecnici esclusi:** {scan.excluded_directories}  
**File tecnici esclusi:** {scan.excluded_files}  
**Dettaglio esclusioni:** {scan.exclusion_summary}

---

## 1. Obiettivo corrente

{task_text}

## 1.1 Istruzioni personalizzate

{custom_instructions}

## 2. Ruolo dell'AI esterna

Agisci come senior software engineer. Il programma locale è l'unica autorità sul filesystem.
Non inventare file, funzioni o API che non compaiono nel report o nei file ricevuti.
Prima di proporre modifiche, individua i file reali necessari.

## 3. Stack e tipologia rilevati

{scan.stack}

## 4. File candidati rispetto al task

{candidate_text}

Questa selezione è euristica: verifica sempre i percorsi reali prima di proporre modifiche.

## 5. Regole architetturali

- Evita nuovi monoliti: oltre 300-350 LOC preferisci moduli o skill dedicate.
- Separa UI, logica core, accesso file, provider e integrazioni.
- Mantieni retrocompatibilità salvo richiesta esplicita.
- Non leggere o modificare `.env`, credenziali, chiavi, `.git` o file esterni al workspace.
- Non proporre comandi distruttivi. Indica sempre rischi e test consigliati.

## 6. Protocollo operativo

Quando servono file reali, rispondi con una singola riga:

```text
#scarica percorso/file1.py, percorso/file2.ts, percorso/file3.json
```

Se il report dichiara **WORKSPACE VUOTO**, non usare `#scarica`: crea direttamente tutti i file richiesti,
restituiscili in un unico ZIP completo e indica all'utente di usare **Applica ZIP**.

Formato preferito per modifiche multi-file: **ZIP**.

- Metti direttamente nella radice dello ZIP la struttura relativa del progetto (`src/`, `tests/`, ecc.).
- Non aggiungere una cartella contenitore col nome del progetto.
- `applymanifest.json` è facoltativo; omettilo per il normale mapping percorso→stesso percorso.
- Non includere file non modificati, segreti o file estranei al task.
- Includi nella radice dello ZIP un file `commit-message.md` in UTF-8.
- La prima riga non vuota di `commit-message.md` deve essere un titolo breve e descrittivo del commit.
- Dopo il titolo aggiungi un elenco sintetico delle modifiche realmente contenute nello ZIP.
- `commit-message.md` è un metadato per BridgAI: non è un file del progetto e non deve essere applicato al workspace.

Esempio:

```text
feat(area): descrizione sintetica

- modifica effettiva principale
- test aggiunti o aggiornati
```

Per modifiche chirurgiche a un solo file puoi usare:

```text
<<<<<<< SEARCH
codice esatto esistente
=======
codice sostitutivo
>>>>>>> REPLACE
```

Per la sostituzione completa di un file, restituisci il contenuto integrale e indica il percorso target.

## 7. Stato Git

```text
{git_text}
```

## 8. File più grandi / rischio monolite

{scan.hot_files}

## 9. Verifiche eseguite durante il report

```text
{_diagnostics_text(scan)}
```

Eventuali risultati presenti in README o documenti del repository sono informazioni storiche, non test rieseguiti in questa sessione.

## 10. Struttura reale del progetto

```text
{scan.tree}
```

I percorsi mostrati in questa sezione sono relativi alla root del workspace e devono essere usati nei comandi `#scarica`.
L'indice conserva i percorsi di codice e configurazione; soltanto i sottoalberi composti esclusivamente da file multimediali possono essere raggruppati.

## 11. Firme, dipendenze e configurazioni principali

{scan.summaries}

## 12. Note locali prioritarie

{notes_text}

## 13. Output atteso dall'AI

{output_guidance}Produci, nell'ordine:

1. analisi sintetica del problema;
2. file da richiedere con `#scarica`, se il contesto non basta;
3. piano operativo;
4. ZIP o patch applicabile;
5. test da eseguire;
6. rischi residui reali.

Non dichiarare che una modifica funziona se non puoi verificarla direttamente.
"""
        _trace_report(f"DONE chars={len(report)} elapsed={time.monotonic() - started:.2f}s")
        return report
    except Exception as exc:
        _trace_report(f"ERROR {type(exc).__name__}: {exc}")
        raise
