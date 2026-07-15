from __future__ import annotations

import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from local_ai_bridge import __version__
from local_ai_bridge.core.safety import is_sensitive_relative_path
from local_ai_bridge.core.project_prompts import load_project_prompt
from local_ai_bridge.core.settings import (
    PREFERRED_WEB_AI_DEEPSEEK,
    AppSettings,
    SettingsStore,
    app_data_dir,
)
from local_ai_bridge.core.superpowers import superpowers_markdown
from local_ai_bridge.services.external_contexts import resolve_external_context_roots
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


@dataclass(slots=True)
class BatchProjectReportsResult:
    path: Path
    projects: list[str]


def _safe_report_filename(name: str, used: set[str]) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_", "."} else "_"
        for character in name.strip()
    ).strip("._")
    base = cleaned or "progetto"
    candidate = f"{base}.md"
    counter = 2
    while candidate.lower() in used:
        candidate = f"{base}-{counter}.md"
        counter += 1
    used.add(candidate.lower())
    return candidate


def project_directories_for_batch_reports(projects_root: Path) -> list[Path]:
    root = Path(projects_root).expanduser()
    if not root.exists():
        raise ValueError("La cartella root dei progetti non esiste.")
    if root.is_symlink():
        raise ValueError("La cartella root dei progetti non può essere un link simbolico.")
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("La cartella root dei progetti non è una directory valida.")
    projects: list[Path] = []
    for child in sorted(resolved.iterdir(), key=lambda item: item.name.lower()):
        try:
            if child.is_symlink() or not child.is_dir():
                continue
        except OSError:
            continue
        projects.append(child.resolve(strict=True))
    return projects


def create_batch_project_reports_zip(
    projects_root: Path,
    destination: Path | None = None,
    *,
    task: str = "Report batch del progetto.",
    settings: AppSettings | None = None,
    progress_callback: Callable[[int, int, Path], None] | None = None,
) -> BatchProjectReportsResult:
    root = Path(projects_root).expanduser()
    projects = project_directories_for_batch_reports(root)
    root = root.resolve(strict=True)
    if not projects:
        raise ValueError("La root progetti non contiene cartelle di primo livello da analizzare.")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = destination or root / f"bridgai-project-reports-{timestamp}.zip"
    target = Path(target)
    if target.is_dir():
        raise ValueError("La destinazione del report batch è una directory.")
    target.parent.mkdir(parents=True, exist_ok=True)

    project_names: list[str] = []
    used_names: set[str] = set()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "README.md",
            "# Report batch BridgAI\n\n"
            f"Root progetti: `{root}`\n\n"
            f"Generato: {datetime.now().isoformat(timespec='seconds')}\n\n"
            "Ogni file Markdown corrisponde a una cartella di primo livello della root.\n",
        )
        total = len(projects)
        for index, project in enumerate(projects, start=1):
            project_names.append(project.name)
            if progress_callback is not None:
                progress_callback(index, total, project)
            filename = _safe_report_filename(project.name, used_names)
            report = build_super_report(project, task=task, settings=settings)
            archive.writestr(filename, report)
    return BatchProjectReportsResult(path=target, projects=project_names)


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


def _external_contexts_section(
    root: Path,
    task: str,
    settings: AppSettings,
) -> tuple[str, list[str]]:
    contexts, diagnostics = resolve_external_context_roots(root, settings)
    if not contexts:
        return "_Nessun progetto o cartella di contesto aggiuntiva configurata._", diagnostics

    chunks: list[str] = [
        (
            "I contesti aggiuntivi sono inclusi nel report per consultazione e confronto. "
            "Restano esterni al workspace corrente: puoi richiedere i loro file reali con "
            "`#scarica @context-N:percorso/relativo.ext`, ma solo per lettura. Non proporre "
            "modifiche dirette su questi percorsi e non includerli nello ZIP applicabile."
        )
    ]
    for context in contexts:
        try:
            scan = scan_project(context.path, task=task, time_budget=18.0)
        except Exception as exc:
            diagnostics.append(
                f"Contesto aggiuntivo `{context.path}` non scansionato: {type(exc).__name__}: {exc}"
            )
            continue
        chunks.append(
            f"### {context.label} — `{context.path.name}`\n\n"
            f"**Percorso:** `{context.path}`  \n"
            f"**Modalità:** sola lettura; usa questo contesto per trovare pattern, funzioni o "
            f"idee da portare nel workspace corrente.  \n"
            f"**Richiesta file reali:** `#scarica @{context.label}:percorso/relativo.ext`  \n"
            f"I file richiesti da questo contesto verranno consegnati sotto "
            f"`__bridgai_external_contexts__/{context.label}/...` e restano materiale di "
            f"riferimento, non target di modifica.  \n"
            f"**Stack rilevato:**\n\n{scan.stack}\n\n"
            f"**File candidati rispetto al task:**\n\n{_candidate_section(context.path, task)}\n\n"
            f"**Struttura:**\n\n```text\n{scan.tree}\n```\n\n"
            f"**Firme e contenuti sintetici:**\n\n{scan.summaries}\n"
        )
        diagnostics.extend(
            f"Contesto aggiuntivo {context.label}: {item}" for item in scan.diagnostics
        )
    return "\n\n".join(chunks), diagnostics


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


def _requested_files_protocol(markdown_mode: bool) -> str:
    if markdown_mode:
        return """**FORMATO FILE RICHIESTI — Markdown**

Quando richiedi file con `#scarica`, BridgAI creerà un unico documento Markdown con i percorsi e il contenuto completo dei file testuali. I file binari verranno segnalati ma non incorporati.

- Usa `#scarica percorso/file.py` per file del workspace corrente.
- Usa `#scarica @context-1:percorso/file.py` per file dei contesti aggiuntivi indicati nella sezione 4.1.
- I file dei contesti aggiuntivi sono materiale di sola lettura: usali per confronto, ma non includerli come target nel risultato finale.
- Non chiedere ZIP per ricevere il contesto.
- Considera autorevoli soltanto i contenuti delimitati dai marcatori BridgAI nel documento ricevuto.
- Il formato della risposta finale resta quello indicato nella sezione successiva."""
    return """**FORMATO FILE RICHIESTI — ZIP**

Quando richiedi file con `#scarica`, BridgAI creerà uno ZIP con i file reali selezionati. Allegalo alla conversazione prima di preparare le modifiche finali.

- Usa `#scarica percorso/file.py` per file del workspace corrente.
- Usa `#scarica @context-1:percorso/file.py` per file dei contesti aggiuntivi indicati nella sezione 4.1.
- I file richiesti dai contesti aggiuntivi verranno inseriti nello ZIP sotto `__bridgai_external_contexts__/context-N/...`. Sono materiale di sola lettura: usali per confronto, ma non includerli come target nello ZIP finale."""


def _text_file_operations_protocol() -> str:
    return """**FORMATO MODIFICHE — File Markdown di aggiornamento**

Quando il contesto non basta, usa ancora `#scarica` con una singola riga. Dopo aver ricevuto i file necessari, crea un singolo file scaricabile chiamato preferibilmente `bridgai-update.md`.

Il file deve contenere prima il metadato `commit-message.md` e poi soltanto le operazioni strutturate complete sui file: non produrre ZIP, non usare SEARCH/REPLACE e non aggiungere spiegazioni fuori dai blocchi previsti. Usa il copia-incolla soltanto se l’interfaccia AI non permette di generare un file scaricabile.

Inserisci come primo blocco il messaggio che BridgAI salverà nella sessione e in `BRIDGAI_HISTORY.md`. Questo blocco è un metadato e non verrà creato nel progetto:

````text
<!-- BRIDGAI:FILE commit-message.md -->
<!-- BRIDGAI:TEXT final-newline=1 -->
```markdown
feat(area): descrizione sintetica

- modifica effettiva principale
- test aggiunti o aggiornati
```
````

La prima riga non vuota deve essere un titolo breve e descrittivo; dopo il titolo aggiungi un elenco sintetico delle modifiche realmente contenute nel file Markdown.

**Non copiare valori alternativi o segnaposto.** Ogni campo deve contenere un solo valore letterale. Per esempio, scrivi `OPERATION: REPLACE` e `FINAL_NEWLINE: YES`. Non inserire la parola “oppure”, barre, commenti o più opzioni nella stessa riga.

Per sostituire integralmente un file esistente usa preferibilmente questa forma compatta, con il percorso già nel marcatore di apertura:

````text
BEGIN_FILE src/esempio.py
OPERATION: REPLACE
FINAL_NEWLINE: YES
CONTENT:
```python
contenuto completo del file
```
END_FILE src/esempio.py
````

È ancora accettata la forma estesa con `PATH: src/esempio.py` su una riga separata, ma non usarla se puoi evitarlo: meno righe di controllo riducono gli errori delle AI Web.

Per creare un file inesistente usa la stessa forma, ma con una singola riga `OPERATION: CREATE`.

Per eliminare un file esistente usa esattamente:

```text
BEGIN_FILE
OPERATION: DELETE
PATH: percorso/relativo/nomefile.ext
END_FILE
```

Regole obbligatorie:

- I soli valori ammessi per `OPERATION` sono `CREATE`, `REPLACE` e `DELETE`.
- I soli valori ammessi per `FINAL_NEWLINE` sono `YES` e `NO`.
- Il blocco `commit-message.md` deve comparire una sola volta, prima delle operazioni, e non usa `BEGIN_FILE`, `OPERATION` o `END_FILE`.
- `CREATE` è riservato a file che non esistono nel contesto ricevuto.
- `REPLACE` sostituisce integralmente un file esistente.
- `DELETE` elimina un file esistente e non deve avere `CONTENT` né `FINAL_NEWLINE`.
- Ogni percorso deve essere relativo alla root del progetto e comparire una sola volta; ripetilo in `END_FILE percorso` quando possibile.
- Per `CREATE` e `REPLACE` restituisci il file integrale, dall'inizio alla fine.
- Non usare frammenti, omissioni, segnaposto, “resto invariato” o testo fuori dai blocchi.
- Non includere file non modificati o estranei al task.
- Usa `FINAL_NEWLINE: YES` quando il file deve terminare con una nuova riga; altrimenti usa `FINAL_NEWLINE: NO`.
- Dopo `CONTENT:` apri sempre una fence Markdown. Se il contenuto include tre backtick consecutivi, usa una fence esterna più lunga oppure una fence con tilde.
- Chiudi la fence del contenuto prima di `END_FILE`.
- Non racchiudere l'intera risposta in un'ulteriore fence Markdown e non aggiungere titoli, elenchi o commenti alle righe di controllo.
- Per file binari o non rappresentabili fedelmente come UTF-8, non usare questa modalità: segnala il limite.
- Se non puoi restituire tutti i file completi richiesti, non inviare un risultato parziale: richiedi prima i file mancanti con `#scarica`.

Controllo finale prima dell'invio:

1. esiste un solo blocco metadato `commit-message.md`, con fence chiusa e contenuto non vuoto;
2. il numero di `BEGIN_FILE` coincide con il numero di `END_FILE`;
3. ogni blocco file contiene un solo `OPERATION` e un solo percorso;
4. ogni blocco `CREATE` o `REPLACE` contiene `FINAL_NEWLINE`, `CONTENT` e una fence chiusa;
5. non esiste testo prima, tra o dopo il blocco metadato e i blocchi file.

BridgAI analizzerà localmente le operazioni, controllerà i percorsi e l'esistenza dei file, mostrerà il diff e creerà un unico piano transazionale con backup e rollback. Se la chat rimuove accidentalmente `CONTENT`, la fence di chiusura o `END_FILE`, BridgAI proverà un recupero conservativo solo quando il blocco resta delimitabile; ogni recupero comparirà negli avvisi del piano."""


def _provider_specific_delivery_protocol(settings: AppSettings) -> str:
    if settings.preferred_web_ai == PREFERRED_WEB_AI_DEEPSEEK:
        return (
            "**Nota DeepSeek manuale:** quando prepari le modifiche finali, il formato richiesto "
            "è un unico file scaricabile `bridgai-update.md` contenente prima il blocco "
            "metadato `commit-message.md` e poi le operazioni strutturate `BEGIN_FILE` / "
            "`END_FILE`, senza altro testo esterno. Non restituire patch SEARCH/REPLACE "
            "e non creare ZIP."
        )
    return ""


def _standard_delivery_protocol() -> str:
    return """**FORMATO MODIFICHE — ZIP**

Formato richiesto per modifiche multi-file: **ZIP**.

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
```"""

def build_super_report(
    root: Path,
    task: str = "",
    *,
    settings: AppSettings | None = None,
) -> str:
    started = time.monotonic()
    root = root.expanduser().resolve(strict=True)
    settings = settings or SettingsStore().load()
    markdown_mode = bool(settings.markdown_exchange_mode)
    textual_mode = bool(settings.textual_file_operations_mode)
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
                + (
                    "Quando puoi procedere, realizza direttamente il task creando da zero tutti i file "
                    "necessari e restituiscili in un unico file scaricabile `bridgai-update.md` come "
                    "operazioni `CREATE` complete. Non usare ZIP né `#scarica`."
                    if textual_mode
                    else
                    "Quando puoi procedere, realizza direttamente il task creando da zero tutti i file "
                    "necessari e restituisci un unico archivio ZIP applicabile. Lo ZIP deve contenere nella "
                    "propria radice la struttura completa del nuovo progetto, senza cartella contenitore "
                    "aggiuntiva. Dopo aver prodotto lo ZIP, indica esplicitamente all'utente di usare "
                    "**Applica ZIP**."
                )
            )
        project_version = scan.project_version or "non rilevata"
        candidate_text = (
            (
                "_Workspace vuoto: non richiedere file con `#scarica`; restituisci direttamente "
                "un file `bridgai-update.md` con operazioni `CREATE` complete._"
                if textual_mode
                else "_Workspace vuoto: non richiedere file con `#scarica`; crea direttamente lo ZIP completo._"
            )
            if workspace_is_empty
            else _candidate_section(root, task)
        )
        external_contexts_text, external_context_diagnostics = _external_contexts_section(root, task, settings)

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
        custom_instructions = _custom_instructions(root, settings)
        markdown_superpowers = superpowers_markdown(root, task)
        delivery_protocol = (
            f"{_requested_files_protocol(markdown_mode)}\n\n"
            + (_text_file_operations_protocol() if textual_mode else _standard_delivery_protocol())
        )
        provider_protocol = _provider_specific_delivery_protocol(settings)
        if provider_protocol:
            delivery_protocol = f"{delivery_protocol}\n\n{provider_protocol}"
        delivery_label = (
            "File Markdown di aggiornamento applicabile"
            if textual_mode else "ZIP applicabile"
        )
        empty_workspace_protocol = (
            "Se il report dichiara **WORKSPACE VUOTO**, non usare `#scarica`: "
            "restituisci direttamente un unico file `bridgai-update.md` con il blocco metadato "
            "`commit-message.md` e tutte le operazioni `CREATE` complete."
            if textual_mode
            else
            "Se il report dichiara **WORKSPACE VUOTO**, non usare `#scarica`: crea direttamente "
            "tutti i file richiesti, restituiscili in un unico ZIP completo e indica all'utente "
            "di usare **Applica ZIP**."
        )
        expected_output = (
            "Se il contesto non basta, rispondi esclusivamente con la singola riga `#scarica`. "
            "Dopo aver ricevuto i file necessari, crea e allega un unico file scaricabile "
            "`bridgai-update.md` contenente il blocco metadato `commit-message.md` e i blocchi "
            "`BEGIN_FILE` / `END_FILE` previsti dal protocollo, senza introduzioni, riepiloghi, "
            "testo conclusivo o Markdown esterno ai blocchi. Non creare uno ZIP e usa il "
            "copia-incolla soltanto se "
            "l’interfaccia AI non permette di generare un file scaricabile."
            if textual_mode
            else
            "Produci, nell'ordine:\n\n"
            "1. analisi sintetica del problema;\n"
            "2. file da richiedere con `#scarica`, se il contesto non basta;\n"
            "3. piano operativo;\n"
            f"4. {delivery_label};\n"
            "5. test da eseguire;\n"
            "6. rischi residui reali.\n\n"
            "Non dichiarare che una modifica funziona se non puoi verificarla direttamente."
        )
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
**Copertura `#scarica`:** tutti i file indicizzati del workspace corrente restano richiedibili anche se non espansi; i contesti aggiuntivi usano la forma `@context-N:percorso`.  
**File saltati/troncati:** {scan.skipped_files}  
**Sottoalberi tecnici esclusi:** {scan.excluded_directories}  
**File tecnici esclusi:** {scan.excluded_files}  
**Dettaglio esclusioni:** {scan.exclusion_summary}

---

## 1. Obiettivo corrente

{task_text}

## 1.1 Istruzioni personalizzate

{custom_instructions}

## 1.2 Superpoteri Markdown

{markdown_superpowers}

## 2. Ruolo dell'AI esterna

Agisci come senior software engineer. Il programma locale è l'unica autorità sul filesystem.
Non inventare file, funzioni o API che non compaiono nel report o nei file ricevuti.
Prima di proporre modifiche, individua i file reali necessari.

## 3. Stack e tipologia rilevati

{scan.stack}

## 4. File candidati rispetto al task

{candidate_text}

Questa selezione è euristica: verifica sempre i percorsi reali prima di proporre modifiche.

## 4.1 Progetti/cartelle di contesto aggiuntivi

{external_contexts_text}

## 5. Regole architetturali

- Evita nuovi monoliti: oltre 300-350 LOC preferisci moduli o skill dedicate.
- Separa UI, logica core, accesso file, provider e integrazioni.
- Mantieni retrocompatibilità salvo richiesta esplicita.
- Non leggere o modificare `.env`, credenziali, chiavi, `.git` o file esterni al workspace.
- I contesti aggiuntivi sono fonti di consultazione: puoi richiederne file reali con `#scarica @context-N:...`, copiare idee o adattare pattern, ma lo ZIP finale deve modificare solo il workspace corrente.
- Non proporre comandi distruttivi. Indica sempre rischi e test consigliati.

## 6. Protocollo operativo

Quando servono file reali, rispondi con una singola riga:

```text
#scarica percorso/file1.py, percorso/file2.ts, @context-1:percorso/nel/contesto.py
```

{empty_workspace_protocol}

{delivery_protocol}

## 7. Stato Git

```text
{git_text}
```

## 8. File più grandi / rischio monolite

{scan.hot_files}

## 9. Verifiche eseguite durante il report

```text
{_diagnostics_text(scan)}
{chr(10).join(external_context_diagnostics)}
```

Eventuali risultati presenti in README o documenti del repository sono informazioni storiche, non test rieseguiti in questa sessione.

## 10. Struttura reale del progetto

```text
{scan.tree}
```

I percorsi mostrati in questa sezione sono relativi alla root del workspace e devono essere usati nei comandi `#scarica`. Per i contesti aggiuntivi usa invece la sintassi esplicita mostrata nella sezione 4.1, per esempio `#scarica @context-1:percorso/nel/contesto.py`.
L'indice conserva i percorsi di codice e configurazione; soltanto i sottoalberi composti esclusivamente da file multimediali possono essere raggruppati.

## 11. Firme, dipendenze e configurazioni principali

{scan.summaries}

## 12. Note locali prioritarie

{notes_text}

## 13. Output atteso dall'AI

{output_guidance}{expected_output}
"""
        _trace_report(f"DONE chars={len(report)} elapsed={time.monotonic() - started:.2f}s")
        return report
    except Exception as exc:
        _trace_report(f"ERROR {type(exc).__name__}: {exc}")
        raise
