from pathlib import Path


def _source(relative: str) -> str:
    return (Path(__file__).parents[1] / relative).read_text(encoding='utf-8')


def test_desktop_simple_mode_exposes_superpower_selector_and_editor() -> None:
    workflow = _source('src/local_ai_bridge/ui/tabs/workflow.py')
    actions = _source('src/local_ai_bridge/ui/workflow_actions.py')
    dialog = _source('src/local_ai_bridge/ui/superpower_dialog.py')
    assert "_button(_('Richiama superpoteri')" in workflow
    assert 'setIcon(_superpower_icon())' in workflow
    assert 'task_header_row = QHBoxLayout()' in workflow
    header_block = workflow.split('task_header_row = QHBoxLayout()', 1)[1].split('window.task_edit = QPlainTextEdit()', 1)[0]
    assert "_step_header(" in header_block
    assert 'window.superpower_summary' in header_block
    assert 'window.superpower_button' in header_block
    assert 'task_layout.addLayout(task_header_row)' in workflow
    assert 'superpower_row = QHBoxLayout()' not in workflow
    assert '⚡ Richiama superpoteri' not in workflow
    assert 'def choose_superpowers' in actions
    assert 'class SuperpowerDialog' in dialog
    assert 'save_superpower' in dialog
    assert 'delete_superpower' in dialog


def test_web_ui_exposes_superpower_crud_and_selection() -> None:
    page = _source('src/local_ai_bridge/web/page.py')
    assets = _source('src/local_ai_bridge/web/page_assets.py')
    actions = _source('src/local_ai_bridge/web/project_actions.py')
    assert 'superpowerModal' in page
    assert '<svg class="button-icon"' in page
    assert '⚡ Richiama superpoteri' not in page
    assert '/api/superpowers/list' in actions
    assert '/api/superpowers/save' in actions
    assert '/api/superpowers/delete' in actions
    assert 'applySuperpowerSelection' in assets
    assert '@superpower:${id}' in assets
    assert 'simple-request-toolbar' in page
    toolbar = page.split('<div class="simple-request-toolbar">', 1)[1].split('<div id="reportResult"', 1)[0]
    assert 'superpower-actions' in toolbar
    assert 'request-actions' in toolbar
    assert 'provider-actions' in toolbar
    assert toolbar.index('superpower-actions') < toolbar.index('Prepara richiesta per l’AI') < toolbar.index('Continua su ChatGPT')
    assert '.simple-request-toolbar{display:grid' in assets


def test_superpower_dialog_uses_pyside6_dialog_code() -> None:
    actions = _source('src/local_ai_bridge/ui/workflow_actions.py')
    assert 'QDialog.DialogCode.Accepted' in actions
    assert 'dialog.Accepted' not in actions


def test_desktop_and_web_expose_project_notes_hub() -> None:
    layouts = _source('src/local_ai_bridge/ui/layouts.py')
    desktop = _source('src/local_ai_bridge/ui/project_notes.py')
    page = _source('src/local_ai_bridge/web/page.py')
    assets = _source('src/local_ai_bridge/web/page_assets.py')
    actions = _source('src/local_ai_bridge/web/project_actions.py')
    assert 'build_project_notes_tab' in layouts
    assert 'upsert_project_note' in desktop
    assert 'projectNotesModal' in page
    assert 'openProjectNotes' in assets
    assert '/api/project-notes/save' in actions


def test_superpower_selectors_expose_search_and_category_filters() -> None:
    dialog = _source('src/local_ai_bridge/ui/superpower_dialog.py')
    page = _source('src/local_ai_bridge/web/page.py')
    assets = _source('src/local_ai_bridge/web/page_assets.py')
    assert 'self.search' in dialog
    assert 'self.category_filter' in dialog
    assert 'def _apply_filters' in dialog
    assert 'superpowerSearch' in page
    assert 'superpowerCategoryFilter' in page
    assert 'refreshSuperpowerCategories' in assets
    assert "item.category||'Generale'" in assets


def test_superpower_selectors_show_usage_preview_and_examples() -> None:
    dialog = _source('src/local_ai_bridge/ui/superpower_dialog.py')
    page = _source('src/local_ai_bridge/web/page.py')
    assets = _source('src/local_ai_bridge/web/page_assets.py')
    assert 'def _usage_example' in dialog
    assert 'description_label = QLabel' in dialog
    assert 'example_label = QLabel(_usage_example(item))' in dialog
    assert 'Esempio: @superpower:{id}' in dialog
    assert 'superpowerExample(item)' in assets
    assert "example.className='superpower-example'" in assets
    assert "text.append(title,metadata,description,example)" in assets
    assert 'Cerca per nome, ID o descrizione…' in page


def test_superpower_editors_use_one_app_wide_library() -> None:
    desktop = _source("src/local_ai_bridge/ui/superpower_dialog.py")
    web_page = _source("src/local_ai_bridge/web/page.py")
    web_actions = _source("src/local_ai_bridge/web/project_actions.py")
    assert "Globale" not in desktop
    assert "superpowerScope" not in web_page
    assert "_superpower_scope_workspace" not in web_actions
    superpower_routes = web_actions[web_actions.index('if path == "/api/superpowers/list"'):web_actions.index('if path == "/api/workspace"')]
    assert "state.require_workspace()" not in superpower_routes
    assert "list_superpowers()" in superpower_routes
    assert "La libreria è condivisa tra tutti i progetti" in desktop
    assert "La libreria è condivisa tra tutti i progetti" in web_page



def test_web_superpower_modal_opens_before_loading_and_keeps_errors_visible() -> None:
    assets = _source("src/local_ai_bridge/web/page_assets.py")
    function = assets.split("async function openSuperpowers()", 1)[1].split("function closeSuperpowers()", 1)[0]
    assert "modal.hidden=false" in function
    assert function.index("modal.hidden=false") < function.index("apiGet('/api/superpowers/list'")
    assert "'superpowerResult'" in function


def test_desktop_dictation_uses_vector_microphone_icon() -> None:
    workflow = _source('src/local_ai_bridge/ui/tabs/workflow.py')
    dialog = _source('src/local_ai_bridge/ui/speech_dialog.py')
    widgets = _source('src/local_ai_bridge/ui/widgets.py')
    assert "IconButton('microphone')" in workflow
    assert 'IconButton("microphone")' in dialog
    assert "KINDS = ('add', 'back', 'edit', 'microphone')" in widgets
    assert 'elif self._kind == \'microphone\':' in widgets
    assert 'Lucide Mic geometry' in widgets
    assert 'M19 10v2a7 7 0 0 1-14 0v-2' in widgets
    assert "_button('🎙'" not in workflow
    assert 'QPushButton("🎙")' not in dialog
