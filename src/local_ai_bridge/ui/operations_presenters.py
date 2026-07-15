from __future__ import annotations

from pathlib import Path

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.core.superpowers import list_superpowers
from local_ai_bridge.services.operational_execution import OperationalExecutionRecord
from local_ai_bridge.services.operational_missions import (
    CATEGORY_CUSTOM,
    CATEGORY_DOCUMENTS,
    CATEGORY_FILE_ORGANIZATION,
    CATEGORY_IMAGES,
    CATEGORY_PRESENTATIONS,
    CATEGORY_SPREADSHEETS,
    CATEGORY_TRANSLATION,
    CATEGORY_WRITING,
    MISSION_ARCHIVED,
    MISSION_CANCELLED,
    MISSION_COMPLETED,
    MISSION_DRAFT,
    MISSION_FAILED,
    MISSION_READY,
    MISSION_RUNNING,
    PROCEDURE_CSV_MERGE,
    PROCEDURE_INPUT_INVENTORY,
    PROCEDURE_WEB_MISSION,
    PROVIDER_CHATGPT,
    PROVIDER_CLAUDE,
    PROVIDER_GEMINI,
    OperationalMission,
)


_STATE_LABELS = {
    MISSION_DRAFT: "Bozza",
    MISSION_READY: "Pronta",
    MISSION_RUNNING: "In lavorazione",
    MISSION_COMPLETED: "Completata",
    MISSION_FAILED: "Non riuscita",
    MISSION_CANCELLED: "Annullata",
    MISSION_ARCHIVED: "Archiviata",
}
_PROCEDURE_LABELS = {
    PROCEDURE_WEB_MISSION: "Missione tramite AI Web",
    PROCEDURE_CSV_MERGE: "Unisci e riepiloga CSV",
    PROCEDURE_INPUT_INVENTORY: "Inventario tecnico degli input",
}
_CATEGORY_LABELS = {
    CATEGORY_DOCUMENTS: "Documenti e PDF",
    CATEGORY_SPREADSHEETS: "Fogli di calcolo e dati",
    CATEGORY_PRESENTATIONS: "Presentazioni",
    CATEGORY_IMAGES: "Immagini e grafica",
    CATEGORY_WRITING: "Scrittura e relazioni",
    CATEGORY_FILE_ORGANIZATION: "Organizzazione di file",
    CATEGORY_TRANSLATION: "Traduzione",
    CATEGORY_CUSTOM: "Richiesta personalizzata",
}
_PROVIDER_LABELS = {
    PROVIDER_CHATGPT: "ChatGPT",
    PROVIDER_GEMINI: "Gemini",
    PROVIDER_CLAUDE: "Claude",
}


def state_label(state: str) -> str:
    return _(_STATE_LABELS.get(state, state))


def procedure_label(procedure_id: str) -> str:
    return _(_PROCEDURE_LABELS.get(procedure_id, procedure_id))


def category_label(category_id: str, workspace: str | Path | None = None) -> str:
    legacy = _CATEGORY_LABELS.get(category_id)
    if legacy is not None:
        return _(legacy)
    if workspace:
        match = next(
            (item for item in list_superpowers(Path(workspace)) if item.superpower_id == category_id),
            None,
        )
        if match is not None:
            return match.title
    return category_id


def provider_label(provider_id: str) -> str:
    return _(_PROVIDER_LABELS.get(provider_id, provider_id))


def web_plan(
    category_id: str,
    provider_id: str,
    input_count: int,
    output_directory: str,
) -> str:
    destination = output_directory or _("nessuna cartella selezionata")
    return _(
        "BridgAI creerà uno ZIP contenente soltanto gli input autorizzati e le "
        "istruzioni della missione. Il pacchetto verrà affidato a {provider} per "
        "un lavoro di tipo “{category}”. Lo ZIP restituito sarà controllato prima "
        "di estrarre i risultati in {destination}. Input selezionati: {count}."
    ).format(
        provider=provider_label(provider_id),
        category=category_label(category_id),
        destination=destination,
        count=input_count,
    )


def draft_plan(procedure_id: str, input_count: int, output_directory: str) -> str:
    destination = output_directory or _("nessuna cartella selezionata")
    if procedure_id == PROCEDURE_CSV_MERGE:
        return _(
            "Piano: cercare i CSV negli input autorizzati, verificare intestazioni e "
            "righe, unire le colonne senza modificare gli originali e creare un CSV "
            "unificato con un riepilogo nella cartella {destination}. Input selezionati: {count}."
        ).format(destination=destination, count=input_count)
    return _(
        "Piano: leggere soltanto i metadati degli input autorizzati e creare un "
        "inventario JSON nella cartella {destination}. Input selezionati: {count}."
    ).format(destination=destination, count=input_count)


def execution_confirmation(mission: OperationalMission) -> str:
    if mission.procedure_id == PROCEDURE_CSV_MERGE:
        return _(
            "BridgAI leggerà il contenuto dei soli CSV autorizzati, verificherà le "
            "intestazioni e creerà un nuovo CSV unificato e un riepilogo nella cartella "
            "di output. Gli originali non verranno modificati, i file esistenti non "
            "verranno sovrascritti e non saranno usati rete o programmi esterni. Procedere?"
        )
    return _(
        "BridgAI leggerà soltanto i metadati degli input autorizzati e creerà un nuovo "
        "inventario JSON nella cartella di output. Non modificherà gli originali, non "
        "userà la rete e non avvierà programmi esterni. Procedere?"
    )


def completion_message(procedure_id: str) -> str:
    if procedure_id == PROCEDURE_CSV_MERGE:
        return _("Il CSV unificato e il riepilogo sono stati creati e verificati.")
    return _("L’inventario degli input è stato creato e verificato.")


def execution_summary(record: OperationalExecutionRecord | None) -> str:
    if record is None:
        return _("Nessuna esecuzione locale registrata per questa missione.")
    outputs = "\n".join(f"• {path}" for path in record.output_paths) or _(
        "Nessun risultato esterno prodotto."
    )
    error = f"\n\n{_('Errore:')}\n{record.error}" if record.error else ""
    return (
        f"{_('Procedura:')} {procedure_label(record.procedure_id)}\n"
        f"{_('Stato esecuzione:')} {state_label(record.state)}\n"
        f"{_('Avviata il:')} {record.started_at}\n"
        f"{_('Terminata il:')} {record.finished_at or '-'}\n\n"
        f"{_('Risultati prodotti:')}\n{outputs}{error}"
    )


def result_preview_text(preview: dict[str, object]) -> str:
    files = preview.get("output_files")
    lines = [f"• {item}" for item in files] if isinstance(files, list) else []
    summary = str(preview.get("summary", "")).strip()
    text = _("ZIP risultati pronto. File verificati:") + "\n" + (
        "\n".join(lines) or _("Nessun file elencato.")
    )
    if summary:
        text += "\n\n" + _("Riepilogo dell’AI:") + "\n" + summary
    if preview.get("tool_requested"):
        text += "\n\n" + _(
            "L’AI segnala che potrebbe servire uno strumento locale dedicato."
        )
    return text


def mission_details(
    mission: OperationalMission,
    execution: OperationalExecutionRecord | None = None,
) -> str:
    inputs = "\n".join(f"• {path}" for path in mission.input_paths) or _(
        "Nessun input autorizzato."
    )
    output = mission.output_directory or _("Nessuna cartella di output selezionata.")
    archived = (
        f"\n{_('Archiviata il:')} {mission.archived_at}" if mission.archived_at else ""
    )
    if mission.procedure_id == PROCEDURE_WEB_MISSION:
        heading = (
            f"{_('Titolo:')} {mission.title}\n"
            f"{_('Settore di lavoro:')} {category_label(mission.work_category)}\n"
            + (
                f"{_('Approccio operativo:')} {category_label(mission.superpower_id, mission.workspace)}\n"
                if mission.superpower_id else ""
            )
            + f"{_('AI Web:')} {provider_label(mission.provider)}\n"
        )
    else:
        heading = (
            f"{_('Titolo:')} {mission.title}\n"
            f"{_('Strumento locale:')} {procedure_label(mission.procedure_id)}\n"
        )
    details = (
        heading
        + f"{_('Stato:')} {state_label(mission.state)}\n"
        + f"{_('Creata il:')} {mission.created_at}{archived}\n\n"
        + f"{_('Richiesta:')}\n{mission.original_request}\n\n"
        + f"{_('Input autorizzati:')}\n{inputs}\n\n"
        + f"{_('Cartella risultati:')}\n{output}"
    )
    if mission.procedure_id != PROCEDURE_WEB_MISSION:
        details += "\n\n" + execution_summary(execution)
    return details

