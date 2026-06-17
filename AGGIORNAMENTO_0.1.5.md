# Aggiornamento 0.1.5 — scanner anti-blocco

Questa release corregge un blocco osservato su Windows durante la generazione del Super-Report.

## Correzioni

- traversal del filesystem riscritto con `os.scandir`;
- nessun symlink, junction o reparse point viene seguito;
- esclusioni case-insensitive per `.venv`, `__pycache__`, `node_modules` e directory tecniche;
- limiti espliciti di profondità, directory, file, dimensione e durata;
- albero troncato in sicurezza invece di bloccare indefinitamente;
- ricerca dei file candidati limitata nel tempo;
- log delle fasi del report in `LocalAIBridge/logs/report_generation.log`;
- diagnostica del report distingue errori AST e avvisi di scansione.

## Verifica

```text
python -m py_compile run.py
python -m compileall -q src tests run.py
PYTHONPATH=src pytest -q
29 passed
```
