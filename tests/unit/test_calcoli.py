"""
Unit test della logica di calcolo (app/calcoli.py).

Verificano le regole della prova senza database né server:
quote, rate 40/30/30 con l'ultima per differenza, imputazione dei bonifici.
"""

import pytest

from app.calcoli import (
    calcola_quota,
    calcola_rate,
    cent_a_euro,
    euro_a_cent,
    imputa_pagamento,
)

PERCENTUALI = [40, 30, 30]


# ---------------------------------------------------------------
# Conversioni
# ---------------------------------------------------------------

@pytest.mark.parametrize("testo, atteso", [
    ("350.00", 35000),
    ("100.00", 10000),
    ("0.01", 1),
    ("150", 15000),
])
def test_euro_a_cent(testo, atteso):
    assert euro_a_cent(testo) == atteso


def test_euro_a_cent_rifiuta_frazioni_di_centesimo():
    with pytest.raises(ValueError):
        euro_a_cent("10.005")


def test_cent_a_euro():
    assert str(cent_a_euro(35000)) == "350.00"
    assert str(cent_a_euro(1)) == "0.01"


# ---------------------------------------------------------------
# Quota
# ---------------------------------------------------------------

def test_quota_mario_somma_dei_servizi():
    # Pacchetto 350,00 + Navetta 100,00
    assert calcola_quota([35000, 10000]) == 45000


def test_quota_giulia_un_solo_servizio():
    assert calcola_quota([35000]) == 35000


# ---------------------------------------------------------------
# Rate: risultati attesi del documento
# ---------------------------------------------------------------

@pytest.mark.parametrize("quota, rate_attese", [
    (45000, [18000, 13500, 13500]),  # Mario Rossi: 180 / 135 / 135
    (35000, [14000, 10500, 10500]),  # Giulia Bianchi: 140 / 105 / 105
    (80000, [32000, 24000, 24000]),  # Totale pratica: 320 / 240 / 240
])
def test_rate_risultati_attesi(quota, rate_attese):
    assert calcola_rate(quota, PERCENTUALI) == rate_attese


# ---------------------------------------------------------------
# Rate: arrotondamento e ultima rata per differenza
# ---------------------------------------------------------------

def test_rate_con_arrotondamento():
    # 333,33 €: 40% = 133,332 -> 133,33 | 30% = 99,999 -> 100,00 | resto = 100,00
    assert calcola_rate(33333, PERCENTUALI) == [13333, 10000, 10000]


def test_rate_arrotondamento_mezzo_centesimo_per_eccesso():
    # 0,05 €: 40% = 0,02 | 30% = 0,015 -> 0,02 (per eccesso, non al pari) | resto = 0,01
    assert calcola_rate(5, PERCENTUALI) == [2, 2, 1]


@pytest.mark.parametrize("quota", range(0, 2001))
def test_somma_rate_sempre_uguale_alla_quota(quota):
    # Proprietà fondamentale: per qualunque quota da 0,00 a 20,00 € le rate sommano la quota
    assert sum(calcola_rate(quota, PERCENTUALI)) == quota


def test_rate_percentuali_che_non_sommano_100():
    with pytest.raises(ValueError):
        calcola_rate(45000, [40, 30, 20])


# ---------------------------------------------------------------
# Imputazione dei bonifici
# ---------------------------------------------------------------

def rate_di_mario():
    """Rate di Mario Rossi ancora tutte da pagare."""
    return [
        {"id": 1, "scadenza": "2026-12-15", "residuo": 18000},
        {"id": 2, "scadenza": "2027-02-15", "residuo": 13500},
        {"id": 3, "scadenza": "2027-04-15", "residuo": 13500},
    ]


def test_acconto_parziale_va_tutto_sulla_rata_1():
    # TX-001: 150,00 € a Mario -> rata 1 (residuo 180,00) incassa 150,00
    imputazioni, eccedenza = imputa_pagamento(15000, rate_di_mario())
    assert imputazioni == [{"rata_id": 1, "importo": 15000}]
    assert eccedenza == 0


def test_bonifico_che_copre_piu_rate():
    # 200,00 €: 180,00 saldano la rata 1, i 20,00 restanti vanno sulla rata 2
    imputazioni, eccedenza = imputa_pagamento(20000, rate_di_mario())
    assert imputazioni == [
        {"rata_id": 1, "importo": 18000},
        {"rata_id": 2, "importo": 2000},
    ]
    assert eccedenza == 0


def test_rata_gia_saldata_viene_saltata():
    rate = rate_di_mario()
    rate[0]["residuo"] = 0  # rata 1 già pagata
    imputazioni, _ = imputa_pagamento(5000, rate)
    assert imputazioni == [{"rata_id": 2, "importo": 5000}]


def test_ordine_per_scadenza_anche_se_le_rate_arrivano_in_disordine():
    rate = list(reversed(rate_di_mario()))
    imputazioni, _ = imputa_pagamento(15000, rate)
    assert imputazioni[0]["rata_id"] == 1


def test_bonifico_superiore_al_dovuto_restituisce_eccedenza():
    # Totale dovuto 450,00 €, pagati 500,00 € -> 50,00 € di eccedenza
    imputazioni, eccedenza = imputa_pagamento(50000, rate_di_mario())
    assert sum(i["importo"] for i in imputazioni) == 45000
    assert eccedenza == 5000


@pytest.mark.parametrize("importo", [0, -100])
def test_bonifico_non_positivo_rifiutato(importo):
    with pytest.raises(ValueError):
        imputa_pagamento(importo, rate_di_mario())