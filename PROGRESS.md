# PROGRESS — Mini gestionale InVibe

Diario di lavoro del progetto: per ogni passaggio, **cosa ho fatto** e **perché**,
per rendere chiare le scelte tecniche e la struttura del progetto.

---

## Indice

1. [Il progetto in breve](#il-progetto-in-breve)
2. [Scelte tecniche](#scelte-tecniche)
3. [Architettura](#architettura)
4. [Passo 1 — Ambiente virtuale e librerie](#passo-1--ambiente-virtuale-e-librerie)
5. [Passo 2 — Scheletro del progetto](#passo-2--scheletro-del-progetto)
6. [Passo 3 — File demo](#passo-3--file-demo)
7. [Passo 4 — Schema del database](#passo-4--schema-del-database-schemasql)
8. [Passo 5 — Logica di calcolo](#passo-5--logica-di-calcolo-appcalcolipy)
9. [Passo 6 — Unit test](#passo-6--unit-test-testsunittest_calcolipy)
10. [Passo 7 — Accesso al database](#passo-7--accesso-al-database-appdbpy)
11. [Passo 8 — API e pagine](#passo-8--api-e-pagine-appmainpy)
12. [Passo 9 — Pagina iniziale](#passo-9--pagina-iniziale-indexhtml)
13. [Passo 10 — Pagina della pratica](#passo-10--pagina-della-pratica-praticahtml)
14. [Passo 11 — Test delle API](#passo-11--test-delle-api)
15. [Passo 12 — Test end-to-end con Playwright](#passo-12--test-end-to-end-con-playwright)
16. [Passo 13 — README](#passo-13--readme)
17. [Riepilogo verifiche](#riepilogo-verifiche)

---

## Il progetto in breve

InVibe organizza viaggi di gruppo. Il prototipo gestisce:

1. **Creazione della pratica** da `prenotazione_demo.json`: pratica, IBAN virtuale unico, partecipanti e servizi acquistati.
2. **Calcolo di quote e rate**: la quota di ogni partecipante è la somma dei suoi servizi; le rate sono 40% / 30% / 30%. La prima e la seconda sono arrotondate al centesimo, la terza è la differenza, così la somma delle rate è sempre uguale alla quota.
3. **Import dei bonifici** da `movimenti_bancari_demo.csv`: l'IBAN individua la pratica, la causale individua il partecipante, l'importo viene imputato alle rate in ordine di scadenza.
4. **Consultazione**: pagina HTML e API JSON con quote, rate, incassato, residuo, movimenti e totali.

Esempio con i dati demo:

| Partecipante | Servizi | Quota | Rata 1 (40%) | Rata 2 (30%) | Rata 3 (resto) |
|---|---|---|---|---|---|
| Mario Rossi | Pacchetto 350 + Navetta 100 | 450,00 € | 180,00 € | 135,00 € | 135,00 € |
| Giulia Bianchi | Pacchetto 350 | 350,00 € | 140,00 € | 105,00 € | 105,00 € |
| **Totale pratica** | | **800,00 €** | **320,00 €** | **240,00 €** | **240,00 €** |

Dopo l'import dei bonifici (TX-001: 150 € a Mario, TX-002: 100 € a Giulia):

| | Incassato | Residuo | Rata 1 |
|---|---|---|---|
| Mario Rossi | 150,00 € | 300,00 € | 150 incassati, 30 residui |
| Giulia Bianchi | 100,00 € | 250,00 € | 100 incassati, 40 residui |
| **Pratica** | **250,00 €** | **550,00 €** | **250 incassati, 70 residui** |

---

## Scelte tecniche

### Linguaggio: Python
- La posizione è orientata ad AI e automazione, dove Python è il linguaggio più usato.
- Per un prototipo piccolo serve poco codice e poca configurazione.
- È facile da avviare per chi valuta: basta Python e `pip install -r requirements.txt`.

**Alternativa valutata: Java con Spring Boot.** Più adatta a un gestionale enterprise di grandi dimensioni, ma richiede più struttura (entity, repository, service, controller, configurazione) e un ambiente più pesante (JDK, Maven). Per un prototipo con poche entità e regole di calcolo precise, Python permette di concentrarsi sulla logica e sui test.

### Framework web: FastAPI
FastAPI è un framework Python per creare API REST. Un endpoint si scrive in poche righe:
```python
@app.get("/api/pratiche/{practice_id}")
def api_leggi_pratica(practice_id: str):
    return {"practice_id": practice_id}
```
- Genera in automatico la documentazione interattiva su `/docs`, da cui si provano tutte le API dal browser.
- Ha un client di test integrato: le API si testano con pytest senza avviare il server.
- Ha la *dependency injection* (`Depends`) per fornire risorse alle funzioni, per esempio la connessione al database.
- Equivalente in Java: un `@RestController` di Spring Boot.

**Alternativa valutata: Django.** È un framework completo con ORM, pannello admin, login e permessi già pronti. Il prototipo non richiede login né permessi e il cuore della prova sono API e calcoli, quindi Django sarebbe stato più grande del necessario. In un gestionale reale, con area riservata e ruoli, Django (oppure FastAPI con un frontend separato in Vue o React) sarebbe una scelta da valutare.

### Server: Uvicorn
È il programma che esegue l'applicazione FastAPI e risponde alle richieste HTTP (in Spring Boot questo ruolo lo ha Tomcat).
```bash
uvicorn app.main:app --reload
```
`app.main:app` significa: nel file `app/main.py`, usa l'oggetto `app`. `--reload` riavvia il server quando il codice cambia.

### Database: SQLite
- È un database contenuto in un unico file: nessuna installazione, nessun servizio esterno o a pagamento.
- I dati restano salvati dopo un aggiornamento della pagina o un riavvio.
- È già incluso in Python (modulo `sqlite3`).
- Lo schema è in un file `schema.sql` leggibile, consegnato con il progetto.
- **Limite:** non è pensato per molti utenti in scrittura contemporanea. In produzione userei PostgreSQL.

### Pagine: Jinja2
Le pagine HTML sono generate dal server a partire da template Jinja2: niente frontend separato da compilare. La grafica non è oggetto di valutazione, quindi bastano pagine semplici e leggibili.

### Importi: centesimi e Decimal, mai float
I `float` hanno errori di arrotondamento:
```python
>>> 0.1 + 0.2
0.30000000000000004

>>> from decimal import Decimal
>>> Decimal("0.1") + Decimal("0.2")
Decimal('0.3')
```
- Nel database e nei calcoli gli importi sono **centesimi interi**: `350,00 €` → `35000`.
- Per mostrarli si convertono in `Decimal`: `35000` → `Decimal('350.00')`.
- Nelle risposte API sono **stringhe** (`"350.00"`): un numero decimale nel JSON verrebbe letto come float da chi lo riceve.
- Nel file demo gli importi sono già stringhe (`"amount_eur": "350.00"`) e vengono letti direttamente, senza passare da un float.

### Test: piramide a tre livelli

| Livello | Strumento | Cosa verifica | Numero |
|---|---|---|---|
| Unit | pytest | Calcolo rate e imputazione bonifici | 2022 |
| API | pytest + TestClient di FastAPI | Import dei file, risultati attesi, errori, persistenza | 22 |
| E2E | Playwright | La pagina mostra i dati corretti; form di caricamento | 12 |

Tanti test veloci alla base (logica), meno test in mezzo (API), pochi test mirati in cima (browser).

---

## Architettura

Il codice è diviso in **livelli**, ognuno con un compito solo:

```
Richiesta HTTP (browser, /docs, test)
        │
        ▼
app/main.py      → riceve la richiesta, legge i file caricati, formatta la risposta (JSON o HTML)
        │
        ▼
app/db.py        → salva e legge i dati in SQLite, usando le funzioni di calcolo
        │
        ▼
app/calcoli.py   → regole: quote, rate, imputazione (nessun database, nessun web)
```

**Perché così:**
- `calcoli.py` non dipende da niente: si testa da solo, con test velocissimi.
- Se si passa da SQLite a PostgreSQL, cambia solo `db.py`.
- Se si aggiunge un'altra interfaccia (per esempio un workflow n8n che chiama le API), la logica resta la stessa.
- API e pagine HTML usano le stesse funzioni di import: niente codice duplicato.

### Struttura delle cartelle

```
invibe-gestionale/
├── .venv/                          → ambiente virtuale (escluso da git)
├── app/
│   ├── __init__.py                 → rende "app" un pacchetto Python importabile
│   ├── calcoli.py                  → logica di calcolo
│   ├── db.py                       → accesso al database
│   ├── main.py                     → API FastAPI e pagine
│   └── templates/
│       ├── index.html              → home: caricamento file ed elenco pratiche
│       └── pratica.html            → riepilogo della pratica
├── data/
│   ├── prenotazione_demo.json
│   └── movimenti_bancari_demo.csv
├── tests/
│   ├── conftest.py                 → fixture condivise (database temporaneo, client)
│   ├── unit/test_calcoli.py
│   ├── api/test_api.py
│   └── e2e/
│       ├── conftest.py             → avvio del server per i test E2E
│       └── test_pagina.py
├── schema.sql
├── pytest.ini
├── requirements.txt
├── README.md
├── PROGRESS.md
└── .gitignore
```

---

## Passo 1 — Ambiente virtuale e librerie

**Cosa ho fatto** (Windows, PowerShell):
```powershell
mkdir invibe-gestionale
cd invibe-gestionale
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install fastapi uvicorn jinja2 pytest httpx
pip freeze > requirements.txt
```

Se PowerShell blocca l'attivazione dell'ambiente, si sblocca solo per la finestra corrente:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

In VS Code ho selezionato l'interprete della `.venv` (`Ctrl+Shift+P` → *Python: Select Interpreter*), così l'editor usa le stesse librerie del terminale.

**Perché:**
- **L'ambiente virtuale** isola le librerie di questo progetto da quelle del sistema: progetti diversi non vanno in conflitto per le versioni. Quando è attivo, nel terminale compare `(.venv)`.
- **`requirements.txt`** elenca le librerie con le versioni esatte. Chiunque ricrea lo stesso ambiente con `pip install -r requirements.txt`.

**Librerie installate durante il progetto:**

| Libreria | A cosa serve | Quando |
|---|---|---|
| `fastapi` | Creare le API REST | Passo 1 |
| `uvicorn` | Server che esegue l'app | Passo 1 |
| `jinja2` | Template delle pagine HTML | Passo 1 |
| `pytest` | Eseguire i test | Passo 1 |
| `httpx` | Client HTTP usato dal TestClient di FastAPI | Passo 1 |
| `python-multipart` | Ricevere i file caricati (form e API) | Passo 8 |
| `httpx2` | Sostituisce `httpx` nel client di test, elimina un avviso di deprecazione | Passo 11 |
| `pytest-playwright` | Test end-to-end nel browser | Passo 12 |

Dopo ogni installazione: `pip freeze > requirements.txt`.

---

## Passo 2 — Scheletro del progetto

**Cosa ho fatto:**
```powershell
New-Item -ItemType Directory -Force app, app\templates, data, tests, tests\unit, tests\api, tests\e2e

New-Item -ItemType File -Force schema.sql, README.md, PROGRESS.md, .gitignore, app\__init__.py, app\calcoli.py, app\db.py, app\main.py, app\templates\pratica.html, tests\conftest.py, tests\unit\test_calcoli.py, tests\api\test_api.py, tests\e2e\test_pagina.py

git init
```

Contenuto di `.gitignore`:
```
.venv/
__pycache__/
*.db
.pytest_cache/
reports/
```

**Perché:**
- Avere subito tutta la struttura permette di vedere il progetto nel suo insieme e poi completarlo un file alla volta.
- La separazione in `calcoli.py`, `db.py` e `main.py` segue l'architettura a livelli.
- I test sono divisi per livello, seguendo la piramide dei test.
- `.gitignore` esclude i file generati o locali: l'ambiente virtuale (si ricrea da `requirements.txt`), il database (si ricrea dallo schema), le cache e i report.

---

## Passo 3 — File demo

**Cosa ho fatto:** copiato i file della prova in `data/`, con i nomi usati nel documento:
- `prenotazione_demo_conforme_word.json` → `data/prenotazione_demo.json`
- `movimenti_bancari_demo_conforme_word.csv` → `data/movimenti_bancari_demo.csv`

**Perché:**
- Dati di input separati dal codice: è chiaro cosa è dato e cosa è logica.
- Nomi corti e uguali al documento: codice più leggibile.
- Solo dati fittizi, come richiesto.

**Struttura dei dati in ingresso:**

`prenotazione_demo.json`:
```json
{
  "practice_id": "CASE-1001",
  "virtual_iban": "DEMO-IBAN-1001",
  "installments": [
    { "number": 1, "percent": 40, "due_date": "2026-12-15" },
    { "number": 2, "percent": 30, "due_date": "2027-02-15" },
    { "number": 3, "percent": 30, "due_date": "2027-04-15" }
  ],
  "participants": [
    {
      "participant_id": "P-001", "first_name": "Mario", "last_name": "Rossi",
      "services": [
        { "code": "PACKAGE", "name": "Pacchetto viaggio", "amount_eur": "350.00" },
        { "code": "NAVETTA", "name": "Navetta", "amount_eur": "100.00" }
      ]
    }
  ]
}
```

`movimenti_bancari_demo.csv`:
```csv
id_movimento,data,iban_virtuale,importo,causale
TX-001,2026-11-20,DEMO-IBAN-1001,150.00,CASE-1001 Mario Rossi
TX-002,2026-11-20,DEMO-IBAN-1001,100.00,CASE-1001 Giulia Bianchi
```
- `iban_virtuale` → individua la **pratica**
- `causale` → numero pratica + nome e cognome → individua il **partecipante**

---

## Passo 4 — Schema del database (`schema.sql`)

**Cosa ho fatto:** definito le tabelle.

| Tabella | Cosa rappresenta | Relazioni |
|---|---|---|
| `pratiche` | Il viaggio prenotato, con un solo IBAN virtuale | ha molti partecipanti |
| `partecipanti` | Una persona della pratica | appartiene a una pratica; ha molti servizi, rate, pagamenti |
| `servizi` | Servizio acquistato (pacchetto, navetta) | appartiene a un partecipante |
| `rate` | Rata del partecipante, con importo e scadenza | appartiene a un partecipante |
| `pagamenti` | Bonifico importato dal CSV | appartiene a una pratica e a un partecipante |
| `imputazioni` | Quanta parte di un pagamento va su quale rata | collega pagamenti e rate (molti a molti) |
| `utenti` | Operatore del gestionale | non usata nel prototipo (nessun login) |

Esempio di tabella:
```sql
CREATE TABLE IF NOT EXISTS rate (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id  TEXT NOT NULL REFERENCES partecipanti(participant_id) ON DELETE CASCADE,
    numero          INTEGER NOT NULL CHECK (numero > 0),
    percentuale     INTEGER NOT NULL CHECK (percentuale BETWEEN 0 AND 100),
    scadenza        TEXT NOT NULL,
    importo_cent    INTEGER NOT NULL CHECK (importo_cent >= 0),
    UNIQUE (participant_id, numero)
);
```

**Decisioni e perché:**

| Decisione | Perché |
|---|---|
| Importi in centesimi (`INTEGER`) | SQLite non ha un tipo decimale esatto: con i centesimi i conti sono sempre precisi |
| Incassato e residuo **non salvati**, ma calcolati dalle imputazioni | Una sola fonte di verità: due valori salvati in posti diversi potrebbero non tornare |
| Tabella `imputazioni` | Ogni euro è tracciabile: si sa quale bonifico ha pagato quale rata, anche se un bonifico copre più rate |
| `id_movimento` chiave primaria | Reimportare lo stesso CSV non duplica i pagamenti |
| `ON DELETE CASCADE` solo su partecipanti, servizi, rate | Se si cancella una pratica spariscono i suoi dati di struttura, ma **un bonifico ricevuto non deve mai sparire**: il database blocca la cancellazione se ci sono pagamenti |
| Vincoli `CHECK` e `UNIQUE` | Il database stesso rifiuta dati non validi (importi negativi, percentuali oltre 100, due "rata 1" per la stessa persona), anche se il codice sbagliasse |
| `CREATE TABLE IF NOT EXISTS` | Lo schema si può applicare a ogni avvio senza errori: crea le tabelle solo la prima volta |

Come si calcolano incassato e residuo di una rata:
```sql
SELECT r.importo_cent AS importo,
       COALESCE(SUM(i.importo_cent), 0) AS incassato,
       r.importo_cent - COALESCE(SUM(i.importo_cent), 0) AS residuo
FROM rate r
LEFT JOIN imputazioni i ON i.rata_id = r.id
GROUP BY r.id
```
`LEFT JOIN` tiene anche le rate senza pagamenti; `COALESCE(..., 0)` trasforma il "nessun pagamento" (NULL) in 0.

**Verifica:**
```powershell
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.executescript(open('schema.sql', encoding='utf-8').read()); print([r[0] for r in c.execute('select name from sqlite_master where sql is not null')])"
```
Risultato: tutte le tabelle create (più `sqlite_sequence`, creata da SQLite per gli `AUTOINCREMENT`).

---

## Passo 5 — Logica di calcolo (`app/calcoli.py`)

**Cosa ho fatto:** scritto le funzioni di calcolo, indipendenti da database e web.

| Funzione | Esempio |
|---|---|
| `euro_a_cent("350.00")` | → `35000` |
| `cent_a_euro(35000)` | → `Decimal('350.00')` |
| `calcola_quota([35000, 10000])` | → `45000` |
| `calcola_rate(45000, [40, 30, 30])` | → `[18000, 13500, 13500]` |
| `imputa_pagamento(15000, rate)` | → imputazioni sulle rate + eventuale eccedenza |

### Calcolo delle rate
```python
def calcola_rate(quota: int, percentuali: list[int]) -> list[int]:
    if sum(percentuali) != 100:
        raise ValueError(...)

    rate = []
    for percentuale in percentuali[:-1]:
        importo = (Decimal(quota) * percentuale / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        rate.append(int(importo))

    ultima = quota - sum(rate)   # l'ultima rata è la differenza
    rate.append(ultima)
    return rate
```

**Perché l'ultima rata per differenza.** Con una quota di 333,33 €:
- 40% = 133,332 → **133,33**
- 30% = 99,999 → **100,00**
- resto = 333,33 − 133,33 − 100,00 = **100,00**

La somma torna sempre al centesimo, qualunque sia la quota.

**Perché `ROUND_HALF_UP` e non `round()`.** Il `round()` di Python usa l'arrotondamento "del banchiere", che arrotonda al pari:
```python
>>> round(0.5), round(1.5), round(2.5)
(0, 2, 2)
```
Nei conti commerciali da 0,5 si arrotonda per eccesso. `ROUND_HALF_UP` lo rende esplicito.

**Perché il controllo sulle percentuali.** Se non sommano 100, la funzione segnala l'errore invece di produrre rate sbagliate.

### Imputazione dei bonifici
```python
def imputa_pagamento(importo: int, rate: list[dict]) -> tuple[list[dict], int]:
    imputazioni = []
    da_imputare = importo

    for rata in sorted(rate, key=lambda r: r["scadenza"]):
        if da_imputare == 0:
            break
        if rata["residuo"] <= 0:
            continue                       # rata già saldata
        quota_su_rata = min(da_imputare, rata["residuo"])
        imputazioni.append({"rata_id": rata["id"], "importo": quota_su_rata})
        da_imputare -= quota_su_rata

    return imputazioni, da_imputare        # da_imputare = eccedenza
```

Esempio: Mario ha la rata 1 con 30,00 € residui e paga 50,00 € → 30,00 € sulla rata 1 (saldata), 20,00 € sulla rata 2.

**Perché:**
- **Ordinamento per scadenza dentro la funzione:** la regola vale sempre, anche se le rate arrivano in disordine.
- **Eccedenza restituita:** se un bonifico supera il dovuto, l'importo in più non si perde ma viene segnalato.

**Verifica:**
```powershell
python -c "from app.calcoli import calcola_rate; print(calcola_rate(45000, [40, 30, 30])); print(calcola_rate(35000, [40, 30, 30]))"
# [18000, 13500, 13500]  → Mario: 180 / 135 / 135
# [14000, 10500, 10500]  → Giulia: 140 / 105 / 105
```

---

## Passo 6 — Unit test (`tests/unit/test_calcoli.py`)

**Cosa ho fatto:**

1. Creato `pytest.ini` per far trovare a pytest il pacchetto `app`:
```ini
   [pytest]
   pythonpath = .
   testpaths = tests
```
   Senza `pythonpath = .` i test darebbero `ModuleNotFoundError: No module named 'app'`.

2. Scritto gli unit test.

**Test parametrizzati:** un solo test, più casi, leggibile come una tabella:
```python
@pytest.mark.parametrize("quota, rate_attese", [
    (45000, [18000, 13500, 13500]),  # Mario Rossi
    (35000, [14000, 10500, 10500]),  # Giulia Bianchi
    (80000, [32000, 24000, 24000]),  # Totale pratica
])
def test_rate_risultati_attesi(quota, rate_attese):
    assert calcola_rate(quota, PERCENTUALI) == rate_attese
```

**Test di proprietà:** invece di pochi esempi, verifica una regola su migliaia di valori:
```python
@pytest.mark.parametrize("quota", range(0, 2001))
def test_somma_rate_sempre_uguale_alla_quota(quota):
    assert sum(calcola_rate(quota, PERCENTUALI)) == quota
```

**Test degli errori:**
```python
def test_rate_percentuali_che_non_sommano_100():
    with pytest.raises(ValueError):
        calcola_rate(45000, [40, 30, 20])
```

**Cosa verificano:**

| Gruppo | Esempi |
|---|---|
| Risultati attesi | Mario, Giulia e pratica |
| Arrotondamento | 333,33 € → 133,33 / 100,00 / 100,00; mezzo centesimo arrotondato per eccesso |
| Proprietà | Per ogni quota da 0,00 a 20,00 € la somma delle rate è la quota (2001 casi) |
| Imputazione | Acconto parziale; bonifico su più rate; rata saldata saltata; ordine per scadenza; eccedenza |
| Input non validi | Percentuali errate; frazioni di centesimo; bonifici a zero o negativi |

**Esecuzione:**
```powershell
pytest tests/unit -q
# 2022 passed
```

---

## Passo 7 — Accesso al database (`app/db.py`)

**Cosa ho fatto:** scritto le funzioni che leggono e scrivono i dati.

| Funzione | Cosa fa |
|---|---|
| `connetti()` | Apre la connessione (percorso da variabile `INVIBE_DB` o `invibe.db`) |
| `inizializza_db(conn)` | Applica `schema.sql` |
| `salva_pratica(conn, dati)` | Salva pratica, partecipanti, servizi e rate calcolate |
| `registra_pagamento(conn, movimento)` | Attribuisce il bonifico e lo imputa alle rate |
| `leggi_pratica(conn, practice_id)` | Restituisce il riepilogo completo con i totali |
| `elenco_pratiche(conn)` | Elenco sintetico delle pratiche |

### Connessione
```python
def connetti(percorso=None):
    percorso = percorso or os.environ.get("INVIBE_DB", DB_PREDEFINITO)
    conn = sqlite3.connect(percorso, check_same_thread=False)
    conn.row_factory = sqlite3.Row             # righe leggibili per nome: riga["nome"]
    conn.execute("PRAGMA foreign_keys = ON")   # in SQLite i vincoli tra tabelle vanno attivati
    return conn
```
- **`INVIBE_DB`**: permette ai test di usare un database separato, senza toccare quello vero.
- **`PRAGMA foreign_keys = ON`**: in SQLite i `REFERENCES` sono disattivati per default; senza questa riga si potrebbe inserire una rata per un partecipante inesistente.

### Transazioni
```python
with conn:   # commit se va tutto bene, rollback se c'è un errore
    conn.execute("INSERT INTO pratiche ...")
    conn.execute("INSERT INTO partecipanti ...")
    ...
```
La pratica si salva con molte INSERT. Se una fallisse a metà resterebbe una pratica incompleta: con la transazione si salva **tutto o niente**. Lo stesso per pagamento + imputazioni.

### Query parametrizzate
```python
conn.execute("SELECT practice_id FROM pratiche WHERE virtual_iban = ?", (iban,))
```
I valori non vengono mai concatenati alla stringa SQL, ma passati a parte con `?`: protezione dalla **SQL injection**.

### Attribuzione del bonifico
```
1. id_movimento già presente?             → rifiutato ("già importato")
2. IBAN virtuale → pratica                → se non esiste: rifiutato
3. causale inizia con il numero pratica?  → se no: rifiutato
4. resto della causale = "nome cognome"   → deve corrispondere a UN solo partecipante
5. imputazione alle rate in ordine di scadenza
```
Il confronto del nome non distingue maiuscole e minuscole (`"MARIO ROSSI"` = `"Mario Rossi"`).

**Perché:** un bonifico non attribuibile con certezza **non viene registrato** e viene segnalato con il motivo. È meglio un bonifico da verificare a mano che soldi attribuiti alla persona sbagliata.

### Totali della pratica
Calcolati sommando i dati dei partecipanti; le rate complessive sommano le rate con lo stesso numero:
```python
for p in partecipanti:
    for r in p["rate"]:
        totale = rate_totali.setdefault(r["numero"], {"importo": 0, "incassato": 0, "residuo": 0, ...})
        for campo in ("importo", "incassato", "residuo"):
            totale[campo] += r[campo]
```

**Verifica** con uno script di prova su database in memoria:
```python
conn = connetti(":memory:")
inizializza_db(conn)
salva_pratica(conn, json.load(open("data/prenotazione_demo.json", encoding="utf-8")))
registra_pagamento(conn, {"id_movimento": "TX-001", ..., "causale": "CASE-1001 Mario Rossi"})
print(leggi_pratica(conn, "CASE-1001")["totali"])
# quota 80000, incassato 15000, residuo 65000
registra_pagamento(conn, {...stesso bonifico...})
# ErroreImport: TX-001: movimento già importato
```

---

## Passo 8 — API e pagine (`app/main.py`)

**Cosa ho fatto:**
```powershell
pip install python-multipart     # necessario per ricevere file caricati
```

| Metodo | Endpoint | Risposta |
|---|---|---|
| POST | `/api/pratiche` | `201` + `{"practice_id": ...}` · `400` se file non valido o pratica già presente |
| POST | `/api/movimenti` | `200` + bonifici `registrati` e `scartati` con il motivo |
| GET | `/api/pratiche` | Elenco pratiche |
| GET | `/api/pratiche/{practice_id}` | Riepilogo completo · `404` se non esiste |
| GET | `/` | Pagina iniziale (HTML) |
| GET | `/pratiche/{practice_id}` | Pagina della pratica (HTML) |
| POST | `/importa/pratica`, `/importa/movimenti` | Form HTML: redirect alla pagina con il risultato |

### Connessione per richiesta (`Depends`)
```python
def get_db():
    conn = connetti()
    inizializza_db(conn)
    try:
        yield conn
    finally:
        conn.close()

@app.get("/api/pratiche/{practice_id}")
def api_leggi_pratica(practice_id: str, conn=Depends(get_db)):
    ...
```
Ogni richiesta riceve la sua connessione, chiusa automaticamente alla fine anche in caso di errore. È la *dependency injection* di FastAPI (simile a `@Autowired` in Spring).

### Stessa logica per API e form
```python
def importa_pratica(conn, contenuto: bytes) -> str: ...
def importa_movimenti(conn, contenuto: bytes) -> dict: ...
```
Le usano sia gli endpoint `/api/...` (che rispondono in JSON) sia i form HTML (che fanno redirect alla pagina). Nessun codice duplicato.

### Import del CSV riga per riga
Ogni bonifico è indipendente: quelli validi vengono registrati, quelli non attribuibili finiscono in `scartati` con il motivo. Un errore su una riga non blocca le altre.
```python
testo = contenuto.decode("utf-8-sig")   # gestisce anche i CSV salvati da Excel (con BOM)
```

### Formattazione
- **API**: importi come stringhe in euro (`"450.00"`), per non perdere precisione nel JSON.
- **Pagine**: filtri Jinja2 per il formato italiano:
```python
  formato_euro(45000)          # "450,00 €"
  formato_data("2026-12-15")   # "15/12/2026"
```

`include_in_schema=False` sulle pagine HTML: in `/docs` compaiono solo le API vere.

**Verifica manuale** da `/docs`:
1. POST `/api/pratiche` con il JSON → `201`, `CASE-1001`
2. POST `/api/movimenti` con il CSV → 2 registrati, 0 scartati
3. GET `/api/pratiche/CASE-1001` → tutti i valori uguali alla tabella "Risultati attesi"
4. POST `/api/pratiche` di nuovo → `400`, "La pratica CASE-1001 è già presente"
5. Server fermato e riavviato → GET restituisce ancora gli stessi dati (persistenza)

Nota: in `/api/movimenti` le imputazioni di Giulia riportano `rata_id: 4`. È l'id della riga nella tabella `rate` (le rate 1–3 sono di Mario): corrisponde alla **rata numero 1** di Giulia.

---

## Passo 9 — Pagina iniziale (`index.html`)

**Cosa ho fatto:** home con due form di caricamento (JSON pratica, CSV bonifici), messaggio di esito ed elenco delle pratiche con link.

```html
<form action="/importa/pratica" method="post" enctype="multipart/form-data">
    <input type="file" name="file" accept=".json" required data-testid="file-pratica">
    <button type="submit" data-testid="carica-pratica">Crea pratica</button>
</form>
```

**Perché:**
- **`enctype="multipart/form-data"`** è obbligatorio per inviare file; `name="file"` corrisponde al parametro `file` in `main.py`.
- **`required`**: il browser blocca l'invio se non è stato scelto un file (validazione lato client).
- **`data-testid`**: attributi dedicati ai test. I test Playwright non dipendono da testi o grafica: se cambia la scritta del pulsante, i test non si rompono.
- **Jinja2 fa l'escape automatico**: un testo con `<script>` viene mostrato come testo, non eseguito (protezione da XSS).

Sintassi Jinja2:
```html
{% for p in pratiche %}                       {# istruzione #}
    <td>{{ p.data_inizio | data }}</td>       {# valore passato nel filtro "data" #}
{% endfor %}
```

---

## Passo 10 — Pagina della pratica (`pratica.html`)

**Cosa ho fatto:** riepilogo con:
- dati della pratica (numero, IBAN virtuale, destinazione, turno)
- totali della pratica e tabella delle rate complessive
- per ogni partecipante: saldo (quota, incassato, residuo), servizi, rate con stato, movimenti attribuiti

**Stato della rata** con una macro Jinja2 (una piccola funzione riusabile nel template):
```html
{% macro stato(rata) -%}
    {%- if rata.residuo == 0 -%}Pagata
    {%- elif rata.incassato > 0 -%}Parziale
    {%- else -%}Da pagare
    {%- endif -%}
{%- endmacro %}
```

**`data-testid` a contenitori:** gli stessi nomi (`saldo`, `quota`, `incassato`, `residuo`, `rata-1`) si ripetono dentro sezioni diverse (`totali-pratica`, `partecipante-P-001`, `partecipante-P-002`). Nei test si cerca prima la sezione, poi dentro:
```python
page.get_by_test_id("partecipante-P-001").get_by_test_id("rata-1").get_by_test_id("residuo")
```
I test si leggono come la tabella dei risultati attesi.

**Perché i calcoli non sono nel template:** tutti i numeri arrivano pronti da `leggi_pratica`; il template formatta e mostra soltanto. L'unica eccezione è l'etichetta dello stato, che è pura visualizzazione.

---

## Passo 11 — Test delle API

**Cosa ho fatto:**

### `tests/conftest.py`: fixture condivise
```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client di test collegato a un database vuoto e temporaneo."""
    monkeypatch.setenv("INVIBE_DB", str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def pratica_demo(client, carica):
    """Database con pratica e bonifici demo già importati."""
    assert carica("/api/pratiche", FILE_PRENOTAZIONE).status_code == 201
    assert carica("/api/movimenti", FILE_MOVIMENTI).status_code == 200
    return client
```
- **`tmp_path`**: cartella temporanea diversa per ogni test → ogni test ha il suo database, i test non si influenzano a vicenda e `invibe.db` non viene toccato.
- **`monkeypatch.setenv`**: imposta `INVIBE_DB` solo per la durata del test.
- **`TestClient`**: simula le chiamate HTTP direttamente sull'app, senza avviare uvicorn.
- **Fixture concatenate**: `pratica_demo` usa `carica`, che usa `client`.

### `tests/api/test_api.py`

Esempio: la tabella dei risultati attesi come test parametrizzato:
```python
@pytest.mark.parametrize("pid, incassato, residuo, rata1_incassato, rata1_residuo, residui_rate_2_3", [
    ("P-001", "150.00", "300.00", "150.00", "30.00", ["135.00", "135.00"]),  # Mario Rossi
    ("P-002", "100.00", "250.00", "100.00", "40.00", ["105.00", "105.00"]),  # Giulia Bianchi
])
def test_saldi_e_rate_dopo_i_bonifici(pratica_demo, pid, incassato, residuo, ...):
    ...
```

Esempio: un caso limite costruendo un CSV al volo:
```python
def test_bonifico_che_salda_rata_1_e_passa_alla_rata_2(pratica_demo, carica):
    carica("/api/movimenti", csv_movimenti("TX-300,2026-11-22,DEMO-IBAN-1001,50.00,CASE-1001 Mario Rossi"))
    rata1, rata2, _ = partecipante(riepilogo(pratica_demo), "P-001")["rate"]
    assert (rata1["incassato"], rata1["residuo"]) == ("180.00", "0.00")
    assert (rata2["incassato"], rata2["residuo"]) == ("20.00", "115.00")
```

**Cosa verificano (22 test):**

| Gruppo | Test |
|---|---|
| Risultati attesi del documento | Pratica e IBAN; quote e rate; scadenze; saldi e rate dopo i bonifici; movimenti attribuiti; totali |
| Creazione pratica | `201`; duplicata `400`; JSON non valido; campi mancanti; pratica inesistente `404` |
| Bonifici | Reimport dello stesso CSV (nessun duplicato); IBAN sconosciuto; causale senza numero pratica; nome inesistente; maiuscole nella causale; bonifico su due rate; eccedenza; CSV senza colonne |
| Persistenza | Un nuovo client sullo stesso database ritrova i dati |

**Avviso risolto:** durante l'esecuzione compariva:
```
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```
Risolto installando `httpx2` come indicato dal messaggio; i test sono passati senza avvisi.

**Esecuzione:**
```powershell
pytest tests/api -q
# 22 passed
```

---

## Passo 12 — Test end-to-end con Playwright

**Cosa ho fatto:**
```powershell
pip install pytest-playwright
playwright install chromium
```

### `tests/e2e/conftest.py`: server dedicato ai test
```python
@pytest.fixture(scope="session")
def base_url(tmp_path_factory):
    database = tmp_path_factory.mktemp("e2e") / "e2e.db"
    ambiente = {**os.environ, "INVIBE_DB": str(database)}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8765"],
        cwd=CARTELLA_PROGETTO, env=ambiente,
    )
    # ... attende che il server risponda ...
    yield "http://127.0.0.1:8765"
    server.terminate()
```
- Avvia uvicorn **come processo separato**, su una porta dedicata, con database temporaneo; lo spegne alla fine.
- Sostituisce la fixture `base_url` di pytest-playwright: nei test basta `page.goto("/")`.
- **`scope="session"`**: server e dati preparati una volta sola per tutti i test E2E (avviare browser e server è lento).

I dati demo vengono caricati con il client API di Playwright, non dal browser:
```python
api = playwright.request.new_context(base_url=base_url)
api.post("/api/pratiche", multipart={"file": {"name": ..., "mimeType": "application/json", "buffer": ...}})
```

### `tests/e2e/test_pagina.py`
```python
def test_totali_della_pratica(page: Page):
    page.goto("/pratiche/CASE-1001")
    saldo = page.get_by_test_id("totali-pratica").get_by_test_id("saldo")
    expect(saldo.get_by_test_id("quota")).to_have_text("800,00 €")
    expect(saldo.get_by_test_id("incassato")).to_have_text("250,00 €")
    expect(saldo.get_by_test_id("residuo")).to_have_text("550,00 €")
```
**`expect` aspetta da solo** che l'elemento compaia con il testo giusto (fino a 5 secondi): niente `sleep`, niente test instabili.

Caricamento di un file dal form, generandolo al volo:
```python
page.get_by_test_id("file-pratica").set_input_files(files=[{
    "name": "nuova_pratica.json",
    "mimeType": "application/json",
    "buffer": json.dumps(dati).encode("utf-8"),
}])
page.get_by_test_id("carica-pratica").click()
expect(page).to_have_url(re.compile(r"/pratiche/CASE-2001$"))
```

**Cosa verificano (12 test):**

| Gruppo | Test |
|---|---|
| Navigazione | La home elenca la pratica; il link apre la pratica |
| Risultati attesi | Totali e rate complessive; scadenze; saldo e rate di Mario e di Giulia; movimenti attribuiti |
| Persistenza | Dati presenti dopo il reload della pagina |
| Form | Creazione di una nuova pratica dal form; messaggio per pratica duplicata; reimport dei bonifici senza duplicati |

### Problema trovato e risolto
Alla prima esecuzione due test fallivano:
```
AssertionError: Locator expected to have text '450,00 €'
Error: element(s) not found
get_by_test_id("partecipante-P-001").get_by_test_id("saldo").get_by_test_id("quota")
```
**Analisi:** lo snapshot della pagina restituito da Playwright ("Aria snapshot") mostrava che i valori erano presenti, ma il contenitore del saldo dei partecipanti non aveva `data-testid="saldo"`: l'attributo era presente solo nella sezione dei totali.
**Correzione:** aggiunto `data-testid="saldo"` a entrambi i blocchi di riepilogo in `pratica.html`. Dopo la correzione: 12 test su 12 passati.

**Nota emersa dai test:** nel test di creazione di una nuova pratica è stato necessario usare id partecipante diversi (`P-201`, `P-202`), perché nello schema `participant_id` è unico in tutto il database e non per pratica. Limite dichiarato nel README.

**Esecuzione:**
```powershell
pytest tests/e2e -v
# 12 passed

pytest tests/e2e --headed --slowmo 500   # browser visibile, rallentato
```

---

## Passo 13 — README

**Cosa ho fatto:** scritto il README con:
- istruzioni di avvio e di prova con i dati demo
- comandi per eseguire i test e generare il report JUnit XML
- funzionalità completate (A2, A3, A4)
- entità e relazioni (A1), scelte di modellazione, semplificazioni e limiti noti
- tabella dei cinque rischi (Parte B)
- nota sull'uso dell'AI e sul tempo impiegato

**I cinque rischi individuati:**

| # | Rischio | Già mitigato nel prototipo |
|---|---|---|
| 1 | Bonifico attribuito al partecipante sbagliato o non attribuito | Sì, in parte: i bonifici non attribuibili con certezza vengono scartati con il motivo; nessun duplicato |
| 2 | Accesso non autorizzato ai dati dei partecipanti | No: login e permessi esclusi dal prototipo |
| 3 | Modifiche alla pratica dopo l'inizio dei pagamenti | No: modifiche non previste; i pagamenti non si cancellano a cascata |
| 4 | Rate scadute non monitorate | In parte: lo stato di ogni rata (Pagata / Parziale / Da pagare) è visibile |
| 5 | Perdita o incoerenza dei dati | Sì, in parte: transazioni e vincoli nel database |

---

## Riepilogo verifiche

```powershell
pytest -q
# 2056 passed
```

| Livello | Test | Esito |
|---|---|---|
| Unit | 2022 | ✅ |
| API | 22 | ✅ |
| E2E | 12 | ✅ |
| **Totale** | **2056** | ✅ |

Verifiche manuali:
- ✅ API provate da `/docs`: tutti i valori uguali alla tabella "Risultati attesi"
- ✅ Pagina della pratica controllata nel browser
- ✅ Persistenza dopo il riavvio del server
- ✅ Messaggi di errore per pratica duplicata e bonifici già importati