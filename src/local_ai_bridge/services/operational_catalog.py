from __future__ import annotations


MISSION_DRAFT = "draft"
MISSION_READY = "ready"
MISSION_RUNNING = "running"
MISSION_COMPLETED = "completed"
MISSION_FAILED = "failed"
MISSION_CANCELLED = "cancelled"
MISSION_ARCHIVED = "archived"
MISSION_STATES = (
    MISSION_DRAFT,
    MISSION_READY,
    MISSION_RUNNING,
    MISSION_COMPLETED,
    MISSION_FAILED,
    MISSION_CANCELLED,
    MISSION_ARCHIVED,
)
MISSION_RECORD_VERSION = 1

PROCEDURE_INPUT_INVENTORY = "builtin.input_inventory.v1"
PROCEDURE_CSV_MERGE = "builtin.csv_merge_summary.v1"
PROCEDURE_WEB_MISSION = "web.ai_mission.v1"
MISSION_PROCEDURES = (
    PROCEDURE_INPUT_INVENTORY,
    PROCEDURE_CSV_MERGE,
    PROCEDURE_WEB_MISSION,
)

CATEGORY_DOCUMENTS = "documents_pdf"
CATEGORY_SPREADSHEETS = "spreadsheets_data"
CATEGORY_PRESENTATIONS = "presentations"
CATEGORY_IMAGES = "images_graphics"
CATEGORY_WRITING = "writing_reports"
CATEGORY_FILE_ORGANIZATION = "file_organization"
CATEGORY_TRANSLATION = "translation"
CATEGORY_CUSTOM = "custom"
MISSION_WORK_CATEGORIES = (
    CATEGORY_DOCUMENTS,
    CATEGORY_SPREADSHEETS,
    CATEGORY_PRESENTATIONS,
    CATEGORY_IMAGES,
    CATEGORY_WRITING,
    CATEGORY_FILE_ORGANIZATION,
    CATEGORY_TRANSLATION,
    CATEGORY_CUSTOM,
)

PROVIDER_CHATGPT = "chatgpt"
PROVIDER_GEMINI = "gemini"
PROVIDER_CLAUDE = "claude"
MISSION_PROVIDERS = (PROVIDER_CHATGPT, PROVIDER_GEMINI, PROVIDER_CLAUDE)

MISSION_TRANSITIONS = {
    MISSION_DRAFT: frozenset({MISSION_READY, MISSION_ARCHIVED}),
    MISSION_READY: frozenset({MISSION_DRAFT, MISSION_RUNNING, MISSION_ARCHIVED}),
    MISSION_RUNNING: frozenset(
        {MISSION_COMPLETED, MISSION_FAILED, MISSION_CANCELLED}
    ),
    MISSION_COMPLETED: frozenset({MISSION_ARCHIVED}),
    MISSION_FAILED: frozenset({MISSION_READY, MISSION_ARCHIVED}),
    MISSION_CANCELLED: frozenset({MISSION_READY, MISSION_ARCHIVED}),
    MISSION_ARCHIVED: frozenset(),
}


_OPERATIONAL_CATEGORY_GROUPS = {}


def operational_superpower_allowed(work_category: str, item) -> bool:
    """Return whether a superpower is explicitly available in an operational sector."""
    if getattr(item, "usage_mode", "shared") == "development":
        return False
    sectors = {value.casefold() for value in getattr(item, "operational_sectors", ())}
    return work_category.casefold() in sectors or "*" in sectors

