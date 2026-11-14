#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera os dados do Painel Big Techs (site/data/*.json).

Uso:
  python scripts/build_data.py             # baixa dados reais e gera o site
  python scripts/build_data.py --offline   # usa só o cache em data/prices (sem internet)
  python scripts/build_data.py --demo      # dados SINTÉTICOS, só para testar o visual

Fontes (em ordem de tentativa, por ativo):
  1. Yahoo Finance via biblioteca yfinance
  2. Yahoo Finance via endpoint v8/chart (sem a biblioteca)
  3. Tiingo (só se a variável de ambiente TIINGO_API_KEY existir)
  4. Último cache salvo em data/prices/<ATIVO>.csv
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
CACHE_DIR = ROOT / "data" / "prices"
OUT_DIR = ROOT / "site" / "data"

TRADING_DAYS = 252
FREQS = {
    "M": {"months": 1, "labels": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                                  "Jul", "Ago", "Set", "Out", "Nov", "Dez"]},
    "B": {"months": 2, "labels": ["Jan–Fev", "Mar–Abr", "Mai–Jun",
                                  "Jul–Ago", "Set–Out", "Nov–Dez"]},
    "Q": {"months": 3, "labels": ["1º tri", "2º tri", "3º tri", "4º tri"]},
}
# janelas da matriz de correlação, em semanas
CORR_WINDOWS = {"1a": 52, "3a": 156, "5a": 260, "10a": 520, "tudo": None}


# --------------------------------------------------------------------------- utilidades
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


# --------------------------------------------------------------------------- download
def _finalize(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(pd.Series(s), errors="coerce").dropna()
    s = s[s > 0]
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.name = "adj_close"
    return s.astype("float64")


def fetch_yfinance(symbol: str, start: str | None) -> pd.Series:
    import yfinance as yf

    kwargs = {"auto_adjust": True, "actions": False, "raise_errors": True, "timeout": 30}
    if start:
        kwargs["start"] = start
    else:
        kwargs["period"] = "max"
    df = yf.Ticker(symbol).history(**kwargs)
    if df is None or df.empty or "Close" not in df:
        raise RuntimeError("resposta vazia")
    return pd.Series(df["Close"].values, index=df.index)


def fetch_yahoo_chart(symbol: str, start: str | None) -> pd.Series:
    import requests

    p1 = int(pd.Timestamp(start or "1962-01-01", tz="UTC").timestamp())
    p2 = int(time.time()) + 86400
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    resp = requests.get(
        url,
        params={"period1": p1, "period2": p2, "interval": "1d",
                "events": "div,splits", "includeAdjustedClose": "true"},
        headers={"User-Agent": "Mozilla/5.0 (painel-bigtechs)"},
        timeout=30,
    )
    resp.raise_for_status()
    res = resp.json()["chart"]["result"][0]
    tz = (res.get("meta") or {}).get("exchangeTimezoneName") or "America/New_York"
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(tz).tz_localize(None)
    adj = res["indicators"]["adjclose"][0]["adjclose"]
    return pd.Series(adj, index=idx, dtype="float64")


def fetch_tiingo(symbol: str, start: str | None, key: str) -> pd.Series:
    import requests

    url = f"https://api.tiingo.com/tiingo/daily/{symbol.lower()}/prices"
    resp = requests.get(url, params={"startDate": start or "1962-01-01", "token": key,
                                     "format": "json"}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"resposta inesperada: {str(data)[:120]}")
    return pd.Series({pd.Timestamp(row["date"][:10]): row["adjClose"] for row in data})


def read_cache(path: Path) -> pd.Series | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    if df.empty:
        return None
    return _finalize(pd.Series(df["adj_close"].values, index=df["date"]))


def write_cache(path: Path, s: pd.Series):
    path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame({"date": s.index.strftime("%Y-%m-%d"),
                        "adj_close": [price(v, 7) for v in s.values]})
    out.to_csv(path, index=False)


def looks_valid(s: pd.Series, cached: pd.Series | None) -> tuple[bool, str]:
    if s is None or len(s) < 30:
        return False, "poucos dados"
    age = (pd.Timestamp.today().normalize() - s.index[-1]).days
    if age > 10:
        return False, f"último pregão tem {age} dias"
    if cached is not None and len(cached) and s.index[0] > cached.index[0] + pd.Timedelta(days=45):
        return False, "histórico mais curto que o cache"
    return True, ""


def get_prices(cfg: dict, fetch_start: str | None, offline: bool, tiingo_key: str | None):
    sym = cfg["symbol"]
    cache_file = CACHE_DIR / f"{safe_name(sym)}.csv"
    cached = read_cache(cache_file)

    if not offline:
        yahoo_sym = cfg.get("yahoo", sym)
        sources = [
            ("Yahoo Finance", lambda: fetch_yfinance(yahoo_sym, fetch_start)),
            ("Yahoo Finance (v8)", lambda: fetch_yahoo_chart(yahoo_sym, fetch_start)),
        ]
        if tiingo_key:
            sources.append(("Tiingo", lambda: fetch_tiingo(cfg.get("tiingo", sym), fetch_start, tiingo_key)))
        for name, fn in sources:
            for attempt in range(3):
                try:
                    s = _finalize(fn())
                    ok, why = looks_valid(s, cached)
                    if ok:
                        write_cache(cache_file, s)
                        return s, name, False
                    log(f"  {sym}: {name} descartado ({why})")
                    break
                except Exception as exc:  # noqa: BLE001 - qualquer falha passa para a próxima fonte
                    log(f"  {sym}: {name} falhou (tentativa {attempt + 1}/3): {str(exc)[:160]}")
                    time.sleep(3 * (attempt + 1))

    if cached is not None and len(cached):
        return cached, "cache local", True
    return None, None, True


# --------------------------------------------------------------------------- dados de demonstração
DEMO_IPO = {"GOOGL": "2004-08-19", "META": "2012-05-18", "TSLA": "2010-06-29",
            "AVGO": "2009-08-06", "QQQ": "1999-03-10", "SMH": "2000-06-05"}


def demo_prices(symbols: list[str]) -> dict[str, pd.Series]:
    """Séries SINTÉTICAS (passeio aleatório com fator comum e quatro crises)."""
    idx_all = pd.bdate_range("1990-01-02", pd.Timestamp.today().normalize())
    rng0 = np.random.default_rng(0)
    factor = pd.Series(rng0.normal(0.0004, 0.011, len(idx_all)), index=idx_all)
    for a, b, shock in [("2000-03-10", "2002-10-09", -0.75), ("2007-10-31", "2009-03-09", -0.5),
                        ("2020-02-19", "2020-03-23", -0.3), ("2022-01-03", "2022-10-14", -0.35)]:
        m = (idx_all >= a) & (idx_all <= b)
        factor[m] += np.log1p(shock) / m.sum()
    out = {}
    for i, sym in enumerate(symbols):
        rng = np.random.default_rng(100 + i)
        idx = idx_all[idx_all >= pd.Timestamp(DEMO_IPO.get(sym, "1990-01-02"))]
        beta = rng.uniform(0.8, 1.6)
        r = beta * factor[idx].values + rng.normal(0.0002, rng.uniform(0.012, 0.025), len(idx))
        out[sym] = pd.Series(10 * np.exp(np.cumsum(r)), index=idx)
    return out


# --------------------------------------------------------------------------- métricas
def drawdown(s: pd.Series) -> pd.Series:
    return s / s.cummax() - 1


def drawdown_episodes(s: pd.Series) -> list[dict]:
    dd = drawdown(s)
    dates = s.index
    episodes, cur = [], None
    last_peak_i = 0
    for i, v in enumerate(dd.values):
        if v < 0:
            if cur is None:
                cur = {"peak_i": last_peak_i, "trough_i": i, "depth": v}
            elif v < cur["depth"]:
                cur["trough_i"], cur["depth"] = i, v
        else:
            if cur is not None:
                cur["rec_i"] = i
                episodes.append(cur)
                cur = None
            last_peak_i = i
    if cur is not None:
        cur["rec_i"] = None
        episodes.append(cur)

    out = []
    last = dates[-1]
    for e in episodes:
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


def cycles(s: pd.Series, th: float) -> dict:
    """Fases de alta/baixa pela regra do X%: uma baixa é confirmada quando o preço cai X% desde
    o pico; uma alta, quando sobe X% desde o fundo. A fase começa no pico/fundo, não na confirmação."""
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

    def summarize(kind):
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
    return {"phases": phases, "bull": summarize("alta"), "bear": summarize("baixa"),
            "current": current, "current_days_pctile": pct_days}


def period_table(s_full: pd.Series, months: int, min_year: int | None = None) -> dict:
    """Retornos por mês/bimestre/trimestre: tabela ano × período, só com períodos completos
    (o período em curso entra marcado como parcial)."""
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

    # retorno anual (ano corrente e ano de estreia marcados como parciais)
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


def weekly_last(s: pd.Series) -> pd.Series:
    """Último pregão de cada semana, com a data real do pregão."""
    grp = s.groupby(s.index.to_period("W-FRI"))
    last = grp.tail(1)
    return last


# --------------------------------------------------------------------------- pipeline
def main():
    ap = argparse.ArgumentParser(description="Gera os dados do Painel Big Techs")
    ap.add_argument("--demo", action="store_true", help="usa dados sintéticos (teste visual)")
    ap.add_argument("--offline", action="store_true", help="não acessa a internet; usa o cache")
    args = ap.parse_args()

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    tickers = cfg["tickers"]
    benchmarks = cfg["benchmarks"]
    main_bench = cfg.get("main_benchmark", benchmarks[0]["symbol"])
    thresholds = cfg.get("cycle_thresholds", [0.15, 0.20, 0.30])
    start = cfg.get("start", "max")
    start_ts = None if str(start).lower() == "max" else pd.Timestamp(start)
    # baixa ~2 meses antes do início para ter o fechamento do mês anterior
    fetch_start = None if start_ts is None else (start_ts - pd.Timedelta(days=62)).strftime("%Y-%m-%d")
    tiingo_key = os.environ.get("TIINGO_API_KEY") or None

    all_cfg = tickers + benchmarks
    prices: dict[str, pd.Series] = {}
    sources: dict[str, dict] = {}

    if args.demo:
        log("MODO DEMO: gerando séries sintéticas (não são cotações reais).")
        prices = demo_prices([c["symbol"] for c in all_cfg])
        sources = {k: {"source": "sintético", "stale": False} for k in prices}
    else:
        for c in all_cfg:
            sym = c["symbol"]
            log(f"• {sym}")
            s, src, stale = get_prices(c, fetch_start, args.offline, tiingo_key)
            if s is None:
                log(f"  {sym}: sem dados — ativo ignorado nesta rodada")
                continue
            prices[sym] = s
            sources[sym] = {"source": src, "stale": stale}
            log(f"  {sym}: {len(s)} pregões, {dstr(s.index[0])} → {dstr(s.index[-1])} ({src})")
            if not args.offline:
                time.sleep(1.0)  # educação com a fonte gratuita

    if not prices:
        log("ERRO: nenhum ativo com dados. Nada foi gerado.")
        sys.exit(1)

    tick_syms = [c["symbol"] for c in tickers if c["symbol"] in prices]
    bench_syms = [c["symbol"] for c in benchmarks if c["symbol"] in prices]
    names = {c["symbol"]: c.get("name", c["symbol"]) for c in all_cfg}
    currency = {c["symbol"]: c.get("currency", cfg.get("currency", "US$")) for c in all_cfg}

    # Painel semanal (para correlações)
    trimmed = {}
    for sym, s in prices.items():
        trimmed[sym] = s if start_ts is None else s[s.index >= start_ts]
    wk = pd.DataFrame({sym: s.groupby(s.index.to_period("W-FRI")).last()
                       for sym, s in trimmed.items()}).sort_index()
    wret = wk / wk.shift(1) - 1
    week_dates = [dstr(p.end_time) for p in wret.index]

    (OUT_DIR / "tickers").mkdir(parents=True, exist_ok=True)
    summary_rows = []

    for sym in tick_syms + bench_syms:
        s_full = prices[sym]
        s = trimmed[sym]
        if len(s) < 60:
            log(f"  {sym}: histórico curto demais, ignorado")
            continue
        dd = drawdown(s)
        daily_ret = s / s.shift(1) - 1

        # séries para gráficos (semanais)
        wl = weekly_last(s)
        wk_period = s.index.to_period("W-FRI")
        dd_week_min = dd.groupby(wk_period).min()
        r1 = s / s.shift(TRADING_DAYS) - 1
        r3 = (s / s.shift(3 * TRADING_DAYS)) ** (1 / 3) - 1
        series = {
            "d": [dstr(x) for x in wl.index],
            "p": [price(v) for v in wl.values],
            "dd": series_list(dd_week_min.reindex(wl.index.to_period("W-FRI")), 4),
            "r1": series_list(r1.reindex(wl.index), 4),
            "r3": series_list(r3.reindex(wl.index), 4),
        }

        # correlação móvel de 52 semanas contra cada referência
        corr_series = {}
        if sym in tick_syms:
            first_week = s.index[0].to_period("W-FRI")
            mask = wret.index >= first_week
            for b in bench_syms:
                rc = wret[sym].rolling(52, min_periods=40).corr(wret[b])
                corr_series[b] = series_list(rc[mask], 3)
            corr_series["d"] = [dt for dt, m in zip(week_dates, mask) if m]

        eps = drawdown_episodes(s)
        big = sorted([e for e in eps if e["depth"] is not None and e["depth"] <= -0.10],
                     key=lambda e: e["depth"])
        cur_ep = next((e for e in reversed(eps) if e["ongoing"]), None)
        worst = big[0] if big else (min(eps, key=lambda e: e["depth"]) if eps else None)

        cyc = {str(int(round(th * 100))): cycles(s, th) for th in thresholds}
        seas = {f: period_table(s_full if start_ts is None else
                                s_full[s_full.index >= start_ts - pd.Timedelta(days=62)],
                                FREQS[f]["months"],
                                None if start_ts is None else start_ts.year) for f in FREQS}

        # estatísticas de resumo
        last_close = s.iloc[-1]
        prev_year = s[s.index.year < s.index[-1].year]
        ytd = last_close / prev_year.iloc[-1] - 1 if len(prev_year) else np.nan
        one_y = r1.iloc[-1]
        years = (s.index[-1] - s.index[0]).days / 365.25
        cagr = (last_close / s.iloc[0]) ** (1 / years) - 1 if years > 0.5 else np.nan
        vol1 = daily_ret.tail(TRADING_DAYS).std() * math.sqrt(TRADING_DAYS)
        corr1 = beta3 = np.nan
        if main_bench in wret and sym != main_bench:
            pair = wret[[sym, main_bench]].dropna()
            if len(pair.tail(52)) >= 40:
                corr1 = pair.tail(52).corr().iloc[0, 1]
            last3 = pair.tail(156)
            if len(last3) >= 120 and last3[main_bench].var() > 0:
                beta3 = last3[sym].cov(last3[main_bench]) / last3[main_bench].var()
        cyc20 = cyc.get("20", next(iter(cyc.values())))
        stats = {
            "first_date": dstr(s.index[0]), "last_date": dstr(s.index[-1]),
            "last_price": price(last_close), "ytd": num(ytd), "ret_1y": num(one_y),
            "cagr": num(cagr), "total": num(last_close / s.iloc[0] - 1, 3),
            "dd_current": num(dd.iloc[-1]),
            "dd_max": worst["depth"] if worst else None,
            "dd_max_peak": worst["peak"] if worst else None,
            "dd_max_trough": worst["trough"] if worst else None,
            "dd_max_recovery": worst["recovery"] if worst else None,
            "vol_1y": num(vol1), "corr_1y": num(corr1, 3), "beta_3y": num(beta3, 3),
            "phase": (cyc20["current"] or {}).get("type"),
            "phase_start": (cyc20["current"] or {}).get("start"),
            "phase_days": (cyc20["current"] or {}).get("days"),
            "phase_ret": (cyc20["current"] or {}).get("ret"),
        }

        payload = {
            "symbol": sym, "name": names[sym], "currency": currency[sym], "is_benchmark": sym in bench_syms,
            **sources.get(sym, {}), "stats": stats, "series": series, "corr": corr_series,
            "drawdown": {"episodes": big[:25], "current": cur_ep,
                         "count_20": sum(1 for e in eps if e["depth"] is not None and e["depth"] <= -0.20),
                         "count_30": sum(1 for e in eps if e["depth"] is not None and e["depth"] <= -0.30)},
            "cycles": cyc, "seasonality": seas,
        }
        (OUT_DIR / "tickers" / f"{safe_name(sym)}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        summary_rows.append({"symbol": sym, "name": names[sym], "currency": currency[sym],
                             "is_benchmark": sym in bench_syms,
                             "file": f"tickers/{safe_name(sym)}.json",
                             "source": sources.get(sym, {}).get("source"),
                             "stale": sources.get(sym, {}).get("stale"), **stats})
        log(f"  ✓ {sym}: métricas geradas")

    # Correlações: matrizes por janela + correlação média entre as big techs
    order = tick_syms + bench_syms
    matrices = {}
    for label, n in CORR_WINDOWS.items():
        sub = wret[order] if n is None else wret[order].tail(n)
        minp = 104 if n is None else int(n * 0.8)
        c = sub.corr(min_periods=minp)
        matrices[label] = [[num(c.loc[a, b], 3) for b in order] for a in order]

    pairs = [(a, b) for i, a in enumerate(tick_syms) for b in tick_syms[i + 1:]]
    avg = None
    if pairs:
        acc = pd.DataFrame({f"{a}|{b}": wret[a].rolling(52, min_periods=40).corr(wret[b])
                            for a, b in pairs})
        cnt = acc.notna().sum(axis=1)
        avg = acc.mean(axis=1, skipna=True).where(cnt >= 3)
        valid = avg.notna()
        avg_out = {"d": [dt for dt, v in zip(week_dates, valid) if v],
                   "v": series_list(avg[valid], 3),
                   "n": [int(x) for x in cnt[valid].values]}
    else:
        avg_out = {"d": [], "v": [], "n": []}

    (OUT_DIR / "correlations.json").write_text(json.dumps({
        "symbols": order, "windows": list(CORR_WINDOWS.keys()), "matrices": matrices,
        "avg_pairwise": avg_out}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    meta = {
        "title": cfg.get("title", "Painel Big Techs"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "demo": bool(args.demo),
        "start": start,
        "main_benchmark": main_bench if main_bench in bench_syms else (bench_syms[0] if bench_syms else None),
        "cycle_thresholds": [str(int(round(t * 100))) for t in thresholds],
        "freq_labels": {f: FREQS[f]["labels"] for f in FREQS},
        "tickers": [r for r in summary_rows if not r["is_benchmark"]],
        "benchmarks": [r for r in summary_rows if r["is_benchmark"]],
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")),
                                      encoding="utf-8")
    stale = [r["symbol"] for r in summary_rows if r.get("stale")]
    log(f"\nPronto: {len(summary_rows)} ativos em {os.path.relpath(OUT_DIR, ROOT)}"
        + (f" | usando cache (fonte falhou): {', '.join(stale)}" if stale and not args.demo else ""))


if __name__ == "__main__":
    main()
