"""
Impostazioni condivise dei test.

Ogni test usa un database SQLite NUOVO in una cartella temporanea:
i test non toccano invibe.db e non si influenzano a vicenda.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

CARTELLA_DATI = Path(__file__).resolve().parent.parent / "data"
FILE_PRENOTAZIONE = CARTELLA_DATI / "prenotazione_demo.json"
FILE_MOVIMENTI = CARTELLA_DATI / "movimenti_bancari_demo.csv"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client HTTP di test collegato a un database vuoto e temporaneo."""
    monkeypatch.setenv("INVIBE_DB", str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def carica(client):
    """
    Funzione per caricare un file su un endpoint.
    Accetta un percorso (Path) oppure contenuto in byte.
    """
    def _carica(url: str, file, nome: str = "file"):
        contenuto = file.read_bytes() if isinstance(file, Path) else file
        return client.post(url, files={"file": (nome, contenuto)})
    return _carica


@pytest.fixture
def pratica_demo(client, carica):
    """Database con la pratica demo e i bonifici demo già importati."""
    assert carica("/api/pratiche", FILE_PRENOTAZIONE).status_code == 201
    assert carica("/api/movimenti", FILE_MOVIMENTI).status_code == 200
    return client