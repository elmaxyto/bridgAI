from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import ToggleSwitch, _button


def _wrapped_label(text: str) -> QLabel:
    label = QLabel(_(text))
    label.setWordWrap(True)
    return label


def _section(title: str) -> tuple[QWidget, QVBoxLayout]:
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    title_label = QLabel(_(title))
    title_font = title_label.font()
    title_font.setBold(True)
    title_label.setFont(title_font)
    layout.addWidget(title_label)
    return section, layout


def build_ai_assistant_settings_group(window) -> QGroupBox:
    group = QGroupBox(_("Co-Pilota / Assistente AI Opzionale"))
    group_layout = QVBoxLayout(group)
    group_layout.addWidget(
        _wrapped_label(
            "Funzione opzionale e disattivabile. Quando è spenta BridgAI continua "
            "a usare le espressioni regolari e le euristiche locali esistenti, "
            "senza dipendere da modelli AI."
        )
    )

    window.ai_assistant_enabled_check = ToggleSwitch(
        _("Abilita Assistente AI (Funzioni Extra)")
    )
    window.ai_assistant_enabled_check.toggled.connect(
        window.set_ai_assistant_enabled
    )
    group_layout.addWidget(window.ai_assistant_enabled_check)

    tasks_section, tasks_layout = _section("Micro-task disponibili")
    for task in (
        "Scrittura automatica dei messaggi di commit basati sul diff reale.",
        "Code review e analisi dei rischi nella scheda Anteprima Modifiche "
        "prima dell’applicazione.",
        "Pre-validazione dei blocchi SEARCH/REPLACE e delle patch testuali per "
        "intercettare refusi o troncamenti prima che tocchino il codice reale "
        "(ottimale per risposte testuali da Gemini/Perplexity).",
        "Spiegazione in linguaggio naturale dei test falliti tramite l’analisi "
        "dei log di pytest.",
        "Suggerimento intelligente dei file rilevanti da includere nel "
        "Super-Report in base al task inserito.",
    ):
        task_label = QLabel(f"• {_(task)}")
        task_label.setWordWrap(True)
        tasks_layout.addWidget(task_label)
    group_layout.addWidget(tasks_section)

    window.ai_assistant_options_widget = QWidget()
    options_layout = QVBoxLayout(window.ai_assistant_options_widget)
    options_layout.setContentsMargins(0, 0, 0, 0)
    options_layout.setSpacing(8)

    source_form = QFormLayout()
    window.ai_assistant_source_combo = QComboBox()
    window.ai_assistant_source_combo.addItem(
        _("Gemma 4 Integrata (100% Locale e Offline)"),
        "gemma_internal",
    )
    window.ai_assistant_source_combo.addItem(
        _("Ollama Locale (Per esperti)"),
        "ollama",
    )
    window.ai_assistant_source_combo.addItem(
        _("Provider Cloud (Richiede Internet)"),
        "cloud_provider",
    )
    window.ai_assistant_source_combo.currentIndexChanged.connect(
        window.save_ai_assistant_source
    )
    source_form.addRow(_("Sorgente AI:"), window.ai_assistant_source_combo)
    options_layout.addLayout(source_form)

    window.ai_assistant_source_stack = QStackedWidget()
    window.ai_assistant_source_stack.addWidget(_build_gemma_page(window))
    window.ai_assistant_source_stack.addWidget(_build_ollama_page(window))
    window.ai_assistant_source_stack.addWidget(_build_cloud_page(window))
    options_layout.addWidget(window.ai_assistant_source_stack)
    group_layout.addWidget(window.ai_assistant_options_widget)
    return group


def _build_gemma_page(window) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(
        _wrapped_label(
            "Scarica manualmente un peso compatibile .litertlm o .gguf e usa "
            "il pulsante per copiarlo nella cartella temporanea gestita "
            "LocalAIBridgeTemp."
        )
    )
    window.ai_assistant_gemma_status_label = _wrapped_label(
        "Modello integrato non ancora disponibile."
    )
    layout.addWidget(window.ai_assistant_gemma_status_label)
    button_row = QHBoxLayout()
    button_row.addWidget(
        _button(_("Scarica Modello"), window.download_ai_assistant_gemma_model)
    )
    button_row.addStretch(1)
    layout.addLayout(button_row)
    return page


def _build_ollama_page(window) -> QWidget:
    page = QWidget()
    layout = QFormLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    window.ai_assistant_ollama_url_edit = QLineEdit()
    window.ai_assistant_ollama_url_edit.setPlaceholderText(
        "http://localhost:11434"
    )
    window.ai_assistant_ollama_url_edit.editingFinished.connect(
        window.save_ai_assistant_settings
    )
    window.ai_assistant_ollama_model_edit = QLineEdit()
    window.ai_assistant_ollama_model_edit.setPlaceholderText(
        "qwen2.5-coder:7b"
    )
    window.ai_assistant_ollama_model_edit.editingFinished.connect(
        window.save_ai_assistant_settings
    )
    layout.addRow(_("URL endpoint Ollama:"), window.ai_assistant_ollama_url_edit)
    layout.addRow(_("ID modello Ollama:"), window.ai_assistant_ollama_model_edit)
    return page


def _build_cloud_page(window) -> QWidget:
    page = QWidget()
    layout = QFormLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    window.ai_assistant_cloud_provider_combo = QComboBox()
    for label, provider_id in (
        ("Groq", "groq"),
        ("Cerebras", "cerebras"),
        ("Gemini", "gemini"),
        ("Mistral", "mistral"),
        ("OpenRouter", "openrouter"),
    ):
        window.ai_assistant_cloud_provider_combo.addItem(label, provider_id)
    window.ai_assistant_cloud_provider_combo.currentIndexChanged.connect(
        window.save_ai_assistant_settings
    )

    window.ai_assistant_cloud_key_edit = QLineEdit()
    window.ai_assistant_cloud_key_edit.setEchoMode(QLineEdit.Password)
    window.ai_assistant_cloud_key_edit.setPlaceholderText(
        _("Inserisci la chiave API")
    )
    window.ai_assistant_cloud_key_edit.editingFinished.connect(
        window.save_ai_assistant_settings
    )
    window.ai_assistant_cloud_model_edit = QLineEdit()
    window.ai_assistant_cloud_model_edit.setPlaceholderText(
        "llama-3.3-70b-speculative"
    )
    window.ai_assistant_cloud_model_edit.editingFinished.connect(
        window.save_ai_assistant_settings
    )

    layout.addRow(
        _("Provider cloud:"),
        window.ai_assistant_cloud_provider_combo,
    )
    layout.addRow(_("API Key:"), window.ai_assistant_cloud_key_edit)
    layout.addRow(_("ID modello cloud:"), window.ai_assistant_cloud_model_edit)
    return page
