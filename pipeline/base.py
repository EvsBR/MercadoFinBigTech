"""Base de cotações em disco: um CSV por ativo em data/base/<mercado>/<ATIVO>.csv.

Guarda abertura, máxima, mínima, fechamento, fechamento ajustado, volume, dividendo e
desdobramento de cada pregão. A base é o que mantém o site no ar quando uma fonte falha:
o histórico já baixado fica salvo e só os pregões novos precisam chegar."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .util import COLUNAS, normalizar, safe_name


def caminho(raiz: Path, mercado: str, ativo: str) -> Path:
    return raiz / mercado / f"{safe_name(ativo)}.csv"


def ler(raiz: Path, mercado: str, ativo: str) -> pd.DataFrame | None:
    arq = caminho(raiz, mercado, ativo)
    if not arq.exists():
        return None
    try:
        df = pd.read_csv(arq, parse_dates=["date"], index_col="date")
    except Exception:  # noqa: BLE001 - arquivo corrompido = como se não existisse
        return None
    if df.empty:
        return None
    return normalizar(df)


def gravar(raiz: Path, mercado: str, ativo: str, df: pd.DataFrame):
    arq = caminho(raiz, mercado, ativo)
    arq.parent.mkdir(parents=True, exist_ok=True)
    out = df[COLUNAS].copy()
    out.index = out.index.strftime("%Y-%m-%d")
    out.index.name = "date"
    tmp = arq.with_suffix(".tmp")
    out.to_csv(tmp, float_format="%.8g")
    tmp.replace(arq)   # troca atômica: nunca fica um arquivo pela metade


def ler_estado(raiz: Path, mercado: str) -> dict:
    arq = raiz / mercado / "_estado.json"
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def gravar_estado(raiz: Path, mercado: str, estado: dict):
    arq = raiz / mercado / "_estado.json"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emendar(base: pd.DataFrame, novo: pd.DataFrame) -> tuple[pd.DataFrame | None, str]:
    """Completa a base com os pregões mais recentes de uma fonte que NÃO traz o histórico
    ajustado por proventos. Devolve (tabela, aviso) ou (None, motivo) se a emenda não é segura.

    - Confere os fechamentos nas datas em comum. Se a razão base/novo for constante e diferente
      de 1, houve desdobramento depois da última atualização: a base antiga é reescalada.
    - Os pregões novos entram com adj_close = close (um dividendo pago nesse intervalo só é
      incorporado na próxima atualização completa; o efeito é de poucos décimos de ponto)."""
    comuns = base.index.intersection(novo.index)
    if len(comuns) < 3:
        return None, "sem datas em comum suficientes para emendar"
    comuns = comuns[-20:]
    razao = (novo.loc[comuns, "close"] / base.loc[comuns, "close"]).to_numpy()
    r = float(np.median(razao))
    if not np.isfinite(r) or r <= 0 or np.max(np.abs(razao / r - 1)) > 0.02:
        return None, "fechamentos da reserva não batem com a base"
    antiga = base.copy()
    aviso = ""
    if abs(r - 1) > 0.02:   # desdobramento (ou grupamento) no intervalo
        for c in ("open", "high", "low", "close", "adj_close", "dividend"):
            antiga[c] = antiga[c] * r
        antiga["volume"] = antiga["volume"] / r
        aviso = f"base reescalada por {r:.4g} (desdobramento)"
    novos = novo[novo.index > base.index[-1]].copy()
    if novos.empty:
        return antiga, aviso
    novos["adj_close"] = novos["close"]
    return normalizar(pd.concat([antiga, novos])), aviso
