"""
Applicazione web FastAPI: API e pagine del mini gestionale.

- API (JSON):  /api/...  → per integrazioni, test automatici e /docs
- Pagine HTML: /, /pratiche/{id} → consultazione e caricamento dei file

Qui si ricevono le richieste e si formattano le risposte:
la logica sta in calcoli.py, l'accesso ai dati in db.py.
"""

import csv
import io
import json
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.calcoli import cent_a_euro
from app.db import (
    ErroreImport,
    connetti,
    elenco_pratiche,
    inizializza_db,
    leggi_pratica,
    registra_pagamento,
    salva_pratica,
)

COLONNE_CSV = {"id_movimento", "data", "iban_virtuale", "importo", "causale"}
CAMPI_IMPORTO = {"importo", "quota", "incassato", "residuo", "eccedenza"}

app = FastAPI(
    title="Mini gestionale InVibe",
    description="Pratiche di viaggio, partecipanti, rate e bonifici",
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# ---------------------------------------------------------------
# Connessione al database per ogni richiesta
# ---------------------------------------------------------------

def get_db():
    """
    Apre una connessione per la richiesta e la chiude alla fine.
    Lo schema usa CREATE TABLE IF NOT EXISTS: al primo avvio crea le tabelle,
    poi non fa nulla.
    """
    conn = connetti()
    inizializza_db(conn)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------
# Formattazione
# ---------------------------------------------------------------

def formato_euro(cent: int) -> str:
    """35000 -> '350,00 €' (formato italiano, per le pagine HTML)."""
    testo = f"{cent_a_euro(cent):,.2f}"  # 1,234.56
    return testo.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def formato_data(iso: str) -> str:
    """'2026-12-15' -> '15/12/2026'."""
    anno, mese, giorno = iso.split("-")
    return f"{giorno}/{mese}/{anno}"


templates.env.filters["euro"] = formato_euro
templates.env.filters["data"] = formato_data


def importi_in_euro(dati):
    """
    Converte tutti gli importi da centesimi a euro per le risposte API.
    Gli importi diventano stringhe ("450.00") per non perdere precisione nel JSON.
    """
    if isinstance(dati, list):
        return [importi_in_euro(x) for x in dati]
    if isinstance(dati, dict):
        return {
            chiave: str(cent_a_euro(valore))
            if chiave in CAMPI_IMPORTO and isinstance(valore, int)
            else importi_in_euro(valore)
            for chiave, valore in dati.items()
        }
    return dati


# ---------------------------------------------------------------
# Import dei file (usati sia dalle API sia dai form HTML)
# ---------------------------------------------------------------

def importa_pratica(conn, contenuto: bytes) -> str:
    """Legge il JSON della prenotazione e salva la pratica."""
    try:
        dati = json.loads(contenuto.decode("utf-8-sig"))
        return salva_pratica(conn, dati)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ErroreImport("Il file non è un JSON valido")
    except (KeyError, TypeError) as errore:
        raise ErroreImport(f"Struttura del file non valida, campo mancante: {errore}")
    except ValueError as errore:
        raise ErroreImport(str(errore))


def importa_movimenti(conn, contenuto: bytes) -> dict:
    """
    Legge il CSV dei movimenti e registra ogni bonifico.
    Ogni riga è indipendente: i bonifici validi vengono registrati,
    quelli non attribuibili vengono scartati con il motivo.
    """
    try:
        testo = contenuto.decode("utf-8-sig")  # utf-8-sig gestisce anche i CSV salvati da Excel
    except UnicodeDecodeError:
        raise ErroreImport("Il file CSV deve essere in formato UTF-8")

    lettore = csv.DictReader(io.StringIO(testo))
    mancanti = COLONNE_CSV - set(lettore.fieldnames or [])
    if mancanti:
        raise ErroreImport(f"Colonne mancanti nel CSV: {', '.join(sorted(mancanti))}")

    registrati, scartati = [], []
    for riga in lettore:
        try:
            registrati.append(registra_pagamento(conn, riga))
        except (ErroreImport, ValueError) as errore:
            scartati.append({"id_movimento": riga.get("id_movimento"), "motivo": str(errore)})

    return {"registrati": registrati, "scartati": scartati}


# ---------------------------------------------------------------
# API JSON
# ---------------------------------------------------------------

@app.post("/api/pratiche", status_code=201, tags=["API"])
async def api_importa_pratica(file: UploadFile = File(...), conn=Depends(get_db)):
    """Crea la pratica dal file prenotazione_demo.json."""
    try:
        practice_id = importa_pratica(conn, await file.read())
    except ErroreImport as errore:
        raise HTTPException(status_code=400, detail=str(errore))
    return {"practice_id": practice_id}


@app.post("/api/movimenti", tags=["API"])
async def api_importa_movimenti(file: UploadFile = File(...), conn=Depends(get_db)):
    """Importa i bonifici dal file movimenti_bancari_demo.csv."""
    try:
        esito = importa_movimenti(conn, await file.read())
    except ErroreImport as errore:
        raise HTTPException(status_code=400, detail=str(errore))
    return importi_in_euro(esito)


@app.get("/api/pratiche", tags=["API"])
def api_elenco_pratiche(conn=Depends(get_db)):
    """Elenco delle pratiche salvate."""
    return elenco_pratiche(conn)


@app.get("/api/pratiche/{practice_id}", tags=["API"])
def api_leggi_pratica(practice_id: str, conn=Depends(get_db)):
    """Riepilogo completo della pratica: partecipanti, rate, movimenti e totali."""
    pratica = leggi_pratica(conn, practice_id)
    if pratica is None:
        raise HTTPException(status_code=404, detail=f"Pratica {practice_id} non trovata")
    return importi_in_euro(pratica)


# ---------------------------------------------------------------
# Pagine HTML
# ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def pagina_home(request: Request, messaggio: str | None = None, conn=Depends(get_db)):
    return templates.TemplateResponse(
        request, "index.html", {"pratiche": elenco_pratiche(conn), "messaggio": messaggio}
    )


@app.post("/importa/pratica", include_in_schema=False)
async def form_importa_pratica(file: UploadFile = File(...), conn=Depends(get_db)):
    try:
        practice_id = importa_pratica(conn, await file.read())
    except ErroreImport as errore:
        return RedirectResponse(f"/?messaggio={quote(str(errore))}", status_code=303)
    return RedirectResponse(f"/pratiche/{practice_id}", status_code=303)


@app.post("/importa/movimenti", include_in_schema=False)
async def form_importa_movimenti(file: UploadFile = File(...), conn=Depends(get_db)):
    try:
        esito = importa_movimenti(conn, await file.read())
        messaggio = f"Bonifici registrati: {len(esito['registrati'])} · scartati: {len(esito['scartati'])}"
        for registrato in esito["registrati"]:
            if registrato["eccedenza"] > 0:
                messaggio += f" | {registrato['id_movimento']}: eccedenza di {formato_euro(registrato['eccedenza'])} non imputata"
        for scartato in esito["scartati"]:
            messaggio += f" | {scartato['motivo']}"
    except ErroreImport as errore:
        messaggio = str(errore)
    return RedirectResponse(f"/?messaggio={quote(messaggio)}", status_code=303)


@app.get("/pratiche/{practice_id}", response_class=HTMLResponse, include_in_schema=False)
def pagina_pratica(request: Request, practice_id: str, conn=Depends(get_db)):
    pratica = leggi_pratica(conn, practice_id)
    if pratica is None:
        raise HTTPException(status_code=404, detail=f"Pratica {practice_id} non trovata")
    return templates.TemplateResponse(request, "pratica.html", {"pratica": pratica})