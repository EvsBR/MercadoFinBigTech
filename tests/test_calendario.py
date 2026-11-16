"""Calendário de pregões: feriados da NYSE conferidos com a lista oficial da bolsa."""
from datetime import date

import pandas as pd
import pytest

from pipeline import calendario


def test_feriados_nyse_2026_e_2027():
    assert calendario.feriados_nyse(2026) == {
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
        date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25)}
    assert calendario.feriados_nyse(2027) == {
        date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
        date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24)}


def test_ano_novo_no_sabado_nao_fecha_a_sexta():
    assert date(2027, 12, 31) not in calendario.feriados_nyse(2027)      # 01/01/2028 é sábado
    assert calendario.proximo_pregao("nyse", "2027-12-30") == pd.Timestamp("2027-12-31")


@pytest.mark.parametrize("cal, dia, esperado", [
    ("nyse", "2026-11-13", "2026-11-16"),        # sexta -> segunda
    ("nyse", "2026-04-02", "2026-04-06"),        # quinta antes da Sexta-feira Santa -> segunda
    ("nyse", "2026-11-25", "2026-11-27"),        # véspera do Thanksgiving -> sexta
    ("nyse", "2026-07-02", "2026-07-06"),        # 4 de julho no sábado: fecha a sexta
    ("dias_uteis", "2026-04-02", "2026-04-03"),
    ("24x7", "2026-11-13", "2026-11-14"),
])
def test_proximo_pregao(cal, dia, esperado):
    assert calendario.proximo_pregao(cal, dia) == pd.Timestamp(esperado)


def test_calendario_desconhecido_da_erro():
    with pytest.raises(ValueError):
        calendario.proximo_pregao("lua", "2026-01-01")
