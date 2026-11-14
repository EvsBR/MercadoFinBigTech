#!/usr/bin/env python3
"""Ensaio das fontes de reserva: baixa alguns ativos em cada reserva configurada e compara com a
base salva. Mostra se a chave funciona e se os números batem. Não altera nada.

Uso: python scripts/conferir_reservas.py AAPL NVDA"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from pipeline import base  # noqa: E402
from pipeline.fontes import FONTES  # noqa: E402
from pipeline.universo import carregar  # noqa: E402


def main() -> int:
    env = {k: v for k, v in os.environ.items() if k.endswith("_API_KEY") and v}
    mercado = carregar(RAIZ / "universo")[0]
    ids = sys.argv[1:] or list(mercado.ativos)[:2]
    reservas = [f for f in mercado.fontes[1:] if FONTES[f].disponivel(env)]
    if not reservas:
        print("Nenhuma fonte de reserva configurada (sem chaves). Nada a conferir.")
        return 0
    ruim = False
    for fid in reservas:
        mod = FONTES[fid]
        for aid in ids:
            guardado = base.ler(RAIZ / "data" / "base", mercado.id, aid)
            try:
                novo = mod.baixar(mercado.ativos[aid].ticker(fid), env)
            except Exception as exc:  # noqa: BLE001
                print(f"FALHOU  {mod.NOME:12s} {aid}: {str(exc)[:200]}")
                ruim = True
                continue
            msg = f"{len(novo)} pregões, {novo.index[0].date()} → {novo.index[-1].date()}"
            if guardado is not None:
                comuns = novo.index.intersection(guardado.index)[-250:]
                col = "adj_close" if mod.COMPLETA else "close"
                dif = (novo.loc[comuns, col] / guardado.loc[comuns, col] - 1).abs()
                msg += f" | diferença de {col} vs base no último ano: mediana {dif.median():.4%}, máxima {dif.max():.4%}"
                if mod.COMPLETA:
                    ini = abs((novo.index[0] - guardado.index[0]).days)
                    msg += f" | início difere {ini} dias"
                else:
                    emenda, aviso = base.emendar(guardado.iloc[:-5], novo)
                    msg += " | emenda " + ("ok" if emenda is not None and emenda.index[-1] == novo.index[-1] else f"RECUSADA ({aviso})")
                if dif.median() > 0.005:
                    ruim = True
            print(f"OK      {mod.NOME:12s} {aid}: {msg}")
    return 1 if ruim else 0


if __name__ == "__main__":
    sys.exit(main())
