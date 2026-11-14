"""Tiingo: histórico completo desde 1962 com chave gratuita (TIINGO_API_KEY).
Plano gratuito: 50 chamadas por hora e 1.000 por dia; por isso é reserva, não a fonte do dia a dia."""
from __future__ import annotations

import pandas as pd

from ..util import normalizar
from .base import CotaEsgotada, FonteIndisponivel

NOME = "Tiingo"
COMPLETA = True
PAUSA = 1.5
LIMITE_POR_RODADA = 45
_usadas = 0


def disponivel(env: dict) -> bool:
    return bool(env.get("TIINGO_API_KEY"))


def converter(linhas: list[dict]) -> pd.DataFrame:
    """A Tiingo entrega preços brutos + fator de desdobramento; a base guarda preços já
    ajustados por desdobramento (como o Yahoo). Divide pelo produto dos desdobramentos futuros."""
    df = pd.DataFrame(linhas)
    df.index = pd.to_datetime(df["date"].str[:10])
    df = df.sort_index()
    def col(nome, padrao):
        return pd.to_numeric(df[nome], errors="coerce").fillna(padrao) if nome in df else pd.Series(padrao, index=df.index)

    sf = col("splitFactor", 1.0).replace(0, 1.0)
    # fator acumulado dos desdobramentos que ocorreram DEPOIS de cada data
    futuro = sf[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    out = pd.DataFrame({
        "open": df["open"] / futuro, "high": df["high"] / futuro, "low": df["low"] / futuro,
        "close": df["close"] / futuro, "adj_close": df["adjClose"],
        "volume": df["volume"] * futuro,
        "dividend": col("divCash", 0.0) / futuro,
        "split": sf,
    }, index=df.index)
    return out


def baixar(ticker: str, env: dict) -> pd.DataFrame:
    import requests

    global _usadas
    if not disponivel(env):
        raise FonteIndisponivel("sem TIINGO_API_KEY")
    if _usadas >= LIMITE_POR_RODADA:
        raise CotaEsgotada("limite de chamadas por rodada")
    _usadas += 1
    resp = requests.get(f"https://api.tiingo.com/tiingo/daily/{ticker.lower().replace('.', '-')}/prices",
                        params={"startDate": "1962-01-01", "format": "json",
                                "token": env["TIINGO_API_KEY"]}, timeout=60)
    if resp.status_code == 429:
        raise CotaEsgotada("limite do plano gratuito (HTTP 429)")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"resposta inesperada: {str(data)[:120]}")
    return normalizar(converter(data))
