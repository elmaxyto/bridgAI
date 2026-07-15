from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from local_ai_bridge.core.project_notes import (
    ProjectNote,
    delete_project_note,
    load_project_notes,
    project_note_request_block,
    upsert_project_note,
)
from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import ToggleSwitch


_PROJECT_NOTES_STYLE = """
QWidget#projectNotesRoot {
    background: transparent;
}
QSplitter#projectNotesSplitter::handle {
    background: transparent;
    margin: 10px 0;
}
QListWidget#projectNotesList {
    outline: 0;
}
QListWidget#projectNotesList::item {
    padding: 8px;
    margin: 2px 0;
}
"""


def _label(text: str, class_name: str | None = None) -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(True)
    if class_name:
        widget.setProperty("class", class_name)
    return widget



def _metric(value: str) -> QLabel:
    widget = QLabel(value)
    widget.setProperty("class", "flowPill")
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    widget.setMinimumHeight(30)
    return widget



def _button(text: str, role: str | None = None) -> QPushButton:
    widget = QPushButton(text)
    if role:
        widget.setProperty("role", role)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget



def _card(title: str, card_class: str = "card") -> QGroupBox:
    widget = QGroupBox(title)
    widget.setProperty("class", card_class)
    return widget



def _note_marker(note: ProjectNote) -> str:
    if note.todo and note.completed:
        return "✓"
    if note.todo:
        return "↗"
    return "•"



def _note_status(note: ProjectNote) -> str:
    if note.todo and note.completed:
        return _("completata")
    if note.todo:
        return _("attività aperta")
    return _("nota")



def _note_excerpt(note: ProjectNote) -> str:
    content = " ".join(note.content.split())
    if len(content) > 110:
        content = content[:107].rstrip() + "…"
    return content or _("Nessun dettaglio inserito.")



def build_project_notes_tab(window) -> QWidget:
    tab = QWidget()
    tab.setObjectName("projectNotesRoot")
    tab.setStyleSheet(_PROJECT_NOTES_STYLE)
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(16, 18, 16, 14)
    layout.setSpacing(14)

    title = _label(_("Note e attività del progetto"), "pageTitle")
    subtitle = _label(
        _(
            "Raccogli idee, decisioni e cose da fare del workspace. "
            "Ogni nota può diventare contesto per una richiesta AI con un clic."
        ),
        "pageSubtitle",
    )
    layout.addWidget(title)
    layout.addWidget(subtitle)

    hero = QFrame()
    hero.setProperty("class", "operationsFlow")
    hero.setObjectName("projectNotesHero")
    hero_layout = QHBoxLayout(hero)
    hero_layout.setContentsMargins(16, 14, 16, 14)
    hero_layout.setSpacing(10)
    window.project_notes_total_metric = _metric(_("0 note"))
    window.project_notes_open_metric = _metric(_("0 aperte"))
    window.project_notes_done_metric = _metric(_("0 completate"))
    hero_layout.addWidget(window.project_notes_total_metric)
    hero_layout.addWidget(window.project_notes_open_metric)
    hero_layout.addWidget(window.project_notes_done_metric)
    hero_layout.addStretch(1)
    layout.addWidget(hero)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setObjectName("projectNotesSplitter")
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(12)
    layout.addWidget(splitter, 1)

    left = _card(_("Archivio note"))
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(14, 14, 14, 14)
    left_layout.setSpacing(10)
    window.project_notes_summary_label = _label(_("Nessuna nota caricata."), "muted")
    left_layout.addWidget(window.project_notes_summary_label)
    window.project_notes_search = QLineEdit()
    window.project_notes_search.setPlaceholderText(_("Cerca titolo o dettagli…"))
    window.project_notes_search.textChanged.connect(lambda _text: refresh_project_notes(window))
    left_layout.addWidget(window.project_notes_search)
    window.project_notes_list = QListWidget()
    window.project_notes_list.setObjectName("projectNotesList")
    window.project_notes_list.setMinimumWidth(310)
    window.project_notes_list.setSpacing(2)
    window.project_notes_list.itemSelectionChanged.connect(lambda: _load_selected_note(window))
    left_layout.addWidget(window.project_notes_list, 1)
    new_button = _button(_("+ Nuova nota"), "primary")
    new_button.clicked.connect(lambda: clear_project_note_editor(window))
    left_layout.addWidget(new_button)
    splitter.addWidget(left)

    right = _card(_("Editor nota"))
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(14, 14, 14, 14)
    right_layout.setSpacing(10)
    window.project_note_id = ""
    right_layout.addWidget(
        _label(_("Scrivi il contesto una volta, poi riusalo nelle richieste operative."), "muted")
    )
    right_layout.addWidget(_label(_("Titolo")))
    window.project_note_title = QLineEdit()
    window.project_note_title.setPlaceholderText(_("Es. bug da correggere, decisione, promemoria…"))
    right_layout.addWidget(window.project_note_title)

    switches = QHBoxLayout()
    switches.setSpacing(18)
    window.project_note_todo = ToggleSwitch(_("Attività"))
    window.project_note_completed = ToggleSwitch(_("Completata"))
    window.project_note_todo.toggled.connect(window.project_note_completed.setEnabled)
    switches.addWidget(window.project_note_todo)
    switches.addWidget(window.project_note_completed)
    switches.addStretch(1)
    right_layout.addLayout(switches)

    right_layout.addWidget(_label(_("Dettagli")))
    window.project_note_content = QPlainTextEdit()
    window.project_note_content.setPlaceholderText(
        _("Aggiungi dettagli, decisioni, vincoli o il problema da passare all’AI…")
    )
    right_layout.addWidget(window.project_note_content, 1)

    buttons = QHBoxLayout()
    buttons.setSpacing(10)
    save_button = _button(_("Salva"), "primary")
    save_button.clicked.connect(lambda: save_current_project_note(window))
    window.project_note_use_button = _button(_("Aggiungi alla richiesta"), "success")
    window.project_note_use_button.setToolTip(
        _("Inserisce questa nota nel campo richiesta della sezione Operazioni.")
    )
    window.project_note_use_button.clicked.connect(lambda: append_current_project_note_to_request(window))
    delete_button = _button(_("Elimina"), "danger")
    delete_button.clicked.connect(lambda: delete_current_project_note(window))
    buttons.addWidget(save_button)
    buttons.addWidget(window.project_note_use_button)
    buttons.addWidget(delete_button)
    right_layout.addLayout(buttons)
    splitter.addWidget(right)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([360, 760])
    clear_project_note_editor(window)
    return tab



def _update_metrics(window, notes: list[ProjectNote]) -> None:
    todo_count = sum(1 for note in notes if note.todo and not note.completed)
    completed_count = sum(1 for note in notes if note.todo and note.completed)
    if hasattr(window, "project_notes_total_metric"):
        window.project_notes_total_metric.setText(_("{count} note").format(count=len(notes)))
        window.project_notes_open_metric.setText(_("{count} aperte").format(count=todo_count))
        window.project_notes_done_metric.setText(_("{count} completate").format(count=completed_count))
    if hasattr(window, "project_notes_summary_label"):
        window.project_notes_summary_label.setText(
            _("{count} totali · {todo} attività aperte · {completed} completate").format(
                count=len(notes), todo=todo_count, completed=completed_count
            )
        )



def refresh_project_notes(window, select_id: str = "") -> None:
    if not hasattr(window, "project_notes_list"):
        return
    window.project_notes_list.clear()
    workspace = getattr(window, "workspace", None)
    if workspace is None:
        clear_project_note_editor(window)
        _update_metrics(window, [])
        if hasattr(window, "project_notes_summary_label"):
            window.project_notes_summary_label.setText(_("Apri un progetto per usare le note."))
        return
    notes = load_project_notes(workspace)
    _update_metrics(window, notes)
    query = ""
    if hasattr(window, "project_notes_search"):
        query = window.project_notes_search.text().strip().casefold()
    visible = [
        note for note in notes
        if not query or query in f"{note.title}\n{note.content}".casefold()
    ]
    if not visible:
        empty = QListWidgetItem(_("Nessuna nota trovata. Usa “+ Nuova nota” per iniziare."))
        empty.setFlags(Qt.ItemFlag.NoItemFlags)
        window.project_notes_list.addItem(empty)
        return
    for note in visible:
        row = QListWidgetItem(
            f"{_note_marker(note)}  {note.title}\n{_note_status(note)} · {_note_excerpt(note)}"
        )
        row.setData(Qt.ItemDataRole.UserRole, note)
        row.setToolTip(note.content or note.title)
        window.project_notes_list.addItem(row)
        if note.note_id == select_id:
            window.project_notes_list.setCurrentItem(row)
    if select_id and window.project_notes_list.currentItem() is None:
        clear_project_note_editor(window)



def clear_project_note_editor(window) -> None:
    window.project_note_id = ""
    window.project_note_title.clear()
    window.project_note_todo.setChecked(False)
    window.project_note_completed.setChecked(False)
    window.project_note_completed.setEnabled(False)
    window.project_note_content.clear()
    if hasattr(window, "project_notes_list"):
        window.project_notes_list.clearSelection()
    window.project_note_title.setFocus()



def _load_selected_note(window) -> None:
    row = window.project_notes_list.currentItem()
    if row is None:
        return
    note = row.data(Qt.ItemDataRole.UserRole)
    if not isinstance(note, ProjectNote):
        return
    window.project_note_id = note.note_id
    window.project_note_title.setText(note.title)
    window.project_note_todo.setChecked(note.todo)
    window.project_note_completed.setEnabled(note.todo)
    window.project_note_completed.setChecked(note.completed)
    window.project_note_content.setPlainText(note.content)



def save_current_project_note(window) -> None:
    workspace = window._require_workspace()
    if workspace is None:
        return
    try:
        note = upsert_project_note(
            workspace,
            note_id=window.project_note_id,
            title=window.project_note_title.text(),
            content=window.project_note_content.toPlainText(),
            todo=window.project_note_todo.isChecked(),
            completed=window.project_note_completed.isChecked(),
        )
    except Exception as exc:
        QMessageBox.critical(window, _("Nota non valida"), str(exc))
        return
    window.project_note_id = note.note_id
    refresh_project_notes(window, note.note_id)
    window._show_status(_("Nota salvata."))



def _editor_note(window) -> ProjectNote | None:
    title = window.project_note_title.text().strip()
    content = window.project_note_content.toPlainText().strip()
    if not title and not content:
        return None
    return ProjectNote(
        note_id=window.project_note_id or "draft",
        title=title or _("Nota senza titolo"),
        content=content,
        todo=window.project_note_todo.isChecked(),
        completed=window.project_note_completed.isChecked() if window.project_note_todo.isChecked() else False,
        created_at="",
        updated_at="",
    )



def append_current_project_note_to_request(window) -> None:
    if not hasattr(window, "operations_request_edit"):
        QMessageBox.information(
            window,
            _("Richiesta non disponibile"),
            _("Apri la sezione Operazioni per usare la nota in una richiesta."),
        )
        return
    note = _editor_note(window)
    if note is None:
        QMessageBox.warning(window, _("Nota vuota"), _("Seleziona o scrivi una nota prima."))
        return
    block = project_note_request_block(note)
    current = window.operations_request_edit.toPlainText().strip()
    window.operations_request_edit.setPlainText((current + "\n\n" + block).strip())
    window.operations_request_edit.setFocus()
    if hasattr(window, "_refresh_operational_draft_state"):
        window._refresh_operational_draft_state()
    window._show_status(_("Nota aggiunta alla richiesta."))



def delete_current_project_note(window) -> None:
    workspace = window._require_workspace()
    if workspace is None or not window.project_note_id:
        return
    if QMessageBox.question(window, _("Elimina nota"), _("Eliminare la nota selezionata?")) != QMessageBox.Yes:
        return
    try:
        delete_project_note(workspace, window.project_note_id)
    except Exception as exc:
        QMessageBox.critical(window, _("Eliminazione non riuscita"), str(exc))
        return
    clear_project_note_editor(window)
    refresh_project_notes(window)
    window._show_status(_("Nota eliminata."))
