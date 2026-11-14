"""Yahoo Finance: histórico completo, sem chave. Não é API oficial, por isso há fontes de reserva."""
from __future__ import annotations

import time

import pandas as pd

from ..util import normalizar

NOME = "Yahoo Finance"
COMPLETA = True
PAUSA = 1.0  # segundos entre ativos


def disponivel(env: dict) -> bool:
    return True


def _biblioteca(ticker: str) -> pd.DataFrame:
    import yfinance as yf

    try:  # versões novas: erros viram exceção por esta configuração
        yf.config.debug.hide_exceptions = False
    except Exception:  # noqa: BLE001 - versões antigas não têm essa opção
        pass
    df = yf.Ticker(ticker).history(period="max", auto_adjust=False, actions=True, timeout=30)
    if df is None or df.empty or "Close" not in df:
        raise RuntimeError("resposta vazia")
    return pd.DataFrame({
        "open": df["Open"], "high": df["High"], "low": df["Low"], "close": df["Close"],
        "adj_close": df["Adj Close"] if "Adj Close" in df else df["Close"],
        "volume": df["Volume"],
        "dividend": df["Dividends"] if "Dividends" in df else 0.0,
        "split": df["Stock Splits"] if "Stock Splits" in df else 0.0,
    })


def _endpoint(ticker: str) -> pd.DataFrame:
    import requests

    resp = requests.get(
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"period1": int(pd.Timestamp("1962-01-01", tz="UTC").timestamp()),
                "period2": int(time.time()) + 86400, "interval": "1d",
                "events": "div,splits", "includeAdjustedClose": "true"},
        headers={"User-Agent": "Mozilla/5.0 (painel-de-analise)"}, timeout=30)
    resp.raise_for_status()
    res = resp.json()["chart"]["result"][0]
    tz = (res.get("meta") or {}).get("exchangeTimezoneName") or "America/New_York"
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize()
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
                       "adj_close": res["indicators"]["adjclose"][0]["adjclose"],
                       "volume": q["volume"]}, index=idx)
    ev = res.get("events") or {}
    df["dividend"] = 0.0
    df["split"] = 0.0
    for e in (ev.get("dividends") or {}).values():
        d = pd.Timestamp(e["date"], unit="s", tz="UTC").tz_convert(tz).tz_localize(None).normalize()
        if d in df.index:
            df.loc[d, "dividend"] = float(e["amount"])
    for e in (ev.get("splits") or {}).values():
        d = pd.Timestamp(e["date"], unit="s", tz="UTC").tz_convert(tz).tz_localize(None).normalize()
        if d in df.index and e.get("denominator"):
            df.loc[d, "split"] = float(e["numerator"]) / float(e["denominator"])
    return df


def baixar(ticker: str, env: dict) -> pd.DataFrame:
    erros = []
    for nome, fn in (("biblioteca", _biblioteca), ("endpoint", _endpoint)):
        try:
            return normalizar(fn(ticker))
        except Exception as exc:  # noqa: BLE001 - tenta o outro caminho
            erros.append(f"{nome}: {str(exc)[:120]}")
    raise RuntimeError(" | ".join(erros))
