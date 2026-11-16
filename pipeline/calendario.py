"""Calendário de pregões: qual é o próximo dia de negociação de cada mercado.

Serve aos preços-alvo da Análise Técnica, que respondem "que fechamento, no próximo pregão,
leva o indicador a tal nível". Para barras semanais e mensais é preciso saber se o próximo
pregão ainda cai na barra em andamento ou se já abre uma barra nova.

Calendários:
  nyse        bolsas dos EUA (fins de semana + feriados regulares da NYSE)
  dias_uteis  segunda a sexta, sem feriados
  24x7        todo dia (cripto)
Fechamentos extraordinários (luto oficial, furacões) não estão previstos."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

CALENDARIOS = ("nyse", "dias_uteis", "24x7")


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo gregoriano anônimo)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def _n_esimo(ano: int, mes: int, dia_semana: int, n: int) -> date:
    """n-ésimo dia da semana do mês (segunda = 0). n = -1: o último."""
    if n > 0:
        d = date(ano, mes, 1)
        d += timedelta(days=(dia_semana - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(ano + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - dia_semana) % 7)


def _observado(d: date, sabado_vira_sexta: bool = True) -> date | None:
    """Feriado de data fixa: domingo passa para segunda; sábado passa para sexta."""
    if d.weekday() == 6:
        return d + timedelta(days=1)
    if d.weekday() == 5:
        return d - timedelta(days=1) if sabado_vira_sexta else None
    return d


def feriados_nyse(ano: int) -> set[date]:
    """Feriados regulares da NYSE (regras em vigor desde 2022)."""
    fixos = [
        _observado(date(ano, 1, 1), sabado_vira_sexta=False),   # Ano-Novo num sábado não fecha a sexta
        _observado(date(ano, 6, 19)),                           # Juneteenth
        _observado(date(ano, 7, 4)),                            # Independência
        _observado(date(ano, 12, 25)),                          # Natal
    ]
    moveis = [
        _n_esimo(ano, 1, 0, 3),                # Martin Luther King: 3ª segunda de janeiro
        _n_esimo(ano, 2, 0, 3),                # Presidents' Day: 3ª segunda de fevereiro
        pascoa(ano) - timedelta(days=2),       # Sexta-feira Santa
        _n_esimo(ano, 5, 0, -1),               # Memorial Day: última segunda de maio
        _n_esimo(ano, 9, 0, 1),                # Labor Day: 1ª segunda de setembro
        _n_esimo(ano, 11, 3, 4),               # Thanksgiving: 4ª quinta de novembro
    ]
    return {d for d in fixos + moveis if d is not None}


def e_pregao(calendario: str, d: date) -> bool:
    if calendario == "24x7":
        return True
    if d.weekday() >= 5:
        return False
    if calendario == "nyse":
        # o Ano-Novo de um domingo é observado na segunda, que pertence ao mesmo ano
        return d not in feriados_nyse(d.year)
    return True


def proximo_pregao(calendario: str, dia) -> pd.Timestamp:
    """Primeiro dia de negociação depois de 'dia'."""
    if calendario not in CALENDARIOS:
        raise ValueError(f"calendário desconhecido: {calendario}")
    d = pd.Timestamp(dia).date()
    for _ in range(15):
        d += timedelta(days=1)
        if e_pregao(calendario, d):
            return pd.Timestamp(d)
    raise RuntimeError("não achei pregão nos 15 dias seguintes")
