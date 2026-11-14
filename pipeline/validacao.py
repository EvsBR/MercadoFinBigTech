"""Conferência das cotações antes de entrarem na base e no site.

'erros' impedem o uso da tabela (o pipeline fica com a base anterior e avisa no site).
'avisos' são registrados no relatório de saúde, mas não bloqueiam."""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_PREGOES = 30
MAX_IDADE_DIAS = 10          # último pregão mais velho que isso = fonte parada
SALTO_SUSPEITO = 0.60        # variação diária do preço ajustado acima disso
FATORES_DESDOBRAMENTO = (2, 3, 4, 5, 6, 7, 8, 10, 15, 20, 25, 30, 40, 50, 100)
BURACO_DIAS = 15             # dias corridos sem pregão


def conferir(df: pd.DataFrame | None, base: pd.DataFrame | None = None,
             hoje: pd.Timestamp | None = None, completa: bool = True) -> tuple[list[str], list[str]]:
    erros, avisos = [], []
    if df is None or len(df) < (MIN_PREGOES if completa else 3):
        return ["poucos dados"], avisos
    hoje = (hoje or pd.Timestamp.today()).normalize()

    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        erros.append("datas fora de ordem ou repetidas")
    if df.index[-1] > hoje + pd.Timedelta(days=1):
        erros.append(f"data no futuro ({df.index[-1].date()})")
    idade = (hoje - df.index[-1]).days
    if idade > MAX_IDADE_DIAS:
        erros.append(f"último pregão tem {idade} dias")
    for c in ("open", "high", "low", "close", "adj_close"):
        if not np.isfinite(df[c]).all() or (df[c] <= 0).any():
            erros.append(f"valores inválidos em {c}")
    if (df["volume"] < 0).any():
        erros.append("volume negativo")
    tol = 1.0005   # folga de arredondamento
    ruim = ((df["high"] * tol < df[["open", "close", "low"]].max(axis=1))
            | (df["low"] > df[["open", "close", "high"]].min(axis=1) * tol))
    if ruim.mean() > 0.01:
        avisos.append(f"{int(ruim.sum())} pregões com máxima/mínima incoerentes")

    razao = df["adj_close"] / df["adj_close"].shift(1)
    saltos = razao[(razao - 1).abs() > SALTO_SUSPEITO]
    recentes = saltos[saltos.index >= hoje - pd.Timedelta(days=30)]
    # desdobramento não ajustado aparece como preço multiplicado ou dividido por um número redondo
    suspeitos = [d for d, r in recentes.items()
                 if any(abs(max(r, 1 / r) / n - 1) < 0.03 for n in FATORES_DESDOBRAMENTO)]
    if suspeitos:
        erros.append(f"salto em {suspeitos[-1].date()} com cara de desdobramento não ajustado")
    if len(saltos):
        avisos.append(f"{len(saltos)} variações diárias acima de {SALTO_SUSPEITO:.0%} no histórico")

    buracos = pd.Series(df.index[1:] - df.index[:-1], index=df.index[1:])
    grandes = buracos[buracos > pd.Timedelta(days=BURACO_DIAS)]
    if len(grandes):
        avisos.append(f"{len(grandes)} intervalos sem pregão acima de {BURACO_DIAS} dias "
                      f"(o maior termina em {grandes.idxmax().date()})")

    if base is not None and len(base) and completa:
        if df.index[0] > base.index[0] + pd.Timedelta(days=45):
            erros.append("histórico mais curto que o da base")
        if df.index[-1] < base.index[-1]:
            erros.append("termina antes da base")
        comuns = df.index.intersection(base.index)
        if len(comuns) > 60:
            a = df.loc[comuns, "adj_close"].pct_change().iloc[1:]
            b = base.loc[comuns, "adj_close"].pct_change().iloc[1:]
            dif = (a - b).abs()
            if float(dif.median()) > 0.002 or float((dif > 0.05).mean()) > 0.01:
                avisos.append("retornos diferentes dos que estavam na base (fonte divergente)")
    return erros, avisos
