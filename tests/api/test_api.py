"""
Test delle API.

Il gruppo principale verifica, riga per riga, la tabella "Risultati attesi"
del documento della prova. Gli altri gruppi verificano gli errori e i casi limite.
"""

import pytest

from tests.conftest import FILE_PRENOTAZIONE

INTESTAZIONE_CSV = "id_movimento,data,iban_virtuale,importo,causale"


def csv_movimenti(*righe: str) -> bytes:
    """Crea al volo un CSV di movimenti con le righe indicate."""
    return "\n".join([INTESTAZIONE_CSV, *righe]).encode("utf-8")


def riepilogo(client) -> dict:
    risposta = client.get("/api/pratiche/CASE-1001")
    assert risposta.status_code == 200
    return risposta.json()


def partecipante(dati: dict, participant_id: str) -> dict:
    return next(p for p in dati["partecipanti"] if p["participant_id"] == participant_id)


# ===============================================================
# Risultati attesi del documento
# ===============================================================

def test_pratica_e_iban_virtuale_unico(pratica_demo):
    dati = riepilogo(pratica_demo)
    assert dati["practice_id"] == "CASE-1001"
    assert dati["virtual_iban"] == "DEMO-IBAN-1001"


@pytest.mark.parametrize("pid, servizi, quota, rate", [
    ("P-001", ["350.00", "100.00"], "450.00", ["180.00", "135.00", "135.00"]),  # Mario Rossi
    ("P-002", ["350.00"],           "350.00", ["140.00", "105.00", "105.00"]),  # Giulia Bianchi
])
def test_quote_e_rate_dei_partecipanti(pratica_demo, pid, servizi, quota, rate):
    p = partecipante(riepilogo(pratica_demo), pid)
    assert [s["importo"] for s in p["servizi"]] == servizi
    assert p["quota"] == quota
    assert [r["importo"] for r in p["rate"]] == rate


def test_scadenze_delle_rate(pratica_demo):
    dati = riepilogo(pratica_demo)
    attese = ["2026-12-15", "2027-02-15", "2027-04-15"]
    for p in dati["partecipanti"]:
        assert [r["scadenza"] for r in p["rate"]] == attese
    assert [r["scadenza"] for r in dati["totali"]["rate"]] == attese


@pytest.mark.parametrize("pid, incassato, residuo, rata1_incassato, rata1_residuo, residui_rate_2_3", [
    ("P-001", "150.00", "300.00", "150.00", "30.00", ["135.00", "135.00"]),  # Mario Rossi
    ("P-002", "100.00", "250.00", "100.00", "40.00", ["105.00", "105.00"]),  # Giulia Bianchi
])
def test_saldi_e_rate_dopo_i_bonifici(pratica_demo, pid, incassato, residuo,
                                      rata1_incassato, rata1_residuo, residui_rate_2_3):
    p = partecipante(riepilogo(pratica_demo), pid)
    assert p["incassato"] == incassato
    assert p["residuo"] == residuo

    rata1, rata2, rata3 = p["rate"]
    assert rata1["incassato"] == rata1_incassato
    assert rata1["residuo"] == rata1_residuo
    # Rate 2 e 3: ancora da pagare
    assert [rata2["incassato"], rata3["incassato"]] == ["0.00", "0.00"]
    assert [rata2["residuo"], rata3["residuo"]] == residui_rate_2_3


def test_movimenti_attribuiti(pratica_demo):
    dati = riepilogo(pratica_demo)
    mario = partecipante(dati, "P-001")
    giulia = partecipante(dati, "P-002")
    assert [(m["id_movimento"], m["importo"]) for m in mario["movimenti"]] == [("TX-001", "150.00")]
    assert [(m["id_movimento"], m["importo"]) for m in giulia["movimenti"]] == [("TX-002", "100.00")]


def test_totali_della_pratica(pratica_demo):
    totali = riepilogo(pratica_demo)["totali"]
    assert totali["quota"] == "800.00"
    assert totali["incassato"] == "250.00"
    assert totali["residuo"] == "550.00"

    rata1, rata2, rata3 = totali["rate"]
    assert [r["importo"] for r in totali["rate"]] == ["320.00", "240.00", "240.00"]
    assert (rata1["incassato"], rata1["residuo"]) == ("250.00", "70.00")
    # Rate 2 e 3: 480,00 € ancora da pagare
    assert rata2["incassato"] == rata3["incassato"] == "0.00"
    assert rata2["residuo"] == rata3["residuo"] == "240.00"


# ===============================================================
# Creazione della pratica: errori
# ===============================================================

def test_crea_pratica_risponde_201(client, carica):
    risposta = carica("/api/pratiche", FILE_PRENOTAZIONE)
    assert risposta.status_code == 201
    assert risposta.json() == {"practice_id": "CASE-1001"}


def test_pratica_duplicata_rifiutata(pratica_demo, carica):
    risposta = carica("/api/pratiche", FILE_PRENOTAZIONE)
    assert risposta.status_code == 400
    assert "già presente" in risposta.json()["detail"]


def test_json_non_valido(client, carica):
    risposta = carica("/api/pratiche", b"questo non e' un json")
    assert risposta.status_code == 400


def test_json_con_campi_mancanti(client, carica):
    risposta = carica("/api/pratiche", b'{"practice_id": "CASE-2000"}')
    assert risposta.status_code == 400
    assert "campo mancante" in risposta.json()["detail"]


def test_pratica_inesistente(client):
    assert client.get("/api/pratiche/CASE-9999").status_code == 404


# ===============================================================
# Import dei bonifici: casi limite
# ===============================================================

def test_reimport_stesso_csv_non_duplica_i_pagamenti(pratica_demo, carica):
    from tests.conftest import FILE_MOVIMENTI
    esito = carica("/api/movimenti", FILE_MOVIMENTI).json()
    assert esito["registrati"] == []
    assert all("già importato" in s["motivo"] for s in esito["scartati"])
    # I totali non cambiano
    assert riepilogo(pratica_demo)["totali"]["incassato"] == "250.00"


@pytest.mark.parametrize("riga, motivo", [
    ("TX-100,2026-11-21,IBAN-SCONOSCIUTO,50.00,CASE-1001 Mario Rossi", "nessuna pratica"),
    ("TX-101,2026-11-21,DEMO-IBAN-1001,50.00,Mario Rossi",             "numero di pratica"),
    ("TX-102,2026-11-21,DEMO-IBAN-1001,50.00,CASE-1001 Luca Verdi",    "partecipante non individuato"),
])
def test_bonifico_non_attribuibile_viene_scartato(pratica_demo, carica, riga, motivo):
    esito = carica("/api/movimenti", csv_movimenti(riga)).json()
    assert esito["registrati"] == []
    assert motivo in esito["scartati"][0]["motivo"]
    assert riepilogo(pratica_demo)["totali"]["incassato"] == "250.00"


def test_causale_non_distingue_maiuscole(pratica_demo, carica):
    esito = carica("/api/movimenti", csv_movimenti("TX-200,2026-11-21,DEMO-IBAN-1001,30.00,CASE-1001 MARIO ROSSI")).json()
    assert esito["registrati"][0]["participant_id"] == "P-001"


def test_bonifico_che_salda_rata_1_e_passa_alla_rata_2(pratica_demo, carica):
    # Mario ha 30,00 € residui sulla rata 1: con 50,00 € la salda e 20,00 € vanno sulla rata 2
    carica("/api/movimenti", csv_movimenti("TX-300,2026-11-22,DEMO-IBAN-1001,50.00,CASE-1001 Mario Rossi"))
    rata1, rata2, _ = partecipante(riepilogo(pratica_demo), "P-001")["rate"]
    assert (rata1["incassato"], rata1["residuo"]) == ("180.00", "0.00")
    assert (rata2["incassato"], rata2["residuo"]) == ("20.00", "115.00")


def test_bonifico_superiore_al_dovuto_segnala_eccedenza(pratica_demo, carica):
    # Mario deve ancora 300,00 €: con 350,00 € restano 50,00 € di eccedenza
    esito = carica("/api/movimenti", csv_movimenti("TX-400,2026-11-22,DEMO-IBAN-1001,350.00,CASE-1001 Mario Rossi")).json()
    assert esito["registrati"][0]["eccedenza"] == "50.00"
    assert partecipante(riepilogo(pratica_demo), "P-001")["residuo"] == "0.00"


def test_csv_senza_colonne_obbligatorie(pratica_demo, carica):
    risposta = carica("/api/movimenti", b"id,importo\nTX-1,10.00")
    assert risposta.status_code == 400
    assert "Colonne mancanti" in risposta.json()["detail"]


# ===============================================================
# Persistenza
# ===============================================================

def test_dati_salvati_restano_dopo_un_nuovo_avvio(pratica_demo):
    from fastapi.testclient import TestClient
    from app.main import app
    # Un nuovo client equivale a riavviare l'app: lo stesso database deve contenere ancora i dati
    nuovo_client = TestClient(app)
    assert riepilogo(nuovo_client)["totali"]["incassato"] == "250.00"