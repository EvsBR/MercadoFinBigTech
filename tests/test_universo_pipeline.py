import json
from pathlib import Path

import pytest

from pipeline import base, construir
from pipeline.fontes import FONTES, demo
from pipeline.universo import ErroUniverso, carregar

RAIZ = Path(__file__).resolve().parents[1]


def escrever_universo(pasta, segmentos, refs=({"id": "QQQ"},), **mercado):
    pasta.mkdir(parents=True, exist_ok=True)
    m = {"id": "eua", "nome": "EUA", "moeda": "US$", "arquivo": "eua.json", "fontes": ["yahoo"], **mercado}
    (pasta / "mercados.json").write_text(json.dumps({"mercados": [m]}))
    (pasta / "eua.json").write_text(json.dumps({"referencias": list(refs), "segmentos": segmentos}))
    return pasta


def test_universo_do_repositorio_e_valido():
    mercados = carregar(RAIZ / "universo", set(FONTES) - {"demo"})
    assert mercados and all(m.segmentos and m.referencia_principal in m.referencias for m in mercados)
    for m in mercados:
        for s in m.segmentos:
            assert all(a in m.ativos for a in s.ativos)


def test_ticker_por_fonte(tmp_path):
    u = escrever_universo(tmp_path, [{"id": "x", "ativos": [{"id": "BRK.B", "tickers": {"yahoo": "BRK-B"}}]}])
    a = carregar(u)[0].ativos["BRK.B"]
    assert a.ticker("yahoo") == "BRK-B" and a.ticker("tiingo") == "BRK.B"


@pytest.mark.parametrize("segmentos, kw", [
    ([{"id": "x", "ativos": [{"id": "AAPL"}, {"id": "AAPL"}]}], {}),          # ativo repetido
    ([{"id": "x", "ativos": []}], {}),                                        # segmento vazio
    ([{"id": "Tem Espaço", "ativos": [{"id": "AAPL"}]}], {}),                 # id de segmento inválido
    ([{"id": "x", "ativos": [{"id": "QQQ"}]}], {}),                           # ação que já é referência
    ([{"id": "x", "ativos": [{"id": "AAPL"}]}], {"referencia_principal": "SPY"}),
    ([{"id": "x", "ativos": [{"id": "AAPL"}]}], {"fontes": ["inexistente"]}),
])
def test_universo_mal_preenchido_e_recusado(tmp_path, segmentos, kw):
    with pytest.raises(ErroUniverso):
        carregar(escrever_universo(tmp_path, segmentos, **kw), set(FONTES))


def test_construcao_completa_em_modo_demo(tmp_path):
    saida = tmp_path / "data"
    assert construir.main(["--demo", "--saida", str(saida), "--base", str(tmp_path / "base")]) == 0
    idx = json.loads((saida / "indice.json").read_text())
    assert idx["demo"] is True and idx["mercados"][0]["segmentos"]
    m, s = idx["mercados"][0]["id"], idx["mercados"][0]["segmentos"][0]["id"]
    meta = json.loads((saida / m / s / "meta.json").read_text())
    assert len(meta["tickers"]) == idx["mercados"][0]["segmentos"][0]["n"]
    ativo = json.loads((saida / meta["tickers"][0]["file"]).read_text())
    for chave in [i["chave"] for i in idx["indicadores"]] + ["stats"]:
        assert chave in ativo
    for tempo in ativo["tecnica"]["tempos"]:            # arquivos à parte da análise técnica
        arq = saida / meta["tickers"][0]["file"].replace(".json", f".tecnica.{tempo}.json")
        tec = json.loads(arq.read_text())
        assert tec["tf"] == tempo and len(tec["d"]) == len(tec["c"]) == len(tec["v"])
    assert not (tmp_path / "base").exists()          # o modo demo nunca toca na base real


def test_fonte_fora_do_ar_usa_a_base_e_marca_falha(tmp_path, monkeypatch):
    mercado = carregar(RAIZ / "universo")[0]
    ativo = next(iter(mercado.ativos.values()))
    base.gravar(tmp_path, mercado.id, ativo.id, demo.baixar(ativo.id, {}))

    def fora_do_ar(ticker, env):
        raise RuntimeError("HTTP 503")
    for f in mercado.fontes:
        monkeypatch.setattr(FONTES[f], "baixar", fora_do_ar)
        monkeypatch.setattr(FONTES[f], "disponivel", lambda env: True)
        monkeypatch.setattr(FONTES[f], "PAUSA", 0)
    monkeypatch.setattr(construir.time, "sleep", lambda s: None)
    estado = {}
    df, info = construir.obter(ativo, mercado, tmp_path, estado, {}, False, set())
    assert df is not None and info["falhou"] is True and len(info["tentativas"]) == len(mercado.fontes)
    assert estado[ativo.id]["falhou"] is True


def test_fonte_boa_grava_na_base_e_reaproveita_na_rodada_seguinte(tmp_path, monkeypatch):
    mercado = carregar(RAIZ / "universo")[0]
    ativo = next(iter(mercado.ativos.values()))
    chamadas = []
    primeira = mercado.fontes[0]
    monkeypatch.setattr(FONTES[primeira], "baixar", lambda t, env: chamadas.append(t) or demo.baixar(t, env))
    monkeypatch.setattr(FONTES[primeira], "PAUSA", 0)
    estado = {}
    df, info = construir.obter(ativo, mercado, tmp_path, estado, {}, False, set())
    assert info["falhou"] is False and base.ler(tmp_path, mercado.id, ativo.id) is not None
    construir.obter(ativo, mercado, tmp_path, estado, {}, False, set())
    assert len(chamadas) == 1                        # baixado há pouco: não baixa de novo
