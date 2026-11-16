"""Análise técnica: Drawdown, Médias Móveis, RSI e OBV em barras diárias, semanais e mensais.

Para cada indicador saem três coisas:
  medida   valor de agora contra o histórico (mínima, média, máxima, percentil)
  alvos    fechamento necessário no próximo pregão para o indicador chegar a cada nível
  barras   datas, fechamentos e volumes; o site desenha as curvas a partir delas (site/indicadores.js)

Preço usado: fechamento de tela (ajustado por desdobramentos, sem dividendos), arredondado em
7 algarismos. É o mesmo número que o usuário vê em qualquer plataforma de gráficos, e o site
recebe exatamente os valores que entraram na conta.

Todo preço-alvo é conferido antes de ser publicado: a barra hipotética é montada com o preço
calculado, o indicador é recalculado do zero e precisa cair no nível pedido. Se não cair, o
alvo sai vazio e a execução avisa."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import calendario
from ..util import dstr, log, num, preco_tela, price
from . import drawdown as _dd

ID, NOME, CHAVE, VERSAO = "tecnica", "Análise técnica", "tecnica", 1

TEMPOS = {"D": "Diário", "S": "Semanal", "M": "Mensal"}
TIPOS_MM = {"sma": "Simples", "ema": "Exponencial", "wma": "Ponderada"}
PERIODOS_MM = (50, 100, 200, 250)
RSI_N = 14
OBV_N = 20
TOL = 1e-9


# ---------------------------------------------------------------- barras
def barras(df: pd.DataFrame, tempo: str) -> pd.DataFrame:
    """Barras do período: fechamento = último pregão; volume = soma; data = último pregão da barra."""
    b = pd.DataFrame({"c": preco_tela(df), "v": df["volume"].fillna(0.0)})
    if tempo == "D":
        return b
    per = b.index.to_period("W-FRI" if tempo == "S" else "M")
    g = b.assign(d=b.index).groupby(per)
    out = pd.DataFrame({"c": g["c"].last(), "v": g["v"].sum()})
    out.index = pd.DatetimeIndex(g["d"].last().values, name="date")
    return out


def mesma_barra(tempo: str, ultimo: pd.Timestamp, proximo: pd.Timestamp) -> bool:
    """O próximo pregão ainda pertence à barra em andamento?"""
    if tempo == "S":
        return ultimo.to_period("W-FRI") == proximo.to_period("W-FRI")
    if tempo == "M":
        return (ultimo.year, ultimo.month) == (proximo.year, proximo.month)
    return False


# ---------------------------------------------------------------- indicadores (vetores numpy)
def dd(c: np.ndarray) -> np.ndarray:
    """Drawdown: distância do fechamento ao maior fechamento até a data."""
    return c / np.maximum.accumulate(c) - 1


def sma(c: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        out[n - 1:] = np.correlate(c, np.ones(n), "valid") / n
    return out


def wma(c: np.ndarray, n: int) -> np.ndarray:
    """Ponderada linear: peso n no fechamento mais recente, 1 no mais antigo."""
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        out[n - 1:] = np.correlate(c, np.arange(1.0, n + 1), "valid") / (n * (n + 1) / 2)
    return out


def ema(c: np.ndarray, n: int) -> np.ndarray:
    """Exponencial com alfa = 2/(n+1); o primeiro valor é a média simples das n primeiras barras."""
    out = np.full(len(c), np.nan)
    if len(c) < n:
        return out
    a = 2.0 / (n + 1)
    e = float(np.mean(c[:n]))
    out[n - 1] = e
    for i in range(n, len(c)):
        e = a * c[i] + (1 - a) * e
        out[i] = e
    return out


MEDIAS = {"sma": sma, "ema": ema, "wma": wma}


def _rsi_valor(ag: float, al: float) -> float:
    if al == 0:
        return 100.0 if ag > 0 else 50.0   # sem perdas: 100; preço parado: neutro
    return 100.0 - 100.0 / (1.0 + ag / al)


def rsi_estado(c: np.ndarray, n: int = RSI_N):
    """RSI de Wilder. Devolve (rsi, ganho médio, perda média) barra a barra."""
    N = len(c)
    out, ags, als = (np.full(N, np.nan) for _ in range(3))
    if N <= n:
        return out, ags, als
    d = np.diff(c)
    g = np.where(d > 0, d, 0.0)
    p = np.where(d < 0, -d, 0.0)
    ag, al = float(np.mean(g[:n])), float(np.mean(p[:n]))
    out[n], ags[n], als[n] = _rsi_valor(ag, al), ag, al
    for i in range(n, N - 1):
        ag = (ag * (n - 1) + g[i]) / n
        al = (al * (n - 1) + p[i]) / n
        out[i + 1], ags[i + 1], als[i + 1] = _rsi_valor(ag, al), ag, al
    return out, ags, als


def rsi(c: np.ndarray, n: int = RSI_N) -> np.ndarray:
    return rsi_estado(c, n)[0]


def obv(c: np.ndarray, v: np.ndarray) -> np.ndarray:
    """On-Balance Volume: soma o volume quando o fechamento sobe, subtrai quando cai. Começa em 0."""
    if len(c) == 0:
        return np.array([])
    return np.concatenate([[0.0], np.cumsum(np.sign(np.diff(c)) * v[1:])])


def obv_fluxo(o: np.ndarray, v: np.ndarray, n: int = OBV_N) -> np.ndarray:
    """Saldo de volume: variação do OBV em n barras ÷ volume total das mesmas n barras (-1 a +1)."""
    out = np.full(len(o), np.nan)
    if len(o) > n:
        soma = np.correlate(v, np.ones(n), "valid")[1:]          # v[t-n+1..t], t = n..N-1
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n:] = np.where(soma > 0, (o[n:] - o[:-n]) / soma, np.nan)
    return out


def obv_volatilidade(o: np.ndarray, v: np.ndarray, n: int = OBV_N) -> np.ndarray:
    """Desvio-padrão (amostral) da variação do OBV em n barras ÷ volume médio das mesmas n barras."""
    out = np.full(len(o), np.nan)
    if len(o) > n:
        d = np.diff(o)                                            # d[i] = o[i+1] - o[i]
        for t in range(n, len(o)):
            media = v[t - n + 1:t + 1].mean()
            if media > 0:
                out[t] = np.std(d[t - n:t], ddof=1) / media
    return out


# ---------------------------------------------------------------- agora × histórico
def medida(x: np.ndarray, datas) -> tuple[dict | None, dict | None]:
    """Resumo publicado e os mesmos números sem arredondar (para calcular os alvos)."""
    ok = np.isfinite(x)
    if not ok.any():
        return None, None
    xv, dv = x[ok], np.asarray(datas)[ok]
    agora = float(x[-1]) if np.isfinite(x[-1]) else None
    i0, i1 = int(np.argmin(xv)), int(np.argmax(xv))
    bruto = {"agora": agora, "min": float(xv[i0]), "max": float(xv[i1]), "media": float(xv.mean())}
    pub = {"agora": num(agora, 6),
           "min": {"v": num(xv[i0], 6), "d": dstr(dv[i0])},
           "max": {"v": num(xv[i1], 6), "d": dstr(dv[i1])},
           "media": num(bruto["media"], 6), "mediana": num(np.median(xv), 6),
           "pctl": num(float((xv < agora).mean()), 4) if agora is not None else None,
           "n": int(len(xv))}
    return pub, bruto


# ---------------------------------------------------------------- preços-alvo
class _Alvos:
    """Monta as linhas de preço-alvo de um indicador, conferindo cada uma por recálculo."""

    def __init__(self, atual: float, f, rotulo: str):
        self.atual, self.f, self.rotulo = atual, f, rotulo
        self.linhas: list[dict] = []

    def add(self, ident: str, nome: str, nivel: float | None, preco: float | None):
        if nivel is None:
            return
        linha = {"id": ident, "nome": nome, "nivel": num(nivel, 8), "preco": None, "var": None}
        self.linhas.append(linha)
        if preco is None or not np.isfinite(preco) or preco <= 0:
            linha["inalcancavel"] = True
            return
        obtido = self.f(float(preco))
        if not np.isfinite(obtido) or abs(obtido - nivel) > TOL * max(1.0, abs(nivel)):
            linha["erro"] = True
            print(f"::warning::Preço-alvo reprovado na conferência ({self.rotulo}, {ident}): "
                  f"pedido {nivel!r}, obtido {obtido!r} com preço {preco!r}", flush=True)
            return
        linha["preco"] = price(preco, 7)
        linha["var"] = num(preco / self.atual - 1, 6)


def alvos_drawdown(base: np.ndarray, atual: float, niveis: list[tuple], rotulo: str) -> list[dict]:
    pico = float(base.max())
    A = _Alvos(atual, lambda p: float(dd(np.append(base, p))[-1]), rotulo)
    for ident, nome, nivel in niveis:
        if nivel is None:
            continue
        # no recorde, o alvo é o maior entre o pico e o preço de agora (já pode estar acima do pico)
        A.add(ident, nome, nivel, max(pico, atual) if nivel == 0 else pico * (1 + nivel))
    return A.linhas


def alvos_media(base: np.ndarray, atual: float, tipo: str, n: int, niveis: list[tuple], rotulo: str) -> list[dict]:
    """A média da barra nova é linear no preço dela: média(P) = a·P + b.
    Distância pedida X  =>  P = (1+X)·b / (1 − (1+X)·a)."""
    if len(base) < n - 1:
        return []
    fn = MEDIAS[tipo]
    cauda = base if tipo == "ema" else base[-(n - 1):]

    def media_nova(p: float) -> float:
        return float(fn(np.append(cauda, p), n)[-1])

    b = media_nova(0.0)
    a = (media_nova(atual) - b) / atual
    A = _Alvos(atual, lambda p: p / media_nova(p) - 1, rotulo)
    for ident, nome, nivel in niveis:
        if nivel is None:
            continue
        den = 1 - (1 + nivel) * a
        A.add(ident, nome, nivel, (1 + nivel) * b / den if den > 0 else None)
    return A.linhas


def alvos_rsi(base: np.ndarray, atual: float, niveis: list[tuple], rotulo: str, n: int = RSI_N) -> list[dict]:
    """RSI de Wilder invertido para a barra seguinte. Com RS* = R/(100−R):
    alta:  P = C + (n−1)·(RS*·perda − ganho)      queda:  P = C − (n−1)·(ganho/RS* − perda)"""
    if len(base) <= n:
        return []
    _, ags, als = rsi_estado(base, n)
    ag, al, c0 = float(ags[-1]), float(als[-1]), float(base[-1])
    rs0 = ag / al if al > 0 else np.inf
    A = _Alvos(atual, lambda p: float(rsi(np.append(base, p), n)[-1]), rotulo)
    for ident, nome, nivel in niveis:
        if nivel is None:
            continue
        preco = None
        if 0 < nivel < 100:
            rs = nivel / (100 - nivel)
            preco = c0 + (n - 1) * (rs * al - ag) if rs >= rs0 else c0 - (n - 1) * (ag / rs - al)
        A.add(ident, nome, nivel, preco)
    return A.linhas


# ---------------------------------------------------------------- blocos
def bloco_drawdown(c, datas, base, atual, proximo, rotulo) -> dict:
    x = dd(c)
    m, bruto = medida(x, datas)
    idx = pd.DatetimeIndex(datas)
    por_ano = pd.Series(x, index=idx.year).groupby(level=0).min()
    ano_atual = int(idx[-1].year)
    fora = set()
    if proximo.year == ano_atual:
        fora.add(ano_atual)                                       # ano em andamento
    if (idx[0].month, idx[0].day) > (1, 10):
        fora.add(int(idx[0].year))                                # ano do início dos dados, incompleto
    completos = por_ano[[a for a in por_ano.index if a not in fora]]
    m_ano, media_ano = None, None
    if len(completos):
        agora_ano = float(por_ano[ano_atual])
        media_ano = float(completos.mean())
        m_ano = {"agora": num(agora_ano, 6), "ano": ano_atual,
                 "min": {"v": num(completos.min(), 6), "d": str(int(completos.idxmin()))},
                 "max": {"v": num(completos.max(), 6), "d": str(int(completos.idxmax()))},
                 "media": num(media_ano, 6), "mediana": num(completos.median(), 6),
                 "pctl": num(float((completos < agora_ano).mean()), 4), "n": int(len(completos))}
    i_pico, i_ref = int(np.argmax(c)), int(np.argmax(base))
    eps = _dd.episodios(pd.Series(c, index=idx))
    grandes = sorted((e for e in eps if e["depth"] is not None and e["depth"] <= -0.10), key=lambda e: e["depth"])
    return {
        "medida": m, "medida_ano": m_ano,
        "pico": {"v": price(c[i_pico], 7), "d": dstr(idx[i_pico])},
        # pico de onde os alvos medem a queda: o maior fechamento já definido (sem a barra em andamento)
        "pico_alvo": {"v": price(base[i_ref], 7), "d": dstr(idx[i_ref])},
        "alvos": alvos_drawdown(base, atual, [
            ("topo", "Recorde histórico", 0.0),
            ("media", "Média histórica", bruto["media"]),
            ("media_ano", "Média do pior drawdown do ano", media_ano),
            ("min", "Pior drawdown da história", bruto["min"])], rotulo + " drawdown"),
        "episodios": grandes[:25],
        "contagem": {"20": sum(1 for e in eps if e["depth"] <= -0.20), "30": sum(1 for e in eps if e["depth"] <= -0.30)},
    }


def bloco_medias(c, datas, base, atual, rotulo) -> dict:
    out = {}
    for tipo, fn in MEDIAS.items():
        out[tipo] = {}
        for n in PERIODOS_MM:
            ma = fn(c, n)
            with np.errstate(invalid="ignore"):
                dist = c / ma - 1
            m, bruto = medida(dist, datas)
            if m is None or bruto["agora"] is None:
                out[tipo][str(n)] = {"valor": None, "medida": None, "alvos": [], "faltam": max(0, n - len(c))}
                continue
            out[tipo][str(n)] = {
                "valor": price(ma[-1], 7), "medida": m,
                "alvos": alvos_media(base, atual, tipo, n, [
                    ("max", "Máxima histórica", bruto["max"]),
                    ("media", "Média histórica", bruto["media"]),
                    ("toque", "Preço igual à média", 0.0),
                    ("min", "Mínima histórica", bruto["min"])], f"{rotulo} {tipo}{n}")}
    return out


def bloco_rsi(c, datas, base, atual, rotulo) -> dict:
    m, bruto = medida(rsi(c), datas)
    if m is None or bruto["agora"] is None:
        return {"medida": None, "alvos": [], "faltam": max(0, RSI_N + 1 - len(c))}
    return {"medida": m, "alvos": alvos_rsi(base, atual, [
        ("max", "Máxima histórica", bruto["max"]),
        ("70", "Sobrecompra (70)", 70.0),
        ("media", "Média histórica", bruto["media"]),
        ("30", "Sobrevenda (30)", 30.0),
        ("min", "Mínima histórica", bruto["min"])], rotulo + " rsi")}


def bloco_obv(c, v, datas) -> dict:
    if not (v > 0).any():
        return {"sem_volume": True}
    o = obv(c, v)
    return {"nivel": medida(o, datas)[0],
            "fluxo": medida(obv_fluxo(o, v), datas)[0],
            "volatilidade": medida(obv_volatilidade(o, v), datas)[0]}


def analisar(df: pd.DataFrame, tempo: str, cal: str = "dias_uteis", rotulo: str = "") -> dict:
    """Tudo de um período (D, S ou M) para um ativo."""
    b = barras(df, tempo)
    c, v, datas = b["c"].to_numpy(float), b["v"].to_numpy(float), b.index
    ultimo = pd.Timestamp(df.index[-1])
    proximo = calendario.proximo_pregao(cal, ultimo)
    mesma = mesma_barra(tempo, ultimo, proximo)
    base = c[:-1] if mesma else c          # fechamentos que já estão definidos quando o próximo pregão fechar
    atual = float(c[-1])
    rot = f"{rotulo} {tempo}".strip()
    return {
        "tf": tempo,
        "d": [dstr(x) for x in datas], "c": [float(x) for x in c], "v": [int(round(x)) for x in v],
        "ultimo": {"d": dstr(ultimo), "preco": atual},
        "proximo": {"d": dstr(proximo), "mesma_barra": bool(mesma)},
        "parametros": {"mm": list(PERIODOS_MM), "rsi": RSI_N, "obv": OBV_N},
        "drawdown": bloco_drawdown(c, datas, base, atual, proximo, rot) if len(base) else None,
        "mm": bloco_medias(c, datas, base, atual, rot),
        "rsi": bloco_rsi(c, datas, base, atual, rot),
        "obv": bloco_obv(c, v, datas),
    }


def reprovados(a: dict) -> list[str]:
    """Alvos que não passaram na conferência (deve ser sempre vazio)."""
    ruins = []
    for nome, alvos in [("drawdown", (a.get("drawdown") or {}).get("alvos", [])), ("rsi", a["rsi"]["alvos"])] + \
            [(f"{t}{n}", blk["alvos"]) for t, per in a["mm"].items() for n, blk in per.items()]:
        ruins += [f"{nome}/{x['id']}" for x in alvos if x.get("erro")]
    return ruins


def calcular(ctx) -> dict:
    arquivos, resumo = {}, {}
    comum = {"symbol": ctx.ativo.id, "name": ctx.ativo.nome, "currency": ctx.ativo.moeda}
    for tempo in TEMPOS:
        a = analisar(ctx.df, tempo, ctx.calendario, ctx.ativo.id)
        ruins = reprovados(a)
        if ruins:
            log(f"  {ctx.ativo.id} {tempo}: alvos reprovados na conferência: {', '.join(ruins)}")
        arquivos[tempo] = {**comum, **a}
        if tempo == "D":
            resumo = {"rsi14": (a["rsi"]["medida"] or {}).get("agora"),
                      "dist_mm200": ((a["mm"]["sma"]["200"]["medida"]) or {}).get("agora")}
    return {"dados": {"tempos": list(TEMPOS)}, "resumo": resumo, "arquivos": arquivos}
