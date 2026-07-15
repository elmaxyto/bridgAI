# BridgAI project history

Cronostoria permanente delle modifiche applicate tramite BridgAI.

## 2026-06-20 21:41:32 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T194132Z-3dfe24b1`
**Messaggio:** feat(scanner): rende la scansione robusta e consapevole di Git

**Dettagli:**
- separa policy di esclusione, integrazione Git e sintesi dei file
- esclude dipendenze, ambienti virtuali, cache, output di build, file temporanei e binari compilati
- usa il manifest Git per rispettare .gitignore e regole annidate quando disponibile
- conserva i sorgenti prioritari e i risultati parziali quando vengono raggiunti i limiti
- compatta i lockfile e limita il rilevamento dei monoliti ai file di codice
- aggiunge override espliciti con ! in .bridgai/ignore
- aggiunge test di regressione multi-ecosistema e sul caso roadtrip

**File modificati:**
- `src/local_ai_bridge/services/project_scanner.py`
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/services/project_scanner_policy.py`
- `src/local_ai_bridge/services/project_scanner_git.py`
- `src/local_ai_bridge/services/project_scanner_summary.py`
- `tests/test_reporting_export.py`

**Test salvati:** 0 ok, 1 problemi
## 2026-06-20 21:55:23 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T195523Z-504f1bfd`
**Messaggio:** fix(testing): distingue errori del codice da problemi ambientali

**Dettagli:**
- esegue i controlli Python con cache temporanea esterna al workspace
- impedisce a Pytest di creare la propria cache nel progetto
- classifica permessi, cache bloccate e timeout come verifiche incomplete
- mantiene il rosso per gli errori strutturali realmente confermati
- aggiunge test di regressione per WinError 5 e isolamento delle cache

**File modificati:**
- `src/local_ai_bridge/services/testing.py`
- `tests/test_testing.py`

**Test salvati:** 0 ok, 1 problemi
## 2026-06-20 22:12:15 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T201215Z-33ff4258`
**Messaggio:** fix(scanner): usa il filesystem quando il manifest Git scade

**Dettagli:**
- riserva un budget indipendente al fallback sul filesystem filtrato
- filtra dipendenze e cache prima degli accessi al filesystem nei manifest Git
- riutilizza la classificazione delle directory per ridurre gli accessi su SSHFS
- mantiene la ricerca dei file candidati anche quando Git non risponde
- esclude keystore, chiavi e configurazioni Android locali dal report
- aggiunge test di regressione per timeout Git, fallback e percorsi sensibili

**File modificati:**
- `src/local_ai_bridge/services/project_scanner.py`
- `src/local_ai_bridge/services/project_scanner_git.py`
- `src/local_ai_bridge/services/project_scanner_policy.py`
- `tests/test_reporting_export.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-20 22:25:54 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T202554Z-62a90adb`
**Messaggio:** feat(report): riduce il rumore mantenendo un contesto bilanciato

**Dettagli:**
- limita l'espansione del contesto a 240 file selezionati in modo bilanciato
- privilegia entry point, configurazioni, file grandi e percorsi collegati al task
- esclude scratch, bozze e output diagnostici generati con override tramite .bridgai/ignore
- compatta nell'albero i sottoalberi composti soltanto da asset multimediali
- nasconde dal dettaglio Git le modifiche in dipendenze, cache e percorsi tecnici
- distingue validazione AST Python da estrazione euristica JavaScript/TypeScript
- aggiunge test di regressione per selezione, filtri, asset, Git e diagnostica

**File modificati:**
- `src/local_ai_bridge/services/project_scanner.py`
- `src/local_ai_bridge/services/project_scanner_policy.py`
- `src/local_ai_bridge/services/project_scanner_summary.py`
- `src/local_ai_bridge/services/project_scanner_git.py`
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/services/reporting_git.py`
- `tests/test_reporting_export.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-20 22:37:09 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T203709Z-ef07489c`
**Messaggio:** feat(ui): add recent projects menu

**Dettagli:**
- persist up to 10 recently opened project paths
- add a toolbar dropdown to reopen or clear recent projects
- mark the current project and unavailable paths in the menu
- add Italian and English labels plus regression tests

**File modificati:**
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/recent_projects.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-20 22:49:08 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T204908Z-7d0b3bb4`
**Messaggio:** feat(report): rende il contesto adattivo e privo di duplicati

**Dettagli:**
- deduplica stabilmente i file prima della selezione e della sintesi
- usa limiti adattivi per report generali, task specifici e analisi complete
- mantiene tutti i file indicizzati disponibili tramite #scarica
- migliora le sintesi JavaScript, TypeScript, Markdown, HTML, XML e CSS
- elimina boilerplate e intestazioni di licenza dai riepiloghi generici
- classifica correttamente dipendenze, cache e percorsi sensibili
- evita duplicati anche nel manifest Git
- aggiunge test di regressione dedicati alla qualità del contesto

**File modificati:**
- `src/local_ai_bridge/services/project_scanner.py`
- `src/local_ai_bridge/services/project_scanner_git.py`
- `src/local_ai_bridge/services/project_scanner_helpers.py`
- `src/local_ai_bridge/services/project_scanner_policy.py`
- `src/local_ai_bridge/services/project_scanner_summary.py`
- `src/local_ai_bridge/services/reporting.py`
- `tests/test_reporting_export.py`
- `tests/test_reporting_context_quality.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-20 23:22:27 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T212227Z-1783e58d`
**Messaggio:** feat(extension): aggiungi automazione browser opzionale

**Dettagli:**
- aggiunge un’estensione Chrome Manifest V3 inclusa nelle risorse del progetto
- introduce impostazioni avanzate disattivate per default e un token locale dedicato
- automatizza invio del report, acquisizione risposta, gestione #scarica e ricezione ZIP
- mantiene invariato il flusso manuale e non applica mai automaticamente gli aggiornamenti
- aggiunge API localhost isolate, stato persistente e test mirati

**File modificati:**
- `pyproject.toml`
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/resources/chrome_extension/README.md`
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/resources/chrome_extension/options.html`
- `src/local_ai_bridge/resources/chrome_extension/options.js`
- `src/local_ai_bridge/resources/chrome_extension/popup.html`
- `src/local_ai_bridge/resources/chrome_extension/popup.js`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/services/browser_extension.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/tabs/advanced.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `src/local_ai_bridge/web/extension_api.py`
- `src/local_ai_bridge/web/launcher.py`
- `src/local_ai_bridge/web/server.py`
- `tests/test_browser_extension.py`
- `tests/test_browser_extension_api.py`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`
- `tests/test_web_launcher.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-21 00:49:36 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T224936Z-7d561a47`
**Messaggio:** fix(extension): delegate local bridge requests to service worker

**Dettagli:**
- verifica la connessione dalla background extension invece che dalla pagina opzioni
- scarica il contesto #scarica nel service worker e lo passa al content script
- aggiunge test di regressione sulle richieste locali dell'estensione
- aggiorna la versione dell'estensione Chrome a 0.1.1

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/resources/chrome_extension/options.js`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-21 01:22:19 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260620T232219Z-63128089`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/web/launcher.py.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-24 13:20:15 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260624T112015Z-6a114ea4`
**Messaggio:** feat(ui): introduce le modalità Sviluppo e Operativa

**Dettagli:**
- aggiunge la preferenza persistente con compatibilità per le configurazioni precedenti
- propone la scelta della modalità al primo avvio e consente il cambio immediato dalle Impostazioni
- introduce una schermata operativa informativa separata senza modificare i workspace
- aggiunge traduzioni italiane e inglesi e test di regressione mirati
- aggiorna il piano con stato, decisioni, verifiche e rischi residui

**File modificati:**
- `PIANO_MODALITA_OPERATIVA.md`
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/ui/application_modes.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-24 13:33:16 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260624T113316Z-ff4b42c9`
**Messaggio:** feat(operations): aggiunge il modello persistente delle missioni

**Dettagli:**
- introduce missioni operative separate dalle sessioni di modifica software
- salva input autorizzati, output, stati, cronologia e cartelle artefatti gestite
- estende la schermata operativa con creazione, consultazione e archiviazione
- aggiunge traduzioni italiane e inglesi e test mirati della Fase 2

**File modificati:**
- `src/local_ai_bridge/services/operational_missions.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_operational_missions.py`
- `tests/test_settings_layout.py`
- `PIANO_MODALITA_OPERATIVA.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-24 13:45:32 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260624T114532Z-69676e54`
**Messaggio:** feat(operations): aggiungi l’esecutore controllato delle missioni

**Dettagli:**
- introduce una procedura nativa per creare l’inventario JSON degli input autorizzati
- valida separazione e sicurezza di input, output e artefatti senza modificare gli originali
- registra stati, log, errori, risultati e artefatti di ogni esecuzione
- integra avvio e consultazione dell’esecuzione nella Modalità Operativa
- aggiunge traduzioni, test di regressione e aggiornamento della roadmap

**File modificati:**
- `src/local_ai_bridge/services/operational_execution.py`
- `src/local_ai_bridge/services/operational_execution_policy.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_operational_execution.py`
- `tests/test_settings_layout.py`
- `PIANO_MODALITA_OPERATIVA.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-24 13:58:04 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260624T115804Z-c77d6321`
**Messaggio:** feat(operations): completa il primo flusso CSV

**Dettagli:**
- aggiunge la procedura locale per unire e riepilogare file CSV autorizzati
- salva la procedura scelta mantenendo compatibilità con le missioni precedenti
- mostra piano, autorizzazioni, risultati e riepilogo nella Modalità Operativa
- protegge originali e output esistenti e rimuove risultati parziali in caso di errore
- aggiunge traduzioni e test mirati del flusso CSV

**File modificati:**
- `PIANO_MODALITA_OPERATIVA.md`
- `src/local_ai_bridge/services/operational_missions.py`
- `src/local_ai_bridge/services/operational_execution.py`
- `src/local_ai_bridge/services/operational_csv.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/operations_presenters.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_operational_missions.py`
- `tests/test_operational_csv.py`
- `tests/test_operational_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-24 15:03:34 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260624T130334Z-a71a6347`
**Messaggio:** feat(operations): introduce missioni operative tramite AI Web

**Dettagli:**
- semplifica la Modalità Operativa con categorie, richiesta, input autorizzati, output e provider Web
- crea pacchetti missione ZIP e importa risultati verificati senza modificare o sovrascrivere gli originali
- estende il canale Chrome per allegare il pacchetto iniziale e distinguere risultati operativi dagli aggiornamenti di codice
- mantiene inventario e unione CSV come strumenti locali avanzati e prepara il passaggio guidato alla Modalità Sviluppo
- aggiorna piano, traduzioni e test mirati del nuovo flusso

**File modificati:**
- `PIANO_MODALITA_OPERATIVA.md`
- `src/local_ai_bridge/services/operational_catalog.py`
- `src/local_ai_bridge/services/operational_missions.py`
- `src/local_ai_bridge/services/operational_web.py`
- `src/local_ai_bridge/services/operational_results.py`
- `src/local_ai_bridge/services/browser_extension.py`
- `src/local_ai_bridge/web/extension_operational.py`
- `src/local_ai_bridge/web/extension_api.py`
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/download_tracking.js`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/ui/operations_presenters.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/operations_web_actions.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `tests/test_operational_web.py`
- `tests/test_operational_missions.py`
- `tests/test_operational_ui.py`
- `tests/test_browser_extension.py`
- `tests/test_browser_extension_api.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-24 15:10:09 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260624T131009Z-5cc33808`
**Messaggio:** fix(ui): allinea il tema della modalità operativa

**Dettagli:**
- applica la palette condivisa agli sfondi della pagina e dell’area scorrevole operativa
- uniforma QTextEdit, QListWidget e la selezione degli elementi ai controlli della modalità sviluppo
- aggiunge un test di regressione per i temi chiaro e scuro

**File modificati:**
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/theme.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-24 15:24:26 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260624T132426Z-4db1e0e3`
**Messaggio:** feat(operations): semplifica il flusso operativo guidato

**Dettagli:**
- ridisegna la Modalità Operativa in quattro passaggi visivi con stato e piano più leggibili
- sostituisce i gruppi selezionabili a casella con slider per cronologia e strumenti locali
- abilita l’invio solo quando richiesta, input e destinazione sono completi
- apre automaticamente la cronologia quando arrivano risultati verificati
- aggiorna tema, traduzioni italiane e inglesi e test di regressione

**File modificati:**
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/tabs/operations_secondary.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/operations_web_actions.py`
- `src/local_ai_bridge/ui/theme.py`
- `tests/test_operational_ui.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-28 14:41:28 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260628T124128Z-338b6aa2`
**Messaggio:** feat(settings): aggiunge la preferenza per l’AI Web

**Dettagli:**
- aggiunge i preset persistenti ChatGPT, Claude, Gemini e Personalizzato
- sincronizza i formati ZIP/Markdown e filtra i provider nel flusso semplice
- espone la preferenza anche nella Web UI e aggiunge test di regressione

**File modificati:**
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/ui/preferred_web_ai_actions.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/web/power_user_settings.py`
- `src/local_ai_bridge/web/server.py`
- `tests/test_reporting_export.py`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-28 14:55:58 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260628T125558Z-9db69110`
**Messaggio:** feat(onboarding): configura modalità e AI Web al primo avvio

**Dettagli:**
- sostituisce la selezione iniziale della sola modalità con un onboarding unico
- aggiunge ChatGPT, Claude, Gemini e Personalizzato alla scelta iniziale
- applica e salva i formati di scambio associati al provider scelto
- aggiorna traduzioni italiane e inglesi e test di regressione del layout

**File modificati:**
- `src/local_ai_bridge/ui/application_modes.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-28 15:00:52 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260628T130052Z-2703cc03`
**Messaggio:** feat(onboarding): consenti di riaprire il wizard dalle preferenze

**Dettagli:**
- aggiunge nelle preferenze il pulsante per riavviare la configurazione iniziale
- preseleziona modalità e AI Web correnti e permette di annullare senza modifiche
- salva le nuove scelte senza ripristinare le altre impostazioni
- aggiorna traduzioni italiane e inglesi e test di regressione

**File modificati:**
- `src/local_ai_bridge/ui/application_modes.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-28 15:04:16 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260628T130416Z-20bcce16`
**Messaggio:** chore(release): prepara BridgAI 1.1.0

**Dettagli:**
- aggiorna la versione del package e dei metadati di build a 1.1.0
- aggiunge changelog e note di rilascio per le funzionalità introdotte dopo la 1.0.0
- allinea README italiano e inglese ai nuovi flussi Web, operativi, AI e di sicurezza

**File modificati:**
- `src/local_ai_bridge/__init__.py`
- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `README.it.md`
- `AGGIORNAMENTO_1.1.0.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-29 16:06:43 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260629T140643Z-8bc66b46`
**Messaggio:** fix(git): evita la discovery sui mount SSHFS

**Dettagli:**
- esegue i comandi Git con repository e work tree espliciti
- crea la repository GitHub senza discovery locale e collega origin separatamente
- aggiunge test di regressione per percorsi SSHFS/UNC e account GitHub attivo

**File modificati:**
- `src/local_ai_bridge/services/git.py`
- `src/local_ai_bridge/services/github.py`
- `tests/test_git_service.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-29 16:14:18 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260629T141418Z-f5227a89`
**Messaggio:** fix(git): esegui Git sul server per workspace SSHFS

**Dettagli:**
- riconosce i percorsi UNC SSHFS-Win e li converte nel percorso POSIX remoto
- esegue init, status, add, commit, remote e push tramite OpenSSH sul server Linux
- valida realmente il repository remoto e ripara il caso .git incompleto tramite git init remoto
- usa il remote SSH GitHub per i workspace SSHFS e mantiene invariati i repository locali
- aggiunge test di regressione per backend remoto, quoting dei percorsi e URL origin

**File modificati:**
- `src/local_ai_bridge/services/git.py`
- `src/local_ai_bridge/services/github.py`
- `tests/test_git_service.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-29 16:24:04 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260629T142404Z-4c54c437`
**Messaggio:** fix(git): gestisci la prima connessione SSH dei workspace SSHFS

**Dettagli:**
- accetta automaticamente soltanto le chiavi host nuove tramite StrictHostKeyChecking=accept-new
- continua a rifiutare una chiave host già registrata ma cambiata
- non scambia più gli errori SSH di trust o autenticazione per repository Git mancanti
- mostra indicazioni operative per chiave host e autenticazione SSH non interattiva
- aggiunge test di regressione per bootstrap SSH sicuro e propagazione degli errori

**File modificati:**
- `src/local_ai_bridge/services/git.py`
- `tests/test_git_service.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-29 16:38:15 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260629T143815Z-dfb14764`
**Messaggio:** fix(git): ripara repository locali inizializzati solo parzialmente

**Dettagli:**
- verifica la validità di .git tramite git rev-parse anche sui workspace Linux locali
- usa il codice di uscita Git invece di analizzare messaggi localizzati
- riesegue git init in sicurezza quando una precedente inizializzazione ha lasciato .git incompleta
- verifica che il repository sia realmente valido dopo git init
- mantiene visibili gli errori SSH e filesystem non riconducibili a repository assente
- aggiorna i test Git/GitHub e aggiunge regressioni per il caso dynaqr

**File modificati:**
- `src/local_ai_bridge/services/git.py`
- `tests/test_git_service.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-29 16:49:13 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260629T144913Z-db37ca26`
**Messaggio:** fix(github): collega repository esistenti durante la prima pubblicazione

**Dettagli:**
- rileva il repository omonimo già presente sull'account GitHub attivo
- collega automaticamente origin invece di tentare una seconda creazione
- mantiene il push non forzato e non esegue pull, merge o rebase automatici
- distingue nel risultato repository creati e repository esistenti riutilizzati
- aggiunge test di regressione per il caso GraphQL "Name already exists"

**File modificati:**
- `src/local_ai_bridge/services/github.py`
- `tests/test_git_service.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 12:43:41 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T104341Z-7c365867`
**Messaggio:** feat(windows): add direct Web server launcher for Chrome extension

**Dettagli:**
- add a Windows-only button beside the Chrome extension controls
- launch web_server_force_win.bat in a separate console
- clarify that the extension requires the BridgAI Web server
- add regression coverage and bilingual UI strings

**File modificati:**
- `src/local_ai_bridge/ui/tabs/advanced.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `tests/test_browser_extension.py`
- `tests/test_settings_layout.py`
- `web_server_force_win.bat`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 12:51:28 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T105128Z-746491e0`
**Messaggio:** fix(extension): rendi affidabile il watcher delle richieste successive

**Dettagli:**
- rileva nuove risposte anche quando il sito riutilizza lo stesso nodo DOM
- inoltra la prima risposta solo dopo una direttiva #scarica completa e stabile
- mantiene separato il flusso finale di ricezione dello ZIP dopo l'allegato
- aggiorna la versione dell'estensione e aggiunge test di regressione

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 13:00:58 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T110058Z-fb98c7e9`
**Messaggio:** fix(ui): ripristina il filtro del modello e aggiunge la chat temporanea

**Dettagli:**
- mantiene visibile solo il provider preferito dopo il riavvio in modalità super semplice
- lascia visibili tutti i provider quando la preferenza è Personalizzato
- aggiunge una preferenza persistente per aprire ChatGPT come Chat temporanea
- aggiorna traduzioni e test di regressione

**File modificati:**
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/preferred_web_ai_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 13:06:36 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T110636Z-98d4aed8`
**Messaggio:** fix(ui): mostra la chat temporanea nell’assistente semplice

**Dettagli:**
- aggiunge lo slider della modalità anonima direttamente nella scheda Assistente
- sincronizza lo slider con la copia presente nelle Preferenze
- mantiene il filtro persistente dei pulsanti del provider selezionato
- aggiorna i test di regressione del layout

**File modificati:**
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/preferred_web_ai_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 13:28:02 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T112802Z-94e45111`
**Messaggio:** fix(extension): avvia il server prima di accodare le richieste

**Dettagli:**
- verifica l'endpoint autenticato dell'estensione prima di usare il servizio locale
- avvia automaticamente il server Web quando non risponde e ne verifica l'effettiva disponibilità
- evita di accodare richieste quando il servizio non può essere avviato
- aggiunge test di regressione per ordine di avvio, fallimento e doppia verifica

**File modificati:**
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 13:48:12 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T114812Z-7fdb0f33`
**Messaggio:** fix(ui): applica la chat temporanea a tutti i pulsanti ChatGPT

**Dettagli:**
- centralizza la trasformazione dell'URL ChatGPT con temporary-chat=true
- usa la modalità anonima anche dal pulsante secondario Apri ChatGPT
- aggiunge una regressione sul wiring del pulsante

**File modificati:**
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 14:29:37 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T122937Z-96688645`
**Messaggio:** feat(superpowers): add personalized Markdown superpower library

**Dettagli:**
- add safe global and project Markdown superpower discovery, validation, creation, and invocation
- resolve @superpower:id and @superpotere:id references in Super-Reports
- expose list and render operations through the built-in skill registry
- document the workflow in the Web power-user panel
- add focused unit and reporting regression tests

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/skills/builtins.py`
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `tests/test_superpowers.py`
- `tests/test_reporting_export.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 14:38:40 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T123840Z-39a2633d`
**Messaggio:** feat(superpowers): add Markdown editor and selectors

**Dettagli:**
- add shared CRUD operations for global and project Markdown superpowers
- add desktop editor and multi-select control to the simple workflow
- add authenticated Web UI editor, selection modal, and CRUD endpoints
- add bilingual labels and focused regression tests

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `src/local_ai_bridge/web/project_actions.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_superpower_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 14:41:14 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T124114Z-a1e64a97`
**Messaggio:** feat(superpowers): add starter Markdown superpowers

**Dettagli:**
- add five project-scoped superpowers for review, bug fixing, refactoring, testing, and documentation
- keep each template editable through the existing superpower editor

**File modificati:**
- `.bridgai/superpowers/revisione-sicura.md`
- `.bridgai/superpowers/correzione-bug.md`
- `.bridgai/superpowers/refactoring-controllato.md`
- `.bridgai/superpowers/test-mirati.md`
- `.bridgai/superpowers/documentazione-allineata.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 14:41:58 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T124158Z-d9b30a4b`
**Messaggio:** feat(superpowers): add starter Markdown superpowers

**Dettagli:**
- add five project-scoped superpowers for review, bug fixing, refactoring, testing, and documentation
- keep each template editable through the existing superpower editor

**File modificati:**
- `.bridgai/superpowers/revisione-sicura.md`
- `.bridgai/superpowers/correzione-bug.md`
- `.bridgai/superpowers/refactoring-controllato.md`
- `.bridgai/superpowers/test-mirati.md`
- `.bridgai/superpowers/documentazione-allineata.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 15:43:56 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T134356Z-e7daa906`
**Messaggio:** feat(superpowers): add curated general-purpose starter library

**Dettagli:**
- add a project-level collection of general-purpose Markdown superpowers
- cover critical thinking, decisions, productivity, creativity, writing, research and learning
- include the existing software-development superpowers in the unified catalog
- keep every prompt editable and selectable through the BridgAI superpower editor

**File modificati:**
- `.bridgai/superpowers/analisi-critica.md`
- `.bridgai/superpowers/avvocato-del-diavolo.md`
- `.bridgai/superpowers/decisione-ponderata.md`
- `.bridgai/superpowers/cinque-prospettive.md`
- `.bridgai/superpowers/principi-primi.md`
- `.bridgai/superpowers/piano-a-ritroso.md`
- `.bridgai/superpowers/architetto-produttivita.md`
- `.bridgai/superpowers/priorita-80-20.md`
- `.bridgai/superpowers/matrice-urgente-importante.md`
- `.bridgai/superpowers/scomposizione-atomica.md`
- `.bridgai/superpowers/moltiplicatore-idee.md`
- `.bridgai/superpowers/connessioni-inattese.md`
- `.bridgai/superpowers/creativita-vincolata.md`
- `.bridgai/superpowers/critico-miglioratore.md`
- `.bridgai/superpowers/riscrittura-professionale.md`
- `.bridgai/superpowers/spiegazione-principianti.md`
- `.bridgai/superpowers/sintesi-operativa.md`
- `.bridgai/superpowers/email-efficace.md`
- `.bridgai/superpowers/contenuto-multicanale.md`
- `.bridgai/superpowers/revisore-chiarezza.md`
- `.bridgai/superpowers/intervista-prima-di-scrivere.md`
- `.bridgai/superpowers/ricercatore-con-fonti.md`
- `.bridgai/superpowers/confronto-fonti.md`
- `.bridgai/superpowers/verifica-affermazioni.md`
- `.bridgai/superpowers/tutor-socratico.md`
- `.bridgai/superpowers/piano-apprendimento.md`
- `.bridgai/superpowers/mappa-concettuale.md`
- `.bridgai/superpowers/preparazione-riunione.md`
- `.bridgai/superpowers/revisione-settimanale.md`
- `.bridgai/superpowers/confronto-acquisti.md`
- `.bridgai/superpowers/revisione-sicura.md`
- `.bridgai/superpowers/correzione-bug.md`
- `.bridgai/superpowers/refactoring-controllato.md`
- `.bridgai/superpowers/test-mirati.md`
- `.bridgai/superpowers/documentazione-allineata.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 15:55:08 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T135508Z-be847cc6`
**Messaggio:** fix(workflow): remove anonymous mode and harden extension startup

**Dettagli:**
- replace the superpower emoji with inline SVG icons in desktop and Web UI
- remove the unsupported anonymous ChatGPT setting, controls, translations, and URL rewriting
- launch the Windows direct Web server script when the extension service is offline and wait before queueing
- add regression tests for the updated UI and startup sequence

**File modificati:**
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `src/local_ai_bridge/ui/preferred_web_ai_actions.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/web/launcher.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`
- `tests/test_superpower_ui.py`
- `tests/test_browser_extension.py`
- `tests/test_web_launcher.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 16:11:14 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T141114Z-211f48b0`
**Messaggio:** feat(notes): add shared project notes and todo hub

**Dettagli:**
- add atomic project-local notes and todo persistence in .bridgai/notes.json
- add desktop notes tab and Web UI notes editor with CRUD endpoints
- fix PySide6 superpower dialog acceptance handling
- add translations and regression tests for notes and superpowers

**File modificati:**
- `src/local_ai_bridge/core/project_notes.py`
- `src/local_ai_bridge/ui/project_notes.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `src/local_ai_bridge/ui/layouts.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/web/project_actions.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_project_notes.py`
- `tests/test_superpower_ui.py`
- `tests/test_web_project_management.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 16:18:30 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T141830Z-c25dabab`
**Messaggio:** feat(superpowers): add search and category filters

**Dettagli:**
- add optional category metadata with backward-compatible General fallback
- add search and category filtering to desktop and Web superpower selectors
- persist category edits through desktop and Web CRUD flows
- add regression coverage for legacy files and filter controls

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/web/project_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_superpower_ui.py`
- `tests/test_superpowers.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 16:27:37 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T142737Z-0bb099c6`
**Messaggio:** feat(superpowers): classify the built-in library

**Dettagli:**
- add a functional category to every project superpower
- keep existing titles, descriptions and instructions unchanged
- reserve the General fallback for uncategorized custom entries

**File modificati:**
- `.bridgai/superpowers/analisi-critica.md`
- `.bridgai/superpowers/architetto-produttivita.md`
- `.bridgai/superpowers/avvocato-del-diavolo.md`
- `.bridgai/superpowers/cinque-prospettive.md`
- `.bridgai/superpowers/confronto-acquisti.md`
- `.bridgai/superpowers/confronto-fonti.md`
- `.bridgai/superpowers/connessioni-inattese.md`
- `.bridgai/superpowers/contenuto-multicanale.md`
- `.bridgai/superpowers/correzione-bug.md`
- `.bridgai/superpowers/creativita-vincolata.md`
- `.bridgai/superpowers/critico-miglioratore.md`
- `.bridgai/superpowers/decisione-ponderata.md`
- `.bridgai/superpowers/documentazione-allineata.md`
- `.bridgai/superpowers/email-efficace.md`
- `.bridgai/superpowers/intervista-prima-di-scrivere.md`
- `.bridgai/superpowers/mappa-concettuale.md`
- `.bridgai/superpowers/matrice-urgente-importante.md`
- `.bridgai/superpowers/moltiplicatore-idee.md`
- `.bridgai/superpowers/piano-a-ritroso.md`
- `.bridgai/superpowers/piano-apprendimento.md`
- `.bridgai/superpowers/preparazione-riunione.md`
- `.bridgai/superpowers/principi-primi.md`
- `.bridgai/superpowers/priorita-80-20.md`
- `.bridgai/superpowers/refactoring-controllato.md`
- `.bridgai/superpowers/revisione-settimanale.md`
- `.bridgai/superpowers/revisione-sicura.md`
- `.bridgai/superpowers/revisore-chiarezza.md`
- `.bridgai/superpowers/ricercatore-con-fonti.md`
- `.bridgai/superpowers/riscrittura-professionale.md`
- `.bridgai/superpowers/scomposizione-atomica.md`
- `.bridgai/superpowers/sintesi-operativa.md`
- `.bridgai/superpowers/spiegazione-principianti.md`
- `.bridgai/superpowers/test-mirati.md`
- `.bridgai/superpowers/tutor-socratico.md`
- `.bridgai/superpowers/verifica-affermazioni.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 16:37:20 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T143720Z-5ef7212b`
**Messaggio:** feat(superpowers): unify project library with operational work types

**Dettagli:**
- save and manage superpowers only inside the current project's .bridgai directory
- replace operational work categories with the project's superpower library
- embed the selected superpower instructions in Web AI operational missions
- preserve compatibility with previously saved operational category identifiers
- update desktop, Web UI, API, and regression tests

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/services/operational_missions.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/operations_presenters.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/web/project_actions.py`
- `tests/test_superpowers.py`
- `tests/test_superpower_ui.py`
- `tests/test_operational_ui.py`
- `tests/test_operational_missions.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 17:48:23 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T154823Z-be6ad52d`
**Messaggio:** feat(operations): simplify sectors and filtered approaches

**Dettagli:**
- restore clear operational work sectors such as documents, data, presentations and images
- add an optional superpower approach filtered by the selected sector
- exclude software-development profiles from operational mode
- persist sector and optional superpower separately with backward-compatible mission loading
- update operational package metadata, translations and regression tests

**File modificati:**
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/services/operational_catalog.py`
- `src/local_ai_bridge/services/operational_missions.py`
- `src/local_ai_bridge/services/operational_web.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/operations_presenters.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `tests/test_operational_missions.py`
- `tests/test_operational_ui.py`
- `tests/test_superpowers.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 18:16:21 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T161621Z-65f767e9`
**Messaggio:** feat(operations): add sector-specific operational superpowers

**Dettagli:**
- distinguish development, operational and shared superpowers with explicit metadata
- add sector-aware operational methods and the Translation work area
- filter the operational selector by declared compatible sectors
- add translation, PDF, data, presentation, image, writing and file-organization profiles
- update bilingual labels and regression tests

**File modificati:**
- `tests/test_operational_ui.py`
- `tests/test_superpowers.py`
- `.bridgai/superpowers/analisi-critica.md`
- `.bridgai/superpowers/architetto-produttivita.md`
- `.bridgai/superpowers/avvocato-del-diavolo.md`
- `.bridgai/superpowers/cinque-prospettive.md`
- `.bridgai/superpowers/confronto-acquisti.md`
- `.bridgai/superpowers/confronto-fonti.md`
- `.bridgai/superpowers/connessioni-inattese.md`
- `.bridgai/superpowers/contenuto-multicanale.md`
- `.bridgai/superpowers/correzione-bug.md`
- `.bridgai/superpowers/creativita-vincolata.md`
- `.bridgai/superpowers/critico-miglioratore.md`
- `.bridgai/superpowers/decisione-ponderata.md`
- `.bridgai/superpowers/documentazione-allineata.md`
- `.bridgai/superpowers/email-efficace.md`
- `.bridgai/superpowers/intervista-prima-di-scrivere.md`
- `.bridgai/superpowers/mappa-concettuale.md`
- `.bridgai/superpowers/matrice-urgente-importante.md`
- `.bridgai/superpowers/moltiplicatore-idee.md`
- `.bridgai/superpowers/piano-a-ritroso.md`
- `.bridgai/superpowers/piano-apprendimento.md`
- `.bridgai/superpowers/preparazione-riunione.md`
- `.bridgai/superpowers/priorita-80-20.md`
- `.bridgai/superpowers/principi-primi.md`
- `.bridgai/superpowers/refactoring-controllato.md`
- `.bridgai/superpowers/revisione-settimanale.md`
- `.bridgai/superpowers/revisione-sicura.md`
- `.bridgai/superpowers/revisore-chiarezza.md`
- `.bridgai/superpowers/ricercatore-con-fonti.md`
- `.bridgai/superpowers/riscrittura-professionale.md`
- `.bridgai/superpowers/scomposizione-atomica.md`
- `.bridgai/superpowers/sintesi-operativa.md`
- `.bridgai/superpowers/spiegazione-principianti.md`
- `.bridgai/superpowers/test-mirati.md`
- `.bridgai/superpowers/tutor-socratico.md`
- `.bridgai/superpowers/verifica-affermazioni.md`
- `.bridgai/superpowers/pdf-riassumi.md`
- `.bridgai/superpowers/pdf-confronta.md`
- `.bridgai/superpowers/pdf-estrai-informazioni.md`
- `.bridgai/superpowers/dati-analizza.md`
- `.bridgai/superpowers/dati-confronta.md`
- `.bridgai/superpowers/dati-controllo-qualita.md`
- `.bridgai/superpowers/presentazione-crea.md`
- `.bridgai/superpowers/presentazione-da-immagini.md`
- `.bridgai/superpowers/immagini-organizza.md`
- `.bridgai/superpowers/immagini-concept.md`
- `.bridgai/superpowers/scrittura-relazione.md`
- `.bridgai/superpowers/scrittura-controllo-qualita.md`
- `.bridgai/superpowers/file-organizza.md`
- `.bridgai/superpowers/file-indice.md`
- `.bridgai/superpowers/traduzione-principali-lingue.md`
- `.bridgai/superpowers/traduzione-professionale.md`
- `.bridgai/superpowers/traduzione-confronta.md`
- `.bridgai/superpowers/traduzione-semplifica.md`
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/services/operational_catalog.py`
- `src/local_ai_bridge/services/operational_missions.py`
- `src/local_ai_bridge/services/operational_web.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/operations_presenters.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 18:27:42 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T162742Z-814caab4`
**Messaggio:** fix(operations): velocizza il caricamento dei metodi operativi

**Dettagli:**
- memorizza la libreria dei superpoteri finché i file del progetto non cambiano
- aggiorna la tendina operativa solo al cambio di progetto o settore
- mantiene subito disponibile l'opzione automatica
- aggiunge test di regressione per la cache e il wiring dell'interfaccia

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `tests/test_superpowers.py`
- `tests/test_operational_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 18:40:05 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T164005Z-cc241174`
**Messaggio:** perf(superpowers): aggiungi indice persistente per la modalità operativa

**Dettagli:**
- salva i metadati dei superpoteri in .bridgai/superpowers/index.json
- popola subito il menu da un singolo JSON senza analizzare tutti i Markdown
- costruisce l'indice mancante in background mantenendo disponibile Automatico
- carica le istruzioni complete solo per il superpotere selezionato
- aggiorna incrementalmente l'indice su salvataggio ed eliminazione
- aggiunge test per indice persistente, caricamento lazy e ricostruzione

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/main_window.py`
- `tests/test_superpowers.py`
- `tests/test_operational_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 19:40:38 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T174038Z-eb661c39`
**Messaggio:** fix(ui): ripristina missioni operative e avvio Web forzato Windows

**Dettagli:**
- importa lo stato MISSION_RUNNING usato dai controlli delle missioni Web
- aggiunge nelle preferenze super semplici il pulsante Windows per l'avvio forzato
- collega il pulsante al launcher diretto già esistente e mostra stato o errore
- allinea lo script batch richiesto e mantiene aperta la console al termine
- aggiunge traduzioni italiane/inglesi e test di regressione mirati

**File modificati:**
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_operational_ui.py`
- `tests/test_settings_layout.py`
- `tests/test_web_launcher.py`
- `web_server_force_win.bat`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 19:46:56 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T174656Z-7fa01a2c`
**Messaggio:** fix(ui): de-enfatizza la modalità operativa sperimentale

**Dettagli:**
- rimuove la modalità operativa dal wizard iniziale e dal selettore delle impostazioni
- mantiene il flusso di sviluppo come scelta stabile per nuove configurazioni
- sposta la scheda operativa in coda e la identifica esplicitamente come sperimentale
- aggiorna traduzioni e test di regressione senza rimuovere i servizi operativi esistenti

**File modificati:**
- `src/local_ai_bridge/ui/application_modes.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings_layout.py`
- `tests/test_operational_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 20:02:36 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T180236Z-b166a516`
**Messaggio:** feat(ui): introduce simplified AI Task Assistant mode

**Dettagli:**
- restore the primary mode choice in the initial wizard and settings
- rename the operational experience to Assistente Attività AI / AI Task Assistant
- replace the mandatory mission setup with a guided prompt-first workflow
- keep local projects optional and preserve legacy advanced mission tools
- update Italian and English translations and regression tests

**File modificati:**
- `src/local_ai_bridge/ui/application_modes.py`
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/ui/tabs/operations.py`
- `src/local_ai_bridge/ui/tabs/operations_secondary.py`
- `src/local_ai_bridge/ui/operations_actions.py`
- `src/local_ai_bridge/ui/operations_web_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings_layout.py`
- `tests/test_operational_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 20:24:45 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T182445Z-ad17cf4d`
**Messaggio:** fix(superpowers): conserva la libreria tra i progetti

**Dettagli:**
- sposta il salvataggio dei superpoteri nella cartella dati globale di BridgAI
- migra in modo non distruttivo i superpoteri legacy presenti nei progetti
- evita sovrascritture quando un ID globale esiste già
- aggiorna testi UI e test di regressione sul cambio progetto

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`
- `src/local_ai_bridge/web/page.py`
- `tests/test_superpowers.py`
- `tests/test_superpower_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 21:56:44 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260630T195644Z-c193e91e`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/resources/prompt_presets.json`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 21:57:20 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260630T195720Z-b6198a44`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/resources/prompt_presets.json`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 22:15:19 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260630T201519Z-88d21b4c`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/resources/prompt_presets.json`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 22:21:04 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260630T202104Z-19683dc3`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/resources/prompt_presets.json`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 22:34:53 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T203453Z-6fa196ca`
**Messaggio:** feat(superpowers): add deep software project assessment

**Dettagli:**
- add the `valutazione-progetto-software` development superpower for value, strengths, weaknesses, risks, maturity, and priorities
- install the bundled profile once without overwriting custom copies or recreating deliberate deletions
- add regression coverage for indexing, report invocation, customization, and deletion behavior

**File modificati:**
- `src/local_ai_bridge/core/default_superpowers.py`
- `src/local_ai_bridge/core/superpowers.py`
- `tests/test_superpowers.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-06-30 22:48:42 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260630T204842Z-74761492`
**Messaggio:** refactor(prompts): rendi i preset verificabili e robusti

**Dettagli:**
- sostituisce richieste di ragionamento interno e confidenza arbitraria con criteri osservabili
- chiarisce obiettivi, verifiche e rischi residui dei cinque preset integrati
- valida formato degli ID, catalogo non vuoto ed etichette duplicate
- separa il profilo operativo dal task preservando la priorità del Super-Report
- amplia i test di regressione del catalogo e della composizione dei task

**File modificati:**
- `src/local_ai_bridge/core/prompt_presets.py`
- `src/local_ai_bridge/resources/prompt_presets.json`
- `tests/test_prompt_presets.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-01 20:19:32 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260701T181932Z-26f275a4`
**Messaggio:** fix(extension): rendi condizionale la richiesta di modifiche dopo #scarica

**Dettagli:**
- sostituisce l'ordine automatico di procedere con le modifiche con un invito a proseguire con il task
- richiede lo ZIP applicabile solo quando il task richiede effettivamente modifiche
- aggiunge una regressione sul testo del prompt di follow-up

**File modificati:**
- `src/local_ai_bridge/web/extension_api.py`
- `tests/test_browser_extension_api.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-01 21:57:26 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260701T195726Z-7356e376`
**Messaggio:** feat(extension): supporta ChatGPT, Claude e Gemini

**Dettagli:**
- instrada le richieste dell’estensione verso il provider Web AI preferito
- aggiunge adattatori DOM e permessi Chrome per ChatGPT, Claude e Gemini
- valida la provenienza delle risposte e mantiene ChatGPT come fallback personalizzato
- gestisce gli aggiornamenti testuali usati dal preset Gemini con anteprima manuale
- aggiorna documentazione e test di regressione dell’automazione browser

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/README.md`
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/download_tracking.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/resources/chrome_extension/options.html`
- `src/local_ai_bridge/resources/chrome_extension/providers.js`
- `src/local_ai_bridge/services/browser_extension.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `src/local_ai_bridge/ui/workflow_actions.py`
- `src/local_ai_bridge/web/browser_automation.py`
- `src/local_ai_bridge/web/extension_api.py`
- `tests/test_browser_extension.py`
- `tests/test_browser_extension_api.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-01 22:36:04 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260701T203604Z-7fd93fd0`
**Messaggio:** fix(extension): route requests to the selected Web AI provider

**Dettagli:**
- refresh the persisted preferred provider before Web UI queueing
- negotiate extension provider capabilities and block stale ChatGPT-only workers
- reject missing provider routing instead of silently falling back to ChatGPT
- bump the Chrome extension to 0.6.1 and add regression coverage

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/resources/chrome_extension/providers.js`
- `src/local_ai_bridge/services/browser_extension.py`
- `src/local_ai_bridge/web/browser_automation.py`
- `src/local_ai_bridge/web/extension_api.py`
- `tests/test_browser_extension.py`
- `tests/test_browser_extension_api.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-01 22:47:52 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260701T204752Z-0f8a93c7`
**Messaggio:** fix(extension): harden ChatGPT, Claude and Gemini automation

**Dettagli:**
- validate generated ZIP links against the provider that received the request
- make content-script fallback injection idempotent and improve composer/file-input handling
- detect provider streaming states more conservatively before capturing responses
- bump the Chrome extension to 0.6.2 and update regression checks and verification notes

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/README.md`
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/resources/chrome_extension/providers.js`
- `tests/test_browser_extension.py`
- `tests/test_browser_extension_api.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-01 22:56:10 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260701T205610Z-48229b65`
**Messaggio:** fix(extension): instrada e attiva Claude e Gemini

**Dettagli:**
- porta in primo piano la scheda del provider selezionato e ne verifica l'origine prima dell'invio
- rende più robusti inserimento del prompt, rilevamento streaming e scelta degli allegati
- limita i download ZIP agli host attendibili del provider che ha ricevuto la richiesta
- aggiorna versione, documentazione e test di regressione dell'estensione

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/README.md`
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/resources/chrome_extension/providers.js`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-03 01:40:44 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260702T234044Z-8df73185`
**Messaggio:** feat(ui): ridisegna la finestra Superpoteri con libreria + editor separato

**Dettagli:**
- sostituisce il layout a due colonne (lista + form sempre visibile) con
  una libreria a schermo intero e un editor dedicato aperto solo su
  richiesta (Nuovo / matita per riga), tramite QStackedWidget
- aggiunge una sezione "Attivi" con chip removibili con un click,
  visibile solo quando c'è almeno un superpotere attivo
- ogni riga della libreria usa il ToggleSwitch già esistente per
  attivare/disattivare senza aprire l'editor
- l'editor riunisce creazione, modifica ed eliminazione in un unico
  pannello con pulsante "indietro" verso la libreria
- aggiunge FlowLayout e un helper per pulsanti "chip" in widgets.py,
  riutilizzabili altrove nell'app
- aggiunge stile per i chip e per le righe della lista superpoteri in
  theme.py (dark e light)
- aggiunge le nuove stringhe i18n ("Attivi:", "Nuovo superpotere",
  "Modifica superpotere", "Modifica") in italiano e inglese
- mantiene invariata l'API pubblica del dialog (costruttore,
  selected_superpower_ids(), self.search, self.category_filter,
  _apply_filters) per compatibilità con workflow_actions.py e con i
  test di regressione esistenti

**File modificati:**
- `src/local_ai_bridge/ui/theme.py`
- `src/local_ai_bridge/ui/widgets.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-03 01:54:08 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260702T235408Z-b9f3415f`
**Messaggio:** fix(ui): riordina i pulsanti e rende cliccabile l'intera riga del superpotere

**Dettagli:**
- sposta "Nuovo" nella riga di ricerca/filtro (icona "+"), lasciando
  in fondo solo OK/Cancel invece di tre pulsanti ravvicinati
- l'intera riga del superpotere (non solo il piccolo interruttore) è
  ora cliccabile per attivare/disattivare, tramite un piccolo
  contenitore dedicato (_SuperpowerRow) che intercetta il click
  quando non cade su interruttore o pulsante di modifica
- ingrandisce leggermente l'interruttore stesso (38x21 invece di
  34x18) per un bersaglio più comodo anche al click diretto

**File modificati:**
- `src/local_ai_bridge/ui/widgets.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-03 02:00:54 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260703T000054Z-7c137ede`
**Messaggio:** fix(ui): sostituisce le icone a carattere con glifi vettoriali disegnati

**Dettagli:**
- aggiunge IconButton in widgets.py: pulsante circolare che disegna da sé
  il proprio glifo (add/back/edit) invece di affidarsi a caratteri
  Unicode/emoji (✎, +, ←), la cui resa e centratura variano per
  font/piattaforma e apparivano tagliate o decentrate
- usa IconButton per "Nuovo" (+), "Indietro" (←) nell'editor e
  "Modifica" (matita) su ogni riga della libreria superpoteri
- aggiunge stile esplicito per la freccia del QComboBox in theme.py
  (drop-down e down-arrow disegnati via CSS), risolvendo la resa
  nativa del sistema operativo che appariva tagliata dagli angoli
  arrotondati del filtro categorie; aggiunge anche lo stile per il
  popup a tendina (QComboBox QAbstractItemView)
- aggiunge la stringa i18n "Torna alla libreria" (IT/EN) per il
  tooltip del pulsante indietro

**File modificati:**
- `src/local_ai_bridge/ui/theme.py`
- `src/local_ai_bridge/ui/widgets.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-05 12:51:32 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260705T105132Z-a1c2e9e8`
**Messaggio:** fix(scarica): riconosce #scarica anche con formattazione Markdown variabile

**Dettagli:**
- rende parse_download_requests (services/exporting.py) tollerante a: riga
  intera racchiusa in backtick/grassetto/corsivo, prefissi da elenco o
  citazione (-, *, •, 1., >), e forma a blocco multilinea (#scarica seguito
  da un elenco di file su righe successive)
- allinea la stessa identica logica di pulizia in downloadRequestDirective
  (resources/chrome_extension/content.js), cosi' il gate lato estensione e
  il parser lato server riconoscono sempre gli stessi casi
- mantiene invariati DOWNLOAD_PATTERN e la firma di parse_download_requests
  per compatibilita' con eventuale codice/test esistente
- non gestisce prosa prima di #scarica sulla stessa riga (scelta
  deliberata per evitare falsi positivi); vedi note nella conversazione

**File modificati:**
- `src/local_ai_bridge/services/exporting.py`
- `src/local_ai_bridge/resources/chrome_extension/content.js`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-05 13:02:26 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260705T110226Z-1d475c02`
**Messaggio:** fix(extension): accelera hand-off AI Web e intercetta #scarica successivi

**Dettagli:**
- riduce la latenza del polling dell’estensione e dà priorità alla presa in carico delle richieste prima della manutenzione download
- limita il heartbeat ai tab AI visibili per evitare competizione tra ChatGPT, Claude e Gemini aperti insieme
- aggiunge un watcher passivo per intercettare direttive #scarica successive nella stessa chat dopo l’invio automatico iniziale
- rende il riconoscimento #scarica più tollerante a varianti Markdown con due punti e heading
- aggiorna i test di regressione dell’estensione browser

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-05 13:13:15 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260705T111315Z-d43fb09f`
**Messaggio:** fix(extension): wake provider tabs and serialize passive #scarica watcher

**Dettagli:**
- open the selected AI provider when the extension was not recently seen, so Chrome can load the content script and poll immediately instead of waiting for the alarm cycle
- expose canonical provider URLs alongside provider labels and normalization
- prevent overlapping passive #scarica checks while a previous passive action is still running
- bump the unpacked Chrome extension version to 0.6.4
- update browser extension regression tests for wake-up behavior and passive watcher serialization

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/services/browser_extension.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-05 13:23:42 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260705T112342Z-994a7637`
**Messaggio:** fix(extension): wake stale hand-offs without waiting for Chrome alarms

**Dettagli:**
- wake the selected provider when the last extension heartbeat is older than the hot hand-off window
- avoid waiting on provider tab load before trying to deliver a queued request
- shorten composer send timeout and add a form-submit fallback when the send button is not immediately detected
- bump the unpacked Chrome extension version to 0.6.5
- update browser extension regression coverage for stale heartbeat wake-up

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/resources/chrome_extension/manifest.json`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 00:21:50 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260706T222150Z-04a92339`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/resources/chrome_extension/content.js`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 00:26:01 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260706T222601Z-86291e90`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/ui/browser_extension_actions.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 00:36:24 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T223624Z-54e9dac5`
**Messaggio:** fix(extension): rendi più sicura l’adozione manuale degli ZIP

**Dettagli:**
- registra il timestamp reale di ricezione della risposta AI nello stato dell’estensione
- evita di adottare ZIP scaricati prima della risposta corrente, riducendo il rischio di agganciare file non pertinenti dalla cartella Download
- applica la stessa soglia temporale al webhook download-complete del backend
- corregge il messaggio di timeout dello ZIP in content.js
- aggiunge regressioni per debounce, sanitizzazione #scarica e filtro temporale dell’adozione manuale

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/content.js`
- `src/local_ai_bridge/services/browser_extension.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `src/local_ai_bridge/web/extension_api.py`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 00:50:30 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260706T225030Z-fcf97fd4`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/services/text_utils.py`
- `src/local_ai_bridge/services/text_file_operations.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:10:31 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T231031Z-aad33742`
**Messaggio:** refactor(core): separa parsing e indice dei superpoteri

**Dettagli:**
- estrae modello, validazione ID, parsing front matter e caricamento Markdown in core/superpower_models.py
- estrae serializzazione, lettura e aggiornamento dell'indice persistente in core/superpower_index.py
- mantiene core/superpowers.py come API pubblica e coordinatore di migrazione, cache e risoluzione richiami
- preserva compatibilità con import esistenti da local_ai_bridge.core.superpowers

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/core/superpower_models.py`
- `src/local_ai_bridge/core/superpower_index.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:16:16 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T231616Z-68822c70`
**Messaggio:** chore(release): prepare BridgAI 1.1.1

**Dettagli:**
- bump package and runtime version from 1.1.0 to 1.1.1
- add 1.1.1 release notes covering superpowers, project notes, browser-extension refinements, and report improvements
- align README, README.it, SECURITY, TEST_RESULTS, and report-version regression expectations with the 1.1.1 release

**File modificati:**
- `src/local_ai_bridge/__init__.py`
- `tests/test_reporting_export.py`
- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `README.it.md`
- `SECURITY.md`
- `TEST_RESULTS.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:42:39 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T234239Z-e73ef388`
**Messaggio:** chore(release): prepare BridgAI 1.1.1

**Dettagli:**
- bump package and runtime version from 1.1.0 to 1.1.1
- add 1.1.1 release notes covering superpowers, project notes, browser-extension refinements, and report improvements
- align README, README.it, SECURITY, TEST_RESULTS, and report-version regression expectations with the 1.1.1 release

**File modificati:**
- `src/local_ai_bridge/__init__.py`
- `tests/test_reporting_export.py`
- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `README.it.md`
- `SECURITY.md`
- `TEST_RESULTS.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:47:00 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T234700Z-51c16344`
**Messaggio:** chore(release): prepare BridgAI 1.1.1

**Dettagli:**
- bump package and runtime version from 1.1.0 to 1.1.1
- add 1.1.1 release notes covering superpowers, project notes, browser-extension refinements, and report improvements
- align README, README.it, SECURITY, TEST_RESULTS, and report-version regression expectations with the 1.1.1 release

**File modificati:**
- `src/local_ai_bridge/__init__.py`
- `tests/test_reporting_export.py`
- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `README.it.md`
- `SECURITY.md`
- `TEST_RESULTS.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:50:07 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T235007Z-6e33906b`
**Messaggio:** chore(release): prepare BridgAI 1.1.1

**Dettagli:**
- bump package and runtime version from 1.1.0 to 1.1.1
- add 1.1.1 release notes covering superpowers, project notes, browser-extension refinements, and report improvements
- align README, README.it, SECURITY, TEST_RESULTS, and report-version regression expectations with the 1.1.1 release

**File modificati:**
- `src/local_ai_bridge/__init__.py`
- `tests/test_reporting_export.py`
- `pyproject.toml`
- `CHANGELOG.md`
- `README.md`
- `README.it.md`
- `SECURITY.md`
- `TEST_RESULTS.md`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:53:29 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T235329Z-98ab83eb`
**Messaggio:** fix(web): mostra la versione sorgente nella Web UI

**Dettagli:**
- preferisce local_ai_bridge.__version__ rispetto ai metadati della distribuzione installata
- mantiene il fallback a importlib.metadata e development per ambienti non pacchettizzati
- aggiunge una regressione per evitare che una distribuzione installata vecchia mostri 1.0.0

**File modificati:**
- `src/local_ai_bridge/web/server.py`
- `tests/test_web_startup_regression.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:53:46 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T235346Z-76663efa`
**Messaggio:** feat(ui): mostra il recap dell'aggiornamento prima dell'applicazione

**Dettagli:**
- aggiunge un riepilogo riutilizzabile basato sul commit-message incluso nello ZIP
- mostra nel popup di conferma il messaggio di commit, i file interessati e gli eventuali avvisi
- aggiorna le traduzioni italiano/inglese delle nuove etichette
- aggiunge test di regressione per il recap e il limite dei file visualizzati

**File modificati:**
- `src/local_ai_bridge/services/apply.py`
- `src/local_ai_bridge/ui/change_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_patching.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:54:42 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T235442Z-eabf3a5d`
**Messaggio:** feat(web): mostra recap aggiornamento prima dell’applicazione

**Dettagli:**
- aggiunge nella Web UI un riquadro “Recap aggiornamento” alimentato dal commit-message.md dell’update
- include il recap anche nel popup di conferma prima di applicare lo ZIP
- mantiene un fallback chiaro quando lo ZIP non contiene commit-message.md
- aggiunge una regressione sul markup e sul wiring JavaScript della Web UI

**File modificati:**
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 01:55:03 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260706T235503Z-4b15ca72`
**Messaggio:** fix(ui): mostra il recap anche nel popup finale

**Dettagli:**
- aggiunge il riepilogo dell'aggiornamento al messaggio di completamento desktop
- riusa il commit-message.md già presente nello ZIP applicato
- include il recap anche quando i controlli post-applicazione sono saltati o generano avvisi
- mantiene invariato il flusso Web UI già aggiornato

**File modificati:**
- `src/local_ai_bridge/ui/change_actions.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 02:03:23 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T000323Z-76b7afd2`
**Messaggio:** feat(ui): abilita Shift+clic per scegliere manualmente lo ZIP

**Dettagli:**
- aggiunge a “Applica aggiornamento” il comportamento Shift+clic per aprire il selettore manuale dello ZIP
- rende visibile il suggerimento direttamente sul pulsante e nel tooltip
- mantiene il clic normale sull’ultimo ZIP disponibile nella cartella configurata
- aggiorna il feedback dell’automazione browser quando lo ZIP è pronto
- aggiunge traduzioni e test di regressione sul comportamento UI

**File modificati:**
- `src/local_ai_bridge/ui/change_actions.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_browser_extension.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 02:10:26 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T001026Z-69ba6441`
**Messaggio:** feat(notes): migliora note progetto e invio alle richieste

**Dettagli:**
- ridisegna la scheda desktop delle note con ricerca, riepilogo e layout editor più leggibile
- aggiunge l'azione per inserire una nota nella richiesta operativa desktop
- rinnova il pannello Note e attività della Web UI con ricerca, schede e inserimento diretto nel task
- aggiunge una funzione condivisa per formattare le note come blocco di richiesta AI
- aggiorna i test di regressione per formattazione e presenza delle nuove azioni Web

**File modificati:**
- `src/local_ai_bridge/core/project_notes.py`
- `src/local_ai_bridge/ui/project_notes.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `tests/test_project_notes.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 02:15:34 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T001534Z-b6583f0d`
**Messaggio:** feat(notes): modernizza UI note con slider

**Dettagli:**
- sostituisce i check desktop con controlli slider/toggle dedicati per attività e completamento
- aggiunge una skin moderna alla scheda Note e attività con hero, metriche, card, ricerca e stati vuoti più chiari
- migliora il pannello note della Web UI con layout più moderno e toggle più evidenti
- mantiene il flusso per aggiungere una nota direttamente alla richiesta AI
- verifica py_compile sui file modificati e test unitari delle note

**File modificati:**
- `src/local_ai_bridge/core/project_notes.py`
- `src/local_ai_bridge/ui/project_notes.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `tests/test_project_notes.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 02:19:12 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T001912Z-2b760a45`
**Messaggio:** fix(notes): usa gli switch standard nella scheda note

**Dettagli:**
- sostituisce gli slider custom delle note con il ToggleSwitch condiviso già usato nelle impostazioni
- rimuove lo stile dedicato che causava il look a pallino/testo disallineato
- mantiene invariata la logica di attività e completamento

**File modificati:**
- `src/local_ai_bridge/ui/project_notes.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 02:21:39 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T002139Z-33490c36`
**Messaggio:** refactor(notes-ui): align project notes tab with assistant visual language

**Dettagli:**
- replace the custom note switches with the shared ToggleSwitch control
- redesign the project notes tab using the same title, card, pill and button language used by the assistant tab
- remove dark-theme-specific note styling that looked poor in the light theme
- add a shared danger button role to the application theme for the delete action
- add a regression test that checks the notes UI uses the standard switches and shared card patterns

**File modificati:**
- `src/local_ai_bridge/ui/project_notes.py`
- `src/local_ai_bridge/ui/theme.py`
- `tests/test_project_notes.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 14:48:00 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T124800Z-5f360d58`
**Messaggio:** fix(web): compatta i superpoteri nella toolbar semplice

**Dettagli:**
- sposta i comandi superpoteri e note nella stessa toolbar di preparazione richiesta e provider Web
- aggiunge regole responsive per mantenere il layout compatto su desktop e leggibile su mobile
- estende il test Web dei superpoteri per verificare la nuova toolbar compatta

**File modificati:**
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `tests/test_superpower_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 14:57:18 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T125718Z-6277e591`
**Messaggio:** fix(desktop): allinea i superpoteri all'intestazione richiesta

**Dettagli:**
- sposta il selettore superpoteri nella stessa riga del titolo "Descrivi la richiesta" nell'interfaccia desktop
- rimuove la riga separata dei superpoteri per lasciare più spazio alla descrizione
- aggiorna il test di regressione del layout desktop semplice

**File modificati:**
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `tests/test_superpower_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 15:06:38 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T130638Z-b4c2147e`
**Messaggio:** style(desktop): aggiorna icona microfono dettatura

**Dettagli:**
- sostituisce l'emoji del microfono nella modalità semplice desktop con un'icona vettoriale moderna
- riusa la stessa icona nel dialogo di dettatura
- aggiunge una regressione per evitare il ritorno dell'icona emoji

**File modificati:**
- `src/local_ai_bridge/ui/widgets.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/ui/speech_dialog.py`
- `tests/test_superpower_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 15:12:11 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T131211Z-2c3cf74d`
**Messaggio:** fix(ui): usa geometria Lucide per il microfono desktop

**Dettagli:**
- sostituisce il disegno custom del microfono con la geometria Lucide Mic adattata a QPainter
- mantiene il pulsante vettoriale e compatibile con tema chiaro/scuro
- aggiorna il test di regressione sul microfono desktop

**File modificati:**
- `src/local_ai_bridge/ui/widgets.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/ui/speech_dialog.py`
- `tests/test_superpower_ui.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 15:42:01 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T134201Z-88266e55`
**Messaggio:** fix(text-updates): recover common malformed AI text packages

**Dettagli:**
- accept inline paths on BEGIN_FILE markers for complete text-file operations
- infer missing END_FILE and missing Markdown fence closures only when a safe boundary is found
- keep all recovered cases visible as normalization warnings in the review plan
- recover unclosed Markdown Exchange fences before the next BRIDGAI:FILE marker or at EOF
- add regression tests for malformed Gemini-style text responses

**File modificati:**
- `src/local_ai_bridge/services/text_file_operations.py`
- `src/local_ai_bridge/services/markdown_exchange.py`
- `tests/test_text_file_operations.py`
- `tests/test_markdown_exchange.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 15:50:37 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T135037Z-be9078e8`
**Messaggio:** feat(markdown): rendi più resiliente l'ingestione degli aggiornamenti testuali

**Dettagli:**
- accetta metadati compatti nel marcatore BEGIN_FILE e valida l'eventuale percorso in END_FILE
- recupera in modo conservativo CONTENT e OPERATION mancanti quando il blocco resta delimitabile
- accetta marker Markdown Exchange anche se la chat rimuove i commenti HTML
- aggiorna il Super-Report per preferire il formato compatto e documentare il recupero controllato
- aggiunge test di regressione per i nuovi casi di formattazione rumorosa

**File modificati:**
- `src/local_ai_bridge/services/text_file_operations.py`
- `src/local_ai_bridge/services/markdown_exchange.py`
- `src/local_ai_bridge/services/reporting.py`
- `tests/test_text_file_operations.py`
- `tests/test_markdown_exchange.py`
- `tests/test_reporting_export.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 15:56:33 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T135633Z-d13a3629`
**Messaggio:** feat(markdown): unify textual update ingestion

**Dettagli:**
- add a shared textual update importer that accepts both BEGIN_FILE update files and Markdown Exchange documents
- let the Markdown and text update UI entry points fall back to the other supported textual parser safely
- validate END_FILE target names for unfenced text-operation content
- add regression tests for cross-format import fallback and unfenced END_FILE mismatch handling

**File modificati:**
- `src/local_ai_bridge/services/text_file_operations.py`
- `src/local_ai_bridge/services/text_update_import.py`
- `src/local_ai_bridge/ui/markdown_update_actions.py`
- `tests/test_text_file_operations.py`
- `tests/test_text_update_import.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 16:22:48 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T142248Z-694bb6bd`
**Messaggio:** fix(markdown): classify risky text update recovery

**Dettagli:**
- add structured recovery metadata with severity and explicit-confirmation flags for text operations and Markdown Exchange
- mark inferred operations, unclosed fences, unfenced content, and parser fallback as high-risk recoveries
- make cross-format import fallback conservative when the detected primary format is malformed
- add an extra UI confirmation before applying plans recovered with high severity
- add regression tests for inferred CREATE, greedy fences, trailing EOF recovery, missing Markdown fences, and ambiguous parser fallback

**File modificati:**
- `src/local_ai_bridge/services/text_file_operations.py`
- `src/local_ai_bridge/services/markdown_exchange.py`
- `src/local_ai_bridge/services/text_update_import.py`
- `src/local_ai_bridge/ui/change_actions.py`
- `tests/test_text_file_operations.py`
- `tests/test_markdown_exchange.py`
- `tests/test_text_update_import.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 17:11:26 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T151126Z-25f4421c`
**Messaggio:** fix(text-updates): enforce high-risk recovery confirmation

**Dettagli:**
- blocca nel layer ApplyService l'applicazione di piani con recuperi ad alta severità senza consenso esplicito
- propaga severità e azioni di recupero alla Web UI e richiede una seconda conferma prima dell'applicazione
- conserva il diff per file Python sintatticamente invalidi marcandoli come recupero high-severity
- usa l'import testuale unificato anche per gli upload Markdown Web
- aggiunge test per enforcement desktop/backend, Web apply e SyntaxError ispezionabili

**File modificati:**
- `src/local_ai_bridge/services/apply.py`
- `src/local_ai_bridge/services/patching.py`
- `src/local_ai_bridge/services/text_file_operations.py`
- `src/local_ai_bridge/ui/change_actions.py`
- `src/local_ai_bridge/web/bridge_actions.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/web/server.py`
- `tests/test_patching.py`
- `tests/test_text_file_operations.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 17:43:49 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T154349Z-a01ecd67`
**Messaggio:** feat(superpowers): mostra anteprime ed esempi nella selezione

**Dettagli:**
- aggiunge descrizione e esempio d’uso alle righe della modale desktop dei superpoteri
- mostra nella Web UI un box di esempio sicuro creato via DOM per ogni superpotere
- aggiorna le regressioni statiche per coprire anteprime, esempi e rendering DOM

**File modificati:**
- `src/local_ai_bridge/ui/superpower_dialog.py`
- `src/local_ai_bridge/web/page_assets.py`
- `tests/test_superpower_ui.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 17:56:54 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260707T155654Z-386fe527`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `src/local_ai_bridge/core/superpower_models.py`
- `src/local_ai_bridge/core/superpowers.py`
- `src/local_ai_bridge/core/superpower_index.py`
- `src/local_ai_bridge/ui/superpower_dialog.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-07 17:59:39 ora legale Europa occidentale — file completo — applicata

**Sessione:** `20260707T155939Z-6c9552ce`
**Messaggio:** Nessun messaggio salvato

**File modificati:**
- `tests/test_superpowers.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 00:46:29 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T224629Z-8a971ce5`
**Messaggio:** refactor(services): split text file operations pipeline

**Dettagli:**
- estrae modelli condivisi e blocchi raw per il formato BEGIN_FILE/END_FILE
- sposta tokenizzazione, normalizzazione parser e planning in moduli dedicati
- mantiene parse_text_file_operations e inspect_text_file_operations come API pubbliche compatibili
- preserva i warning/recovery metadata e la validazione su contenuto unfenced senza END_FILE

**File modificati:**
- `src/local_ai_bridge/services/text_file_operations.py`
- `src/local_ai_bridge/services/text_file_models.py`
- `src/local_ai_bridge/services/text_file_lexer.py`
- `src/local_ai_bridge/services/text_file_parser.py`
- `src/local_ai_bridge/services/text_file_planner.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 00:53:38 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T225338Z-7de1958f`
**Messaggio:** refactor(ui): extract simple mode layout manager

**Dettagli:**
- add SimpleModeManager for desktop simple/operations mode visibility rules
- reduce MainWindow.apply_simple_mode to state preparation and delegation
- update layout source tests to assert the extracted manager behavior

**File modificati:**
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/ui/layout_managers/__init__.py`
- `src/local_ai_bridge/ui/layout_managers/simple_mode_manager.py`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 01:02:29 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T230229Z-eda6718d`
**Messaggio:** refactor(web): extract server route dispatch

**Dettagli:**
- sposta routing GET/POST e dispatch applicativo in web/server_routes.py
- sposta validazione e gestione upload ZIP/Markdown in web/server_uploads.py
- riduce BridgeHandler a gestione HTTP, serializzazione risposte e bootstrap server
- mantiene invariati endpoint, payload e API pubbliche del server web

**File modificati:**
- `src/local_ai_bridge/web/server.py`
- `src/local_ai_bridge/web/server_routes.py`
- `src/local_ai_bridge/web/server_uploads.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 01:08:58 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T230858Z-a9cfb08f`
**Messaggio:** fix(web): restore superpower payload export for web startup

**Dettagli:**
- re-export superpower_payload from core.superpowers for backward-compatible imports
- add a startup regression check covering the web project actions import path

**File modificati:**
- `src/local_ai_bridge/core/superpowers.py`
- `tests/test_web_startup_regression.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 01:15:44 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T231544Z-0bd21bee`
**Messaggio:** feat(apply): mostra il nome del file patch nel recap

**Dettagli:**
- aggiunge il nome del file ZIP/Markdown al riepilogo pre-applicazione e al popup di conferma
- conserva il nome dei file Markdown caricati da desktop e Web UI senza mostrarlo per testo incollato
- aggiorna checklist Web, traduzioni e test di regressione dedicati

**File modificati:**
- `src/local_ai_bridge/services/apply.py`
- `src/local_ai_bridge/services/pre_apply.py`
- `src/local_ai_bridge/ui/change_actions.py`
- `src/local_ai_bridge/ui/markdown_update_actions.py`
- `src/local_ai_bridge/web/server_uploads.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_patching.py`
- `tests/test_web_server.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 01:23:50 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T232350Z-1aa23d40`
**Messaggio:** feat(publication): mostra lo storico patch del progetto

**Dettagli:**
- aggiunge nella scheda Pubblicazione uno storico delle modifiche applicate al progetto aperto
- mostra data/ora, tipo applicazione, stato, messaggio salvato, file modificati e riepilogo test
- aggiorna traduzioni italiane/inglesi e test di regressione del layout

**File modificati:**
- `src/local_ai_bridge/ui/tabs/publication.py`
- `src/local_ai_bridge/ui/github_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings_layout.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 01:41:39 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T234139Z-7515cb1f`
**Messaggio:** feat(history): persisti la cronostoria applicativa nel progetto

**Dettagli:**
- aggiunge una cronostoria permanente nel workspace con BRIDGAI_HISTORY.md e .bridgai/applied-history.jsonl
- registra applicazioni ZIP/patch/file completo e rollback con data, stato, messaggio commit, file e test salvati
- aggiorna la scheda Pubblicazione per leggere prima lo storico permanente del progetto e poi le sessioni locali
- aggiunge test di regressione per applicazione, lettura journal e rollback

**File modificati:**
- `src/local_ai_bridge/core/sessions.py`
- `src/local_ai_bridge/services/project_history.py`
- `src/local_ai_bridge/ui/github_actions.py`
- `src/local_ai_bridge/ui/tabs/publication.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_archive_and_sessions.py`

**Test salvati:** 1 ok, 0 problemi
## 2026-07-08 01:45:28 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T234528Z-47330572`
**Messaggio:** feat(history): importa silenziosamente lo storico locale nel progetto

**Dettagli:**
- aggiunge una migrazione idempotente dalle vecchie sessioni locali allo storico permanente del workspace
- ricostruisce BRIDGAI_HISTORY.md e .bridgai/applied-history.jsonl senza duplicare eventi già importati
- mantiene il fallback alle sessioni locali se la migrazione non riesce
- aggiunge test per import automatico e idempotenza

**File modificati:**
- `src/local_ai_bridge/core/sessions.py`
- `src/local_ai_bridge/services/project_history.py`
- `src/local_ai_bridge/ui/github_actions.py`
- `src/local_ai_bridge/ui/tabs/publication.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_archive_and_sessions.py`
## 2026-07-08 01:49:58 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260707T234958Z-d12b05d8`
**Messaggio:** style(publication): modernize applied history list

**Dettagli:**
- replace the plain text applied-history box with an expandable table-style list
- let the project history section fill the available vertical space in the Publication tab
- add compact summary/count labels and row tooltips with full commit details and modified files
- update Italian and English UI strings for the redesigned history panel

**File modificati:**
- `src/local_ai_bridge/ui/tabs/publication.py`
- `src/local_ai_bridge/ui/github_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
## 2026-07-08 02:10:53 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T001053Z-92ce0509`
**Messaggio:** feat(reporting): add read-only external project contexts

**Dettagli:**
- persist and normalize additional context folders in application settings
- add a desktop settings section to manage extra Super-Report contexts
- include configured external projects in Super-Report as read-only reference sections
- add translations and regression tests for settings, layout, and reporting

**File modificati:**
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/services/external_contexts.py`
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings.py`
- `tests/test_reporting_export.py`
- `tests/test_settings_layout.py`
## 2026-07-08 02:17:14 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T001714Z-ee2bf077`
**Messaggio:** fix(reporting): harden additional context boundaries

**Dettagli:**
- reject additional context paths that overlap the current workspace or another context
- ignore symbolic-link context roots during Super-Report generation
- warn in the settings UI when an added context is dropped by normalization limits
- add regression coverage for external context boundary checks

**File modificati:**
- `src/local_ai_bridge/services/external_contexts.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `tests/test_reporting_export.py`
- `tests/test_external_contexts.py`
## 2026-07-08 02:27:31 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T002731Z-983f47db`
**Messaggio:** feat(contexts): allow read-only #scarica requests from additional contexts

**Dettagli:**
- support @context-N:path references in #scarica exports for configured additional contexts
- store external context files under __bridgai_external_contexts__/context-N/ inside export ZIPs
- keep update ZIP targets restricted to the current workspace through protocol guidance and metadata
- document the new read-only context request syntax in Super-Report output
- add regression coverage for external context file export and traversal rejection

**File modificati:**
- `src/local_ai_bridge/services/external_contexts.py`
- `src/local_ai_bridge/services/exporting.py`
- `src/local_ai_bridge/services/reporting.py`
- `tests/test_reporting_export.py`
## 2026-07-08 12:36:01 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T103601Z-8fceeb54`
**Messaggio:** fix(extension): evita nomi probe nascosti per la verifica Download

**Dettagli:**
- usa un file probe senza punto iniziale durante la sincronizzazione della sottocartella Download dell'estensione Chrome
- mantiene compatibilità backend con i vecchi file probe nascosti già accettati
- aggiorna i test di regressione per il nuovo nome probe e per la compatibilità legacy

**File modificati:**
- `src/local_ai_bridge/resources/chrome_extension/background.js`
- `src/local_ai_bridge/web/extension_downloads.py`
- `tests/test_browser_extension.py`
- `tests/test_browser_extension_api.py`
## 2026-07-08 13:22:29 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T112229Z-1efdde46`
**Messaggio:** feat(reports): genera report batch per tutti i progetti

**Dettagli:**
- aggiunge un servizio che scansiona le cartelle di primo livello della root progetti e crea uno ZIP con un report Markdown per progetto
- espone il report batch nella Web UI con download artefatto e salvataggio dello ZIP nella root progetti
- aggiunge il comando desktop nelle impostazioni della cartella progetti Web UI
- copre servizio, endpoint Web e markup con test di regressione

**File modificati:**
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/web/project_actions.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `tests/test_reporting_export.py`
- `tests/test_web_project_management.py`
- `tests/test_web_server.py`
## 2026-07-08 13:27:53 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T112753Z-326d81ed`
**Messaggio:** feat(reports): mostra avanzamento report batch progetti

**Dettagli:**
- aggiunge callback di avanzamento alla generazione batch dei report progetto
- mostra una finestra di progresso desktop con progetto corrente e conteggio X/Y
- aggiunge un pop-up Web UI con flusso dei progetti durante la generazione dello ZIP
- aggiorna i test di regressione per servizio e markup Web UI

**File modificati:**
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/web/project_actions.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `tests/test_reporting_export.py`
- `tests/test_web_project_management.py`
- `tests/test_web_server.py`
## 2026-07-09 00:55:58 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T225558Z-78e18f5a`
**Messaggio:** fix(ui): evita cartelle progetto annidate

**Dettagli:**
- chiede prima il nome del progetto e poi la cartella che lo conterrà
- se l'utente ha già creato una cartella vuota con lo stesso nome, usa quella cartella invece di creare nome/nome
- aggiorna messaggi e traduzioni italiano/inglese
- aggiunge regressioni sul flusso di creazione progetto

**File modificati:**
- `src/local_ai_bridge/ui/main_window.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings_layout.py`
## 2026-07-09 01:26:20 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260708T232620Z-9a9ae7d7`
**Messaggio:** feat(web-ai): add manual DeepSeek Markdown workflow

**Dettagli:**
- aggiunge DeepSeek tra le AI Web preferite con preset Markdown → File Markdown di aggiornamento
- espone DeepSeek nei pulsanti manuali desktop e Web UI e nella tabella di compatibilità
- rafforza il Super-Report per DeepSeek richiedendo un unico bridgai-update.md con blocchi BEGIN_FILE/END_FILE senza testo esterno
- aggiorna traduzioni e test di regressione per preset, UI e compatibilità

**File modificati:**
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/ui/preferred_web_ai_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/web/page.py`
- `src/local_ai_bridge/web/page_assets.py`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`
- `tests/test_web_server.py`
## 2026-07-11 01:28:12 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260710T232812Z-803e7205`
**Messaggio:** fix(windows): ripristina icona e nasconde le console di avvio

**Dettagli:**
- usa l’icona ICO multi-risoluzione per la finestra e la taskbar di Windows
- avvia BridgAI e il server web senza terminali visibili per impostazione predefinita
- salva l’output nei log persistenti e aggiunge controlli diagnostici nelle preferenze avanzate
- consente di riattivare le console al riavvio e aggiorna i test di regressione

**File modificati:**
- `run.py`
- `start_windows.bat`
- `start_windows_hidden.vbs`
- `web_server_force_win.bat`
- `src/local_ai_bridge/app.py`
- `src/local_ai_bridge/core/settings.py`
- `src/local_ai_bridge/web/launcher.py`
- `src/local_ai_bridge/ui/browser_extension_actions.py`
- `src/local_ai_bridge/ui/settings_actions.py`
- `src/local_ai_bridge/ui/tabs/settings.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_settings.py`
- `tests/test_settings_layout.py`
- `tests/test_web_launcher.py`
- `tests/test_web_startup_regression.py`
## 2026-07-11 01:41:10 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260710T234110Z-81dc9e50`
**Messaggio:** fix(windows): mostra l'icona BridgAI nella barra delle applicazioni

**Dettagli:**
- imposta l'identità Windows prima dell'inizializzazione di Qt
- applica l'icona ICO direttamente alla finestra nativa e alla relativa classe Win32
- riapplica l'icona dopo la creazione della finestra per evitare il fallback a pythonw.exe
- aggiunge test mirati per il collegamento delle icone native

**File modificati:**
- `src/local_ai_bridge/app.py`
- `tests/test_windows_taskbar_icon.py`
## 2026-07-11 01:58:56 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260710T235856Z-8037823d`
**Messaggio:** fix(web): stabilize Windows startup and client disconnects

**Dettagli:**
- launch the web server through run.py so the src package is always importable
- pass an absolute source path to diagnostic Windows launches
- drain readiness responses before closing their sockets
- ignore normal client disconnects instead of logging repeated WinError 10053 tracebacks
- add regression coverage for the Windows bootstrap and disconnect handling

**File modificati:**
- `run.py`
- `web_server_force_win.bat`
- `src/local_ai_bridge/web/launcher.py`
- `src/local_ai_bridge/web/server.py`
- `tests/test_web_launcher.py`
- `tests/test_web_startup_regression.py`
- `tests/test_web_disconnects.py`
## 2026-07-11 02:10:31 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260711T001031Z-56c56111`
**Messaggio:** fix(speech): evita WinError 50 nella dettatura Windows

**Dettagli:**
- protegge l'import di sounddevice nei processi Windows senza console
- esegue la conversione FLAC senza ereditare handle standard non validi
- mostra errori di trascrizione più comprensibili
- aggiunge test mirati per import audio, conversione FLAC e WinError 50

**File modificati:**
- `src/local_ai_bridge/services/speech_to_text.py`
- `src/local_ai_bridge/ui/speech_dialog.py`
- `src/local_ai_bridge/resources/i18n_it.json`
- `src/local_ai_bridge/resources/i18n_en.json`
- `tests/test_speech_to_text.py`
## 2026-07-11 02:13:32 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260711T001332Z-569c2bc8`
**Messaggio:** fix(speech): abilita l'inserimento della trascrizione nel task

**Dettagli:**
- corregge il controllo dello stato di registrazione nella modale di dettatura
- abilita il pulsante Inserisci nel task quando il testo è presente e la registrazione è terminata
- aggiunge test di regressione per lo stato del pulsante

**File modificati:**
- `src/local_ai_bridge/ui/speech_dialog.py`
- `tests/test_speech_dialog.py`
## 2026-07-11 02:20:17 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260711T002017Z-d1233f9c`
**Messaggio:** feat(desktop): add subtle clear buttons to workflow text areas

**Dettagli:**
- add hover-only clear controls to the request and AI-response editors
- render a small theme-aware vector X with accessible tooltip text
- add Italian and English translations and layout regression checks

**File modificati:**
- `src/local_ai_bridge/ui/tabs/workflow.py`
- `src/local_ai_bridge/ui/widgets.py`
- `src/local_ai_bridge/resources/i18n_en.json`
- `src/local_ai_bridge/resources/i18n_it.json`
- `tests/test_settings_layout.py`
## 2026-07-13 12:17:25 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260713T101725Z-b6c72192`
**Messaggio:** feat(history): persist Markdown update metadata

**Dettagli:**
- extract commit-message.md metadata from Markdown update files without applying it to the workspace
- propagate the commit message through desktop, Web upload, and pasted-text flows into project history
- document the Markdown metadata block and add regression coverage for parsing, history, reports, and Web parity

**File modificati:**
- `src/local_ai_bridge/services/markdown_exchange.py`
- `src/local_ai_bridge/services/reporting.py`
- `src/local_ai_bridge/services/text_file_planner.py`
- `src/local_ai_bridge/services/text_update_import.py`
- `src/local_ai_bridge/web/bridge_actions.py`
- `tests/test_archive_and_sessions.py`
- `tests/test_markdown_exchange.py`
- `tests/test_reporting_export.py`
- `tests/test_text_file_operations.py`
- `tests/test_text_update_import.py`
- `tests/test_web_server.py`
## 2026-07-13 12:27:16 ora legale Europa occidentale — ZIP — applicata

**Sessione:** `20260713T102716Z-f9a12704`
**Messaggio:** fix(github): abilita la prima pubblicazione da BridgAI

**Dettagli:**
- configura localmente solo i campi mancanti dell'identità autore Git
- ricava dall'account GitHub attivo un indirizzo noreply basato sull'ID
- configura GitHub CLI come credential helper prima del push
- propaga gli errori di git status senza interpretarli come modifiche
- aggiunge test di regressione per workspace Git non inizializzati

**File modificati:**
- `src/local_ai_bridge/services/git.py`
- `src/local_ai_bridge/services/github.py`
- `tests/test_git_service.py`
