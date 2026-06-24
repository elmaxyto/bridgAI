from __future__ import annotations

from local_ai_bridge.core.prompt_presets import load_prompt_presets
from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import _button, _provider_button, _step_header
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

def build_workflow_tab(window) -> QWidget:
    page = QWidget()
    page.setObjectName('workflowPage')
    layout = QVBoxLayout(page)
    layout.setContentsMargins(22, 18, 22, 22)
    layout.setSpacing(16)

    window.simple_welcome = QLabel(_('Cosa vuoi fare oggi?'))
    window.simple_welcome.setProperty('class', 'pageTitle')
    layout.addWidget(window.simple_welcome)
    window.simple_subtitle = QLabel(_('Descrivi il risultato che vuoi ottenere. BridgAI preparerà tutto il necessario per dialogare con la tua AI.'))
    window.simple_subtitle.setProperty('class', 'pageSubtitle')
    window.simple_subtitle.setWordWrap(True)
    layout.addWidget(window.simple_subtitle)

    task_group = QGroupBox()
    task_group.setProperty('class', 'card')
    window.task_group = task_group
    task_layout = QVBoxLayout(task_group)
    task_layout.setContentsMargins(18, 16, 18, 18)
    task_layout.setSpacing(12)
    task_layout.addWidget(_step_header('1', _('Descrivi la richiesta'), _('Scrivi con parole semplici cosa vuoi creare, correggere o migliorare.')))
    window.task_edit = QPlainTextEdit()
    window.task_edit.setPlaceholderText(_('Ad esempio: rendi più semplice la schermata iniziale e usa pulsanti più chiari...'))
    window.task_edit.setMaximumHeight(120)
    window.task_edit.setProperty('class', 'largeInput')
    task_layout.addWidget(window.task_edit)
    preset_row = QHBoxLayout()
    window.prompt_preset_label = QLabel(_('Preset di prompt:'))
    preset_row.addWidget(window.prompt_preset_label)
    window.prompt_preset_combo = QComboBox()
    window.prompt_preset_combo.addItem(_('Nessun preset'), '')
    for preset in load_prompt_presets():
        window.prompt_preset_combo.addItem(_(preset.label), preset.preset_id)
        index = window.prompt_preset_combo.count() - 1
        window.prompt_preset_combo.setItemData(index, _(preset.description), Qt.ToolTipRole)
    window.prompt_preset_combo.setToolTip(_('Il preset aggiunge istruzioni al task senza modificarne il testo.'))
    preset_row.addWidget(window.prompt_preset_combo, 1)
    task_layout.addLayout(preset_row)
    report_buttons = QHBoxLayout()
    window.report_button = _button(_('Prepara per l’AI'), window.generate_report, 'primary')
    report_buttons.addWidget(window.report_button)
    window.simple_chatgpt_button = _provider_button(
        _('Continua su ChatGPT'),
        lambda: window.open_external_ai(window.settings.chatgpt_url),
    )
    window.simple_claude_button = _provider_button(
        _('Continua su Claude'),
        lambda: window.open_external_ai(window.settings.claude_url),
        '#e58a2b',
    )
    window.simple_gemini_button = _provider_button(
        _('Continua su Gemini'),
        window.open_gemini,
        '#6c63ff',
    )
    window.simple_report_buttons = [
        window.simple_chatgpt_button,
        window.simple_claude_button,
        window.simple_gemini_button,
    ]
    for button in window.simple_report_buttons:
        report_buttons.addWidget(button)
    actions = ((_('Copia report'), window.copy_report), (_('Salva report'), window.save_report), (_('Apri ChatGPT'), lambda: window._open_web(window.settings.chatgpt_url)), (_('Apri Claude'), lambda: window._open_web(window.settings.claude_url)), (_('Apri Gemini'), window.open_gemini))
    window.report_extra_buttons = []
    for label, callback in actions:
        button = _button(label, callback)
        window.report_extra_buttons.append(button)
        report_buttons.addWidget(button)
    report_buttons.addStretch(1)
    window.speech_button = _button('🎙', window.open_speech_dialog, 'icon')
    window.speech_button.setAccessibleName(_('Dettatura'))
    window.speech_button.setToolTip(_('Detta il task tramite microfono'))
    report_buttons.addWidget(window.speech_button)
    task_layout.addLayout(report_buttons)
    layout.addWidget(task_group)

    window.report_edit = QPlainTextEdit()
    window.report_edit.setReadOnly(True)
    window.report_edit.setPlaceholderText(_('Il Super-Report apparirà qui.'))
    layout.addWidget(window.report_edit, 3)
    window.report_edit.textChanged.connect(window._auto_copy_report_in_simple_mode)

    response_group = QGroupBox()
    response_group.setProperty('class', 'card')
    window.response_group = response_group
    response_layout = QVBoxLayout(response_group)
    response_layout.setContentsMargins(18, 16, 18, 18)
    response_layout.setSpacing(12)
    window.response_step_header = _step_header('2', _('Incolla la risposta dell’AI'), _('Torna qui e incolla tutto il messaggio ricevuto, senza modificarlo.'))
    response_layout.addWidget(window.response_step_header)
    window.response_edit = QPlainTextEdit()
    window.response_edit.setPlaceholderText(_('Incolla qui la risposta completa dell’AI...'))
    window.response_edit.setProperty('class', 'largeInput')
    response_layout.addWidget(window.response_edit, 2)
    form = QFormLayout()
    window.target_edit = QLineEdit()
    window.target_edit.setPlaceholderText(_('es. src/app.py — necessario per patch o file completo'))
    form.addRow(_('File target:'), window.target_edit)
    window.target_form = form
    response_layout.addLayout(form)
    response_buttons = QHBoxLayout()
    response_actions = ((_('Analizza risposta'), window.analyze_response), (_('Esporta file #scarica'), window.export_requested_files), (_('Apri cartella #scarica'), window.open_download_folder), (_('Prepara file completo'), window.prepare_full_file))
    window.response_action_buttons = []
    for label, callback in response_actions:
        button = _button(label, callback)
        window.response_action_buttons.append(button)
        response_buttons.addWidget(button)
    window.simple_paste_response_button = _button(_('Incolla'), window.paste_response_from_clipboard, 'primary')
    window.simple_prepare_files_button = _button(_('Prepara i file richiesti'), window.export_requested_files, 'primary')
    window.simple_response_buttons = [
        window.simple_paste_response_button,
        window.simple_prepare_files_button,
    ]
    for button in window.simple_response_buttons:
        response_buttons.addWidget(button)
    window.simple_apply_zip_button = _button(_('Applica aggiornamento'), window.apply_latest_zip, 'success')
    response_buttons.addWidget(window.simple_apply_zip_button)
    window.simple_patch_directory_button = _button(_('Scegli cartella aggiornamenti'), window.choose_update_zip_directory)
    response_buttons.addWidget(window.simple_patch_directory_button)
    response_buttons.addStretch(1)
    response_layout.addLayout(response_buttons)
    layout.addWidget(response_group, 2)

    markdown_result_group = QGroupBox()
    markdown_result_group.setProperty('class', 'card')
    window.markdown_result_group = markdown_result_group
    markdown_result_layout = QVBoxLayout(markdown_result_group)
    markdown_result_layout.setContentsMargins(18, 16, 18, 18)
    markdown_result_layout.setSpacing(12)
    markdown_result_layout.addWidget(
        _step_header(
            '3',
            _('Ricevi e applica il Markdown'),
            _('Usa l’ultimo file scaricato, scegline uno oppure incolla il documento completo. BridgAI mostrerà sempre l’anteprima prima di scrivere.'),
        )
    )
    window.markdown_result_edit = QPlainTextEdit()
    window.markdown_result_edit.setPlaceholderText(
        _('Incolla qui il documento Markdown completo restituito dall’AI...')
    )
    window.markdown_result_edit.setProperty('class', 'largeInput')
    window.markdown_result_edit.setMaximumHeight(170)
    markdown_result_layout.addWidget(window.markdown_result_edit)
    markdown_file_buttons = QHBoxLayout()
    markdown_file_buttons.addWidget(
        _button(_('Applica ultimo Markdown'), window.apply_latest_markdown, 'success')
    )
    markdown_file_buttons.addWidget(
        _button(_('Scegli Markdown...'), window.choose_markdown_response)
    )
    markdown_file_buttons.addWidget(
        _button(_('Cartella Markdown scaricati'), window.choose_markdown_download_directory)
    )
    markdown_file_buttons.addStretch(1)
    markdown_result_layout.addLayout(markdown_file_buttons)
    markdown_text_buttons = QHBoxLayout()
    markdown_text_buttons.addWidget(
        _button(_('Incolla'), window.paste_markdown_result_from_clipboard, 'primary')
    )
    markdown_text_buttons.addWidget(
        _button(_('Prepara anteprima'), window.prepare_pasted_markdown_response, 'primary')
    )
    markdown_text_buttons.addStretch(1)
    markdown_result_layout.addLayout(markdown_text_buttons)
    layout.addWidget(markdown_result_group, 2)

    window.simple_finish_hint = QLabel(_('3  Quando ricevi uno ZIP dall’AI, salvalo nella cartella scelta e premi “Applica aggiornamento”. Prima dell’applicazione verrà sempre mostrata un’anteprima.'))
    window.simple_finish_hint.setProperty('class', 'infoBanner')
    window.simple_finish_hint.setWordWrap(True)
    layout.addWidget(window.simple_finish_hint)

    text_result_group = QGroupBox()
    text_result_group.setProperty('class', 'card')
    window.text_result_group = text_result_group
    text_result_layout = QVBoxLayout(text_result_group)
    text_result_layout.setContentsMargins(18, 16, 18, 18)
    text_result_layout.setSpacing(12)
    text_result_layout.addWidget(
        _step_header(
            '3',
            _('Carica il file Markdown di aggiornamento'),
            _(
                'Seleziona o trascina un file .md o .txt con operazioni CREATE, REPLACE e DELETE. '
                'BridgAI mostrerà il diff prima di applicare qualsiasi file.'
            ),
        )
    )
    text_file_row = QHBoxLayout()
    window.text_update_path_edit = QLineEdit()
    window.text_update_path_edit.setReadOnly(True)
    window.text_update_path_edit.setPlaceholderText(
        _('Nessun file Markdown di aggiornamento selezionato.')
    )
    text_file_row.addWidget(window.text_update_path_edit, 1)
    text_file_row.addWidget(
        _button(_('Scegli file…'), window.choose_text_update_file)
    )
    text_file_row.addWidget(
        _button(_('Analizza file'), window.analyze_selected_text_update_file, 'primary')
    )
    text_result_layout.addLayout(text_file_row)

    manual_label = QLabel(_('Oppure incolla manualmente la risposta'))
    manual_label.setProperty('class', 'sectionTitle')
    text_result_layout.addWidget(manual_label)
    window.text_result_edit = QPlainTextEdit()
    window.text_result_edit.setPlaceholderText(
        _('Incolla qui le operazioni complete del file Markdown di aggiornamento...')
    )
    window.text_result_edit.setProperty('class', 'largeInput')
    text_result_layout.addWidget(window.text_result_edit, 2)
    text_result_buttons = QHBoxLayout()
    text_result_buttons.addWidget(
        _button(_('Incolla'), window.paste_text_result_from_clipboard, 'secondary')
    )
    text_result_buttons.addWidget(
        _button(_('Analizza testo incollato'), window.prepare_text_result_plan, 'primary')
    )
    text_result_buttons.addStretch(1)
    text_result_layout.addLayout(text_result_buttons)
    layout.addWidget(text_result_group, 2)

    # Alias interni mantenuti per la pulizia dello stato e la retrocompatibilità UI.
    window.gemini_result_group = text_result_group
    window.gemini_result_edit = window.text_result_edit
    return page
