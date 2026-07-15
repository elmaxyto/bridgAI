from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.services.operational_missions import (
    CATEGORY_CUSTOM,
    CATEGORY_DOCUMENTS,
    CATEGORY_FILE_ORGANIZATION,
    CATEGORY_IMAGES,
    CATEGORY_PRESENTATIONS,
    CATEGORY_SPREADSHEETS,
    CATEGORY_TRANSLATION,
    CATEGORY_WRITING,
    PROVIDER_CHATGPT,
    PROVIDER_CLAUDE,
    PROVIDER_GEMINI,
)
from local_ai_bridge.ui.tabs.operations_secondary import add_advanced_tools, add_status_and_history
from local_ai_bridge.ui.widgets import _step_header


def _wrapped_label(text: str, style_class: str | None = None) -> QLabel:
    label = QLabel(_(text))
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if style_class:
        label.setProperty("class", style_class)
    return label


def _card(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    card = QGroupBox(_(title))
    card.setProperty("class", "operationsCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(18, 18, 18, 18)
    card_layout.setSpacing(12)
    return card, card_layout


def _flow_strip() -> QWidget:
    strip = QWidget()
    strip.setProperty("class", "operationsFlow")
    row = QHBoxLayout(strip)
    row.setContentsMargins(12, 10, 12, 10)
    row.setSpacing(8)
    for text in (
        "1 · Descrivi l’attività",
        "2 · Scegli il prompt",
        "3 · Apri l’AI",
        "4 · Allega ciò che serve",
    ):
        pill = QLabel(_(text))
        pill.setProperty("class", "flowPill")
        pill.setAlignment(Qt.AlignCenter)
        pill.setWordWrap(True)
        row.addWidget(pill, 1)
    return strip


def build_operations_tab(window) -> QWidget:
    """Build the lightweight guided AI task assistant."""
    page = QWidget()
    page.setObjectName("operationsPage")
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setObjectName("operationsScrollArea")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    content = QWidget()
    content.setObjectName("operationsScrollContent")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(28, 24, 28, 28)
    layout.setSpacing(16)

    title = QLabel(_("Assistente Attività AI"))
    title.setObjectName("operationsTitle")
    title.setProperty("class", "pageTitle")
    layout.addWidget(title)

    subtitle = _wrapped_label(
        "Ottimizza documenti, presentazioni, PDF, immagini, dati e altri lavori di ufficio. "
        "BridgAI prepara un prompt guidato; sarà poi l’AI Web a chiederti soltanto i file e "
        "i chiarimenti realmente necessari.",
        "pageSubtitle",
    )
    subtitle.setObjectName("operationsSubtitle")
    layout.addWidget(subtitle)
    layout.addWidget(_flow_strip())

    project_note = _wrapped_label(
        "Il progetto locale è facoltativo. Puoi lavorare senza cartella oppure usare i controlli "
        "del progetto per organizzare materiali, note e risultati di un’attività più lunga.",
        "infoBanner",
    )
    project_note.setObjectName("operationsOptionalProjectNotice")
    layout.addWidget(project_note)

    mission_group, mission_layout = _card("Nuova attività guidata")
    mission_layout.addWidget(
        _step_header(
            "1",
            _("Descrivi cosa vuoi ottenere"),
            _("Non devi scegliere subito file o cartelle: l’AI ti chiederà solo ciò che serve."),
        )
    )

    request_form = QFormLayout()
    request_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

    window.operations_category_combo = QComboBox()
    window.operations_category_combo.setObjectName("operationsCategoryCombo")
    for label, value in (
        ("Documenti e PDF", CATEGORY_DOCUMENTS),
        ("Fogli di calcolo e dati", CATEGORY_SPREADSHEETS),
        ("Presentazioni", CATEGORY_PRESENTATIONS),
        ("Immagini e grafica", CATEGORY_IMAGES),
        ("Scrittura e relazioni", CATEGORY_WRITING),
        ("Organizzazione di file", CATEGORY_FILE_ORGANIZATION),
        ("Traduzione", CATEGORY_TRANSLATION),
        ("Richiesta personalizzata", CATEGORY_CUSTOM),
    ):
        window.operations_category_combo.addItem(_(label), value)
    window.operations_category_combo.currentIndexChanged.connect(window.refresh_operational_superpowers)
    window.operations_category_combo.currentIndexChanged.connect(window._refresh_operational_draft_state)
    request_form.addRow(_("Tipo di attività:"), window.operations_category_combo)

    window.operations_superpower_combo = QComboBox()
    window.operations_superpower_combo.setObjectName("operationsSuperpowerCombo")
    window.operations_superpower_combo.currentIndexChanged.connect(window._refresh_operational_draft_state)
    request_form.addRow(_("Prompt guidato:"), window.operations_superpower_combo)
    window.refresh_operational_superpowers()

    window.operations_title_edit = QLineEdit()
    window.operations_title_edit.setPlaceholderText(_("Titolo facoltativo dell’attività"))
    request_form.addRow(_("Titolo:"), window.operations_title_edit)

    window.operations_request_edit = QTextEdit()
    window.operations_request_edit.setAcceptRichText(False)
    window.operations_request_edit.setPlaceholderText(
        _("Esempio: aiutami a creare una presentazione professionale per illustrare i risultati trimestrali.")
    )
    window.operations_request_edit.setMinimumHeight(150)
    window.operations_request_edit.textChanged.connect(window._refresh_operational_draft_state)
    request_form.addRow(_("Cosa vuoi realizzare:"), window.operations_request_edit)
    mission_layout.addLayout(request_form)

    mission_layout.addWidget(
        _step_header(
            "2",
            _("Scegli l’AI Web"),
            _("BridgAI copierà il prompt negli appunti e aprirà il servizio scelto."),
        )
    )
    provider_form = QFormLayout()
    window.operations_provider_combo = QComboBox()
    window.operations_provider_combo.setObjectName("operationsProviderCombo")
    window.operations_provider_combo.addItem(_("ChatGPT"), PROVIDER_CHATGPT)
    window.operations_provider_combo.addItem(_("Gemini"), PROVIDER_GEMINI)
    window.operations_provider_combo.addItem(_("Claude"), PROVIDER_CLAUDE)
    window.operations_provider_combo.currentIndexChanged.connect(window._refresh_operational_draft_state)
    provider_form.addRow(_("AI Web:"), window.operations_provider_combo)
    mission_layout.addLayout(provider_form)

    window.operations_draft_state_label = QLabel(_("Aggiungi una descrizione per continuare"))
    window.operations_draft_state_label.setObjectName("operationsDraftState")
    window.operations_draft_state_label.setProperty("class", "stateBadge")
    window.operations_draft_state_label.setProperty("state", "draft")
    mission_layout.addWidget(window.operations_draft_state_label)

    window.operations_plan_edit = QTextEdit()
    window.operations_plan_edit.setObjectName("operationsPlanPreview")
    window.operations_plan_edit.setReadOnly(True)
    window.operations_plan_edit.setAcceptRichText(False)
    window.operations_plan_edit.setMaximumHeight(110)
    mission_layout.addWidget(window.operations_plan_edit)

    privacy = _wrapped_label(
        "Nessun file viene inviato da BridgAI in questa fase. Dopo l’apertura della chat, "
        "allega direttamente nell’interfaccia Web del modello solo i materiali richiesti dall’AI.",
        "infoBanner",
    )
    privacy.setObjectName("operationsPrivacyNotice")
    mission_layout.addWidget(privacy)

    mission_actions = QHBoxLayout()
    window.operations_start_button = QPushButton(_("Prepara richiesta e apri l’AI"))
    window.operations_start_button.setObjectName("startOperationalWebMissionButton")
    window.operations_start_button.setProperty("role", "primary")
    window.operations_start_button.setEnabled(False)
    window.operations_start_button.clicked.connect(window.start_operational_web_mission)
    mission_actions.addWidget(window.operations_start_button)
    clear_button = QPushButton(_("Azzera"))
    clear_button.clicked.connect(window.clear_operational_mission_form)
    mission_actions.addWidget(clear_button)
    mission_actions.addStretch(1)
    mission_layout.addLayout(mission_actions)
    layout.addWidget(mission_group)

    # Compatibility widgets used by the legacy advanced mission tools.
    window.operations_input_list = QListWidget()
    window.operations_input_count_label = QLabel()
    window.operations_output_edit = QLineEdit()

    add_status_and_history(window, layout)
    add_advanced_tools(window, layout)

    footer = QHBoxLayout()
    settings_button = QPushButton(_("Apri le Impostazioni"))
    settings_button.clicked.connect(window.open_mode_settings)
    footer.addWidget(settings_button)
    development_button = QPushButton(_("Passa a Sviluppo software"))
    development_button.clicked.connect(window.activate_development_mode)
    footer.addWidget(development_button)
    footer.addStretch(1)
    layout.addLayout(footer)

    window._refresh_operational_draft_state()
    scroll.setWidget(content)
    page_layout.addWidget(scroll)
    return page
