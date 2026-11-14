"""Ciclos de alta e baixa pela regra do X%."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..util import dstr, num

ID, NOME, CHAVE, VERSAO = "ciclos", "Ciclos de mercado", "cycles", 1


def fases(s: pd.Series, th: float) -> dict:
    """Uma baixa é confirmada quando o preço cai X% desde o pico; uma alta, quando sobe X% desde
    o fundo. A fase começa no pico/fundo, não na confirmação."""
    p, d, n = s.values, s.index, len(s)
    turns, kinds = [0], [None]
    state, hi, lo = None, 0, 0
    for i in range(1, n):
        if state in (None, "bull"):
            if p[i] > p[hi]:
                hi = i
            if p[i] <= p[hi] * (1 - th):
                turns.append(hi)
                kinds.append("peak")
                state = "bear"
                lo = hi + int(np.argmin(p[hi:i + 1]))
                continue
        if state in (None, "bear"):
            if p[i] < p[lo]:
                lo = i
            if p[i] >= p[lo] * (1 + th):
                turns.append(lo)
                kinds.append("trough")
                state = "bull"
                hi = lo + int(np.argmax(p[lo:i + 1]))
                continue

    phases = []
    for k in range(1, len(turns)):
        a, b = turns[k - 1], turns[k]
        if b <= a:
            continue
        kind = "alta" if kinds[k] == "peak" else "baixa"
        phases.append({"type": kind, "start": dstr(d[a]), "end": dstr(d[b]),
                       "ret": num(p[b] / p[a] - 1), "days": int((d[b] - d[a]).days),
                       "ongoing": False, "truncated": a == 0})
    a = turns[-1]
    if state is None:
        cur_type = "alta" if p[-1] >= p[0] else "baixa"
    else:
        cur_type = "baixa" if state == "bear" else "alta"
    if n - 1 > a:
        ext = (lo if cur_type == "baixa" else hi) if state is not None else n - 1
        phases.append({"type": cur_type, "start": dstr(d[a]), "end": dstr(d[-1]),
                       "ret": num(p[-1] / p[a] - 1), "days": int((d[-1] - d[a]).days),
                       "extreme": num(p[ext] / p[a] - 1), "extreme_date": dstr(d[ext]),
                       "ongoing": True})

    def resumir(kind):
        # a 1ª fase começa no primeiro pregão disponível (início arbitrário): fica fora das médias
        done = [ph for ph in phases if ph["type"] == kind and not ph["ongoing"] and not ph.get("truncated")]
        if not done:
            return {"n": 0}
        rets = np.array([ph["ret"] for ph in done])
        days = np.array([ph["days"] for ph in done])
        return {"n": len(done), "ret_median": num(np.median(rets)), "ret_mean": num(rets.mean()),
                "days_median": int(np.median(days)), "days_mean": int(days.mean()),
                "days_max": int(days.max())}

    current = phases[-1] if phases and phases[-1]["ongoing"] else None
    pct_days = None
    if current is not None:
        same = [ph["days"] for ph in phases
                if ph["type"] == current["type"] and not ph["ongoing"] and not ph.get("truncated")]
        if same:
            pct_days = num(np.mean(np.array(same) <= current["days"]), 3)
    return {"phases": phases, "bull": resumir("alta"), "bear": resumir("baixa"),
            "current": current, "current_days_pctile": pct_days}


def calcular(ctx) -> dict:
    dados = {str(int(round(th * 100))): fases(ctx.s, th) for th in ctx.limiares}
    ref = dados.get("20", next(iter(dados.values())))
    atual = ref["current"] or {}
    resumo = {"phase": atual.get("type"), "phase_start": atual.get("start"),
              "phase_days": atual.get("days"), "phase_ret": atual.get("ret")}
    return {"dados": dados, "resumo": resumo}
