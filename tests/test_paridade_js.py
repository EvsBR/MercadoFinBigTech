"""As curvas que o site desenha (site/indicadores.js) têm de ser as mesmas do pipeline."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from pipeline.fontes import demo
from pipeline.indicadores import tecnica as T

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("paridade.js")


def curvas_python(c, v):
    o = T.obv(c, v)
    out = {"dd": T.dd(c), "rsi": T.rsi(c), "obv": o, "obv_fluxo": T.obv_fluxo(o, v), "obv_volatilidade": T.obv_volatilidade(o, v)}
    for tipo, fn in T.MEDIAS.items():
        for n in T.PERIODOS_MM:
            out[f"{tipo}{n}"] = fn(c, n)
    return out


def casos():
    for ticker in ("AAPL", "TSLA"):
        b = T.barras(demo.baixar(ticker, {}), "D")
        yield ticker, b["c"].to_numpy(float), b["v"].to_numpy(float)
    # trechos parados (variação zero), volume zero e histórico curto
    rng = np.random.default_rng(3)
    c = np.round(50 + np.cumsum(rng.choice([-1.0, 0.0, 0.0, 1.0], 400)), 2)
    v = rng.integers(0, 5, 400).astype(float) * 1000
    yield "parado", c, v
    yield "curto", c[:30], v[:30]


@pytest.mark.skipif(NODE is None, reason="Node.js não instalado")
@pytest.mark.parametrize("nome, c, v", list(casos()), ids=lambda x: x if isinstance(x, str) else "")
def test_javascript_e_python_dao_as_mesmas_curvas(nome, c, v):
    r = subprocess.run([NODE, str(SCRIPT)], input=json.dumps({"c": c.tolist(), "v": v.tolist()}),
                       capture_output=True, text=True, check=True)
    js = json.loads(r.stdout)
    py = curvas_python(c, v)
    assert set(js) == set(py)
    for chave, esperado in py.items():
        obtido = np.array([np.nan if x is None else x for x in js[chave]], dtype=float)
        assert obtido.shape == esperado.shape, chave
        assert np.array_equal(np.isnan(obtido), np.isnan(esperado)), f"{chave}: buracos em lugares diferentes"
        assert np.allclose(obtido, esperado, rtol=1e-9, atol=1e-9, equal_nan=True), chave
