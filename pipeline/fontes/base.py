"""Contrato comum das fontes de cotações.

Cada fonte é um módulo com:
  NOME      nome exibido no site
  COMPLETA  True se devolve o histórico inteiro já ajustado por proventos;
            False se só serve para completar os últimos pregões (emenda na base)
  disponivel(env) -> bool   (ex.: a chave de API existe?)
  baixar(ticker, env) -> DataFrame no formato de util.normalizar
"""
from __future__ import annotations


class FonteIndisponivel(RuntimeError):
    """A fonte não pode ser usada agora (sem chave, cota esgotada, bloqueio)."""


class CotaEsgotada(FonteIndisponivel):
    """Limite do plano gratuito atingido: não adianta tentar de novo nesta rodada."""
