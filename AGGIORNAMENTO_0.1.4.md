# Aggiornamento 0.1.4 — affidabilità del Super-Report

Correzione mirata del Super-Report dopo la verifica reale su Windows.

- ricostruito l'albero con directory e percorsi relativi espliciti;
- esclusi `AI_SUPER_REPORT*.md`, `REPORT_DIAGNOSTIC*.md` e report equivalenti da albero, riepiloghi, file caldi e candidati;
- aggiunta la versione del generatore direttamente nell'intestazione del report;
- aggiunta la versione del progetto rilevata da `pyproject.toml` o `package.json`;
- rilevamento stack ampliato con GUI, dipendenze, test, build backend e requisito Python;
- diagnostica distinta tra parsing AST, import runtime, test e GUI;
- README escluso dalle note locali prioritarie;
- titolo della finestra allineato alla versione centralizzata;
- test di regressione per due report consecutivi senza auto-inclusione.

Dopo l'applicazione chiudere completamente il programma e riaprirlo.
Il nuovo report deve contenere:

```text
Generatore report: Local AI Bridge 0.1.4
```
