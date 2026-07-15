from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from local_ai_bridge.core.superpowers import (
    MarkdownSuperpower, delete_superpower, list_superpowers, save_superpower,
)
from local_ai_bridge.i18n import tr as _
from local_ai_bridge.ui.widgets import FlowLayout, IconButton, ToggleSwitch, _chip_button


def _usage_example(item: MarkdownSuperpower) -> str:
    description = item.description.strip()
    if description:
        prompt = description[0].lower() + description[1:] if len(description) > 1 else description.lower()
        prompt = prompt.rstrip('.!?')
        return _('Esempio: @superpower:{id} — {prompt}.').format(
            id=item.superpower_id, prompt=prompt
        )
    return _('Esempio: @superpower:{id} — applica questo profilo alla richiesta corrente.').format(
        id=item.superpower_id
    )


class _SuperpowerRow(QWidget):
    """Whole-row click target: clicking anywhere (except the edit button) flips the toggle."""

    def __init__(self, toggle: ToggleSwitch, parent=None) -> None:
        super().__init__(parent)
        self._toggle = toggle
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._toggle.setChecked(not self._toggle.isChecked())
            event.accept()
            return
        super().mousePressEvent(event)


class SuperpowerDialog(QDialog):
    """Libreria dei superpoteri: seleziona/attiva dalla lista, modifica in un editor dedicato."""

    def __init__(self, workspace: Path | None, selected_ids: set[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.selected_ids = set(selected_ids or ())
        self._items: dict[str, MarkdownSuperpower] = {}
        self._ordered_ids: list[str] = []
        self._editing_id = ''
        self.setWindowTitle(_('Superpoteri Markdown'))
        self.resize(720, 640)

        root = QVBoxLayout(self)
        intro = QLabel(_('Seleziona i superpoteri da richiamare oppure creane e modificali. La libreria è condivisa tra tutti i progetti.'))
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_library_page())
        self.stack.addWidget(self._build_editor_page())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh()

    # ------------------------------------------------------------------
    # Pagina libreria: ricerca, filtro, superpoteri attivi, elenco righe
    # ------------------------------------------------------------------
    def _build_library_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        filters_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(_('Cerca superpoteri…'))
        self.search.textChanged.connect(self._apply_filters)
        filters_row.addWidget(self.search, 1)
        self.category_filter = QComboBox()
        self.category_filter.currentIndexChanged.connect(self._apply_filters)
        filters_row.addWidget(self.category_filter)
        new_button = IconButton('add')
        new_button.setToolTip(_('Nuovo superpotere'))
        new_button.clicked.connect(self._new)
        filters_row.addWidget(new_button)
        layout.addLayout(filters_row)

        self.active_label = QLabel(_('Attivi:'))
        self.active_label.setProperty('class', 'muted')
        self.active_chips = QWidget()
        self._active_chips_layout = FlowLayout(self.active_chips, spacing=6)
        layout.addWidget(self.active_label)
        layout.addWidget(self.active_chips)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName('superpowerLibraryList')
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.setSpacing(2)
        layout.addWidget(self.list_widget, 1)
        return page

    def _build_editor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        back_button = IconButton('back')
        back_button.setToolTip(_('Torna alla libreria'))
        back_button.clicked.connect(self._close_editor)
        header.addWidget(back_button)
        self.editor_title_label = QLabel(_('Nuovo superpotere'))
        self.editor_title_label.setProperty('class', 'stepTitle')
        header.addWidget(self.editor_title_label, 1)
        layout.addLayout(header)

        form = QFormLayout()
        self.title = QLineEdit()
        self.identifier = QLineEdit()
        self.description = QLineEdit()
        self.category = QLineEdit()
        self.includes = QLineEdit()
        self.includes.setPlaceholderText(_('es. json-mode, no-markdown'))
        self.markdown = QPlainTextEdit()
        form.addRow(_('Nome:'), self.title)
        form.addRow(_('ID:'), self.identifier)
        form.addRow(_('Descrizione:'), self.description)
        form.addRow(_('Categoria:'), self.category)
        form.addRow(_('Includi altri ID:'), self.includes)
        form.addRow(_('Markdown:'), self.markdown)
        layout.addLayout(form, 1)

        actions_row = QHBoxLayout()
        self.delete_button = QPushButton(_('Elimina'))
        self.delete_button.clicked.connect(self._delete)
        actions_row.addWidget(self.delete_button)
        actions_row.addStretch()
        save_button = QPushButton(_('Salva'))
        save_button.setProperty('role', 'primary')
        save_button.clicked.connect(self._save)
        actions_row.addWidget(save_button)
        layout.addLayout(actions_row)
        return page

    # ------------------------------------------------------------------
    # Stato e popolamento
    # ------------------------------------------------------------------
    def _refresh(self, select_id: str = '') -> None:
        previous_category = self.category_filter.currentData()
        items = list_superpowers(self.workspace)
        self._items = {item.superpower_id: item for item in items}
        self._ordered_ids = [item.superpower_id for item in items]

        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem(_('Tutte le categorie'), '')
        for category in sorted({item.category for item in items}, key=str.casefold):
            self.category_filter.addItem(category, category)
        index = self.category_filter.findData(previous_category)
        self.category_filter.setCurrentIndex(index if index >= 0 else 0)
        self.category_filter.blockSignals(False)

        self.list_widget.clear()
        for item in items:
            row = QListWidgetItem()
            row.setData(Qt.UserRole, item)
            widget = self._build_row_widget(item)
            row.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(row)
            self.list_widget.setItemWidget(row, widget)
            if item.superpower_id == select_id:
                self.list_widget.scrollToItem(row)

        self._refresh_active_chips()
        self._apply_filters()

    def _build_row_widget(self, item: MarkdownSuperpower) -> QWidget:
        toggle = ToggleSwitch('')
        toggle.setChecked(item.superpower_id in self.selected_ids)
        toggle.toggled.connect(lambda checked, sid=item.superpower_id: self._set_active(sid, checked))

        row_widget = _SuperpowerRow(toggle)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.addWidget(toggle)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        title_label = QLabel(item.title)
        title_label.setStyleSheet('font-weight: 600;')
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        meta_label = QLabel(f"{item.category or _('Generale')} · {item.superpower_id}")
        meta_label.setProperty('class', 'muted')
        meta_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        description_label = QLabel(item.description or _('Profilo riutilizzabile per guidare la risposta dell’AI.'))
        description_label.setWordWrap(True)
        description_label.setProperty('class', 'muted')
        description_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        example_label = QLabel(_usage_example(item))
        example_label.setWordWrap(True)
        example_label.setProperty('class', 'muted')
        example_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        text_box.addWidget(title_label)
        text_box.addWidget(meta_label)
        text_box.addWidget(description_label)
        text_box.addWidget(example_label)
        row_layout.addLayout(text_box, 1)

        edit_button = IconButton('edit')
        edit_button.setToolTip(_('Modifica'))
        edit_button.clicked.connect(lambda _checked=False, sid=item.superpower_id: self._open_editor(sid))
        row_layout.addWidget(edit_button)
        return row_widget

    def _apply_filters(self) -> None:
        query = self.search.text().strip().casefold()
        category = self.category_filter.currentData() or ''
        for index in range(self.list_widget.count()):
            row = self.list_widget.item(index)
            item: MarkdownSuperpower = row.data(Qt.UserRole)
            haystack = f"{item.title} {item.superpower_id} {item.description} {item.category}".casefold()
            row.setHidden(bool((query and query not in haystack) or (category and item.category != category)))

    # ------------------------------------------------------------------
    # Attivazione con un click
    # ------------------------------------------------------------------
    def _set_active(self, superpower_id: str, checked: bool) -> None:
        if checked:
            self.selected_ids.add(superpower_id)
        else:
            self.selected_ids.discard(superpower_id)
        self._refresh_active_chips()

    def _refresh_active_chips(self) -> None:
        while self._active_chips_layout.count():
            taken = self._active_chips_layout.takeAt(0)
            widget = taken.widget() if taken else None
            if widget is not None:
                widget.deleteLater()
        active_ids = [sid for sid in self._ordered_ids if sid in self.selected_ids]
        has_active = bool(active_ids)
        self.active_label.setVisible(has_active)
        self.active_chips.setVisible(has_active)
        for superpower_id in active_ids:
            item = self._items.get(superpower_id)
            if item is None:
                continue
            chip = _chip_button(item.title, lambda _checked=False, sid=superpower_id: self._deactivate(sid))
            self._active_chips_layout.addWidget(chip)

    def _deactivate(self, superpower_id: str) -> None:
        self.selected_ids.discard(superpower_id)
        self._refresh()

    def selected_superpower_ids(self) -> list[str]:
        return [sid for sid in self._ordered_ids if sid in self.selected_ids]

    # ------------------------------------------------------------------
    # Editor: creazione, modifica, salvataggio, eliminazione
    # ------------------------------------------------------------------
    def _open_editor(self, superpower_id: str = '') -> None:
        self._editing_id = superpower_id
        item = self._items.get(superpower_id)
        if item is not None:
            self.identifier.setText(item.superpower_id)
            self.title.setText(item.title)
            self.description.setText(item.description)
            self.category.setText(item.category)
            self.includes.setText(', '.join(item.includes))
            self.markdown.setPlainText(item.instructions)
            self.delete_button.setEnabled(True)
            self.editor_title_label.setText(_('Modifica superpotere'))
        else:
            self.identifier.clear()
            self.title.clear()
            self.description.clear()
            self.category.setText(_('Generale'))
            self.includes.clear()
            self.markdown.clear()
            self.delete_button.setEnabled(False)
            self.editor_title_label.setText(_('Nuovo superpotere'))
        self.stack.setCurrentIndex(1)
        self.title.setFocus()

    def _close_editor(self) -> None:
        self.stack.setCurrentIndex(0)

    def _new(self) -> None:
        self._open_editor('')

    def _save(self) -> None:
        try:
            if self.workspace is None:
                raise ValueError(_('Apri prima un progetto per creare un superpotere.'))
            includes = tuple(x.strip() for x in self.includes.text().split(',') if x.strip())
            path = save_superpower(
                self.identifier.text(),
                self.title.text(),
                self.markdown.toPlainText(),
                workspace=self.workspace,
                description=self.description.text(),
                category=self.category.text(),
                includes=includes
            )
            self._refresh(path.stem)
            self._close_editor()
        except Exception as exc:
            QMessageBox.critical(self, _('Superpotere non valido'), str(exc))

    def _delete(self) -> None:
        item = self._items.get(self._editing_id)
        if item is None:
            return
        if QMessageBox.question(self, _('Elimina superpotere'), _('Eliminare “{name}”?').format(name=item.title)) != QMessageBox.Yes:
            return
        try:
            if self.workspace is None:
                raise ValueError(_('Apri prima un progetto per eliminare un superpotere.'))
            delete_superpower(item.superpower_id, workspace=self.workspace)
            self.selected_ids.discard(item.superpower_id)
            self._refresh()
            self._close_editor()
        except Exception as exc:
            QMessageBox.critical(self, _('Eliminazione non riuscita'), str(exc))
