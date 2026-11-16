"""Análise técnica: casos calculados à mão, comparação com a biblioteca TA-Lib e conferência
independente de todo preço-alvo publicado."""
import numpy as np
import pandas as pd
import pytest

from pipeline.fontes import demo
from pipeline.indicadores import tecnica as T


# ---------------------------------------------------------------- casos calculados à mão
def test_medias_a_mao():
    c = np.array([1.0, 2, 3, 4, 5])
    assert T.sma(c, 3)[2:].tolist() == [2, 3, 4] and np.isnan(T.sma(c, 3)[:2]).all()
    # ponderada 3: (1·a + 2·b + 3·c) / 6
    assert T.wma(c, 3)[2:] == pytest.approx([14 / 6, 20 / 6, 26 / 6])
    # exponencial 3: semente = média(1,2,3) = 2; alfa = 0,5 -> 0,5·4 + 0,5·2 = 3 -> 0,5·5 + 0,5·3 = 4
    assert T.ema(c, 3)[2:].tolist() == [2, 3, 4]


def test_rsi_de_wilder_a_mao():
    # variações: +1, −1, +2, −1 ; n = 2
    r, ag, al = T.rsi_estado(np.array([10.0, 11, 10, 12, 11]), 2)
    assert np.isnan(r[:2]).all()
    assert r[2] == pytest.approx(50)                    # ganho médio 0,5 ; perda média 0,5
    assert (ag[3], al[3]) == pytest.approx((1.25, 0.25))
    assert r[3] == pytest.approx(100 - 100 / 6)         # RS = 5
    assert r[4] == pytest.approx(50)                    # 0,625 e 0,625


def test_obv_drawdown_e_saldo_de_volume_a_mao():
    c = np.array([10.0, 11, 11, 9, 12])
    v = np.array([5.0, 3, 4, 2, 6])
    o = T.obv(c, v)
    assert o.tolist() == [0, 3, 3, 1, 7]                # sobe +3, parado 0, cai −2, sobe +6
    f = T.obv_fluxo(o, v, 2)
    assert f[2:] == pytest.approx([3 / 7, -2 / 6, 4 / 8])
    vol = T.obv_volatilidade(o, v, 2)
    assert vol[2] == pytest.approx(np.std([3, 0], ddof=1) / 3.5)
    assert T.dd(np.array([100.0, 120, 90, 120, 60])).tolist() == pytest.approx([0, 0, -0.25, 0, -0.5])


def test_barras_semanais_e_mensais(fazer_tabela):
    # 10 pregões terminando na sexta 30/01/2026: duas semanas inteiras, um mês
    df = fazer_tabela(range(1, 11), fim="2026-01-30", volume=100.0)
    s = T.barras(df, "S")
    assert s["c"].tolist() == [5, 10] and s["v"].tolist() == [500, 500]
    assert [d.strftime("%Y-%m-%d") for d in s.index] == ["2026-01-23", "2026-01-30"]
    m = T.barras(df, "M")
    assert m["c"].tolist() == [10] and m["v"].tolist() == [1000]
    assert T.barras(df, "D")["c"].tolist() == list(range(1, 11))


def test_pior_drawdown_por_ano_a_mao():
    # 2023 começa em 02/01 (ano completo), 2024 completo, 2025 em andamento
    idx = pd.to_datetime(["2023-01-02", "2023-06-01", "2023-12-29", "2024-03-01", "2024-12-31", "2025-02-03"])
    c = np.array([100.0, 80, 100, 50, 90, 95])
    b = T.bloco_drawdown(c, idx, c, 95.0, pd.Timestamp("2025-02-04"), "teste")
    a = b["medida_ano"]
    assert a["n"] == 2 and a["ano"] == 2025
    assert a["media"] == pytest.approx((-0.20 + -0.50) / 2)
    assert a["min"] == {"v": -0.5, "d": "2024"} and a["max"] == {"v": -0.2, "d": "2023"}
    assert a["agora"] == pytest.approx(-0.05)
    alvos = {x["id"]: x for x in b["alvos"]}
    assert alvos["topo"]["preco"] == 100 and alvos["min"]["preco"] == 50
    assert alvos["media_ano"]["preco"] == pytest.approx(65)       # 100 × (1 − 0,35)
    assert alvos["media_ano"]["var"] == pytest.approx(65 / 95 - 1, abs=1e-6)


# ---------------------------------------------------------------- biblioteca de referência
def test_bate_com_a_talib():
    talib = pytest.importorskip("talib")
    b = T.barras(demo.baixar("NVDA", {}), "D")
    c, v = b["c"].to_numpy(float), b["v"].to_numpy(float)
    for n in T.PERIODOS_MM:
        assert np.allclose(T.sma(c, n), talib.SMA(c, n), rtol=1e-10, equal_nan=True)
        assert np.allclose(T.ema(c, n), talib.EMA(c, n), rtol=1e-10, equal_nan=True)
        assert np.allclose(T.wma(c, n), talib.WMA(c, n), rtol=1e-10, equal_nan=True)
    assert np.allclose(T.rsi(c, 14), talib.RSI(c, 14), rtol=1e-10, equal_nan=True)
    dif = talib.OBV(c, v) - T.obv(c, v)                 # a TA-Lib começa no volume da 1ª barra; aqui, em 0
    assert np.allclose(dif, v[0], rtol=0, atol=1e-3)


# ---------------------------------------------------------------- preços-alvo
def ema_lento(c, n):
    e = sum(c[:n]) / n
    for x in c[n:]:
        e += (2 / (n + 1)) * (x - e)
    return e


def rsi_lento(c, n=14):
    """RSI pela suavização exponencial do pandas (outro caminho de cálculo)."""
    d = pd.Series(c).diff().dropna().reset_index(drop=True)
    g, p = d.clip(lower=0), (-d).clip(lower=0)
    media = lambda s: pd.concat([pd.Series([s[:n].mean()]), s[n:]]).ewm(alpha=1 / n, adjust=False).mean().iloc[-1]
    ag, al = media(g), media(p)
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def indicador_lento(nome, c):
    """Valor do indicador na última barra, por implementações que não usam o código do pipeline."""
    if nome == "drawdown":
        return c[-1] / max(c) - 1
    if nome == "rsi":
        return rsi_lento(c)
    tipo, n = nome[:3], int(nome[3:])
    if tipo == "sma":
        media = sum(c[-n:]) / n
    elif tipo == "wma":
        media = sum((k + 1) * x for k, x in enumerate(c[-n:])) / (n * (n + 1) / 2)
    else:
        media = ema_lento(list(c), n)
    return c[-1] / media - 1


def todos_os_alvos(a):
    yield from (("drawdown", x) for x in a["drawdown"]["alvos"])
    yield from (("rsi", x) for x in a["rsi"]["alvos"])
    for tipo, per in a["mm"].items():
        for n, blk in per.items():
            yield from ((f"{tipo}{n}", x) for x in blk["alvos"])


CORTES = ["2026-10-30",   # sexta, último pregão do mês: semana e mês fechados
          "2026-11-11",   # quarta: semana e mês em andamento
          "2026-04-02"]   # quinta antes da Sexta-feira Santa: semana fechada, mês em andamento


@pytest.mark.parametrize("ticker", ["AAPL", "TSLA", "QQQ"])
@pytest.mark.parametrize("corte", CORTES)
@pytest.mark.parametrize("tempo", list(T.TEMPOS))
def test_todo_alvo_publicado_leva_o_indicador_ao_nivel(ticker, corte, tempo):
    df = demo.baixar(ticker, {})[:corte]
    a = T.analisar(df, tempo, "nyse", ticker)
    assert T.reprovados(a) == []
    c = np.array(a["c"])
    base = c[:-1] if a["proximo"]["mesma_barra"] else c
    n_alvos = 0
    for nome, x in todos_os_alvos(a):
        if x["preco"] is None:
            assert x.get("inalcancavel") is True
            continue
        n_alvos += 1
        obtido = indicador_lento(nome, list(base) + [x["preco"]])
        # folga = arredondamento do preço publicado (7 algarismos)
        assert obtido == pytest.approx(x["nivel"], abs=2e-3 if nome == "rsi" else 5e-6), (nome, x)
        assert x["var"] == pytest.approx(x["preco"] / a["ultimo"]["preco"] - 1, abs=1e-6)
    assert n_alvos >= 30                                   # históricos curtos não têm MM250 mensal


def test_alvo_bate_com_busca_numerica_independente():
    """Acha o preço por bisseção sobre o recálculo lento e compara com o publicado."""
    a = T.analisar(demo.baixar("MSFT", {})[:"2026-11-11"], "S", "nyse", "MSFT")
    base = list(np.array(a["c"])[:-1])
    assert a["proximo"]["mesma_barra"] is True
    for nome, ident in [("sma200", "min"), ("ema50", "max"), ("wma100", "toque"), ("rsi", "30"), ("rsi", "70"), ("drawdown", "media")]:
        alvos = a["rsi"]["alvos"] if nome == "rsi" else a["drawdown"]["alvos"] if nome == "drawdown" else a["mm"][nome[:3]][nome[3:]]["alvos"]
        x = next(k for k in alvos if k["id"] == ident)
        lo, hi = 1e-6, base[-1] * 50
        for _ in range(200):
            meio = (lo + hi) / 2
            if indicador_lento(nome, base + [meio]) < x["nivel"]:
                lo = meio
            else:
                hi = meio
        assert x["preco"] == pytest.approx(meio, rel=1e-6), (nome, ident)


@pytest.mark.parametrize("corte, semana, mes", [("2026-10-30", False, False), ("2026-11-11", True, True),
                                               ("2026-04-02", False, True)])
def test_barra_em_andamento_ou_barra_nova(corte, semana, mes):
    df = demo.baixar("AAPL", {})[:corte]
    assert T.analisar(df, "D", "nyse")["proximo"]["mesma_barra"] is False
    assert T.analisar(df, "S", "nyse")["proximo"]["mesma_barra"] is semana
    assert T.analisar(df, "M", "nyse")["proximo"]["mesma_barra"] is mes


def test_no_recorde_o_alvo_do_topo_e_o_preco_atual(fazer_tabela):
    # semana anterior fecha em 100 (sexta 06/11); a semana em andamento está em 104 na quarta
    df = fazer_tabela([80, 90, 95, 100, 98, 99, 104], fim="2026-11-11")
    a = T.analisar(df, "S", "nyse")
    topo = next(x for x in a["drawdown"]["alvos"] if x["id"] == "topo")
    assert a["proximo"]["mesma_barra"] is True
    assert topo["preco"] == 104 and topo["var"] == 0
    assert a["drawdown"]["pico"]["v"] == 104 and a["drawdown"]["pico_alvo"]["v"] == 100


def test_rsi_fora_de_alcance_em_um_pregao_sai_sem_preco():
    # depois de 40 altas seguidas o RSI é 100; cair a 5 pediria um preço negativo
    c = np.arange(1.0, 42.0)
    linhas = T.alvos_rsi(c, c[-1], [("x", "teste", 5.0), ("y", "teste", 60.0)], "teste")
    assert linhas[0]["preco"] is None and linhas[0]["inalcancavel"] is True
    assert linhas[1]["preco"] is not None and linhas[1]["preco"] < c[-1]


def test_alvo_errado_nao_e_publicado(capsys):
    A = T._Alvos(100.0, lambda p: p / 100 - 1, "teste")
    A.add("ok", "certo", 0.10, 110.0)
    A.add("ruim", "errado", 0.10, 120.0)
    assert A.linhas[0]["preco"] == 110 and "erro" not in A.linhas[0]
    assert A.linhas[1]["preco"] is None and A.linhas[1]["erro"] is True
    assert "reprovado" in capsys.readouterr().out


def test_historico_curto_nao_quebra(fazer_tabela):
    df = fazer_tabela(np.linspace(10, 12, 40), fim="2026-11-13")
    for tempo in T.TEMPOS:
        a = T.analisar(df, tempo, "nyse")
        assert a["mm"]["sma"]["50"]["valor"] is None and a["mm"]["sma"]["50"]["faltam"] > 0
        assert T.reprovados(a) == []
    assert T.analisar(df, "D", "nyse")["rsi"]["medida"]["agora"] is not None
    assert T.analisar(df, "M", "nyse")["rsi"]["medida"] is None


def test_sem_volume_o_obv_fica_marcado(fazer_tabela):
    df = fazer_tabela(np.linspace(10, 12, 80), fim="2026-11-13", volume=0.0)
    assert T.analisar(df, "D", "nyse")["obv"] == {"sem_volume": True}


def test_percentil_e_extremos():
    x = np.array([np.nan, 1.0, 5, 3, 2, 4])
    pub, bruto = T.medida(x, pd.bdate_range("2026-01-05", periods=6))
    assert pub["min"] == {"v": 1.0, "d": "2026-01-06"} and pub["max"] == {"v": 5.0, "d": "2026-01-07"}
    assert pub["media"] == 3 and pub["mediana"] == 3 and pub["n"] == 5
    assert pub["agora"] == 4 and pub["pctl"] == 0.6      # 3 de 5 valores abaixo de 4
