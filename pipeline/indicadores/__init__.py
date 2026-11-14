"""Registro dos indicadores.

Cada indicador é um arquivo nesta pasta com:
  ID, NOME, VERSAO     identificação (vai para o manifesto que o site lê)
  CHAVE                nome do bloco no arquivo JSON do ativo
  calcular(ctx) -> {"dados": ..., "resumo": {...}}
      'dados' vai para o bloco CHAVE do ativo; 'resumo' entra na tabela de resumo.

Para criar um indicador: escreva o arquivo e inclua o módulo em POR_ATIVO, na ordem de cálculo."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import ciclos, correlacao, drawdown, retornos, sazonalidade

POR_ATIVO = [retornos, drawdown, ciclos, sazonalidade, correlacao]


@dataclass
class Contexto:
    """Tudo que um indicador pode precisar para um ativo."""
    ativo: object                    # universo.Ativo
    df: pd.DataFrame                 # cotações (já cortadas em 'inicio', se houver)
    df_cheio: pd.DataFrame           # cotações completas
    inicio: pd.Timestamp | None
    limiares: list[float]
    ret_semanal: pd.DataFrame        # retornos semanais de todos os ativos do mercado
    datas_semana: list[str]
    referencias: list[str]           # ids das referências com dados
    referencia_principal: str | None
    resumo: dict = field(default_factory=dict)   # o que os indicadores anteriores já resumiram

    @property
    def s(self) -> pd.Series:
        return self.df["adj_close"]


def manifesto() -> list[dict]:
    return [{"id": m.ID, "nome": m.NOME, "chave": m.CHAVE, "versao": m.VERSAO} for m in POR_ATIVO]


def calcular_ativo(ctx: Contexto) -> tuple[dict, dict]:
    blocos = {}
    for m in POR_ATIVO:
        r = m.calcular(ctx)
        blocos[m.CHAVE] = r["dados"]
        ctx.resumo.update(r.get("resumo") or {})
    return blocos, ctx.resumo
