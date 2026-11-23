"""
Accesso al database SQLite: salvataggio della pratica, registrazione dei bonifici,
lettura del riepilogo.

Le regole di calcolo stanno in calcoli.py: qui si leggono e si scrivono solo i dati.
Tutti gli importi sono in CENTESIMI (int).
"""

import os
import sqlite3
from pathlib import Path

from app.calcoli import calcola_quota, calcola_rate, euro_a_cent, imputa_pagamento

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent
SCHEMA = CARTELLA_PROGETTO / "schema.sql"
DB_PREDEFINITO = CARTELLA_PROGETTO / "invibe.db"


class ErroreImport(Exception):
    """Errore nei dati importati (pratica già presente, bonifico non attribuibile, ...)."""


# ---------------------------------------------------------------
# Connessione e inizializzazione
# ---------------------------------------------------------------

def connetti(percorso=None) -> sqlite3.Connection:
    """
    Apre la connessione al database.

    Il percorso si può scegliere con la variabile d'ambiente INVIBE_DB
    (utile nei test, per usare un database separato); altrimenti si usa invibe.db.
    """
    percorso = percorso or os.environ.get("INVIBE_DB", DB_PREDEFINITO)
    conn = sqlite3.connect(percorso, check_same_thread=False)
    conn.row_factory = sqlite3.Row             # righe leggibili per nome: riga["nome"]
    conn.execute("PRAGMA foreign_keys = ON")   # in SQLite i vincoli tra tabelle vanno attivati
    return conn


def inizializza_db(conn: sqlite3.Connection) -> None:
    """Crea le tabelle se non esistono (lo schema usa CREATE TABLE IF NOT EXISTS)."""
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))


# ---------------------------------------------------------------
# Creazione della pratica
# ---------------------------------------------------------------

def salva_pratica(conn: sqlite3.Connection, dati: dict) -> str:
    """
    Salva la pratica letta da prenotazione_demo.json:
    pratica, partecipanti, servizi e rate calcolate.

    Tutto avviene in una sola transazione: o si salva tutto o niente.
    """
    practice_id = dati["practice_id"]
    if conn.execute("SELECT 1 FROM pratiche WHERE practice_id = ?", (practice_id,)).fetchone():
        raise ErroreImport(f"La pratica {practice_id} è già presente")

    piano_rate = sorted(dati["installments"], key=lambda r: r["number"])
    percentuali = [r["percent"] for r in piano_rate]

    with conn:  # transazione: commit se va tutto bene, rollback se c'è un errore
        conn.execute(
            "INSERT INTO pratiche (practice_id, virtual_iban, destinazione, data_inizio, data_fine) "
            "VALUES (?, ?, ?, ?, ?)",
            (practice_id, dati["virtual_iban"], dati["destination"],
             dati["turn"]["start_date"], dati["turn"]["end_date"]),
        )

        for partecipante in dati["participants"]:
            participant_id = partecipante["participant_id"]
            conn.execute(
                "INSERT INTO partecipanti (participant_id, practice_id, nome, cognome) VALUES (?, ?, ?, ?)",
                (participant_id, practice_id, partecipante["first_name"], partecipante["last_name"]),
            )

            importi_servizi = []
            for servizio in partecipante["services"]:
                importo = euro_a_cent(servizio["amount_eur"])
                importi_servizi.append(importo)
                conn.execute(
                    "INSERT INTO servizi (participant_id, codice, nome, importo_cent) VALUES (?, ?, ?, ?)",
                    (participant_id, servizio["code"], servizio["name"], importo),
                )

            quota = calcola_quota(importi_servizi)
            for rata, importo in zip(piano_rate, calcola_rate(quota, percentuali)):
                conn.execute(
                    "INSERT INTO rate (participant_id, numero, percentuale, scadenza, importo_cent) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (participant_id, rata["number"], rata["percent"], rata["due_date"], importo),
                )

    return practice_id


# ---------------------------------------------------------------
# Registrazione dei bonifici
# ---------------------------------------------------------------

# Rate di un partecipante con incassato e residuo calcolati dalle imputazioni
SQL_RATE_PARTECIPANTE = """
    SELECT r.id,
           r.numero,
           r.percentuale,
           r.scadenza,
           r.importo_cent AS importo,
           COALESCE(SUM(i.importo_cent), 0) AS incassato,
           r.importo_cent - COALESCE(SUM(i.importo_cent), 0) AS residuo
    FROM rate r
    LEFT JOIN imputazioni i ON i.rata_id = r.id
    WHERE r.participant_id = ?
    GROUP BY r.id
    ORDER BY r.scadenza
"""


def registra_pagamento(conn: sqlite3.Connection, movimento: dict) -> dict:
    """
    Registra un bonifico (una riga del CSV) e lo imputa alle rate del partecipante.

    - L'IBAN virtuale individua la pratica.
    - La causale ("CASE-1001 Mario Rossi") individua il partecipante.
    Se il bonifico non è attribuibile senza dubbi, NON viene registrato.
    """
    id_movimento = movimento["id_movimento"].strip()

    if conn.execute("SELECT 1 FROM pagamenti WHERE id_movimento = ?", (id_movimento,)).fetchone():
        raise ErroreImport(f"{id_movimento}: movimento già importato")

    # 1. Pratica dall'IBAN virtuale
    iban = movimento["iban_virtuale"].strip()
    pratica = conn.execute("SELECT practice_id FROM pratiche WHERE virtual_iban = ?", (iban,)).fetchone()
    if pratica is None:
        raise ErroreImport(f"{id_movimento}: nessuna pratica con IBAN virtuale {iban}")
    practice_id = pratica["practice_id"]

    # 2. La causale deve contenere il numero della stessa pratica
    parole = movimento["causale"].split()
    if not parole or parole[0] != practice_id:
        raise ErroreImport(f"{id_movimento}: la causale non riporta il numero di pratica {practice_id}")

    # 3. Partecipante da nome e cognome nella causale (senza differenze tra maiuscole e minuscole)
    nome_in_causale = " ".join(parole[1:]).lower()
    candidati = [
        riga for riga in conn.execute(
            "SELECT participant_id, nome, cognome FROM partecipanti WHERE practice_id = ?", (practice_id,)
        )
        if f"{riga['nome']} {riga['cognome']}".lower() == nome_in_causale
    ]
    if len(candidati) != 1:
        raise ErroreImport(f"{id_movimento}: partecipante non individuato con certezza dalla causale")
    participant_id = candidati[0]["participant_id"]

    # 4. Imputazione alle rate in ordine di scadenza
    importo = euro_a_cent(movimento["importo"].strip())
    rate = [dict(r) for r in conn.execute(SQL_RATE_PARTECIPANTE, (participant_id,))]
    imputazioni, eccedenza = imputa_pagamento(importo, rate)

    with conn:
        conn.execute(
            "INSERT INTO pagamenti (id_movimento, data, iban_virtuale, importo_cent, causale, practice_id, participant_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (id_movimento, movimento["data"].strip(), iban, importo,
             movimento["causale"].strip(), practice_id, participant_id),
        )
        for imp in imputazioni:
            conn.execute(
                "INSERT INTO imputazioni (id_movimento, rata_id, importo_cent) VALUES (?, ?, ?)",
                (id_movimento, imp["rata_id"], imp["importo"]),
            )

    return {
        "id_movimento": id_movimento,
        "participant_id": participant_id,
        "importo": importo,
        "imputazioni": imputazioni,
        "eccedenza": eccedenza,
    }


# ---------------------------------------------------------------
# Consultazione della pratica
# ---------------------------------------------------------------

def leggi_pratica(conn: sqlite3.Connection, practice_id: str) -> dict | None:
    """
    Restituisce il riepilogo completo della pratica: partecipanti con servizi, quote,
    rate (con incassato e residuo), movimenti attribuiti e totali.
    I totali della pratica si ottengono sommando i dati dei partecipanti.
    """
    pratica = conn.execute("SELECT * FROM pratiche WHERE practice_id = ?", (practice_id,)).fetchone()
    if pratica is None:
        return None

    partecipanti = []
    righe_partecipanti = conn.execute(
        "SELECT * FROM partecipanti WHERE practice_id = ? ORDER BY participant_id", (practice_id,)
    ).fetchall()

    for p in righe_partecipanti:
        pid = p["participant_id"]
        servizi = [dict(s) for s in conn.execute(
            "SELECT codice, nome, importo_cent AS importo FROM servizi WHERE participant_id = ? ORDER BY id", (pid,)
        )]
        rate = [dict(r) for r in conn.execute(SQL_RATE_PARTECIPANTE, (pid,))]
        movimenti = [dict(m) for m in conn.execute(
            "SELECT id_movimento, data, importo_cent AS importo, causale FROM pagamenti "
            "WHERE participant_id = ? ORDER BY data, id_movimento", (pid,)
        )]

        quota = sum(s["importo"] for s in servizi)
        incassato = sum(r["incassato"] for r in rate)
        partecipanti.append({
            "participant_id": pid,
            "nome": p["nome"],
            "cognome": p["cognome"],
            "servizi": servizi,
            "quota": quota,
            "incassato": incassato,
            "residuo": quota - incassato,
            "rate": rate,
            "movimenti": movimenti,
        })

    # Totali delle rate della pratica: somma delle rate con lo stesso numero
    rate_totali = {}
    for p in partecipanti:
        for r in p["rate"]:
            totale = rate_totali.setdefault(r["numero"], {
                "numero": r["numero"], "scadenza": r["scadenza"],
                "importo": 0, "incassato": 0, "residuo": 0,
            })
            for campo in ("importo", "incassato", "residuo"):
                totale[campo] += r[campo]

    return {
        "practice_id": pratica["practice_id"],
        "virtual_iban": pratica["virtual_iban"],
        "destinazione": pratica["destinazione"],
        "data_inizio": pratica["data_inizio"],
        "data_fine": pratica["data_fine"],
        "partecipanti": partecipanti,
        "totali": {
            "quota": sum(p["quota"] for p in partecipanti),
            "incassato": sum(p["incassato"] for p in partecipanti),
            "residuo": sum(p["residuo"] for p in partecipanti),
            "rate": [rate_totali[n] for n in sorted(rate_totali)],
        },
    }

def elenco_pratiche(conn: sqlite3.Connection) -> list[dict]:
    """Elenco sintetico di tutte le pratiche salvate."""
    return [dict(r) for r in conn.execute(
        "SELECT practice_id, virtual_iban, destinazione, data_inizio, data_fine "
        "FROM pratiche ORDER BY practice_id"
    )]