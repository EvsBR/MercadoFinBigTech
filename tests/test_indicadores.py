"""Indicadores conferidos contra casos calculados à mão."""
import numpy as np
import pandas as pd
import pytest

from pipeline.fontes import demo, tiingo
from pipeline.indicadores import ciclos, correlacao, drawdown, sazonalidade


def serie(valores, inicio="2020-01-01"):
    return pd.Series([float(v) for v in valores], index=pd.bdate_range(inicio, periods=len(valores)))


def test_drawdown_episodio_recuperado_e_em_andamento():
    s = serie([100, 120, 90, 60, 120, 130, 117])
    eps = drawdown.episodios(s)
    assert len(eps) == 2
    a, b = eps
    assert a["depth"] == pytest.approx(-0.5)            # 120 -> 60
    assert (a["peak"], a["trough"], a["recovery"]) == ("2020-01-02", "2020-01-06", "2020-01-07")
    assert a["ongoing"] is False
    assert b["depth"] == pytest.approx(-0.1)            # 130 -> 117, ainda aberto
    assert b["ongoing"] is True and b["recovery"] is None
    assert drawdown.serie(s).iloc[-1] == pytest.approx(-0.1)


def test_ciclos_regra_de_20_por_cento():
    # sobe 100->150, cai 150->100 (-33%), sobe 100->130 (+30%)
    s = serie([100, 125, 150, 135, 110, 100, 115, 130])
    r = ciclos.fases(s, 0.20)
    tipos = [(f["type"], f["start"], f["end"]) for f in r["phases"]]
    assert tipos == [("alta", "2020-01-01", "2020-01-03"),
                     ("baixa", "2020-01-03", "2020-01-08"),
                     ("alta", "2020-01-08", "2020-01-10")]
    assert r["phases"][1]["ret"] == pytest.approx(100 / 150 - 1, abs=1e-5)
    assert r["phases"][0]["truncated"] is True          # começa no 1º dado: fora das medianas
    assert r["current"]["type"] == "alta" and r["current"]["ret"] == pytest.approx(0.30)
    assert r["bull"]["n"] == 0 and r["bear"]["n"] == 1


def test_sazonalidade_trimestre_e_produto_dos_meses():
    idx = pd.bdate_range("2019-12-02", "2021-12-31")
    rng = np.random.default_rng(7)
    s = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))), index=idx)
    mensal = sazonalidade.tabela(s, 1)
    tri = sazonalidade.tabela(s, 3)
    y = mensal["years"].index(2020)
    for q in range(4):
        esperado = np.prod([1 + mensal["values"][y][m] for m in range(q * 3, q * 3 + 3)]) - 1
        assert tri["values"][tri["years"].index(2020)][q] == pytest.approx(esperado, abs=1e-4)
    # confere um mês direto nos preços
    jan = s[:"2020-01-31"].iloc[-1] / s[:"2019-12-31"].iloc[-1] - 1
    assert mensal["values"][y][0] == pytest.approx(jan, abs=1e-5)
    assert mensal["annual"][y] == pytest.approx(s[:"2020-12-31"].iloc[-1] / s[:"2019-12-31"].iloc[-1] - 1, abs=1e-4)


def test_correlacao_do_segmento_e_simetrica_com_diagonal_1():
    precos = {t: demo.baixar(t, {})["adj_close"] for t in ("AAPL", "MSFT", "NVDA", "QQQ")}
    wret, datas = correlacao.painel_semanal(precos)
    r = correlacao.do_segmento(wret, datas, ["AAPL", "MSFT", "NVDA"], ["QQQ"])
    m = np.array(r["matrices"]["3a"], dtype=float)
    assert np.allclose(m, m.T) and np.allclose(np.diag(m), 1)
    direto = wret[["AAPL", "MSFT"]].tail(156).corr().iloc[0, 1]
    assert m[0, 1] == pytest.approx(direto, abs=1e-3)
    assert len(r["avg_pairwise"]["d"]) == len(r["avg_pairwise"]["v"]) > 0


def test_tiingo_converte_precos_brutos_para_ajustados_por_desdobramento():
    # desdobramento 4:1 no 3º dia: os dois primeiros dias devem ser divididos por 4
    linhas = [
        {"date": "2024-01-02T00:00:00.000Z", "open": 400, "high": 404, "low": 396, "close": 400, "volume": 100, "adjClose": 100, "divCash": 0, "splitFactor": 1},
        {"date": "2024-01-03T00:00:00.000Z", "open": 404, "high": 408, "low": 400, "close": 404, "volume": 100, "adjClose": 101, "divCash": 0, "splitFactor": 1},
        {"date": "2024-01-04T00:00:00.000Z", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 400, "adjClose": 102, "divCash": 0, "splitFactor": 4},
    ]
    df = tiingo.converter(linhas)
    assert list(df["close"]) == [100, 101, 102]
    assert list(df["volume"]) == [400, 400, 400]
    assert df["split"].iloc[2] == 4
