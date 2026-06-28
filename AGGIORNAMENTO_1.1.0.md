# BridgAI 1.1.0

Release funzionale successiva alla 1.0.0, mantenuta retrocompatibile e focalizzata sull’estensione del flusso desktop/Web.

## Novità principali

- estensione browser per lo scambio controllato di report, download e aggiornamenti;
- missioni operative persistenti con policy di esecuzione, risultati e artefatti;
- configurazione dell’assistente AI con provider locali Gemma/LiteRT-LM e Ollama, oltre ai provider cloud;
- prompt globali e per progetto, esclusioni personalizzate e impostazioni equivalenti nella GUI desktop e nella Web UI;
- scelta indipendente del formato dei file richiesti e delle modifiche, con supporto ZIP, Markdown e operazioni testuali su file completi;
- selettore italiano/inglese, tema persistente e dettatura vocale nella Web UI;
- autenticazione a due fattori TOTP con QR, codici di recupero, protezione dal riuso e deroga opzionale per reti private;
- cronologia dei commit inclusa nei Super-Report e disponibile come skill interna.

## Miglioramenti

- interfaccia Web responsive ridisegnata per dispositivi mobili;
- icona ufficiale usata come favicon, icona PWA e marchio dell’header;
- controlli di accesso più chiari, compresa la visualizzazione protetta della password;
- scanner, regole ignore, selezione del contesto e diagnostica dei report più completi;
- interpretazione più precisa dei risultati dei test e migliore esclusione di ambienti, cache e backup;
- integrazione più robusta tra desktop, server Web ed estensione browser;
- Markdown e file di testo promossi a percorso principale per gli aggiornamenti testuali, mantenendo i flussi legacy.

## Sicurezza

- impostazioni Web protette da autenticazione, CSRF e conferme esplicite;
- sessioni temporanee, rate limiting e rilevamento sicuro del client dietro proxy;
- protezione dal replay dei codici TOTP;
- mantenimento dei limiti del workspace, del blocco dei percorsi sensibili e della revisione obbligatoria prima dell’applicazione.

## Compatibilità

- versione aggiornata a `1.1.0` in `pyproject.toml` e nel package Python;
- formato delle impostazioni esistenti preservato con valori predefiniti retrocompatibili;
- flusso predefinito ZIP → ZIP invariato;
- supporto SEARCH/REPLACE mantenuto internamente per compatibilità, anche se non più proposto come modalità principale;
- package ed entry point storici `local_ai_bridge` conservati.

## Verifica consigliata

```bash
python -m compileall -q src tests run.py
python -m pytest -q
python run.py --check-report .
```

È inoltre consigliata una verifica manuale della GUI desktop, della Web UI responsive, del login 2FA e del collegamento con l’estensione browser.
