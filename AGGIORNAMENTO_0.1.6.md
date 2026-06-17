# Aggiornamento 0.1.6

Questa release aggiunge due controlli alla toolbar principale:

- **Apri cartella**: apre il workspace corrente nel file manager predefinito di Windows, macOS o Linux;
- **Riavvia**: salva le impostazioni, avvia una nuova istanza usando lo stesso interprete/ambiente virtuale e chiude quella corrente dopo conferma.

Il pulsante **Apri cartella** rimane disabilitato finché non viene selezionato un workspace valido.

Il riavvio supporta:

- esecuzione da `run.py`;
- avvio come modulo `python -m local_ai_bridge`;
- futura distribuzione come eseguibile autonomo.
