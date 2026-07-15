from __future__ import annotations

import pytest
from pathlib import Path
from local_ai_bridge.core.superpower_models import MarkdownSuperpower, SuperpowerError, load_superpower, parse_superpower_front_matter
from local_ai_bridge.core.superpowers import (
    superpowers_directory,
    list_superpowers,
    save_superpower,
    delete_superpower,
    resolve_superpowers,
    clear_superpower_cache,
    rebuild_superpower_index,
)

@pytest.fixture
def isolated_app_data(tmp_path: Path, monkeypatch):
    """Isola la directory dei dati dell'app usando una cartella temporanea."""
    monkeypatch.setattr("local_ai_bridge.core.superpowers.app_data_dir", lambda: tmp_path)
    clear_superpower_cache()
    yield tmp_path
    clear_superpower_cache()

def test_save_list_and_resolve_app_superpower(isolated_app_data):
    """Verifica il ciclo di vita base di un superpotere isolato."""
    path = save_superpower(
        superpower_id="test-puro",
        title="Superpotere di Test",
        instructions="Fai qualcosa di fantastico.",
        description="Una descrizione",
        category="Sviluppo"
    )
    assert path.exists()
    
    available = list_superpowers()
    assert any(item.superpower_id == "test-puro" for item in available)

def test_superpower_backward_compatibility(tmp_path: Path):
    """Verifica che i vecchi file senza il metadato 'includes' vengano caricati con un valore vuoto."""
    legacy_content = (
        "---\n"
        "id: vecchio-stile\n"
        "title: Vecchio Prompt\n"
        "category: Legacy\n"
        "---\n\n"
        "Istruzioni vecchio stile."
    )
    test_file = tmp_path / "vecchio-stile.md"
    test_file.write_text(legacy_content, encoding="utf-8")
    
    item = load_superpower(test_file, scope="app")
    assert item.superpower_id == "vecchio-stile"
    assert item.includes == ()  # Inferred di default

def test_recursive_resolution_and_chaining(isolated_app_data):
    """Verifica che resolve_superpowers risolva correttamente le inclusioni multiple concatenate."""
    # 1. Base atomica
    save_superpower(
        superpower_id="solo-json",
        title="Formatta in JSON",
        instructions="Rispondi esclusivamente in formato JSON valido.",
        category="Formato"
    )
    # 2. Strato intermedio che include la base
    save_superpower(
        superpower_id="validatore-api",
        title="Validatore API",
        instructions="Controlla i vincoli dello schema OpenAPI.",
        category="Analisi",
        includes=("solo-json",)
    )
    # 3. Macro-superpotere che include lo strato intermedio
    save_superpower(
        superpower_id="super-architetto",
        title="Super Architetto",
        instructions="Disegna l'architettura dei componenti.",
        category="Core",
        includes=("validatore-api",)
    )

    selected, missing = resolve_superpowers(isolated_app_data, "@superpower:super-architetto")
    assert not missing
    
    # Devono essere stati estratti tutti e 3 i superpoteri nell'albero delle dipendenze
    ids_risolti = [item.superpower_id for item in selected]
    assert "super-architetto" in ids_risolti
    assert "validatore-api" in ids_risolti
    assert "solo-json" in ids_risolti

def test_recursive_resolution_circular_protection(isolated_app_data):
    """Verifica che la risoluzione ricorsiva non entri in loop infinito in presenza di dipendenze cicliche."""
    # A include B
    save_superpower(
        superpower_id="ciclo-a",
        title="Ciclo A",
        instructions="Istruzioni A",
        includes=("ciclo-b",)
    )
    # B include A
    save_superpower(
        superpower_id="ciclo-b",
        title="Ciclo B",
        instructions="Istruzioni B",
        includes=("ciclo-a",)
    )

    # L'esecuzione non deve sollevare RecursionError o andare in loop infinito
    selected, missing = resolve_superpowers(isolated_app_data, "@superpower:ciclo-a")
    assert not missing
    
    ids_risolti = {item.superpower_id for item in selected}
    assert ids_risolti == {"ciclo-a", "ciclo-b"}

def test_save_rejects_unsafe_identifier(isolated_app_data):
    with pytest.raises(SuperpowerError):
        save_superpower(superpower_id="ID_NON_VALIDO!", title="Test", instructions="Test")

def test_delete_superpower_removes_file_and_updates_index(isolated_app_data):
    path = save_superpower(superpower_id="da-cancellare", title="Temporaneo", instructions="Rimuovimi")
    assert path.exists()
    
    delete_superpower("da-cancellare")
    assert not path.exists()
    
    available = list_superpowers()
    assert not any(item.superpower_id == "da-cancellare" for item in available)
