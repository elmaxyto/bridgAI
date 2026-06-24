# BridgAI — Piano generale per la Modalità Operativa

**Stato del documento:** bozza iniziale approvata concettualmente  
**Data iniziale:** 23 giugno 2026  
**Progetto:** BridgAI  
**Versione di partenza:** 1.0.0  
**Ruolo del documento:** fonte principale per la progettazione e l’implementazione progressiva della Modalità Operativa

---

## 1. Scopo del documento

Questo documento raccoglie la visione, le decisioni architetturali, i vincoli e il piano progressivo per estendere BridgAI con una nuova Modalità Operativa.

Deve essere utilizzato come riferimento nelle future sessioni di progettazione e sviluppo.

L’obiettivo è evitare di perdere decisioni importanti tra conversazioni diverse e impedire che l’implementazione proceda attraverso modifiche isolate prive di una direzione comune.

Il documento deve essere aggiornato quando:

- viene approvata una nuova decisione architetturale;
- viene completata una fase;
- emerge un vincolo tecnico rilevante;
- una decisione precedente viene modificata;
- viene scoperto un rischio non considerato;
- cambia il perimetro dell’MVP.

Non deve essere aggiornato con ipotesi non ancora approvate come se fossero decisioni definitive.

---

## 2. Visione generale

BridgAI attualmente è principalmente uno strumento che permette di costruire e modificare soluzioni software attraverso assistenti AI Web, mantenendo il controllo locale sui file.

Il flusso attuale può essere riassunto così:

```text
Richiesta dell’utente
→ generazione del contesto del progetto
→ proposta di codice, patch o ZIP
→ revisione locale
→ applicazione controllata
→ test, cronologia e rollback
```

Questo flusso costituisce la futura **Modalità Sviluppo**.

La nuova Modalità Operativa deve aggiungere un secondo flusso:

```text
Richiesta dell’utente
→ selezione degli input
→ definizione del risultato atteso
→ piano operativo
→ scelta o generazione dello strumento necessario
→ autorizzazione
→ esecuzione locale
→ verifica
→ consegna dei risultati
```

La differenza fondamentale è:

> Nella Modalità Sviluppo il risultato principale è lo strumento.

> Nella Modalità Operativa lo strumento è un mezzo interno e il risultato principale è il lavoro completato.

Esempio:

### Modalità Sviluppo

Richiesta:

> Crea un programma che riassuma tutti i PDF presenti in una cartella.

Risultato:

- sorgenti del programma;
- dipendenze;
- test;
- documentazione;
- applicazione riutilizzabile.

### Modalità Operativa

Richiesta:

> Riassumi questi venti PDF in una pagina ciascuno.

Risultato:

- venti riassunti;
- eventuale documento riepilogativo;
- elenco dei PDF non elaborati;
- registro dell’esecuzione.

Il programma usato per produrre il risultato può essere temporaneo, nascosto all’utente non tecnico oppure salvato come procedura riutilizzabile.

---

## 3. Principio fondamentale

La nuova modalità deve essere **aggiunta**, non deve sostituire o riscrivere il funzionamento attuale.

La Modalità Sviluppo di BridgAI viene considerata funzionalmente stabile.

Durante la prima evoluzione verso la Modalità Operativa, la Modalità Sviluppo deve ricevere principalmente:

- correzioni di bug;
- correzioni di sicurezza;
- risoluzione di regressioni;
- piccoli miglioramenti compatibili;
- adeguamenti strettamente necessari ai servizi condivisi.

Non devono essere introdotte rifattorizzazioni profonde del flusso esistente soltanto per adattarlo alla nuova modalità.

Il nuovo sviluppo deve rispettare questa regola:

> La Modalità Operativa deve appoggiarsi ai servizi condivisi di BridgAI senza trasformare il flusso di sviluppo esistente nel proprio motore interno monolitico.

---

## 4. Terminologia approvata

### Modalità Sviluppo

Modalità dedicata alla costruzione e modifica di:

- programmi;
- applicazioni;
- siti;
- script;
- automazioni;
- repository software.

Descrizione indicativa per l’interfaccia:

> Crea o modifica programmi, siti, script e automazioni. BridgAI prepara codice, patch, test e aggiornamenti del progetto.

### Modalità Operativa

Modalità dedicata al completamento di attività sui file dell’utente.

Descrizione indicativa per l’interfaccia:

> Lavora sui tuoi documenti e dati per produrre direttamente report, analisi, fogli, presentazioni e altri risultati.

Il termine “Modalità Produzione” viene evitato nell’interfaccia perché potrebbe essere confuso con:

- ambiente di produzione;
- deployment;
- pubblicazione software;
- rilascio di una versione.

Come identificatori interni si potranno usare valori simili a:

```text
development
operations
```

La scelta definitiva degli identificatori dovrà essere verificata durante l’implementazione.

---

## 5. Esperienza al primo avvio

Al primo avvio BridgAI deve chiedere:

> Che cosa vuoi fare con BridgAI?

L’utente deve poter scegliere tra due opzioni.

### Modalità Sviluppo

> Crea o modifica programmi, siti, script e automazioni.

### Modalità Operativa

> Lavora sui tuoi file e ottieni direttamente documenti, analisi e altri risultati.

Deve essere presente una nota esplicita:

> Puoi cambiare modalità in qualsiasi momento dalle Impostazioni.

La scelta iniziale:

- non deve essere irreversibile;
- non deve disabilitare definitivamente funzioni;
- non deve trasformare i workspace;
- deve determinare il flusso principale mostrato all’avvio;
- deve essere salvata nelle impostazioni dell’applicazione.

Il cambio modalità dovrebbe avvenire senza reinstallazione.

La possibilità di applicarlo senza riavvio deve essere verificata tecnicamente. Se il cambio immediato risultasse rischioso nella prima versione, è accettabile richiedere un riavvio esplicito, purché l’interfaccia lo comunichi chiaramente.

---

## 6. Preferenza dell’utente e tipo di workspace

La modalità principale dell’interfaccia e la natura del workspace non sono necessariamente la stessa cosa.

Esempio:

- un utente che usa normalmente la Modalità Operativa può aprire un progetto Python;
- uno sviluppatore può usare occasionalmente la Modalità Operativa per creare un report;
- uno stesso utente può mantenere contemporaneamente progetti software e attività documentali.

Devono quindi restare separati i concetti di:

### Modalità principale

Preferenza globale che stabilisce quale esperienza viene mostrata normalmente all’apertura di BridgAI.

### Tipo di workspace

Informazione facoltativa che descrive la natura del singolo workspace:

- software;
- operativo;
- automazione;
- generico.

Il tipo di workspace non deve essere introdotto obbligatoriamente nella prima fase, ma l’architettura non deve impedire di aggiungerlo successivamente.

BridgAI potrà in futuro suggerire:

> Questo workspace sembra contenere un progetto software. Vuoi aprirlo con il flusso di sviluppo?

Il suggerimento non dovrà cambiare automaticamente la preferenza globale.

---

## 7. Architettura generale desiderata

BridgAI deve restare una sola applicazione con servizi comuni e due esperienze principali.

```text
BridgAI
├── servizi condivisi
│   ├── impostazioni
│   ├── workspace
│   ├── sicurezza
│   ├── AI e provider
│   ├── cronologia
│   ├── esecuzione in background
│   ├── file temporanei
│   └── artefatti
│
├── Modalità Sviluppo
│   ├── Super-Report
│   ├── #scarica
│   ├── ZIP e patch
│   ├── applicazione
│   ├── rollback
│   ├── test
│   └── Git e GitHub
│
└── Modalità Operativa
    ├── richiesta
    ├── input
    ├── piano
    ├── autorizzazioni
    ├── esecuzione
    ├── verifica
    └── risultati
```

La Modalità Operativa deve essere implementata attraverso nuovi moduli chiaramente separati.

Si deve evitare di introdurre numerose condizioni sparse nei componenti esistenti:

```python
if mode == "development":
    ...
else:
    ...
```

La separazione preferita è concettualmente simile a:

```text
MainWindow
├── DevelopmentView
├── OperationsView
└── servizi condivisi
```

La forma concreta dovrà essere determinata analizzando i file reali del progetto prima dell’implementazione.

---

## 8. Funzioni della Modalità Sviluppo da preservare

Le seguenti funzioni costituiscono la baseline da non rompere:

- creazione di un progetto;
- apertura di un workspace;
- cronologia dei progetti recenti;
- generazione del Super-Report;
- selezione euristica dei file candidati;
- protocollo `#scarica`;
- esportazione controllata dei file;
- gestione degli ZIP;
- gestione delle patch SEARCH/REPLACE;
- sostituzione di file completi;
- anteprima delle modifiche;
- applicazione transazionale;
- backup;
- rollback;
- test rilevati;
- interpretazione degli esiti dei test;
- Git locale;
- GitHub;
- prompt personalizzati;
- prompt preset;
- AI Web;
- estensione browser;
- interfaccia desktop;
- interfaccia Web;
- impostazioni esistenti;
- sicurezza dei percorsi;
- blocco dei file sensibili.

I test esistenti rappresentano una parte importante del contratto di compatibilità.

Ogni modifica a servizi condivisi dovrà verificare che la Modalità Sviluppo continui a rispettare questo contratto.

---

## 9. Definizione di missione operativa

L’unità principale della Modalità Operativa sarà denominata provvisoriamente **missione**.

Una missione rappresenta un’attività richiesta dall’utente.

Esempi:

- riassumere una serie di PDF;
- unire fogli Excel;
- creare un report mensile;
- generare documenti da un modello;
- classificare file;
- rinominare documenti;
- produrre una presentazione;
- confrontare due versioni di un documento.

Una missione dovrebbe contenere progressivamente:

- identificativo;
- titolo;
- richiesta originale;
- workspace;
- input autorizzati;
- output previsti;
- piano;
- strumenti necessari;
- permessi;
- stato;
- log;
- risultati;
- errori;
- data di creazione;
- data di esecuzione;
- eventuale procedura riutilizzabile.

Non tutti questi elementi devono essere implementati nella prima versione.

---

## 10. Flusso operativo ideale

Il flusso completo desiderato è:

### 10.1 Richiesta

L’utente descrive il risultato che vuole ottenere.

Esempio:

> Leggi i PDF presenti nella cartella selezionata e crea un riassunto di circa una pagina per ogni documento.

### 10.2 Selezione degli input

L’utente seleziona:

- file;
- cartelle;
- eventuali modelli;
- eventuali dati aggiuntivi.

Gli input devono essere esplicitamente visibili.

### 10.3 Definizione degli output

BridgAI identifica o chiede:

- formato desiderato;
- cartella di destinazione;
- numero previsto di risultati;
- convenzione dei nomi;
- eventuale documento riepilogativo.

### 10.4 Piano

Prima dell’esecuzione viene mostrato un piano leggibile.

Esempio:

```text
Input:
- 20 file PDF

Operazioni:
1. Verificare quali PDF contengono testo.
2. Estrarre il contenuto.
3. Generare un riassunto per ogni documento.
4. Creare i file nella cartella output.
5. Verificare che ogni input abbia un risultato.

Output:
- 20 file DOCX
- 1 rapporto sugli eventuali errori
```

### 10.5 Scelta dello strumento

BridgAI può:

1. usare una skill nativa;
2. combinare più skill native;
3. utilizzare una procedura già approvata;
4. generare un programma specifico;
5. richiedere un’integrazione esterna autorizzata.

### 10.6 Autorizzazione

L’utente deve vedere cosa verrà permesso.

Esempio:

```text
Consentito:
- leggere 20 PDF nella cartella input;
- creare file nella cartella output.

Non consentito:
- modificare gli originali;
- cancellare file;
- accedere alla rete;
- eseguire programmi esterni non dichiarati.
```

### 10.7 Esecuzione

BridgAI esegue la missione e mostra:

- stato;
- avanzamento;
- avvisi;
- errori;
- eventuali input non elaborati.

### 10.8 Verifica

Il sistema controlla almeno:

- esistenza degli output;
- quantità degli output;
- destinazioni;
- errori;
- file prodotti non previsti.

Controlli più specifici potranno essere aggiunti in base al formato.

### 10.9 Consegna

L’utente riceve:

- elenco dei risultati;
- apertura della cartella;
- possibilità di aprire i singoli file;
- riepilogo dell’esecuzione;
- eventuali problemi.

### 10.10 Riutilizzo

In futuro BridgAI potrà chiedere:

> Vuoi salvare questa procedura per riutilizzarla con altri file?

---

## 11. Strategie di esecuzione

La Modalità Operativa dovrà essere ibrida.

### 11.1 Skill native

Strumenti implementati e testati direttamente nel progetto.

Esempi futuri:

- lettura PDF;
- creazione DOCX;
- lettura e creazione XLSX;
- elaborazione CSV;
- creazione PPTX;
- conversione di documenti;
- classificazione file;
- generazione di archivi;
- validazione degli output.

Le skill native devono essere preferite quando disponibili.

### 11.2 Procedure riutilizzabili

Automazioni già generate, controllate e salvate.

Una procedura potrà ricevere nuovi input senza essere riscritta ogni volta.

### 11.3 Programmi generati per una missione

Quando le skill disponibili non bastano, l’AI può generare un piccolo programma specifico.

Il programma generato deve dichiarare:

- entry point;
- input;
- output;
- dipendenze;
- permessi;
- accesso alla rete;
- uso di processi esterni;
- possibilità di modificare o cancellare file.

L’esecuzione di codice generato non deve avvenire automaticamente senza revisione e approvazione.

---

## 12. Programmi effimeri

Un programma generato per una singola missione potrà essere trattato come programma effimero.

Struttura concettuale:

```text
missione/
├── manifest.json
├── plan.md
├── run.py
├── requirements.txt
├── logs/
└── artifacts/
```

Il formato concreto non è ancora approvato.

Un programma effimero:

- viene creato per un compito specifico;
- ha accesso limitato;
- non modifica gli input per impostazione predefinita;
- produce output in una destinazione autorizzata;
- registra gli errori;
- può essere eliminato dopo l’esecuzione;
- può essere salvato come procedura solo su richiesta dell’utente.

---

## 13. Sicurezza della Modalità Operativa

La Modalità Operativa non deve equivalere all’esecuzione libera di codice generato dall’AI.

Ogni missione deve poter dichiarare o derivare permessi per:

- lettura;
- creazione;
- modifica;
- cancellazione;
- rete;
- browser;
- subprocess;
- clipboard;
- dipendenze;
- servizi esterni.

Principi iniziali:

### Input protetti

Gli input non devono essere modificati per impostazione predefinita.

### Output separati

I risultati devono essere creati in una cartella di output esplicita.

### Nessuna cancellazione predefinita

Le missioni non devono cancellare file senza autorizzazione specifica.

### Rete disattivata quando non necessaria

L’accesso alla rete deve essere esplicito e motivato.

### Dipendenze controllate

Non devono essere installati automaticamente pacchetti arbitrari indicati dall’AI.

### Percorsi limitati

Una missione deve poter accedere soltanto alle destinazioni autorizzate.

### Tracciabilità

Devono essere registrati almeno:

- missione;
- procedura utilizzata;
- input;
- output;
- stato;
- errori;
- momento dell’esecuzione.

Il livello esatto di isolamento del processo dovrà essere valutato tecnicamente.

---

## 14. Dipendenze documentali

La Modalità Operativa completa richiederà probabilmente dipendenze ulteriori rispetto a quelle attuali.

Esempi possibili:

- PDF testuali;
- DOCX;
- XLSX;
- CSV;
- PPTX;
- OCR;
- conversioni.

Non è ancora deciso se queste dipendenze debbano essere:

- incluse nell’installazione principale;
- organizzate come pacchetti opzionali;
- installate in un ambiente dedicato;
- distribuite attraverso plugin;
- richieste soltanto quando necessarie.

La decisione deve tenere conto di:

- dimensione dell’installazione;
- compatibilità Windows, Linux e macOS;
- affidabilità;
- licenze;
- aggiornamenti;
- sicurezza;
- facilità per utenti non tecnici.

Il progetto non deve aggiungere subito tutte le dipendenze documentali.

---

## 15. Intelligenza artificiale per le attività operative

Alcune attività possono essere completate interamente con strumenti locali deterministici.

Esempi:

- unione di CSV;
- rinomina di file;
- creazione di documenti da template;
- calcoli;
- conversioni.

Altre attività richiedono un modello linguistico.

Esempi:

- riassunti;
- classificazione semantica;
- riscrittura;
- estrazione di concetti;
- confronto testuale avanzato.

Possibili fonti AI:

- modello locale;
- provider cloud tramite API;
- AI Web attraverso il flusso BridgAI;
- combinazione delle precedenti.

Ogni soluzione deve dichiarare chiaramente quando i dati vengono inviati all’esterno.

La Modalità Operativa non deve presumere che tutti gli utenti abbiano:

- una chiave API;
- un modello locale;
- hardware potente;
- autorizzazione a inviare documenti aziendali nel cloud.

---

## 16. MVP operativo corrente

Il primo MVP locale ha validato missioni, autorizzazioni, stati, artefatti e output attraverso inventario e unione CSV. Queste procedure restano disponibili come strumenti avanzati, ma non rappresentano più l’esperienza principale.

Il MVP corrente deve dimostrare in modo affidabile il ciclo Web-first:

```text
categoria e richiesta
→ input autorizzati
→ cartella risultati
→ conferma del caricamento
→ pacchetto ZIP della missione
→ AI Web
→ ZIP dei risultati
→ verifica
→ importazione controllata
```

### Funzioni minime del flusso principale

- apertura della Modalità Operativa con un’interfaccia semplice;
- scelta del tipo di lavoro;
- descrizione libera del risultato desiderato;
- selezione di file o cartelle autorizzati;
- selezione della cartella risultati;
- scelta del provider Web;
- visualizzazione del piano e dell’avviso privacy;
- creazione di uno ZIP con manifest, istruzioni e soli input autorizzati;
- passaggio automatico tramite estensione quando supportato;
- passaggio manuale sempre disponibile;
- ricezione o selezione dello ZIP finale;
- anteprima dei risultati;
- importazione senza traversal, symlink o sovrascritture;
- registrazione della missione e dell’esito.

### Categorie iniziali

- documenti e PDF;
- fogli di calcolo e dati;
- presentazioni;
- immagini e grafica;
- scrittura e relazioni;
- organizzazione di file;
- richiesta personalizzata.

Le categorie non sono motori locali: sono preset semantici che aiutano a formulare la missione e il contratto del risultato per l’AI Web.

### Strumenti locali precedenti

L’inventario tecnico e l’unione CSV:

- restano compatibili con le missioni già salvate;
- rimangono disponibili in una sezione avanzata chiusa;
- non vengono proposti come percorso principale;
- possono essere usati per lavori deterministici o diagnostici.

Quando l’AI segnala che serve un programma dedicato, BridgAI deve preparare una specifica e trasferirla alla Modalità Sviluppo. La creazione, revisione e prova del programma avvengono nel flusso di sviluppo esistente; nessun codice generato viene eseguito automaticamente dalla missione.

---

## 17. Roadmap

### Fase 0 — Documento e baseline

Obiettivi:

- approvare questo documento;
- eseguire i test attuali;
- registrare la baseline;
- identificare i comportamenti della Modalità Sviluppo da preservare;
- evitare nuove grandi funzionalità nel flusso sviluppo.

Stato: parzialmente completata. Il documento e la baseline architetturale sono stati analizzati; la suite completa deve ancora essere rieseguita sul workspace integrale.

### Fase 1 — Introduzione delle modalità

Obiettivi:

- aggiungere la preferenza della modalità;
- introdurre la scelta al primo avvio;
- aggiungere la scelta nelle Impostazioni;
- permettere il cambio modalità;
- mantenere invariata la Modalità Sviluppo;
- creare una schermata iniziale separata per la Modalità Operativa;
- aggiungere traduzioni italiane e inglesi;
- aggiungere test di regressione.

La schermata operativa può inizialmente essere informativa e non eseguire ancora missioni complete.

Stato: implementata il 24 giugno 2026 nel codice desktop, con validazione mirata completata e verifica completa della suite ancora richiesta sul workspace integrale.

### Fase 2 — Modello minimo di missione

Obiettivi:

- definire i dati di una missione;
- descrivere input e output;
- gestire gli stati;
- creare una cronologia minima;
- separare le missioni dalle sessioni di modifica software;
- definire la cartella degli artefatti.

Stato: implementata il 24 giugno 2026 nel codice desktop, con validazione mirata del modello completata e verifica completa della suite ancora richiesta sul workspace integrale. Le missioni vengono salvate nell’area dati di BridgAI, con input autorizzati, output dichiarato, stato, cronologia e cartella artefatti gestita; l’esecuzione resta intenzionalmente rinviata alla Fase 3.

### Fase 3 — Esecutore operativo minimo

Obiettivi:

- eseguire una procedura controllata;
- limitare input e output;
- acquisire log ed errori;
- registrare i risultati;
- mostrare gli artefatti prodotti;
- evitare la modifica degli originali.

Stato: implementata il 24 giugno 2026 nel codice desktop con una procedura nativa minima di inventario degli input. L’esecutore valida l’esistenza e la separazione di input, output e artefatti, non legge il contenuto dei file, non modifica gli originali, non usa rete o processi esterni, crea un nuovo risultato JSON con nome univoco e registra log, errori e metadati di esecuzione. La verifica completa della suite e la prova manuale della GUI restano richieste sul workspace integrale.

### Fase 4 — Primo caso d’uso reale

Obiettivi:

- implementare un’attività end-to-end;
- verificare l’esperienza con utenti non tecnici;
- controllare qualità e sicurezza;
- raccogliere i limiti emersi.

Stato: implementata il 24 giugno 2026 con la procedura nativa **Unisci e riepiloga CSV**. La missione salva la procedura scelta, mostra un piano prima dell’esecuzione, legge soltanto i CSV autorizzati dopo conferma, produce un CSV unificato e un riepilogo senza modificare gli originali o sovrascrivere file esistenti. L’inventario tecnico della Fase 3 resta disponibile per compatibilità. La prova manuale della GUI e la suite completa restano da eseguire nel workspace integrale.

### Fase 5 — Missioni tramite AI Web

Obiettivi:

- rendere l’AI Web il percorso principale della Modalità Operativa;
- scegliere una categoria di lavoro e un provider;
- creare un pacchetto ZIP con istruzioni, manifest e soli input autorizzati;
- riutilizzare l’estensione Chrome per il passaggio automatico a ChatGPT;
- offrire un passaggio manuale compatibile con ChatGPT, Gemini e Claude;
- richiedere uno ZIP di risultati con un contratto semplice e verificabile;
- mostrare l’anteprima e importare soltanto dentro la cartella autorizzata;
- proporre il passaggio guidato alla Modalità Sviluppo quando serve un nuovo strumento.

Stato: implementata il 24 giugno 2026 nel codice desktop. La Modalità Operativa è ora Web-first: categorie, richiesta, input, cartella risultati e provider costituiscono il flusso principale; inventario e unione CSV restano nascosti come strumenti locali avanzati. ChatGPT può usare l’estensione esistente per allegare automaticamente il pacchetto e intercettare lo ZIP finale; Gemini e Claude usano il passaggio manuale. Lo ZIP ricevuto viene validato, associato alla missione e importato senza sovrascrivere file esistenti. Restano richiesti il collaudo manuale della GUI e la verifica nel workspace integrale.

### Fase 6 — Preset operativi e compatibilità dei provider

Possibili sviluppi:

- modelli di richiesta per documenti, fogli di calcolo, presentazioni, immagini e scrittura;
- esempi guidati e formati di output consigliati;
- limiti e capacità dichiarati per ogni provider Web;
- adattatori specifici per ChatGPT, Gemini e Claude;
- gestione più chiara dei provider che non producono ZIP scaricabili;
- ripresa e reinvio di una missione già salvata.

Stato: non iniziata.

### Fase 7 — Strumenti riutilizzabili e ponte con la Modalità Sviluppo

Obiettivi:

- riconoscere la richiesta dell’AI di creare uno strumento dedicato;
- trasferire alla Modalità Sviluppo una specifica tecnica già compilata;
- revisionare e collaudare il programma attraverso il flusso di sviluppo esistente;
- registrare strumenti approvati e renderli riutilizzabili;
- mantenere sempre separata la creazione del codice dalla sua esecuzione operativa.

Stato: non iniziata; la Fase 5 introduce soltanto il primo passaggio guidato della specifica, senza eseguire codice generato.

### Fase 8 — Integrazioni avanzate

Possibili sviluppi:

- OCR;
- browser;
- servizi aziendali;
- email in bozza;
- cartelle cloud;
- schedulazione;
- trigger;
- approvazioni multiple.

Stato: futuro.

---

## 18. Criteri di completamento della Fase 1

La Fase 1 sarà considerata completata quando:

- una nuova installazione chiede la modalità principale;
- la scelta viene salvata;
- l’utente può cambiarla dalle Impostazioni;
- la Modalità Sviluppo apre il flusso attuale;
- la Modalità Operativa apre una propria schermata;
- il cambio non modifica i file del workspace;
- le traduzioni sono disponibili in italiano e inglese;
- le impostazioni precedenti restano compatibili;
- una configurazione vecchia senza il nuovo campo usa un comportamento predefinito documentato;
- i test della Modalità Sviluppo continuano a passare;
- sono presenti test specifici per la selezione delle modalità.

### Criteri di completamento della Fase 2

La Fase 2 sarà considerata completata quando:

- una missione contiene identificativo, titolo, richiesta originale, workspace associato, input, output, stato e date;
- i metadati delle missioni sono salvati fuori dal workspace e separati dalle sessioni di modifica software;
- ogni missione dispone di una cartella artefatti interna e controllata;
- il salvataggio non legge, copia o modifica gli input e non scrive nella cartella di output;
- una missione incompleta resta in bozza e una missione con input e output risulta pronta;
- le transizioni di stato incoerenti vengono rifiutate;
- la cronologia resta leggibile dopo il riavvio e ignora in sicurezza record corrotti;
- l’utente può creare, consultare e archiviare missioni dalla schermata operativa;
- l’interfaccia chiarisce che l’esecuzione non è ancora disponibile;
- sono presenti test unitari del modello e test di regressione della UI e delle traduzioni.

### Criteri di completamento della Fase 3

La Fase 3 sarà considerata completata quando:

- soltanto una missione pronta può avviare l’esecutore;
- l’esecuzione usa una procedura nativa dichiarata e non codice generato;
- gli input devono esistere e restano separati dalla cartella di output e dagli artefatti interni;
- collegamenti simbolici e sovrapposizioni di percorso vengono rifiutati;
- la procedura minima legge soltanto metadati e non il contenuto degli input;
- nessun originale viene modificato o cancellato;
- rete, browser, dipendenze e processi esterni non vengono utilizzati;
- ogni esecuzione dispone di identificativo, record persistente e log;
- successo ed errore aggiornano coerentemente lo stato della missione;
- i risultati esterni vengono creati senza sovrascrivere file esistenti;
- l’interfaccia mostra autorizzazioni, stato, log, risultati e artefatti;
- sono presenti test per successo, errori, confini dei percorsi e compatibilità della UI.

### Criteri di completamento della Fase 4

La Fase 4 sarà considerata completata quando:

- l’utente può scegliere esplicitamente la procedura CSV o l’inventario tecnico precedente;
- una missione conserva la procedura scelta ed è compatibile con i record precedenti privi del campo;
- il piano operativo è visibile prima del salvataggio e della conferma;
- file CSV singoli e cartelle autorizzate vengono elaborati localmente;
- delimitatori comuni e codifiche UTF-8/Windows-1252 sono gestiti in modo deterministico;
- intestazioni duplicate, righe incoerenti, file non CSV, symlink e limiti eccessivi vengono rifiutati;
- le colonne vengono unite preservando l’ordine di prima comparsa e indicando il file sorgente;
- vengono prodotti un CSV unificato, un riepilogo leggibile e un report JSON interno;
- gli originali restano invariati e gli output esistenti non vengono sovrascritti;
- un errore non lascia risultati esterni parziali;
- l’interfaccia mostra procedura, piano, autorizzazioni, esito e percorsi dei risultati;
- sono presenti test automatici del flusso CSV, della compatibilità del modello e delle traduzioni.

### Criteri di completamento della Fase 5

La Fase 5 sarà considerata completata quando:

- il flusso principale della schermata operativa richiede soltanto categoria, richiesta, input, cartella risultati e provider;
- gli strumenti locali precedenti restano disponibili ma chiusi in una sezione avanzata;
- il pacchetto della missione contiene `ISTRUZIONI.md`, `manifest.json` e la cartella `input/`;
- link simbolici, percorsi sensibili, sovrapposizioni e limiti eccessivi vengono rifiutati;
- prima dell’invio l’utente vede quali input saranno caricati sul provider Web;
- ChatGPT può ricevere automaticamente il primo ZIP tramite l’estensione esistente;
- è sempre disponibile un percorso manuale basato su ZIP e prompt negli appunti;
- la risposta operativa non viene interpretata come aggiornamento del codice;
- lo ZIP finale accetta soltanto `RISULTATO.md`, un manifest facoltativo e file sotto `output/`;
- traversal, symlink, elementi inattesi e archivi eccessivi vengono bloccati;
- l’importazione avviene soltanto nella cartella autorizzata e non sovrascrive file esistenti;
- un errore durante l’importazione rimuove i risultati parziali;
- il risultato pendente resta associato alla missione che lo ha generato;
- una specifica per un eventuale strumento locale può essere trasferita alla Modalità Sviluppo;
- sono presenti test del pacchetto, del contratto dei risultati, del rollback e della compatibilità delle missioni.


---

## 19. Rischi principali

### Regressioni nella Modalità Sviluppo

Mitigazione:

- modifiche additive;
- test di regressione;
- separazione dei moduli;
- evitare rifattorizzazioni non necessarie.

### Crescita di nuovi monoliti

Mitigazione:

- moduli dedicati;
- separazione UI, modello, esecutore e servizi;
- evitare di aggiungere tutta la logica a `main_window.py`, `server.py` o file già grandi.

### Esecuzione non sicura di codice generato

Mitigazione:

- permessi dichiarativi;
- anteprima;
- ambiente limitato;
- nessuna esecuzione automatica;
- controllo di input, output, rete e processi.

### Dipendenze troppo pesanti

Mitigazione:

- dipendenze opzionali;
- introduzione progressiva;
- primo MVP con requisiti minimi.

### Interfaccia troppo tecnica

Mitigazione:

- linguaggio orientato al risultato;
- dettagli tecnici nascosti ma consultabili;
- flusso guidato;
- anteprima leggibile.

### Riservatezza degli input inviati ai provider Web

Mitigazione:

- riepilogo esplicito dei file prima dell’invio;
- inclusione dei soli input autorizzati;
- avviso sulle condizioni e impostazioni privacy del provider scelto;
- nessun invio implicito quando l’utente non conferma.

### Variazioni delle interfacce e delle capacità dei provider

Mitigazione:

- percorso manuale sempre disponibile;
- contratto ZIP semplice e indipendente dal provider;
- automazione limitata inizialmente a ChatGPT;
- errori visibili e nessuna importazione automatica non verificata.

### Promessa troppo ampia

Mitigazione:

- MVP limitato;
- casi d’uso dichiarati;
- messaggi chiari sulle capacità disponibili.

### Confusione tra modalità e workspace

Mitigazione:

- concetti separati;
- suggerimenti non automatici;
- nessuna conversione implicita.

---

## 20. Decisioni già prese

Le seguenti decisioni sono considerate approvate a livello concettuale:

1. BridgAI resterà una sola applicazione.
2. Verranno introdotte Modalità Sviluppo e Modalità Operativa.
3. La scelta sarà proposta al primo avvio.
4. La modalità sarà modificabile successivamente nelle Impostazioni.
5. La Modalità Sviluppo attuale verrà preservata.
6. Lo sviluppo iniziale sarà prevalentemente additivo.
7. La Modalità Operativa sarà orientata al risultato.
8. La Modalità Operativa potrà usare o generare programmi come strumenti interni.
9. Gli input non dovranno essere modificati per impostazione predefinita.
10. La nuova modalità sarà sviluppata progressivamente.
11. Il primo MVP sarà limitato a pochi casi d’uso.
12. Questo documento sarà la fonte principale per le implementazioni future.

---

## 21. Decisioni ancora aperte

Le seguenti decisioni richiedono ulteriore analisi:

- caso d’uso esatto del primo MVP;
- struttura concreta della UI operativa;
- necessità di riavvio dopo il cambio modalità;
- modello dati definitivo delle missioni;
- formato del manifest dei programmi generati;
- isolamento del processo;
- strategia per gli ambienti Python;
- strategia per le dipendenze opzionali;
- provider AI iniziale della Modalità Operativa;
- cartella e durata dei programmi effimeri;
- supporto iniziale della Web UI;
- modalità di distribuzione delle skill documentali.

Le decisioni aperte non devono essere implementate implicitamente senza essere prima registrate.

---

## 22. Metodo di lavoro per le future sessioni

Ogni nuova sessione di sviluppo dovrebbe ricevere:

1. il Super-Report aggiornato;
2. questo documento;
3. la fase da affrontare;
4. eventuali modifiche locali non ancora consolidate;
5. risultati reali dei test più recenti.

La richiesta dovrebbe essere circoscritta.

Esempio:

> Stiamo lavorando alla Fase 1 del Piano Modalità Operativa. In questa sessione voglio implementare soltanto la persistenza della modalità e la scelta al primo avvio. Non implementare ancora missioni o strumenti documentali.

Prima di modificare il codice bisogna:

- identificare i file reali necessari;
- verificare le modifiche locali già presenti;
- evitare di sovrascrivere lavoro non correlato;
- stabilire i test interessati.

Dopo ogni fase bisogna aggiornare:

- stato della roadmap;
- decisioni prese;
- file principali introdotti;
- test eseguiti;
- rischi residui;
- eventuali deviazioni dal piano.

---

## 23. Registro delle implementazioni

Questa sezione dovrà essere aggiornata dopo ogni modifica completata.

### Implementazione 001

**Data:** 24 giugno 2026  
**Fase:** Fase 1  
**Obiettivo:** introduzione della selezione Modalità Sviluppo / Modalità Operativa  
**Stato:** implementata, in attesa della verifica completa sul workspace integrale  
**File modificati:** `PIANO_MODALITA_OPERATIVA.md`, `src/local_ai_bridge/core/settings.py`, `src/local_ai_bridge/ui/main_window.py`, `src/local_ai_bridge/ui/settings_actions.py`, `src/local_ai_bridge/ui/tabs/settings.py`, `src/local_ai_bridge/resources/i18n_it.json`, `src/local_ai_bridge/resources/i18n_en.json`, `tests/test_settings.py`, `tests/test_settings_layout.py`  
**File introdotti:** `src/local_ai_bridge/ui/application_modes.py`, `src/local_ai_bridge/ui/tabs/operations.py`  
**Test eseguiti:** compilazione Python dei file modificati; validazione JSON dei cataloghi; `PYTHONPATH=src pytest -q tests/test_settings.py -k 'primary_mode'`  
**Risultato:** 4 test superati; nessun errore di sintassi o JSON nei file verificati  
**Rischi residui:** suite completa e prova manuale PySide6 non eseguibili dal solo pacchetto di contesto; supporto specifico della Web UI rinviato perché resta una decisione aperta; la schermata operativa è intenzionalmente informativa e non esegue missioni.

### Implementazione 002

**Data:** 24 giugno 2026  
**Fase:** Fase 2  
**Obiettivo:** modello persistente e cronologia minima delle missioni operative  
**Stato:** implementata, in attesa della verifica completa sul workspace integrale  
**File principali introdotti:** `src/local_ai_bridge/services/operational_missions.py`, `src/local_ai_bridge/ui/operations_actions.py`  
**File principali aggiornati:** `src/local_ai_bridge/ui/main_window.py`, `src/local_ai_bridge/ui/tabs/operations.py`, cataloghi di traduzione e test  
**Test eseguiti:** `PYTHONPATH=src pytest -q tests/test_operational_missions.py` e validazioni sintattiche/JSON nel contesto disponibile  
**Risultato:** 6 test del modello missione superati  
**Rischi residui:** suite completa e prova manuale PySide6 ancora richieste; nessuna esecuzione era inclusa nella Fase 2.

### Implementazione 003

**Data:** 24 giugno 2026  
**Fase:** Fase 3  
**Obiettivo:** esecutore operativo minimo con confini espliciti, log e risultati verificabili  
**Stato:** implementata, in attesa della verifica completa sul workspace integrale  
**File introdotti:** `src/local_ai_bridge/services/operational_execution.py`, `src/local_ai_bridge/services/operational_execution_policy.py`, `tests/test_operational_execution.py`  
**File aggiornati:** `PIANO_MODALITA_OPERATIVA.md`, `src/local_ai_bridge/ui/main_window.py`, `src/local_ai_bridge/ui/operations_actions.py`, `src/local_ai_bridge/ui/tabs/operations.py`, `src/local_ai_bridge/resources/i18n_it.json`, `src/local_ai_bridge/resources/i18n_en.json`, `tests/test_settings_layout.py`  
**Test eseguiti:** `PYTHONPATH=src pytest -q tests/test_operational_missions.py tests/test_operational_execution.py`; compilazione Python dei file modificati; validazione JSON dei cataloghi  
**Risultato:** 13 test superati nel contesto disponibile, inclusi 7 test dell’esecutore  
**Rischi residui:** GUI PySide6 e suite completa non eseguite nel pacchetto di contesto; una chiusura forzata durante l’esecuzione può lasciare una missione nello stato `running`; il primo caso d’uso operativo reale resta assegnato alla Fase 4.

### Implementazione 004

**Data:** 24 giugno 2026  
**Fase:** Fase 4  
**Obiettivo:** primo flusso operativo completo per unione e riepilogo CSV  
**Stato:** implementata, in attesa della verifica completa sul workspace integrale  
**File introdotti:** `src/local_ai_bridge/services/operational_csv.py`, `src/local_ai_bridge/ui/operations_presenters.py`, `tests/test_operational_csv.py`, `tests/test_operational_ui.py`  
**File aggiornati:** `PIANO_MODALITA_OPERATIVA.md`, `src/local_ai_bridge/services/operational_missions.py`, `src/local_ai_bridge/services/operational_execution.py`, `src/local_ai_bridge/ui/operations_actions.py`, `src/local_ai_bridge/ui/tabs/operations.py`, cataloghi di traduzione e `tests/test_operational_missions.py`  
**Test eseguiti:** `PYTHONPATH=src pytest -q tests/test_operational_missions.py tests/test_operational_execution.py tests/test_operational_csv.py`; compilazione Python dei moduli modificati; validazione JSON dei cataloghi  
**Risultato:** 19 test superati nel contesto disponibile, inclusi 5 test end-to-end della procedura CSV  
**Rischi residui:** GUI PySide6 e suite completa non eseguite nel pacchetto di contesto; il riepilogo esterno è testuale e bilingue fisso, non adattato dinamicamente alla lingua dell’interfaccia; file CSV molto complessi o con codifiche diverse da UTF-8/Windows-1252 vengono rifiutati.


### Implementazione 005

**Data:** 24 giugno 2026  
**Fase:** Fase 5  
**Obiettivo:** riallineare la Modalità Operativa al flusso Web-first originariamente previsto  
**Stato:** implementata nel pacchetto di aggiornamento, in attesa del collaudo sul workspace integrale  
**File introdotti:** `src/local_ai_bridge/services/operational_catalog.py`, `src/local_ai_bridge/services/operational_web.py`, `src/local_ai_bridge/services/operational_results.py`, `src/local_ai_bridge/ui/operations_web_actions.py`, `src/local_ai_bridge/web/extension_operational.py`, `tests/test_operational_web.py`  
**File principali aggiornati:** `PIANO_MODALITA_OPERATIVA.md`, modello missioni, servizio dell’estensione, API dell’estensione, automazione Chrome, schermata e azioni operative, cataloghi di traduzione e test di regressione  
**Verifiche eseguite:** test mirati dei servizi operativi e del contratto Web, compilazione Python, validazione JSON e controllo sintattico JavaScript  
**Risultato:** 26 test mirati superati nel contesto disponibile; pacchetto missione, ciclo dell’estensione, validazione ZIP, rollback e importazione controllata verificati. I test che richiedono PySide6 o l’intero server restano da eseguire nel workspace completo  
**Rischi residui:** affidabilità dell’automazione dipendente dall’interfaccia Web; disponibilità dello ZIP finale dipendente dal provider; file inviati soggetti alle condizioni privacy del provider; Gemini e Claude inizialmente manuali.


---

## 24. Registro delle decisioni

### Decisione 001 — Due modalità nella stessa applicazione

**Stato:** approvata  
**Motivazione:** preservare BridgAI attuale e aggiungere un nuovo flusso senza duplicare l’intera infrastruttura.

### Decisione 002 — Modalità Sviluppo come baseline stabile

**Stato:** approvata  
**Motivazione:** il flusso attuale è considerato sufficientemente maturo e deve essere protetto dalle regressioni durante lo sviluppo della nuova modalità.

### Decisione 003 — Modalità Operativa orientata agli output

**Stato:** approvata  
**Motivazione:** l’utente operativo vuole ottenere il risultato del lavoro, non necessariamente il programma che lo produce.

### Decisione 004 — Cambio modalità reversibile

**Stato:** approvata  
**Motivazione:** la scelta iniziale descrive la preferenza dell’utente e non deve limitare permanentemente le funzioni disponibili.

### Decisione 005 — Cambio modalità immediato nel desktop

**Stato:** approvata e implementata  
**Motivazione:** la struttura a schede permette di cambiare esperienza senza riavvio e senza ricostruire o modificare il workspace. Le configurazioni precedenti prive del nuovo campo mantengono la Modalità Sviluppo come comportamento compatibile.

### Decisione 006 — Primo esecutore nativo e non generato

**Stato:** approvata e implementata  
**Motivazione:** la Fase 3 doveva verificare confini, stati, log e consegna senza introdurre codice generato. Dopo il pivot Web-first, l’eventuale creazione di strumenti resta affidata alla Modalità Sviluppo. La procedura iniziale produce un inventario JSON usando soltanto metadati dei percorsi autorizzati.

### Decisione 007 — CSV come primo caso d’uso reale

**Stato:** approvata e implementata  
**Motivazione:** l’unione CSV è utile, completamente locale, verificabile con strumenti standard, non richiede OCR né dipendenze aggiuntive e permette di validare il ciclo richiesta → input → piano → autorizzazione → esecuzione → output. L’inventario della Fase 3 resta disponibile per compatibilità e diagnostica.

### Decisione 008 — AI Web come esecutore principale della Modalità Operativa

**Stato:** approvata e implementata  
**Motivazione:** BridgAI nasce come ponte controllabile tra il computer e le AI Web. Delegare il lavoro documentale al provider scelto offre maggiore flessibilità, evita di ricostruire localmente una suite da ufficio e mantiene coerente l’esperienza con la Modalità Sviluppo.

### Decisione 009 — Strumenti locali subordinati e sviluppo guidato

**Stato:** approvata e implementata parzialmente  
**Motivazione:** inventario e CSV restano disponibili per compatibilità, ma non dominano la schermata. Quando un lavoro richiede un programma dedicato, la Modalità Operativa prepara una specifica e passa alla Modalità Sviluppo; nessun codice generato viene eseguito automaticamente.

---

## 25. Sintesi della direzione

BridgAI deve evolvere secondo questa formula:

> In Modalità Sviluppo, BridgAI aiuta l’utente a costruire la soluzione.

> In Modalità Operativa, BridgAI usa o costruisce la soluzione necessaria e consegna direttamente il risultato.

La Modalità Sviluppo rimane il nucleo stabile già esistente.

La Modalità Operativa viene sviluppata principalmente come ponte verso le AI Web attraverso:

- categorie di lavoro e richieste in linguaggio naturale;
- input e output dichiarati;
- pacchetti ZIP con manifest e istruzioni;
- conferma prima del caricamento;
- ricezione, verifica e importazione controllata dei risultati;
- strumenti locali opzionali;
- passaggio guidato alla Modalità Sviluppo quando occorre costruire una nuova soluzione.

La priorità non è ricostruire dentro BridgAI tutti gli strumenti per PDF, Excel, grafica o presentazioni.

La priorità è offrire un’esperienza semplice e flessibile in cui l’AI Web svolge il lavoro e BridgAI controlla quali file vengono inviati, quale risultato viene ricevuto e dove può essere salvato.
