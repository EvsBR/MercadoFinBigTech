"""Drawdown: distância do preço ao último recorde, e os episódios de queda.

Usa o fechamento de tela (sem dividendos), o mesmo da aba Análise Técnica, para que o número
do Resumo e o da análise sejam idênticos."""
from __future__ import annotations

import pandas as pd

from ..util import dstr, num, preco_tela

ID, NOME, CHAVE, VERSAO = "drawdown", "Drawdown", "drawdown", 2


def serie(s: pd.Series) -> pd.Series:
    return s / s.cummax() - 1


def episodios(s: pd.Series) -> list[dict]:
    dd = serie(s)
    dates = s.index
    eps, cur = [], None
    ultimo_pico = 0
    for i, v in enumerate(dd.values):
        if v < 0:
            if cur is None:
                cur = {"peak_i": ultimo_pico, "trough_i": i, "depth": v}
            elif v < cur["depth"]:
                cur["trough_i"], cur["depth"] = i, v
        else:
            if cur is not None:
                cur["rec_i"] = i
                eps.append(cur)
                cur = None
            ultimo_pico = i
    if cur is not None:
        cur["rec_i"] = None
        eps.append(cur)

    out = []
    last = dates[-1]
    for e in eps:
        peak, trough = dates[e["peak_i"]], dates[e["trough_i"]]
        rec = dates[e["rec_i"]] if e["rec_i"] is not None else None
        out.append({
            "peak": dstr(peak), "trough": dstr(trough), "recovery": dstr(rec),
            "depth": num(e["depth"]),
            "days_down": int((trough - peak).days),
            "days_recover": int((rec - trough).days) if rec is not None else None,
            "days_total": int(((rec if rec is not None else last) - peak).days),
            "ongoing": rec is None,
        })
    return out


def calcular(ctx) -> dict:
    s = preco_tela(ctx.df)
    dd = serie(s)
    eps = episodios(s)
    grandes = sorted([e for e in eps if e["depth"] is not None and e["depth"] <= -0.10],
                     key=lambda e: e["depth"])
    atual = next((e for e in reversed(eps) if e["ongoing"]), None)
    pior = grandes[0] if grandes else (min(eps, key=lambda e: e["depth"]) if eps else None)
    dados = {
        "episodes": grandes[:25], "current": atual,
        "count_20": sum(1 for e in eps if e["depth"] is not None and e["depth"] <= -0.20),
        "count_30": sum(1 for e in eps if e["depth"] is not None and e["depth"] <= -0.30),
    }
    resumo = {"dd_current": num(dd.iloc[-1]),
              "dd_max": pior["depth"] if pior else None,
              "dd_max_peak": pior["peak"] if pior else None,
              "dd_max_trough": pior["trough"] if pior else None,
              "dd_max_recovery": pior["recovery"] if pior else None}
    return {"dados": dados, "resumo": resumo}
