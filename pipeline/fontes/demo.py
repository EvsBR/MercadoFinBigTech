"""Cotações SINTÉTICAS (passeio aleatório com fator comum e quatro crises). Só para testar o visual."""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from ..util import normalizar

NOME = "sintético"
COMPLETA = True
PAUSA = 0.0
IPO = {"GOOGL": "2004-08-19", "META": "2012-05-18", "TSLA": "2010-06-29",
       "AVGO": "2009-08-06", "QQQ": "1999-03-10", "SMH": "2000-06-05"}
_fator = None


def disponivel(env: dict) -> bool:
    return True


def _fator_comum() -> pd.Series:
    global _fator
    if _fator is None:
        idx = pd.bdate_range("1990-01-02", pd.Timestamp.today().normalize())
        f = pd.Series(np.random.default_rng(0).normal(0.0004, 0.011, len(idx)), index=idx)
        for a, b, choque in [("2000-03-10", "2002-10-09", -0.75), ("2007-10-31", "2009-03-09", -0.5),
                             ("2020-02-19", "2020-03-23", -0.3), ("2022-01-03", "2022-10-14", -0.35)]:
            m = (idx >= a) & (idx <= b)
            f[m] += np.log1p(choque) / m.sum()
        _fator = f
    return _fator


def baixar(ticker: str, env: dict) -> pd.DataFrame:
    f = _fator_comum()
    rng = np.random.default_rng(zlib.crc32(ticker.encode()))
    idx = f.index[f.index >= pd.Timestamp(IPO.get(ticker, "1990-01-02"))]
    beta = rng.uniform(0.8, 1.6)
    r = beta * f[idx].values + rng.normal(0.0002, rng.uniform(0.012, 0.025), len(idx))
    close = 10 * np.exp(np.cumsum(r))
    amp = np.abs(rng.normal(0, 0.012, len(idx)))
    abre = close * np.exp(rng.normal(0, 0.006, len(idx)))
    return normalizar(pd.DataFrame({
        "open": abre, "high": np.maximum(abre, close) * (1 + amp),
        "low": np.minimum(abre, close) * (1 - amp), "close": close, "adj_close": close,
        "volume": rng.lognormal(16, 0.5, len(idx)).round()}, index=idx))
