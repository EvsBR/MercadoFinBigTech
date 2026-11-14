"""Registro das fontes de cotações. Para criar uma fonte nova: um módulo nesta pasta
seguindo o contrato de base.py e uma linha em FONTES."""
from . import demo, tiingo, twelvedata, yahoo
from .base import CotaEsgotada, FonteIndisponivel

FONTES = {"yahoo": yahoo, "tiingo": tiingo, "twelvedata": twelvedata, "demo": demo}

__all__ = ["FONTES", "CotaEsgotada", "FonteIndisponivel"]
