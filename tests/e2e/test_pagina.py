"""
Test end-to-end della pagina di consultazione con Playwright.

Verificano che la pagina mostri all'utente i risultati attesi del documento,
e che i form di caricamento funzionino dal browser.
"""

import json
import re

import pytest
from playwright.sync_api import Page, expect

from tests.conftest import FILE_MOVIMENTI, FILE_PRENOTAZIONE


def apri_pratica(page: Page, practice_id: str = "CASE-1001"):
    page.goto(f"/pratiche/{practice_id}")


# ===============================================================
# Navigazione
# ===============================================================

def test_home_elenca_la_pratica(page: Page):
    page.goto("/")
    elenco = page.get_by_test_id("elenco-pratiche")
    expect(elenco).to_contain_text("CASE-1001")
    expect(elenco).to_contain_text("DEMO-IBAN-1001")


def test_dalla_home_si_apre_la_pratica(page: Page):
    page.goto("/")
    page.get_by_role("link", name="CASE-1001").click()
    expect(page).to_have_url(re.compile(r"/pratiche/CASE-1001$"))
    expect(page.get_by_test_id("virtual-iban")).to_have_text("DEMO-IBAN-1001")


# ===============================================================
# Risultati attesi del documento, come li vede l'utente
# ===============================================================

def test_totali_della_pratica(page: Page):
    apri_pratica(page)
    totali = page.get_by_test_id("totali-pratica")
    saldo = totali.get_by_test_id("saldo")

    expect(saldo.get_by_test_id("quota")).to_have_text("800,00 €")
    expect(saldo.get_by_test_id("incassato")).to_have_text("250,00 €")
    expect(saldo.get_by_test_id("residuo")).to_have_text("550,00 €")

    rata1 = totali.get_by_test_id("rata-1")
    expect(rata1.get_by_test_id("importo")).to_have_text("320,00 €")
    expect(rata1.get_by_test_id("incassato")).to_have_text("250,00 €")
    expect(rata1.get_by_test_id("residuo")).to_have_text("70,00 €")
    expect(rata1).to_contain_text("Parziale")

    for numero in (2, 3):
        rata = totali.get_by_test_id(f"rata-{numero}")
        expect(rata.get_by_test_id("importo")).to_have_text("240,00 €")
        expect(rata.get_by_test_id("residuo")).to_have_text("240,00 €")
        expect(rata).to_contain_text("Da pagare")


def test_scadenze_delle_rate(page: Page):
    apri_pratica(page)
    totali = page.get_by_test_id("totali-pratica")
    for numero, scadenza in [(1, "15/12/2026"), (2, "15/02/2027"), (3, "15/04/2027")]:
        expect(totali.get_by_test_id(f"rata-{numero}").get_by_test_id("scadenza")).to_have_text(scadenza)


@pytest.mark.parametrize("pid, nome, quota, incassato, residuo, rate, rata1_incassato, rata1_residuo", [
    ("P-001", "Mario Rossi", "450,00 €", "150,00 €", "300,00 €",
     ["180,00 €", "135,00 €", "135,00 €"], "150,00 €", "30,00 €"),
    ("P-002", "Giulia Bianchi", "350,00 €", "100,00 €", "250,00 €",
     ["140,00 €", "105,00 €", "105,00 €"], "100,00 €", "40,00 €"),
])
def test_partecipante(page: Page, pid, nome, quota, incassato, residuo, rate, rata1_incassato, rata1_residuo):
    apri_pratica(page)
    sezione = page.get_by_test_id(f"partecipante-{pid}")
    saldo = sezione.get_by_test_id("saldo")

    expect(sezione.get_by_test_id("nome")).to_have_text(nome)
    expect(saldo.get_by_test_id("quota")).to_have_text(quota)
    expect(saldo.get_by_test_id("incassato")).to_have_text(incassato)
    expect(saldo.get_by_test_id("residuo")).to_have_text(residuo)

    for numero, importo in enumerate(rate, start=1):
        expect(sezione.get_by_test_id(f"rata-{numero}").get_by_test_id("importo")).to_have_text(importo)

    rata1 = sezione.get_by_test_id("rata-1")
    expect(rata1.get_by_test_id("incassato")).to_have_text(rata1_incassato)
    expect(rata1.get_by_test_id("residuo")).to_have_text(rata1_residuo)
    expect(rata1).to_contain_text("Parziale")

    for numero in (2, 3):
        rata = sezione.get_by_test_id(f"rata-{numero}")
        expect(rata.get_by_test_id("incassato")).to_have_text("0,00 €")
        expect(rata).to_contain_text("Da pagare")


@pytest.mark.parametrize("pid, id_movimento, importo", [
    ("P-001", "TX-001", "150,00 €"),
    ("P-002", "TX-002", "100,00 €"),
])
def test_movimenti_attribuiti(page: Page, pid, id_movimento, importo):
    apri_pratica(page)
    movimento = page.get_by_test_id(f"partecipante-{pid}").get_by_test_id(f"movimento-{id_movimento}")
    expect(movimento.get_by_test_id("importo")).to_have_text(importo)


def test_dati_presenti_dopo_aggiornamento_pagina(page: Page):
    apri_pratica(page)
    page.reload()
    saldo = page.get_by_test_id("totali-pratica").get_by_test_id("saldo")
    expect(saldo.get_by_test_id("incassato")).to_have_text("250,00 €")


# ===============================================================
# Form di caricamento
# ===============================================================

def test_crea_nuova_pratica_dal_form(page: Page):
    # Stessa prenotazione demo con numero pratica, IBAN e partecipanti diversi
    dati = json.loads(FILE_PRENOTAZIONE.read_text(encoding="utf-8"))
    dati["practice_id"] = "CASE-2001"
    dati["virtual_iban"] = "DEMO-IBAN-2001"
    for indice, partecipante in enumerate(dati["participants"], start=1):
        partecipante["participant_id"] = f"P-20{indice}"

    page.goto("/")
    page.get_by_test_id("file-pratica").set_input_files(files=[{
        "name": "nuova_pratica.json",
        "mimeType": "application/json",
        "buffer": json.dumps(dati).encode("utf-8"),
    }])
    page.get_by_test_id("carica-pratica").click()

    expect(page).to_have_url(re.compile(r"/pratiche/CASE-2001$"))
    saldo = page.get_by_test_id("totali-pratica").get_by_test_id("saldo")
    expect(saldo.get_by_test_id("quota")).to_have_text("800,00 €")
    expect(saldo.get_by_test_id("incassato")).to_have_text("0,00 €")
    expect(page.get_by_test_id("nessun-movimento")).to_have_count(2)


def test_pratica_duplicata_mostra_messaggio(page: Page):
    page.goto("/")
    page.get_by_test_id("file-pratica").set_input_files(FILE_PRENOTAZIONE)
    page.get_by_test_id("carica-pratica").click()
    expect(page.get_by_test_id("messaggio")).to_contain_text("già presente")


def test_reimport_bonifici_non_duplica(page: Page):
    page.goto("/")
    page.get_by_test_id("file-movimenti").set_input_files(FILE_MOVIMENTI)
    page.get_by_test_id("carica-movimenti").click()
    expect(page.get_by_test_id("messaggio")).to_contain_text("Bonifici registrati: 0")
    expect(page.get_by_test_id("messaggio")).to_contain_text("già importato")

    apri_pratica(page)
    saldo = page.get_by_test_id("totali-pratica").get_by_test_id("saldo")
    expect(saldo.get_by_test_id("incassato")).to_have_text("250,00 €")