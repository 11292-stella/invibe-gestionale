# Mini gestionale InVibe

Prototipo di gestionale per i viaggi di gruppo: crea una pratica da un file di prenotazione, calcola quote e rate dei partecipanti, importa i bonifici e li imputa alle rate, mostra il riepilogo della pratica.

**Stack:** Python · FastAPI · SQLite · Jinja2 · pytest · Playwright

---

## Avvio

Requisiti: **Python 3.10 o superiore**.

```bash
# 1. Ambiente virtuale
python -m venv .venv

# 2. Attivazione
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
source .venv/bin/activate         # macOS / Linux

# 3. Librerie
pip install -r requirements.txt

# 4. Avvio del server
uvicorn app.main:app --reload
```

Poi aprire:

- **http://127.0.0.1:8000/**: pagina per caricare i file e consultare le pratiche
- **http://127.0.0.1:8000/docs**: documentazione interattiva delle API

Il database `invibe.db` viene creato automaticamente al primo avvio. Per ripartire da zero basta fermare il server e cancellare il file.

### Prova con i dati demo

1. Nella home, riquadro **1. Crea pratica**: caricare `data/prenotazione_demo.json`
2. Riquadro **2. Importa bonifici**: caricare `data/movimenti_bancari_demo.csv`
3. Aprire la pratica **CASE-1001**

In alternativa, dalle API:

| Metodo | Endpoint | Descrizione |
|---|---|---|
| POST | `/api/pratiche` | Crea la pratica dal file JSON |
| POST | `/api/movimenti` | Importa i bonifici dal file CSV |
| GET | `/api/pratiche` | Elenco delle pratiche |
| GET | `/api/pratiche/{practice_id}` | Riepilogo completo della pratica |

---

## Test

```bash
# Browser per i test end-to-end (solo la prima volta)
playwright install chromium

# Tutti i test
pytest

# Per livello
pytest tests/unit       # logica di calcolo
pytest tests/api        # API
pytest tests/e2e        # pagina nel browser (Playwright)

# Browser visibile, rallentato
pytest tests/e2e --headed --slowmo 500

# Report JUnit XML
pytest --junitxml=reports/junit.xml
```

| Livello | Test | Cosa verificano |
|---|---|---|
| Unit | 2022 | Calcolo di quote e rate, arrotondamenti, imputazione dei bonifici, input non validi. Include un test di proprietà: per ogni quota da 0,00 a 20,00 € la somma delle rate è uguale alla quota |
| API | 22 | Tutta la tabella "Risultati attesi" del documento, errori di import, bonifici non attribuibili, reimport, eccedenze, persistenza |
| E2E | 12 | La pagina mostra i risultati attesi; caricamento dei file dai form; messaggi di errore; dati presenti dopo il reload |

I test usano un database temporaneo e non modificano `invibe.db`. I test E2E avviano un server dedicato sulla porta 8765.

---

## Funzionalità completate

- **A2 – Creazione della pratica** da `prenotazione_demo.json`, con `practice_id` e IBAN virtuale unico per la pratica. Quota del partecipante = somma dei servizi. Rate al 40% / 30% / 30%: le prime due arrotondate al centesimo, la terza calcolata per differenza.
- **A3 – Registrazione dei bonifici** da `movimenti_bancari_demo.csv`. L'IBAN virtuale individua la pratica, la causale individua il partecipante. Imputazione in ordine di scadenza: prima la rata 1, l'eccedenza passa alla 2 e poi alla 3.
- **A4 – Consultazione** tramite pagina HTML e API JSON: partecipanti con servizi e quote, rate con scadenza, incassato e residuo, movimenti attribuiti, totali della pratica.
- **Persistenza** in SQLite: i dati restano dopo un aggiornamento della pagina o un riavvio.

---

## Struttura del progetto

```
app/
  calcoli.py      logica: quote, rate, imputazione dei bonifici (senza database né web)
  db.py           accesso al database
  main.py         API FastAPI e pagine
  templates/      pagine HTML (Jinja2)
data/             file demo
tests/            unit, api, e2e
schema.sql        schema del database
```

La logica di calcolo è separata dal database e dal web: si può testare da sola e resta invariata se cambia il database o l'interfaccia.

---

## A1 – Entità e relazioni

```
PRATICA 1 ──── N PARTECIPANTE 1 ──── N SERVIZIO
                     │
                     ├── 1 ──── N RATA
                     │             │
                     └── 1 ──── N PAGAMENTO ──── N IMPUTAZIONE ──── 1 RATA

UTENTE (operatore del gestionale, non collegato ai dati nel prototipo)
```

| Entità | Descrizione | Campi principali |
|---|---|---|
| **Pratica** | Il viaggio prenotato. Ha un solo IBAN virtuale, usato da tutti i partecipanti | `practice_id`, `virtual_iban` (unico), destinazione, date del turno |
| **Partecipante** | Una persona della pratica | `participant_id`, pratica, nome, cognome |
| **Servizio** | Servizio acquistato dal partecipante (pacchetto, navetta) | codice, nome, importo |
| **Rata** | Parte della quota del partecipante | numero, percentuale, scadenza, importo |
| **Pagamento** | Bonifico ricevuto sull'IBAN virtuale | `id_movimento` (unico), data, importo, causale, pratica, partecipante |
| **Imputazione** | Quanta parte di un pagamento è andata su quale rata | pagamento, rata, importo |
| **Utente** | Operatore InVibe che usa il gestionale | nome, email, ruolo |

**Scelte di modellazione:**

- **Importi in centesimi (interi).** SQLite non ha un tipo decimale esatto; nel codice si usa `Decimal`, mai `float`.
- **La quota del partecipante, l'incassato e il residuo non sono salvati: si calcolano.** La quota è la somma dei servizi, l'incassato è la somma delle imputazioni, il residuo è la differenza. Una sola fonte di verità, nessun dato che non torna.
- **L'imputazione** rende tracciabile ogni euro: si sa quale bonifico ha pagato quale rata, anche quando un bonifico copre più rate.
- **`id_movimento` è chiave primaria:** reimportare lo stesso file non duplica i pagamenti.
- **I pagamenti non si cancellano a cascata** con la pratica: un bonifico ricevuto non deve sparire.

### Semplificazioni della demo

- **Nessun login né permessi:** la tabella `utenti` è nello schema ma non è usata.
- **Il piano rate (3 rate, percentuali e scadenze) arriva dal file** ed è uguale per tutti i partecipanti della pratica.
- **Non è possibile modificare una pratica** dopo la creazione (cambio servizi, ritiro di un partecipante, storni).
- **Il partecipante si individua dal confronto esatto di nome e cognome nella causale** (senza distinguere maiuscole e minuscole). Un bonifico non attribuibile con certezza viene scartato con il motivo, non registrato.
- **Un bonifico superiore al dovuto** viene registrato e l'eccedenza viene segnalata, ma non è gestita come credito.
- **SQLite** come database: adatto a un prototipo, non a molti utenti in scrittura contemporanea.

### Limiti noti

- `participant_id` è unico in tutto il database, non per pratica: due pratiche diverse non possono avere un partecipante `P-001`. In produzione andrebbe usato un identificativo interno generato dal sistema.
- Non c'è una gestione delle omonimie nella stessa pratica: due partecipanti con lo stesso nome renderebbero il bonifico non attribuibile (viene scartato, non attribuito a caso).
- Date e formati dei file sono validati solo nei campi necessari ai calcoli.

---

## Parte B – Analisi dei rischi

| # | Rischio | Conseguenza concreta per InVibe | Probabilità | Impatto | Contromisura proposta |
|---|---|---|---|---|---|
| 1 | **Pagamenti: bonifico attribuito al partecipante sbagliato o non attribuito** (causale scritta male, nome abbreviato, omonimi, un partecipante che paga per un altro) | Rate segnate come pagate per chi non ha pagato e solleciti inviati a chi ha già pagato; contestazioni dei clienti e lavoro manuale per correggere | Alta | Alto | Codice univoco per partecipante da inserire in causale; coda di "bonifici da verificare" per quelli non attribuibili con certezza, invece di attribuirli in automatico; abbinamento manuale con registro di chi l'ha fatto; riconciliazione periodica tra estratto conto e incassi registrati |
| 2 | **Accesso ai dati dei partecipanti** (dati anagrafici e pagamenti visibili a chi non dovrebbe; oggi il prototipo non ha login) | Violazione GDPR con possibili sanzioni e danno di immagine; dati di un partecipante visibili a un altro nell'area riservata | Media | Alto | Login obbligatorio e ruoli (admin, operatore, partecipante); nell'area riservata ogni partecipante vede solo i propri dati, con controllo lato server; HTTPS; log degli accessi ai dati personali; minimizzazione e cifratura dei dati sensibili; backup cifrati |
| 3 | **Modifiche alla pratica dopo l'inizio dei pagamenti** (cambio di un servizio, ritiro di un partecipante) | Rate ricalcolate che non tornano con quanto già incassato, soldi "persi" tra le rate, rimborsi o penali calcolati in modo errato | Alta | Alto | Le modifiche non cancellano i dati ma creano movimenti di rettifica (variazioni di quota, storni, rimborsi) con data e autore; ricalcolo solo delle rate non ancora pagate; regole esplicite per ritiro e penali; conferma obbligatoria e storico delle versioni della pratica |
| 4 | **Rate scadute non monitorate** | Incassi in ritardo, problemi di liquidità verso fornitori (hotel, voli); partecipanti che arrivano alla partenza senza aver pagato | Media | Medio | Elenco e filtri delle rate in scadenza e scadute; promemoria automatici via email prima e dopo la scadenza; cruscotto degli insoluti per pratica |
| 5 | **Perdita o incoerenza dei dati** (errore a metà di un import, file del database danneggiato, import manuali ripetuti) | Pratiche incomplete, pagamenti duplicati o persi, impossibilità di ricostruire chi ha pagato cosa | Bassa | Alto | Transazioni (già nel prototipo: l'import della pratica è "tutto o niente"); vincoli nel database (già presenti: niente pagamenti duplicati, importi negativi, rate doppie); database gestito (PostgreSQL) con backup automatici e test di ripristino; registro delle operazioni |

---

## Uso dell'AI e tempo impiegato

**Tempo impiegato:** [DA COMPLETARE: es. circa X ore]

- **Strumenti:** ho usato Claude (Anthropic) come assistente per la scelta dello stack, la progettazione dello schema, la generazione del codice iniziale e dei test, e le spiegazioni passo per passo.
- **Lavoro diretto:** ho impostato il progetto da terminale (ambiente virtuale, struttura, dipendenze), costruito l'applicazione un file alla volta verificando ogni passaggio, e tenuto un diario delle scelte in `PROGRESS.md`. [DA COMPLETARE: eventuali parti che hai modificato o scritto tu]
- **Verifiche:** ogni file è stato provato prima di passare al successivo (script di prova, `/docs`, browser), poi coperto da test automatici a tre livelli (unit, API, E2E) che confrontano i risultati con la tabella "Risultati attesi". Ho verificato anche la persistenza riavviando il server.
- **Problemi trovati e risolti:** i test E2E hanno individuato un identificativo di test mancante nel template della pratica, corretto dopo aver analizzato lo snapshot della pagina restituito da Playwright; un avviso di deprecazione della libreria di test è stato risolto aggiornando le dipendenze.
- **Limiti e ipotesi:** vedi "Semplificazioni della demo" e "Limiti noti".