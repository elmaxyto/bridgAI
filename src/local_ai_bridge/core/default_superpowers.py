from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DefaultSuperpower:
    superpower_id: str
    version: int
    title: str
    description: str
    category: str
    usage_mode: str
    instructions: str


DEFAULT_SUPERPOWER_STATE_FILENAME = "default-superpowers.json"
DEFAULT_SUPERPOWER_STATE_VERSION = 1
SOFTWARE_PROJECT_ASSESSMENT_ID = "valutazione-progetto-software"

SOFTWARE_PROJECT_ASSESSMENT = DefaultSuperpower(
    superpower_id=SOFTWARE_PROJECT_ASSESSMENT_ID,
    version=1,
    title="Valutazione profonda del progetto software",
    description=(
        "Analizza valore, punti di forza, debolezze, rischi e priorità di "
        "evoluzione di un progetto software."
    ),
    category="Software",
    usage_mode="development",
    instructions="""Agisci come senior software engineer, product strategist e revisore indipendente.

## Obiettivo

Valuta il progetto in profondità come prodotto, sistema tecnico e iniziativa da mantenere nel tempo. Determina quale valore offre oggi, quale valore potrebbe esprimere, quali elementi lo rendono solido e quali ne limitano qualità, adozione, affidabilità o crescita.

## Principi di analisi

- Basa ogni conclusione sui file, sul report e sui risultati di test realmente disponibili.
- Distingui sempre tra **evidenza**, **inferenza ragionevole** e **informazione mancante**.
- Non trasformare impressioni in fatti e non attribuire un valore economico senza dati commerciali, utenti, ricavi, costi o confronti di mercato verificabili.
- Separa il valore attuale dal potenziale futuro e la qualità dell'idea dalla qualità dell'implementazione.
- Evita elogi generici: ogni punto di forza deve indicare perché conta e quale evidenza lo sostiene.
- Per ogni debolezza indica gravità, impatto probabile, area coinvolta e intervento consigliato.
- Considera la fase e le dimensioni del progetto: non penalizzare automaticamente una soluzione semplice quando è proporzionata al problema.
- Prima di concludere, richiedi con il protocollo `#scarica` solo i file reali indispensabili che non sono già disponibili.

## Dimensioni da esaminare

1. **Problema e proposta di valore**: bisogno risolto, destinatari, beneficio concreto, frequenza e intensità del problema.
2. **Completezza del prodotto**: flussi realmente coperti, casi limite, coerenza tra promessa, documentazione e comportamento osservabile.
3. **Differenziazione**: caratteristiche difficili da sostituire, vantaggi rispetto ad alternative plausibili e rischio di essere una semplice combinazione di strumenti esistenti.
4. **Architettura**: confini tra moduli, accoppiamento, estendibilità, dipendenze, gestione dello stato e adeguatezza delle scelte tecnologiche.
5. **Qualità del codice**: chiarezza, duplicazioni, complessità, monoliti, gestione degli errori, retrocompatibilità e debito tecnico.
6. **Affidabilità e sicurezza**: validazione degli input, protezione dei dati, confini del filesystem, transazionalità, ripristino, logging e superfici di attacco.
7. **Test e verificabilità**: copertura dei comportamenti critici, qualità delle regressioni, isolamento, fragilità dei test e lacune non verificate.
8. **Esperienza utente e adozione**: comprensibilità dei flussi, attrito iniziale, accessibilità, feedback, documentazione e facilità di installazione o distribuzione.
9. **Manutenibilità operativa**: configurazione, osservabilità, aggiornamenti, migrazioni, portabilità, supporto e costi prevedibili di evoluzione.
10. **Maturità e prontezza**: prototipo, MVP, beta o prodotto stabile; ostacoli concreti alla pubblicazione, all'uso reale o alla crescita.

## Formato dell'output

### 1. Sintesi esecutiva

Riassumi in pochi paragrafi il valore principale, il livello di maturità, il vantaggio più importante e il limite più serio.

### 2. Valore del progetto

Spiega:
- per chi crea valore;
- quale problema elimina o riduce;
- quanto il beneficio appare concreto e difendibile;
- quali ipotesi di valore non sono ancora validate;
- quali dati servirebbero per stimare il valore economico.

### 3. Punti di forza comprovati

Elenca i punti di forza in ordine di importanza. Per ciascuno indica evidenza, beneficio e possibile leva strategica.

### 4. Punti deboli e debito

Elenca i problemi in ordine di priorità usando gravità **critica**, **alta**, **media** o **bassa**. Distingui debolezze di prodotto, architettura, codice, sicurezza, test, UX e distribuzione.

### 5. Scheda di valutazione

Assegna un punteggio da 1 a 5, con breve motivazione e livello di confidenza, almeno a:
- valore per l'utente;
- differenziazione;
- completezza funzionale;
- architettura;
- qualità e manutenibilità del codice;
- sicurezza e affidabilità;
- test e verificabilità;
- esperienza utente;
- documentazione e distribuzione;
- prontezza per l'uso reale.

### 6. Rischi principali

Descrivi i rischi tecnici, di prodotto e operativi più importanti, includendo probabilità, impatto e possibile mitigazione.

### 7. Opportunità ad alto rendimento

Individua le modifiche capaci di aumentare maggiormente valore, fiducia, adozione o sostenibilità con uno sforzo proporzionato.

### 8. Piano prioritario

Proponi azioni **Adesso**, **Dopo** e **Più avanti**. Ogni azione deve avere risultato atteso, motivazione e verifica di completamento.

### 9. Informazioni mancanti

Indica ciò che non è possibile concludere dai materiali disponibili e quali prove, metriche, test o file ridurrebbero maggiormente l'incertezza.

### 10. Giudizio finale

Concludi con un giudizio netto ma motivato: cosa rende il progetto valido, cosa ne limita oggi il valore e quale singola scelta avrebbe il maggior impatto positivo.""",
)

DEFAULT_SUPERPOWERS = (SOFTWARE_PROJECT_ASSESSMENT,)


class DefaultSuperpowerInstallError(ValueError):
    pass


def render_default_superpower(item: DefaultSuperpower) -> str:
    return (
        "---\n"
        f"id: {item.superpower_id}\n"
        f"title: {item.title}\n"
        f"description: {item.description}\n"
        f"category: {item.category}\n"
        f"mode: {item.usage_mode}\n"
        "---\n\n"
        f"{item.instructions.strip()}\n"
    )


def _state_path(directory: Path) -> Path:
    return directory / DEFAULT_SUPERPOWER_STATE_FILENAME


def _read_state(directory: Path) -> dict[str, int]:
    path = _state_path(directory)
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("version") != DEFAULT_SUPERPOWER_STATE_VERSION:
        return {}
    installed = payload.get("installed")
    if not isinstance(installed, dict):
        return {}
    return {
        str(superpower_id): version
        for superpower_id, version in installed.items()
        if isinstance(superpower_id, str) and isinstance(version, int) and version > 0
    }


def _write_state(directory: Path, installed: dict[str, int]) -> None:
    target = _state_path(directory)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "version": DEFAULT_SUPERPOWER_STATE_VERSION,
                "installed": installed,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def ensure_default_superpowers(directory: Path, maximum_bytes: int) -> bool:
    """Install newly introduced defaults once without owning user copies.

    Existing files always win. The state file records that a bundled profile
    has already been offered, so a later user deletion is respected.
    """
    installed = _read_state(directory)
    pending = [
        item
        for item in DEFAULT_SUPERPOWERS
        if installed.get(item.superpower_id, 0) < item.version
    ]
    if not pending:
        return False
    if directory.exists() and directory.is_symlink():
        raise DefaultSuperpowerInstallError(
            "La cartella dei superpoteri dell’app non può essere un collegamento simbolico."
        )
    directory.mkdir(parents=True, exist_ok=True)

    for item in pending:
        target = directory / f"{item.superpower_id}.md"
        if target.is_symlink():
            raise DefaultSuperpowerInstallError(
                f"Il superpotere predefinito {item.superpower_id} non può essere "
                "un collegamento simbolico."
            )
        if not target.exists():
            content = render_default_superpower(item)
            if len(content.encode("utf-8")) > maximum_bytes:
                raise DefaultSuperpowerInstallError(
                    f"Il superpotere predefinito {item.superpower_id} supera il limite di "
                    f"{maximum_bytes} byte."
                )
            temporary = target.with_suffix(".tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(target)
        elif not target.is_file():
            raise DefaultSuperpowerInstallError(
                f"Il percorso del superpotere predefinito {item.superpower_id} non è un file."
            )
        installed[item.superpower_id] = item.version

    _write_state(directory, installed)
    return True
