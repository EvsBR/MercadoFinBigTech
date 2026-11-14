"""Twelve Data: reserva para completar os pregões mais recentes (TWELVEDATA_API_KEY).
Plano gratuito: 8 chamadas por minuto e 800 por dia. Os preços não vêm ajustados por
dividendos, então esta fonte só emenda o fim da base; não substitui o histórico."""
from __future__ import annotations

import pandas as pd

from ..util import normalizar
from .base import CotaEsgotada, FonteIndisponivel

NOME = "Twelve Data"
COMPLETA = False
PAUSA = 8.0
LIMITE_POR_RODADA = 700
_usadas = 0


def disponivel(env: dict) -> bool:
    return bool(env.get("TWELVEDATA_API_KEY"))


def converter(valores: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(valores)
    df.index = pd.to_datetime(df["datetime"].str[:10])
    out = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    out["adj_close"] = out["close"]
    return out.sort_index()


def baixar(ticker: str, env: dict) -> pd.DataFrame:
    import requests

    global _usadas
    if not disponivel(env):
        raise FonteIndisponivel("sem TWELVEDATA_API_KEY")
    if _usadas >= LIMITE_POR_RODADA:
        raise CotaEsgotada("limite de chamadas por rodada")
    _usadas += 1
    resp = requests.get("https://api.twelvedata.com/time_series",
                        params={"symbol": ticker, "interval": "1day", "outputsize": 120,
                                "order": "ASC", "apikey": env["TWELVEDATA_API_KEY"]}, timeout=60)
    if resp.status_code == 429:
        raise CotaEsgotada("limite do plano gratuito (HTTP 429)")
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "error" or "values" not in data:
        if data.get("code") == 429:
            raise CotaEsgotada(str(data.get("message"))[:120])
        raise RuntimeError(f"resposta inesperada: {str(data)[:160]}")
    return normalizar(converter(data["values"]))
