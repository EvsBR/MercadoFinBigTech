"""Funções pequenas usadas em todo o pipeline."""
from __future__ import annotations

import math
import re

import pandas as pd

COLUNAS = ["open", "high", "low", "close", "adj_close", "volume", "dividend", "split"]


def log(*args):
    print(*args, flush=True)


def safe_name(symbol: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", symbol)


def num(x, nd: int = 5):
    """float -> número para JSON (NaN/inf viram null)."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(xf):
        return None
    return round(xf, nd)


def price(x, digits: int = 6):
    """Preço com N algarismos significativos (preços ajustados antigos podem ser 0,07)."""
    if x is None:
        return None
    xf = float(x)
    if not math.isfinite(xf):
        return None
    return float(f"{xf:.{digits}g}")


def dstr(ts):
    if ts is None or (isinstance(ts, float) and math.isnan(ts)) or pd.isna(ts):
        return None
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def series_list(s: pd.Series, nd: int = 4):
    return [num(v, nd) for v in s.values]


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Deixa qualquer tabela de cotações no formato padrão da base:
    índice = data (sem fuso, sem repetição, crescente); colunas = COLUNAS.
    open/high/low/close: ajustados por desdobramento. adj_close: também por proventos."""
    df = df.copy()
    idx = pd.DatetimeIndex(pd.to_datetime(df.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df.index.name = "date"
    for c in COLUNAS:
        if c not in df:
            df[c] = 0.0 if c == "dividend" else (1.0 if c == "split" else float("nan"))
    df = df[COLUNAS].apply(pd.to_numeric, errors="coerce")
    df = df[df["close"].notna() & (df["close"] > 0)]
    df["adj_close"] = df["adj_close"].where(df["adj_close"] > 0).fillna(df["close"])
    for c in ("open", "high", "low"):
        df[c] = df[c].where(df[c] > 0).fillna(df["close"])
    df["volume"] = df["volume"].fillna(0).clip(lower=0)
    df["dividend"] = df["dividend"].fillna(0.0)
    df["split"] = df["split"].where(df["split"] > 0).fillna(1.0)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.astype("float64")
