import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.util import normalizar  # noqa: E402


def tabela(fechamentos, fim=None, volume=1000.0):
    """Cotações simples a partir de uma lista de fechamentos (dias úteis terminando em 'fim')."""
    fim = pd.Timestamp(fim) if fim else pd.Timestamp.today().normalize()
    idx = pd.bdate_range(end=fim, periods=len(fechamentos))
    c = np.asarray(fechamentos, dtype=float)
    return normalizar(pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
                                    "adj_close": c, "volume": volume}, index=idx))


@pytest.fixture
def fazer_tabela():
    return tabela
