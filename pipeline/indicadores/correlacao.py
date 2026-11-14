"""Correlações com retornos semanais: móvel contra as referências, matrizes e média entre pares."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..util import num, series_list

ID, NOME, CHAVE, VERSAO = "correlacao", "Correlações", "corr", 1
JANELAS = {"1a": 52, "3a": 156, "5a": 260, "10a": 520, "tudo": None}   # em semanas


def painel_semanal(precos: dict[str, pd.Series]) -> tuple[pd.DataFrame, list[str]]:
    wk = pd.DataFrame({k: s.groupby(s.index.to_period("W-FRI")).last()
                       for k, s in precos.items()}).sort_index()
    ret = wk / wk.shift(1) - 1
    return ret, [p.end_time.strftime("%Y-%m-%d") for p in ret.index]


def calcular(ctx) -> dict:
    a, wret = ctx.ativo, ctx.ret_semanal
    dados, corr1, beta3 = {}, np.nan, np.nan
    if not a.referencia and a.id in wret:
        primeira = ctx.s.index[0].to_period("W-FRI")
        mask = wret.index >= primeira
        for b in ctx.referencias:
            rc = wret[a.id].rolling(52, min_periods=40).corr(wret[b])
            dados[b] = series_list(rc[mask], 3)
        dados["d"] = [dt for dt, m in zip(ctx.datas_semana, mask) if m]
    mb = ctx.referencia_principal
    if mb and mb in wret and a.id in wret and a.id != mb:
        par = wret[[a.id, mb]].dropna()
        if len(par.tail(52)) >= 40:
            corr1 = par.tail(52).corr().iloc[0, 1]
        u3 = par.tail(156)
        if len(u3) >= 120 and u3[mb].var() > 0:
            beta3 = u3[a.id].cov(u3[mb]) / u3[mb].var()
    return {"dados": dados, "resumo": {"corr_1y": num(corr1, 3), "beta_3y": num(beta3, 3)}}


def do_segmento(wret: pd.DataFrame, datas_semana: list[str], acoes: list[str], refs: list[str]) -> dict:
    """Matrizes por janela e correlação média entre os pares de ações de um segmento."""
    ordem = acoes + refs
    matrizes = {}
    for rotulo, n in JANELAS.items():
        sub = wret[ordem] if n is None else wret[ordem].tail(n)
        c = sub.corr(min_periods=104 if n is None else int(n * 0.8))
        matrizes[rotulo] = [[num(c.loc[x, y], 3) for y in ordem] for x in ordem]
    pares = [(x, y) for i, x in enumerate(acoes) for y in acoes[i + 1:]]
    media = {"d": [], "v": [], "n": []}
    if pares:
        acc = pd.DataFrame({f"{x}|{y}": wret[x].rolling(52, min_periods=40).corr(wret[y]) for x, y in pares})
        cnt = acc.notna().sum(axis=1)
        avg = acc.mean(axis=1, skipna=True).where(cnt >= min(3, len(pares)))
        ok = avg.notna()
        media = {"d": [dt for dt, v in zip(datas_semana, ok) if v],
                 "v": series_list(avg[ok], 3), "n": [int(x) for x in cnt[ok].values]}
    return {"symbols": ordem, "windows": list(JANELAS.keys()), "matrices": matrizes, "avg_pairwise": media}
