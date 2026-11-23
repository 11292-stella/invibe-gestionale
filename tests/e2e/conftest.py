"""
Impostazioni dei test end-to-end con Playwright.

Prima dei test:
1. avvia il server uvicorn su una porta dedicata, con un database temporaneo
2. carica la pratica e i bonifici demo tramite le API

Così i test E2E girano su un'app vera, senza toccare invibe.db.
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.conftest import FILE_MOVIMENTI, FILE_PRENOTAZIONE

CARTELLA_PROGETTO = Path(__file__).resolve().parents[2]
PORTA = 8765


@pytest.fixture(scope="session")
def base_url(tmp_path_factory):
    """Avvia il server per tutta la sessione di test e restituisce il suo indirizzo."""
    database = tmp_path_factory.mktemp("e2e") / "e2e.db"
    ambiente = {**os.environ, "INVIBE_DB": str(database)}

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORTA)],
        cwd=CARTELLA_PROGETTO,
        env=ambiente,
    )
    url = f"http://127.0.0.1:{PORTA}"

    # Attende che il server risponda (massimo 10 secondi)
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{url}/api/pratiche")
            break
        except OSError:
            time.sleep(0.2)
    else:
        server.terminate()
        raise RuntimeError("Il server di test non è partito")

    yield url

    server.terminate()
    server.wait()


@pytest.fixture(scope="session", autouse=True)
def dati_demo(playwright, base_url):
    """Carica i file demo tramite le API, una volta sola per tutti i test E2E."""
    api = playwright.request.new_context(base_url=base_url)
    for endpoint, file, tipo in [
        ("/api/pratiche", FILE_PRENOTAZIONE, "application/json"),
        ("/api/movimenti", FILE_MOVIMENTI, "text/csv"),
    ]:
        risposta = api.post(endpoint, multipart={
            "file": {"name": file.name, "mimeType": tipo, "buffer": file.read_bytes()}
        })
        assert risposta.ok, risposta.text()
    api.dispose()