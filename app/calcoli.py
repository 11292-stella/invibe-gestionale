"""
Logica di calcolo del gestionale: quote, rate e imputazione dei bonifici.

Questo modulo non usa né il database né il web: riceve numeri e restituisce numeri.
Così si può testare da solo, con test veloci e indipendenti.

Tutti gli importi sono in CENTESIMI (int): 350,00 € = 35000.
"""

from decimal import Decimal, ROUND_HALF_UP


# ---------------------------------------------------------------
# Conversioni euro <-> centesimi
# ---------------------------------------------------------------

def euro_a_cent(importo: str) -> int:
    """
    Converte un importo in euro scritto come testo (es. "350.00") in centesimi (35000).

    Si parte da una stringa e non da un float per non introdurre errori di arrotondamento.
    Rifiuta importi con più di due decimali (es. "10.005"), che non sono centesimi validi.
    """
    valore = Decimal(importo)
    if valore != valore.quantize(Decimal("0.01")):
        raise ValueError(f"Importo con più di due decimali: {importo}")
    return int(valore * 100)


def cent_a_euro(cent: int) -> Decimal:
    """Converte centesimi (35000) in euro (Decimal('350.00')), per mostrarli."""
    return (Decimal(cent) / 100).quantize(Decimal("0.01"))


# ---------------------------------------------------------------
# Quota e rate
# ---------------------------------------------------------------

def calcola_quota(importi_servizi: list[int]) -> int:
    """La quota di un partecipante è la somma dei suoi servizi."""
    return sum(importi_servizi)


def calcola_rate(quota: int, percentuali: list[int]) -> list[int]:
    """
    Divide la quota in rate secondo le percentuali (es. [40, 30, 30]).

    - Tutte le rate tranne l'ultima: percentuale della quota, arrotondata al centesimo
      (arrotondamento commerciale: da 0,5 in su si arrotonda per eccesso).
    - L'ultima rata: differenza tra la quota e le rate precedenti.

    Così la somma delle rate è SEMPRE uguale alla quota, anche quando
    le percentuali producono frazioni di centesimo.
    """
    if sum(percentuali) != 100:
        raise ValueError(f"Le percentuali devono sommare 100, invece sommano {sum(percentuali)}")

    rate = []
    for percentuale in percentuali[:-1]:
        importo = (Decimal(quota) * percentuale / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        rate.append(int(importo))

    ultima = quota - sum(rate)
    rate.append(ultima)
    return rate


# ---------------------------------------------------------------
# Imputazione dei bonifici
# ---------------------------------------------------------------

def imputa_pagamento(importo: int, rate: list[dict]) -> tuple[list[dict], int]:
    """
    Distribuisce un bonifico sulle rate di un partecipante, in ordine di scadenza.

    `rate` è una lista di dizionari con:
        - "id": identificativo della rata
        - "scadenza": data in formato AAAA-MM-GG
        - "residuo": quanto manca ancora da pagare su quella rata (in centesimi)

    Prima si salda la rata con la scadenza più vicina, l'eccedenza passa alla successiva.

    Restituisce:
        - la lista delle imputazioni: [{"rata_id": ..., "importo": ...}, ...]
        - l'eventuale eccedenza non imputata (se il bonifico supera tutto il residuo)
    """
    if importo <= 0:
        raise ValueError(f"L'importo del bonifico deve essere positivo: {importo}")

    imputazioni = []
    da_imputare = importo

    for rata in sorted(rate, key=lambda r: r["scadenza"]):
        if da_imputare == 0:
            break
        if rata["residuo"] <= 0:
            continue  # rata già saldata, si passa alla successiva

        quota_su_rata = min(da_imputare, rata["residuo"])
        imputazioni.append({"rata_id": rata["id"], "importo": quota_su_rata})
        da_imputare -= quota_su_rata

    return imputazioni, da_imputare