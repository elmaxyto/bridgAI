# BridgAI 1.0.0

Prima release stabile del progetto con il nome pubblico **BridgAI**.

## Un progetto sviluppato con il proprio flusso

BridgAI è stato sviluppato in modo iterativo usando BridgAI stesso.

La prima versione 0.1 ha fornito il flusso di generazione del report, esportazione controllata, revisione e applicazione delle modifiche. Quel flusso è stato poi usato per implementare progressivamente le versioni successive fino alla 1.0.0, comprese le più recenti funzioni Git e di gestione dei messaggi di commit.

Questo rappresenta una validazione end-to-end concreta del caso d’uso principale dell’applicazione, pur restando distinta dai test automatici ripetibili.

## Funzioni principali

- interfaccia desktop PySide6 e interfaccia web locale;
- generazione strutturata del Super-Report;
- esportazione controllata dei soli file richiesti tramite `#scarica`;
- analisi di ZIP, patch SEARCH/REPLACE e file completi;
- anteprima unificata delle differenze;
- applicazione transazionale con backup persistenti;
- cronologia delle sessioni, test post-applicazione e rollback esplicito;
- rilevamento ed esecuzione dei controlli del progetto;
- strumenti Git locali e integrazione opzionale con GitHub CLI;
- supporto a `commit-message.md` come metadato degli ZIP generati dall’AI;
- generazione di bozze di commit dalle modifiche Git reali e dalle note delle sessioni;
- staging e commit soltanto dopo revisione e conferma esplicita;
- flusso opzionale tramite Google Drive;
- interfaccia italiana e inglese;
- launcher per Windows, Linux e macOS.

## Sicurezza e controllo

- il programma locale resta l’unica autorità sul filesystem;
- browser e AI Web non ricevono accesso diretto al workspace;
- percorsi sensibili, traversal ZIP e contenuti non sicuri vengono bloccati;
- nessuna modifica viene scritta durante la sola analisi;
- `commit-message.md` viene trattato come metadato e non come file del progetto;
- staging, commit e push non avvengono senza un’azione esplicita dell’utente;
- rollback e ripristino rimangono operazioni esplicite.

## Compatibilità

- nome pubblico aggiornato da Local AI Bridge a BridgAI;
- versione uniformata a `1.0.0` in package, interfaccia, report e metadati;
- package Python `local_ai_bridge`, entry point e directory dati storiche mantenuti;
- launcher storici conservati per non interrompere installazioni e configurazioni precedenti.

## Verifica consigliata

```cmd
.venv\Scripts\python.exe -m compileall -q src tests run.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe run.py --check-report .
```

La verifica manuale dell’interfaccia resta consigliata almeno sulla piattaforma usata per la pubblicazione.
