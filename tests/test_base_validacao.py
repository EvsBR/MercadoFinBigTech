import pandas as pd

from pipeline import base, validacao


def test_gravar_e_ler_devolve_a_mesma_tabela(tmp_path, fazer_tabela):
    df = fazer_tabela([10 + i * 0.1 for i in range(50)])
    base.gravar(tmp_path, "eua", "BRK.B", df)
    lido = base.ler(tmp_path, "eua", "BRK.B")
    pd.testing.assert_frame_equal(df, lido, check_freq=False, rtol=1e-7)
    assert base.ler(tmp_path, "eua", "NAOEXISTE") is None


def test_emendar_acrescenta_so_os_pregoes_novos(fazer_tabela):
    completo = fazer_tabela([100 + i for i in range(60)])
    guardado, reserva = completo.iloc[:50], completo.iloc[30:]
    junto, aviso = base.emendar(guardado, reserva)
    assert aviso == "" and len(junto) == 60
    pd.testing.assert_series_equal(junto["close"], completo["close"])


def test_emendar_reescala_a_base_quando_houve_desdobramento(fazer_tabela):
    completo = fazer_tabela([100 + i for i in range(60)], volume=1000.0)
    guardado = completo.iloc[:50].copy()
    reserva = completo.iloc[30:].copy()
    for c in ("open", "high", "low", "close", "adj_close"):   # a reserva já vem dividida por 4
        reserva[c] = reserva[c] / 4
    junto, aviso = base.emendar(guardado, reserva)
    assert "desdobramento" in aviso
    assert junto["close"].iloc[0] == completo["close"].iloc[0] / 4
    assert junto["volume"].iloc[0] == 4000
    assert abs(junto["adj_close"].pct_change().dropna()).max() < 0.02   # sem degrau na emenda


def test_emendar_recusa_reserva_que_nao_bate(fazer_tabela):
    completo = fazer_tabela([100 + i for i in range(60)])
    reserva = completo.iloc[30:].copy()
    reserva.loc[reserva.index[5], "close"] *= 1.2
    assert base.emendar(completo.iloc[:50], reserva)[0] is None
    assert base.emendar(completo.iloc[:20], completo.iloc[40:])[0] is None   # sem datas em comum


def test_validacao_aceita_tabela_boa(fazer_tabela):
    erros, avisos = validacao.conferir(fazer_tabela([100 + i * 0.2 for i in range(300)]))
    assert erros == [] and avisos == []


def test_validacao_barra_fonte_parada(fazer_tabela):
    velha = fazer_tabela([100.0] * 100, fim=pd.Timestamp.today() - pd.Timedelta(days=40))
    assert any("dias" in e for e in validacao.conferir(velha)[0])


def test_validacao_barra_desdobramento_nao_ajustado(fazer_tabela):
    precos = [200.0] * 95 + [50.0] * 5          # caiu para 1/4 de um dia para o outro
    erros, _ = validacao.conferir(fazer_tabela(precos))
    assert any("desdobramento" in e for e in erros)
    # queda grande que não é número redondo: só aviso
    erros, avisos = validacao.conferir(fazer_tabela([200.0] * 95 + [70.0] * 5))
    assert erros == [] and avisos


def test_validacao_barra_historico_mais_curto_que_a_base(fazer_tabela):
    guardado = fazer_tabela([100 + i * 0.1 for i in range(400)])
    erros, _ = validacao.conferir(guardado.iloc[200:], guardado)
    assert any("mais curto" in e for e in erros)


def test_validacao_avisa_fonte_divergente(fazer_tabela):
    guardado = fazer_tabela([100 + (i % 7) for i in range(300)])
    outro = fazer_tabela([100 + (i % 5) * 2 for i in range(300)])
    assert any("divergente" in a for a in validacao.conferir(outro, guardado)[1])
