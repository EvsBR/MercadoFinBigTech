"""Lê e confere o universo de ativos (universo/*.json): Mercado -> Segmento -> Ativo."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ID_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._^=-]{0,19}$")
SLUG_OK = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")


class ErroUniverso(ValueError):
    pass


@dataclass
class Ativo:
    id: str
    nome: str
    mercado: str
    moeda: str
    tipo: str = "acao"
    referencia: bool = False
    tickers: dict = field(default_factory=dict)
    logo: str | None = None

    def ticker(self, fonte: str) -> str:
        """Símbolo deste ativo numa fonte (por padrão, o próprio id)."""
        return self.tickers.get(fonte, self.id)


@dataclass
class Segmento:
    id: str
    nome: str
    ativos: list[str]
    destaque: str | None = None


@dataclass
class Mercado:
    id: str
    nome: str
    moeda: str
    fontes: list[str]
    referencia_principal: str | None
    ativos: dict[str, Ativo]          # todos (ações + referências), por id
    referencias: list[str]
    segmentos: list[Segmento]


def _ativo(raw: dict, mercado: dict, referencia: bool, onde: str) -> Ativo:
    if not isinstance(raw, dict) or "id" not in raw:
        raise ErroUniverso(f"{onde}: cada ativo precisa de 'id'")
    aid = str(raw["id"]).strip()
    if not ID_OK.match(aid):
        raise ErroUniverso(f"{onde}: id inválido '{aid}'")
    tickers = raw.get("tickers") or {}
    if not isinstance(tickers, dict):
        raise ErroUniverso(f"{onde}/{aid}: 'tickers' deve ser um objeto, ex.: {{\"yahoo\": \"BRK-B\"}}")
    return Ativo(id=aid, nome=str(raw.get("nome") or aid), mercado=mercado["id"],
                 moeda=str(raw.get("moeda") or mercado["moeda"]),
                 tipo=str(raw.get("tipo") or ("etf" if referencia else "acao")),
                 referencia=referencia, tickers={str(k): str(v) for k, v in tickers.items()},
                 logo=raw.get("logo"))


def carregar(pasta: Path, fontes_conhecidas: set[str] | None = None) -> list[Mercado]:
    """Carrega os mercados ativos. Qualquer erro de preenchimento interrompe com mensagem clara."""
    arq = pasta / "mercados.json"
    if not arq.exists():
        raise ErroUniverso(f"não achei {arq}")
    try:
        lista = json.loads(arq.read_text(encoding="utf-8"))["mercados"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ErroUniverso(f"{arq.name}: arquivo inválido ({exc})") from exc

    mercados, vistos = [], set()
    for m in lista:
        if not m.get("ativo", True):
            continue
        for campo in ("id", "nome", "moeda", "arquivo", "fontes"):
            if not m.get(campo):
                raise ErroUniverso(f"{arq.name}: mercado sem '{campo}'")
        mid = m["id"]
        if not SLUG_OK.match(mid) or mid in vistos:
            raise ErroUniverso(f"{arq.name}: id de mercado inválido ou repetido '{mid}'")
        vistos.add(mid)
        if fontes_conhecidas is not None:
            ruins = [f for f in m["fontes"] if f not in fontes_conhecidas]
            if ruins:
                raise ErroUniverso(f"{arq.name}/{mid}: fonte desconhecida {ruins}")
        try:
            raw = json.loads((pasta / m["arquivo"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ErroUniverso(f"{m['arquivo']}: não consegui ler ({exc})") from exc

        ativos: dict[str, Ativo] = {}
        refs = []
        for r in raw.get("referencias", []):
            a = _ativo(r, m, True, f"{m['arquivo']}/referencias")
            if a.id in ativos:
                raise ErroUniverso(f"{m['arquivo']}: referência repetida '{a.id}'")
            ativos[a.id] = a
            refs.append(a.id)
        segmentos, seg_ids = [], set()
        for s in raw.get("segmentos", []):
            sid = s.get("id", "")
            if not SLUG_OK.match(sid) or sid in seg_ids:
                raise ErroUniverso(f"{m['arquivo']}: id de segmento inválido ou repetido '{sid}'")
            seg_ids.add(sid)
            ids = []
            for r in s.get("ativos", []):
                a = _ativo(r, m, False, f"{m['arquivo']}/{sid}")
                if a.id in ids:
                    raise ErroUniverso(f"{m['arquivo']}/{sid}: ativo repetido '{a.id}'")
                if a.id in refs:
                    raise ErroUniverso(f"{m['arquivo']}/{sid}: '{a.id}' já é referência do mercado")
                ativos.setdefault(a.id, a)   # o mesmo ativo pode aparecer em mais de um segmento
                ids.append(a.id)
            if not ids:
                raise ErroUniverso(f"{m['arquivo']}/{sid}: segmento sem ativos")
            destaque = s.get("destaque")
            segmentos.append(Segmento(id=sid, nome=str(s.get("nome") or sid), ativos=ids,
                                      destaque=destaque if destaque in ids else None))
        if not segmentos:
            raise ErroUniverso(f"{m['arquivo']}: nenhum segmento")
        principal = m.get("referencia_principal")
        if principal and principal not in refs:
            raise ErroUniverso(f"{arq.name}/{mid}: referencia_principal '{principal}' não está em referencias")
        mercados.append(Mercado(id=mid, nome=m["nome"], moeda=m["moeda"], fontes=list(m["fontes"]),
                                referencia_principal=principal or (refs[0] if refs else None),
                                ativos=ativos, referencias=refs, segmentos=segmentos))
    if not mercados:
        raise ErroUniverso("nenhum mercado ativo em mercados.json")
    return mercados
