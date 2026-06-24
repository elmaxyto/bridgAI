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
    CATEGORY_WRITING,
    PROVIDER_CHATGPT,
    PROVIDER_CLAUDE,
    PROVIDER_GEMINI,
)
from local_ai_bridge.ui.tabs.operations_secondary import (
    add_advanced_tools,
    add_status_and_history,
)
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
        "1 · Risultato",
        "2 · File autorizzati",
        "3 · Destinazione",
        "4 · Invio e verifica",
    ):
        pill = QLabel(_(text))
        pill.setProperty("class", "flowPill")
        pill.setAlignment(Qt.AlignCenter)
        pill.setWordWrap(True)
        row.addWidget(pill, 1)
    return strip


def build_operations_tab(window) -> QWidget:
    """Build the guided Web-AI operational mission screen."""
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

    title = QLabel(_("Modalità Operativa"))
    title.setObjectName("operationsTitle")
    title.setProperty("class", "pageTitle")
    layout.addWidget(title)

    subtitle = _wrapped_label(
        "Descrivi il risultato, scegli soltanto i file necessari e indica dove salvare "
        "l’output. BridgAI prepara lo scambio con l’AI Web e controlla il risultato prima "
        "dell’importazione.",
        "pageSubtitle",
    )
    subtitle.setObjectName("operationsSubtitle")
    layout.addWidget(subtitle)
    layout.addWidget(_flow_strip())

    mission_group, mission_layout = _card("Nuovo lavoro con AI Web")

    mission_layout.addWidget(
        _step_header(
            "1",
            _("Definisci il risultato"),
            _("Scegli il tipo di lavoro e descrivi in modo concreto ciò che vuoi ottenere."),
        )
    )
    request_form = QFormLayout()
    request_form.setFieldGrowthPolicy(
        QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
    )

    window.operations_category_combo = QComboBox()
    window.operations_category_combo.setObjectName("operationsCategoryCombo")
    for label, value in (
        ("Documenti e PDF", CATEGORY_DOCUMENTS),
        ("Fogli di calcolo e dati", CATEGORY_SPREADSHEETS),
        ("Presentazioni", CATEGORY_PRESENTATIONS),
        ("Immagini e grafica", CATEGORY_IMAGES),
        ("Scrittura e relazioni", CATEGORY_WRITING),
        ("Organizzazione di file", CATEGORY_FILE_ORGANIZATION),
        ("Richiesta personalizzata", CATEGORY_CUSTOM),
    ):
        window.operations_category_combo.addItem(_(label), value)
    window.operations_category_combo.currentIndexChanged.connect(
        window._refresh_operational_draft_state
    )
    request_form.addRow(_("Tipo di lavoro:"), window.operations_category_combo)

    window.operations_title_edit = QLineEdit()
    window.operations_title_edit.setPlaceholderText(_("Nome facoltativo della missione"))
    request_form.addRow(_("Nome missione:"), window.operations_title_edit)

    window.operations_request_edit = QTextEdit()
    window.operations_request_edit.setAcceptRichText(False)
    window.operations_request_edit.setPlaceholderText(
        _(
            "Descrivi cosa vuoi ottenere. Esempio: crea una presentazione professionale "
            "di 12 slide usando il rapporto, i dati e le immagini allegate."
        )
    )
    window.operations_request_edit.setMinimumHeight(140)
    window.operations_request_edit.textChanged.connect(
        window._refresh_operational_draft_state
    )
    request_form.addRow(_("Cosa deve fare l’AI:"), window.operations_request_edit)
    mission_layout.addLayout(request_form)

    mission_layout.addWidget(
        _step_header(
            "2",
            _("Autorizza gli input"),
            _("Aggiungi solo i file o le cartelle che l’AI può usare per questo lavoro."),
        )
    )
    window.operations_input_list = QListWidget()
    window.operations_input_list.setObjectName("operationsInputList")
    window.operations_input_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    window.operations_input_list.setMinimumHeight(112)
    mission_layout.addWidget(window.operations_input_list)

    input_footer = QHBoxLayout()
    window.operations_input_count_label = QLabel(_("Input selezionati: {count}").format(count=0))
    window.operations_input_count_label.setProperty("class", "muted")
    input_footer.addWidget(window.operations_input_count_label)
    input_footer.addStretch(1)
    add_files_button = QPushButton(_("Aggiungi file…"))
    add_files_button.clicked.connect(window.add_operational_input_files)
    input_footer.addWidget(add_files_button)
    add_directory_button = QPushButton(_("Aggiungi cartella…"))
    add_directory_button.clicked.connect(window.add_operational_input_directory)
    input_footer.addWidget(add_directory_button)
    remove_input_button = QPushButton(_("Rimuovi selezionati"))
    remove_input_button.clicked.connect(window.remove_operational_inputs)
    input_footer.addWidget(remove_input_button)
    mission_layout.addLayout(input_footer)

    mission_layout.addWidget(
        _step_header(
            "3",
            _("Scegli la destinazione"),
            _("I risultati verificati potranno essere salvati soltanto in questa cartella."),
        )
    )
    output_row = QHBoxLayout()
    window.operations_output_edit = QLineEdit()
    window.operations_output_edit.setReadOnly(True)
    window.operations_output_edit.setPlaceholderText(_("Seleziona la destinazione dei risultati"))
    output_row.addWidget(window.operations_output_edit, 1)
    output_button = QPushButton(_("Scegli cartella…"))
    output_button.clicked.connect(window.choose_operational_output_directory)
    output_row.addWidget(output_button)
    mission_layout.addLayout(output_row)

    mission_layout.addWidget(
        _step_header(
            "4",
            _("Scegli l’AI e prepara l’invio"),
            _("BridgAI mostrerà sempre il piano e gli input prima di creare il pacchetto."),
        )
    )
    provider_form = QFormLayout()
    window.operations_provider_combo = QComboBox()
    window.operations_provider_combo.setObjectName("operationsProviderCombo")
    window.operations_provider_combo.addItem(_("ChatGPT"), PROVIDER_CHATGPT)
    window.operations_provider_combo.addItem(_("Gemini"), PROVIDER_GEMINI)
    window.operations_provider_combo.addItem(_("Claude"), PROVIDER_CLAUDE)
    window.operations_provider_combo.currentIndexChanged.connect(
        window._refresh_operational_draft_state
    )
    provider_form.addRow(_("AI Web:"), window.operations_provider_combo)
    mission_layout.addLayout(provider_form)

    summary_row = QHBoxLayout()
    summary_row.addWidget(QLabel(_("Stato:")))
    window.operations_draft_state_label = QLabel(_("Bozza"))
    window.operations_draft_state_label.setObjectName("operationsDraftState")
    window.operations_draft_state_label.setProperty("class", "stateBadge")
    window.operations_draft_state_label.setProperty("state", "draft")
    summary_row.addWidget(window.operations_draft_state_label)
    summary_row.addStretch(1)
    mission_layout.addLayout(summary_row)

    window.operations_plan_edit = QTextEdit()
    window.operations_plan_edit.setObjectName("operationsPlanPreview")
    window.operations_plan_edit.setReadOnly(True)
    window.operations_plan_edit.setAcceptRichText(False)
    window.operations_plan_edit.setMaximumHeight(92)
    mission_layout.addWidget(window.operations_plan_edit)

    privacy = _wrapped_label(
        "Prima dell’invio vedrai l’elenco degli input. I file inclusi nello ZIP saranno "
        "caricati sul provider Web scelto e saranno soggetti alle sue condizioni e "
        "impostazioni privacy.",
        "infoBanner",
    )
    privacy.setObjectName("operationsPrivacyNotice")
    mission_layout.addWidget(privacy)

    mission_actions = QHBoxLayout()
    window.operations_start_button = QPushButton(_("Prepara e invia all’AI"))
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

    add_status_and_history(window, layout)
    add_advanced_tools(window, layout)

    footer = QHBoxLayout()
    settings_button = QPushButton(_("Apri le Impostazioni"))
    settings_button.clicked.connect(window.open_mode_settings)
    footer.addWidget(settings_button)
    development_button = QPushButton(_("Passa alla Modalità Sviluppo"))
    development_button.clicked.connect(window.activate_development_mode)
    footer.addWidget(development_button)
    footer.addStretch(1)
    layout.addLayout(footer)

    window._refresh_operational_draft_state()
    scroll.setWidget(content)
    page_layout.addWidget(scroll)
    return page
