"""Preço, retornos móveis e estatísticas básicas do ativo."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..util import dstr, num, price, series_list

ID, NOME, CHAVE, VERSAO = "retornos", "Preço e retornos", "series", 1
PREGOES_ANO = 252


def semanal_ultimo(s: pd.Series) -> pd.Series:
    """Último pregão de cada semana, com a data real do pregão."""
    return s.groupby(s.index.to_period("W-FRI")).tail(1)


def calcular(ctx) -> dict:
    s = ctx.s
    wl = semanal_ultimo(s)
    r1 = s / s.shift(PREGOES_ANO) - 1
    r3 = (s / s.shift(3 * PREGOES_ANO)) ** (1 / 3) - 1
    diario = s / s.shift(1) - 1
    ultimo = s.iloc[-1]
    ano_anterior = s[s.index.year < s.index[-1].year]
    anos = (s.index[-1] - s.index[0]).days / 365.25
    dados = {"d": [dstr(x) for x in wl.index], "p": [price(v) for v in wl.values],
             "r1": series_list(r1.reindex(wl.index), 4), "r3": series_list(r3.reindex(wl.index), 4)}
    resumo = {
        "first_date": dstr(s.index[0]), "last_date": dstr(s.index[-1]), "last_price": price(ultimo),
        "ytd": num(ultimo / ano_anterior.iloc[-1] - 1 if len(ano_anterior) else np.nan),
        "ret_1y": num(r1.iloc[-1]),
        "cagr": num((ultimo / s.iloc[0]) ** (1 / anos) - 1 if anos > 0.5 else np.nan),
        "total": num(ultimo / s.iloc[0] - 1, 3),
        "vol_1y": num(diario.tail(PREGOES_ANO).std() * math.sqrt(PREGOES_ANO)),
    }
    return {"dados": dados, "resumo": resumo}
