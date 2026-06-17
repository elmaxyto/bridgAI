# Aggiornamento 0.1.3

Correzione mirata della generazione del Super-Report su Windows/PySide6.

## Correzioni

- i worker in background vengono conservati fino all'emissione del risultato;
- il pulsante del report mostra chiaramente lo stato di elaborazione e viene riattivato al termine;
- gli errori in background vengono salvati in `LocalAIBridge/logs/errors.log` nella directory dati utente;
- il messaggio di errore mostra il percorso del log;
- corretti i `SyntaxWarning` delle stringhe Windows in `run.py`;
- aggiunta la diagnostica da terminale `run.py --check-report <workspace>`;
- versione aggiornata a 0.1.3.

## Diagnostica manuale

Da terminale, nella cartella del programma:

```cmd
.venv\Scripts\python.exe run.py --check-report "."
```

Per salvare il risultato:

```cmd
.venv\Scripts\python.exe run.py --check-report "." --output REPORT_DIAGNOSTIC.md
```
