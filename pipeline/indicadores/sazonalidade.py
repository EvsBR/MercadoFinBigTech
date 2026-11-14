"""Sazonalidade: retorno por mês, bimestre e trimestre, ano a ano."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..util import num

ID, NOME, CHAVE, VERSAO = "sazonalidade", "Sazonalidade", "seasonality", 1
FREQS = {
    "M": {"months": 1, "labels": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                                  "Jul", "Ago", "Set", "Out", "Nov", "Dez"]},
    "B": {"months": 2, "labels": ["Jan–Fev", "Mar–Abr", "Mai–Jun",
                                  "Jul–Ago", "Set–Out", "Nov–Dez"]},
    "Q": {"months": 3, "labels": ["1º tri", "2º tri", "3º tri", "4º tri"]},
}


def tabela(s_full: pd.Series, months: int, min_year: int | None = None) -> dict:
    """Tabela ano × período, só com períodos completos (o período em curso entra como parcial)."""
    m = s_full.resample("ME").last()
    mret = (m / m.shift(1) - 1).iloc[1:]
    last_day = s_full.index[-1]
    month_partial = last_day < (last_day + pd.offsets.BMonthEnd(0))

    df = pd.DataFrame({"r": mret.values}, index=mret.index)
    df["year"] = df.index.year
    df["p"] = (df.index.month - 1) // months
    g = df.groupby(["year", "p"])["r"]
    comp = g.apply(lambda x: float(np.prod(1 + x.values) - 1))
    cnt = g.count()

    years = list(range(int(df["year"].min()), int(df["year"].max()) + 1))
    nper = 12 // months
    values = [[None] * nper for _ in years]
    partial = []
    last_key = (int(df["year"].iloc[-1]), int(df["p"].iloc[-1]))
    for (y, p), v in comp.items():
        yi = years.index(int(y))
        key = (int(y), int(p))
        complete = cnt[(y, p)] == months
        is_current = key == last_key and (month_partial or not complete)
        if is_current:
            values[yi][p] = num(v)
            partial.append([yi, int(p)])
        elif complete:
            values[yi][p] = num(v)

    yr = df.groupby("year")["r"].apply(lambda x: float(np.prod(1 + x.values) - 1))
    ycount = df.groupby("year")["r"].count()
    annual, annual_partial = [], []
    for y in years:
        annual.append(num(yr.get(y, np.nan)))
        annual_partial.append(bool(ycount.get(y, 0) < 12 or (y == last_key[0] and month_partial)))
    if min_year is not None and years and years[0] < min_year:
        k = next((i for i, y in enumerate(years) if y >= min_year), len(years))
        years, values = years[k:], values[k:]
        annual, annual_partial = annual[k:], annual_partial[k:]
        partial = [[yi - k, pp] for yi, pp in partial if yi >= k]
    return {"years": years, "values": values, "partial": partial,
            "annual": annual, "annual_partial": annual_partial}


def calcular(ctx) -> dict:
    s_full = ctx.df_cheio["adj_close"]
    if ctx.inicio is not None:   # ~2 meses antes do início, para ter o fechamento do mês anterior
        s_full = s_full[s_full.index >= ctx.inicio - pd.Timedelta(days=62)]
    ano = None if ctx.inicio is None else ctx.inicio.year
    return {"dados": {f: tabela(s_full, FREQS[f]["months"], ano) for f in FREQS}, "resumo": {}}
