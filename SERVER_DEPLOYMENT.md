# BridgAI Web su server

Questa modalità esegue BridgAI sul server e permette di usare dal telefono il flusso guidato: gestione progetti, Super-Report, `#scarica`, upload ZIP, patch SEARCH/REPLACE, diff, applicazione, rollback, test e consultazione Git.

## Root dei progetti

BridgAI usa una cartella dedicata come **root progetti**. Ogni sua sottocartella diretta, non nascosta e non simbolica viene proposta come progetto apribile.

```text
/srv/bridgai/projects/
├── progetto-a/
├── progetto-b/
└── progetto-c/
```

Le cartelle annidate non diventano progetti separati. Per esempio, `/srv/bridgai/projects/progetto-a/src` non può essere selezionata come workspace.

Dal pannello mobile puoi:

- aggiornare l’elenco delle cartelle presenti;
- aprire un progetto;
- creare una nuova cartella progetto, con inizializzazione Git opzionale;
- clonare un repository HTTPS o SSH direttamente nella root;
- modificare e salvare la root quando non è stata bloccata dalla configurazione di avvio.

La root salvata viene riutilizzata ai successivi avvii. Se passi `--workspace-root`, `--workspace` oppure `BRIDGAI_WORKSPACE_ROOT`, il valore viene considerato un confine amministrativo e non è modificabile dalla Web UI durante quell’esecuzione.

## Avvio minimo protetto

Crea un ambiente headless. Questo profilo non installa PySide6, microfono o dipendenze desktop:

```bash
python -m venv .venv-server
.venv-server/bin/python -m pip install --upgrade pip
.venv-server/bin/python -m pip install -r requirements-server.txt
```

Genera un token lungo e conservalo fuori dai workspace:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
export BRIDGAI_WEB_TOKEN='INCOLLA_QUI_IL_TOKEN'
PYTHONPATH=src .venv-server/bin/python -m local_ai_bridge.web \
  --host 0.0.0.0 \
  --port 8765 \
  --workspace-root /srv/bridgai/projects \
  --no-browser
```

La root può essere fornita anche tramite ambiente:

```bash
export BRIDGAI_WEB_TOKEN='INCOLLA_QUI_IL_TOKEN'
export BRIDGAI_WORKSPACE_ROOT='/srv/bridgai/projects'
PYTHONPATH=src .venv-server/bin/python -m local_ai_bridge.web \
  --host 0.0.0.0 \
  --port 8765 \
  --no-browser
```

In alternativa limita il server a un solo progetto:

```bash
export BRIDGAI_WEB_TOKEN='INCOLLA_QUI_IL_TOKEN'
PYTHONPATH=src .venv-server/bin/python -m local_ai_bridge.web \
  --host 0.0.0.0 \
  --port 8765 \
  --workspace /srv/bridgai/projects/progetto-a \
  --no-browser
```

Il token non va passato nella riga di comando, perché potrebbe comparire nell'elenco dei processi. Il nome della variabile può essere cambiato con `--token-env`.

### Rendere la root modificabile dal pannello

Un server remoto deve avere già una root valida per poter partire in sicurezza. Al primo avvio puoi quindi passare `--workspace-root`: BridgAI la salva nelle impostazioni.

Negli avvii successivi puoi omettere `--workspace-root`. La root salvata verrà caricata automaticamente e diventerà modificabile dal pannello, dopo una conferma esplicita.

Per modificare la root prima del primo accesso remoto puoi anche avviare temporaneamente il pannello solo su localhost, salvarla e poi riavviare in modalità remota.

## Nuovo progetto

Il pannello richiede un nome di cartella portabile tra Windows, Linux e macOS. Sono bloccati:

- nomi vuoti, nascosti, relativi o riservati;
- separatori di percorso;
- caratteri non validi;
- file o cartelle già esistenti.

Se selezioni **Inizializza repository Git**, viene eseguito soltanto `git init` nella nuova cartella. Non vengono creati commit, remote o push automatici.

## Clona da Git

Sono accettati:

```text
https://github.com/owner/repository.git
ssh://git@example.com/owner/repository.git
git@example.com:owner/repository.git
```

Sono rifiutati percorsi locali, `file://`, protocolli helper come `ext::`, query, frammenti e URL contenenti password o token.

Per repository privati configura prima sul server uno dei seguenti meccanismi:

- chiave SSH e `known_hosts` dell’utente che esegue BridgAI;
- credential helper Git;
- autenticazione già disponibile nell’ambiente del servizio.

Non inserire token nel campo URL. La clonazione ha un timeout e una cartella parziale viene rimossa se Git fallisce.

## Rete e HTTPS

Il server HTTP integrato non offre TLS. Non pubblicare direttamente la porta 8765 su Internet. Usa una delle seguenti barriere:

- rete privata Tailscale o WireGuard;
- reverse proxy Caddy/Nginx con HTTPS e ulteriore autenticazione;
- tunnel autenticato che inoltri soltanto verso `127.0.0.1:8765`.

Quando usi un reverse proxy sullo stesso host, puoi lasciare BridgAI in ascolto su `127.0.0.1` e impostare comunque `BRIDGAI_WEB_TOKEN`.

## Confini di sicurezza

- Solo le directory di primo livello sotto la root, oppure il singolo workspace fisso, sono selezionabili.
- I link simbolici e le cartelle nascoste non vengono proposti come workspace.
- Creazione e clonazione possono scrivere soltanto una nuova cartella diretta sotto la root.
- La modifica della root richiede token, CSRF e conferma esplicita.
- Una root passata all’avvio è bloccata nella Web UI.
- Gli ZIP caricati vengono analizzati prima dell'applicazione.
- Apply e rollback richiedono conferme separate.
- I piani analizzati scadono e vengono invalidati quando cambia workspace o root.
- I link di download sono casuali e temporanei.
- Nessun endpoint accetta comandi shell arbitrari.

Esegui il servizio con un utente Linux dedicato e senza privilegi amministrativi. Concedigli accesso solo alla directory dei progetti e alla propria directory dati.

## Uso dal telefono

1. Apri il pannello HTTPS o l'indirizzo privato VPN.
2. Inserisci il token; resta nella sola sessione del browser.
3. Seleziona un progetto esistente, creane uno oppure clona un repository.
4. Genera e copia il Super-Report in ChatGPT.
5. Incolla la riga `#scarica` e scarica lo ZIP sul telefono.
6. Allega lo ZIP a ChatGPT.
7. Carica nel pannello lo ZIP restituito oppure incolla la patch SEARCH/REPLACE.
8. Controlla il diff, applica, esegui i test e verifica Git.
