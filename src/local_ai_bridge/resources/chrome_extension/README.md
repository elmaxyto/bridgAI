# BridgAI Browser Automation

1. In Chrome apri `chrome://extensions`.
2. Attiva **Modalità sviluppatore**.
3. Premi **Carica estensione non pacchettizzata** e seleziona questa cartella.
4. In BridgAI apri **Avanzato → Automazione browser**, abilita l’integrazione e copia il token.
5. Apri le opzioni dell’estensione, inserisci indirizzo e token, quindi premi **Salva e verifica**.
6. In BridgAI scegli come AI Web preferita **ChatGPT**, **Claude** o **Gemini**: la richiesta successiva verrà aperta sulla relativa applicazione Web. La scelta **Personalizzata** mantiene ChatGPT per retrocompatibilità.

L’estensione è opzionale. Disattivandola, BridgAI continua a usare il flusso manuale preesistente. Gli aggiornamenti non vengono mai applicati automaticamente.

I selettori delle applicazioni Web sono intenzionalmente isolati in `providers.js`: se un provider cambia il proprio DOM, aggiorna quel registro e verifica manualmente invio, allegato, lettura della risposta e download ZIP su ciascun sito.

## Verifica consigliata dopo ogni aggiornamento

- Ricarica l’estensione da `chrome://extensions` per aggiornare service worker e content script.
- Esegui una prova separata su ChatGPT, Claude e Gemini verificando: apertura della scheda corretta, invio del prompt, caricamento dello ZIP, acquisizione di `#scarica` e download dello ZIP finale.
- I collegamenti ZIP vengono accettati soltanto da host attendibili associati al provider che ha ricevuto la richiesta.
- Il content script è reiniettabile in modo idempotente, così il fallback del service worker non registra listener duplicati.

La verifica automatica del codice non sostituisce il collaudo reale nelle tre sessioni Web autenticate: i DOM delle applicazioni possono cambiare senza preavviso.

Quando una richiesta è destinata a Claude o Gemini, il service worker riattiva la scheda più recente del provider e porta in primo piano la relativa finestra. Dopo aver cambiato AI predefinita, genera una nuova richiesta: le richieste già accodate mantengono il provider con cui sono state create.
