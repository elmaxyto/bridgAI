# BridgAI

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Licenza](https://img.shields.io/badge/Licenza-MIT-green)
![Stato](https://img.shields.io/badge/stato-stabile-brightgreen)

**BridgAI è un ponte locale, controllabile e verificabile tra le AI Web e i workspace di sviluppo.**

Permette di generare il contesto del progetto, esportare esclusivamente i file richiesti, analizzare ZIP o patch proposte dall'AI, visualizzare il diff, applicare le modifiche in modo transazionale, eseguire i test rilevati e ripristinare lo stato precedente quando necessario.

BridgAI **non** concede al browser o all'AI Web accesso diretto al computer.

[English](README.md)

---

## Perché BridgAI?

L'uso di un assistente AI Web su un progetto locale richiede spesso di copiare manualmente file, istruzioni, patch e risultati tra browser e filesystem.

BridgAI rende questo flusso esplicito e controllato:

1. selezione del progetto locale;
2. generazione di un Super-Report strutturato;
3. invio del report all'assistente AI Web;
4. esportazione dei soli file richiesti esplicitamente;
5. importazione dello ZIP, della patch o del file completo restituito;
6. verifica del diff prima di qualsiasi scrittura;
7. applicazione con dati di ripristino persistenti;
8. esecuzione dei controlli rilevati;
9. rollback esplicito quando necessario.

## Sviluppato attraverso il proprio flusso

BridgAI è stato sviluppato in modo iterativo usando BridgAI stesso. La prima versione 0.1 ha fornito il flusso di report, esportazione controllata, revisione e applicazione che è stato poi usato per realizzare le versioni successive fino alla 1.1.1, compresi l’attuale flusso dei messaggi di commit Git, i superpoteri, le note progetto e i perfezionamenti del flusso con estensione browser.

Questa esperienza costituisce una validazione end-to-end concreta del caso d’uso principale dell’applicazione. Integra, ma non sostituisce, i test automatici ripetibili.

## Esclusioni locali dal report

Crea `.bridgai/ignore` nel workspace per omettere dal Super-Report file di progetto rumorosi senza modificare `.gitignore`. Usa un glob per riga; le righe vuote e quelle che iniziano con `#` vengono ignorate. Esempio:

```text
dist/
*.sqlite
docs/generated/**
```

Le regole agiscono soltanto sul contesto dello scanner/report, compresi albero, riepiloghi, file candidati e note prioritarie. Non indeboliscono i controlli sui percorsi sensibili e non modificano la sicurezza di ZIP, patch, applicazione o accesso al filesystem.

## Modello di sicurezza

- Il programma locale è l'unica autorità sul filesystem.
- Le AI Web non ricevono accesso diretto ai file.
- I percorsi di destinazione e gli archivi vengono validati.
- I percorsi sensibili, come file di ambiente e credenziali, vengono bloccati.
- Gli ZIP vengono controllati contro path traversal e contenuti pericolosi.
- Nessuna modifica viene scritta durante la sola analisi.
- L'applicazione delle modifiche è transazionale.
- Backup e cronologia persistente consentono il ripristino.
- Il rollback è sempre esplicito.
- Staging, commit, pull, merge e push Git non sono automatici.

Controlla sempre ogni modifica proposta prima di applicarla. BridgAI riduce il rischio, ma non può garantire che il codice generato da un'AI sia corretto o sicuro.

## Funzioni principali

- Interfaccia desktop PySide6
- Interfaccia web locale
- Estensione browser opzionale per scambi assistiti e controllati
- Missioni operative con cronologia, risultati e artefatti persistenti
- Provider configurabili per assistenti AI locali e cloud
- Prompt globali e per progetto ed esclusioni dal report
- Flussi ZIP, Markdown e operazioni testuali su file completi
- Autenticazione a due fattori TOTP opzionale per l’accesso Web remoto
- Lingua, tema e dettatura persistenti nella Web UI
- Generazione del Super-Report
- Esportazione controllata tramite protocollo `#scarica`
- Analisi ZIP e anteprima diff
- Compatibilità legacy con patch SEARCH/REPLACE
- Sostituzione di file completi
- Applicazione transazionale
- Backup persistenti e rollback
- Rilevamento ed esecuzione dei test del progetto
- Cronologia delle sessioni e risultati post-applicazione
- Metadato opzionale `commit-message.md` negli ZIP generati dall’AI
- Bozze di commit basate sulle modifiche Git reali e sulle note delle sessioni
- Staging e creazione del commit soltanto dopo revisione e conferma esplicita
- Strumenti Git locali
- Integrazione opzionale con GitHub CLI
- Supporto opzionale al flusso Google Drive
- Interfaccia italiana e inglese
- Tema chiaro e scuro
- Launcher per Windows, Linux e macOS

## Requisiti

- Python 3.11 o successivo
- Ambiente desktop compatibile con PySide6
- Connessione Internet durante la prima installazione delle dipendenze
- Facoltativo: [GitHub CLI](https://cli.github.com/) per le operazioni GitHub

La dettatura dipende dal sistema operativo, dai permessi del microfono e dalle librerie audio disponibili.

## Avvio rapido

### Windows

```bat
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe run.py
```

Sono inoltre presenti:

```text
Avvia_BridgAI.bat
start_bridgai_windows.bat
```

### Linux e macOS

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python run.py
```

È inoltre presente:

```text
start_bridgai_linux_mac.sh
```

### Comandi installati

```bash
local-ai-bridge
local-ai-bridge-web
```

Il package Python e gli entry point storici sono mantenuti per retrocompatibilità. Il nome pubblico dell'applicazione è **BridgAI**.

## Flusso tipico

1. Seleziona il workspace che BridgAI potrà analizzare.
2. Descrivi il task e genera il Super-Report.
3. Invia il report all'assistente AI Web.
4. Esporta esclusivamente i file richiesti, per esempio:

```text
#scarica src/esempio.py, tests/test_esempio.py
```

5. Importa lo ZIP, che può contenere nella radice il metadato `commit-message.md`, oppure prepara la patch o il file completo.
6. Controlla il piano e il diff. Il metadato del commit non viene applicato al workspace.
7. Applica il piano soltanto dopo la revisione ed esegui i test rilevati.
8. Quando sei pronto, genera e modifica una bozza di commit basata sullo stato Git reale e sulle note delle sessioni applicate.
9. Conferma esplicitamente staging e creazione del commit.
10. Esegui il push separatamente dopo aver controllato lo stato del repository, oppure usa il rollback esplicito quando necessario.

## Interfaccia web

```bash
local-ai-bridge-web
```

oppure:

```bash
python -m local_ai_bridge.web
```

Il server è destinato all'uso su localhost. Non esporlo direttamente a reti non affidabili.

## Git e GitHub

BridgAI può inizializzare Git, mostrare stato, diff e remote, leggere i suggerimenti di commit dai metadati degli ZIP importati e generare una bozza modificabile dalle modifiche reali del working tree e dalle note delle sessioni. Dopo una conferma separata può aggiungere le modifiche all’indice e creare il commit.

L’integrazione con GitHub CLI può creare o collegare un repository e inviare il branch corrente dopo conferma esplicita. BridgAI non esegue staging, commit, pull, merge o push senza un’azione deliberata dell’utente.

## Sviluppo e test

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest
python -m compileall -q src tests run.py
python -m pytest -q
```

Diagnostica del report:

```bash
python run.py --check-report .
```

## Privacy

BridgAI opera localmente. I dati lasciano il computer soltanto quando l'utente decide di copiarli o caricarli su un servizio esterno.

Prima di condividere report o archivi, controlla il contenuto e non condividere mai credenziali, token, segreti, dati personali o codice riservato involontariamente.

## Limiti noti

- Il flusso è volutamente supervisionato e non completamente autonomo.
- Il comportamento grafico richiede verifiche manuali sui diversi sistemi.
- La dettatura dipende dalla configurazione locale.
- L'installazione da sorgente è attualmente il metodo principale di distribuzione.
- Le integrazioni esterne dipendono dai rispettivi client e sistemi di autenticazione.

## Contribuire

Leggi [CONTRIBUTING.md](CONTRIBUTING.md) prima di aprire una pull request.

## Sicurezza

Non pubblicare vulnerabilità in una issue. Leggi [SECURITY.md](SECURITY.md) e usa la segnalazione privata di GitHub quando disponibile.

## Cronologia

Consulta [CHANGELOG.md](CHANGELOG.md) e i documenti storici `AGGIORNAMENTO_*.md`.

## Licenza

BridgAI è distribuito con licenza [MIT](LICENSE).

### Prompt globale e prompt per progetto

Nella scheda **Impostazioni** puoi salvare istruzioni persistenti da includere nel Super-Report. Il prompt globale vale per tutti i workspace; il prompt del progetto corrente viene salvato in `.bridgai/project.json`. Un interruttore permette di escludere temporaneamente entrambe le istruzioni dal report senza cancellarle.

Le istruzioni personalizzate e l’editor di `.bridgai/ignore` sono disponibili nella scheda **Avanzato**. Le impostazioni già salvate continuano a essere applicate anche quando l’interfaccia è in modalità super semplice, ma non sono modificabili da quel flusso.
