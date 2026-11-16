"""Orquestra a atualização: baixa cotações, confere, guarda na base, calcula os indicadores e
escreve os arquivos que o site lê (site/data/).

Uso (pela raiz do projeto):
  python -m pipeline.construir             # dados reais
  python -m pipeline.construir --offline   # só a base em data/base (sem internet)
  python -m pipeline.construir --demo      # dados SINTÉTICOS, para testar o visual
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pandas as pd

from . import base, indicadores, validacao
from .fontes import FONTES, CotaEsgotada, FonteIndisponivel
from .indicadores import correlacao, sazonalidade
from .universo import ErroUniverso, Mercado, carregar
from .util import dstr, log, safe_name

RAIZ = Path(__file__).resolve().parents[1]
REUSO_HORAS = 4            # não baixa de novo o que foi baixado há menos que isso
MIN_PREGOES_INDICADORES = 60
CHAVES_ENV = ("TIINGO_API_KEY", "TWELVEDATA_API_KEY")
# ensaio de falha: PAINEL_PULAR_FONTES=yahoo finge que o Yahoo está fora do ar
PULAR = {f.strip() for f in os.environ.get("PAINEL_PULAR_FONTES", "").split(",") if f.strip()}


def obter(ativo, mercado: Mercado, raiz_base: Path, estado: dict, env: dict,
          offline: bool, esgotadas: set[str]) -> tuple[pd.DataFrame | None, dict]:
    """Devolve as cotações de um ativo e um registro do que aconteceu."""
    guardado = base.ler(raiz_base, mercado.id, ativo.id)
    info = {"fonte": None, "falhou": False, "avisos": [], "tentativas": []}
    anterior = estado.get(ativo.id) or {}

    if not offline and guardado is not None and anterior.get("baixado_em"):
        idade_h = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(anterior["baixado_em"])).total_seconds() / 3600
        if 0 <= idade_h < REUSO_HORAS and not anterior.get("falhou"):
            info.update(fonte=anterior.get("fonte"), reaproveitado=True)
            return guardado, info

    if not offline:
        for fid in mercado.fontes:
            mod = FONTES[fid]
            if fid in esgotadas or fid in PULAR or not mod.disponivel(env):
                continue
            try:
                novo = mod.baixar(ativo.ticker(fid), env)
            except CotaEsgotada as exc:
                esgotadas.add(fid)
                info["tentativas"].append(f"{mod.NOME}: {exc}")
                continue
            except FonteIndisponivel as exc:
                info["tentativas"].append(f"{mod.NOME}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 - qualquer falha passa para a próxima fonte
                info["tentativas"].append(f"{mod.NOME}: {str(exc)[:200]}")
                time.sleep(2)
                continue
            finally:
                time.sleep(mod.PAUSA)

            aviso_emenda = ""
            if not mod.COMPLETA:
                if guardado is None:
                    info["tentativas"].append(f"{mod.NOME}: só completa uma base que já existe")
                    continue
                novo, aviso_emenda = base.emendar(guardado, novo)
                if novo is None:
                    info["tentativas"].append(f"{mod.NOME}: {aviso_emenda}")
                    continue
            erros, avisos = validacao.conferir(novo, guardado if mod.COMPLETA else None)
            if erros:
                info["tentativas"].append(f"{mod.NOME}: descartado ({'; '.join(erros)})")
                continue
            base.gravar(raiz_base, mercado.id, ativo.id, novo)
            info.update(fonte=mod.NOME, avisos=avisos + ([aviso_emenda] if aviso_emenda else []))
            estado[ativo.id] = {"fonte": mod.NOME, "baixado_em": base.agora(), "falhou": False,
                                "ultimo_pregao": dstr(novo.index[-1])}
            return novo, info

    if guardado is not None:
        info.update(fonte="base salva" if offline else f"base salva ({anterior.get('fonte') or 'origem não registrada'})",
                    falhou=not offline)
        if not offline:
            estado[ativo.id] = {**anterior, "falhou": True}
        return guardado, info
    info["falhou"] = True
    return None, info


def escrever(arq: Path, obj):
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def processar_mercado(m: Mercado, cfg: dict, args, env: dict, raiz_base: Path, saida: Path) -> dict:
    inicio = None if str(cfg.get("start", "max")).lower() == "max" else pd.Timestamp(cfg["start"])
    limiares = cfg.get("cycle_thresholds", [0.15, 0.20, 0.30])
    estado = {} if args.demo else base.ler_estado(raiz_base, m.id)
    esgotadas: set[str] = set()
    tabelas: dict[str, pd.DataFrame] = {}
    saude: dict[str, dict] = {}

    log(f"\n== {m.nome} ({len(m.ativos)} ativos) ==")
    for aid, ativo in m.ativos.items():
        if args.demo:
            df, info = FONTES["demo"].baixar(aid, env), {"fonte": "sintético", "falhou": False, "avisos": [], "tentativas": []}
        else:
            df, info = obter(ativo, m, raiz_base, estado, env, args.offline, esgotadas)
        for t in info["tentativas"]:
            log(f"  {aid}: {t}")
        if df is None:
            log(f"  {aid}: SEM DADOS em nenhuma fonte nem na base")
            saude[aid] = {**info, "sem_dados": True}
            continue
        tabelas[aid] = df
        saude[aid] = {**info, "pregoes": len(df), "primeiro": dstr(df.index[0]), "ultimo": dstr(df.index[-1])}
        log(f"  {aid}: {len(df)} pregões, {dstr(df.index[0])} → {dstr(df.index[-1])} ({info['fonte']})"
            + (" [fonte falhou]" if info["falhou"] else "") + ("".join(f" | aviso: {a}" for a in info["avisos"])))
    if not args.demo and not args.offline:
        base.gravar_estado(raiz_base, m.id, estado)

    # um ativo está atrasado se termina antes do pregão mais recente do mercado
    ultimo_mercado = max((df.index[-1] for df in tabelas.values()), default=None)
    for aid, df in tabelas.items():
        saude[aid]["atrasado"] = bool(df.index[-1] < ultimo_mercado)

    cortadas = {k: (df if inicio is None else df[df.index >= inicio]) for k, df in tabelas.items()}
    cortadas = {k: df for k, df in cortadas.items() if len(df) >= MIN_PREGOES_INDICADORES}
    for aid in tabelas.keys() - cortadas.keys():
        saude[aid]["curto"] = True
        log(f"  {aid}: histórico curto demais para os indicadores")
    wret, datas_semana = correlacao.painel_semanal({k: df["adj_close"] for k, df in cortadas.items()})
    refs = [r for r in m.referencias if r in cortadas]
    principal = m.referencia_principal if m.referencia_principal in refs else (refs[0] if refs else None)

    linhas: dict[str, dict] = {}
    for aid, df in cortadas.items():
        ativo = m.ativos[aid]
        ctx = indicadores.Contexto(ativo=ativo, df=df, df_cheio=tabelas[aid], inicio=inicio, limiares=limiares,
                                   ret_semanal=wret, datas_semana=datas_semana, referencias=refs,
                                   referencia_principal=principal, calendario=m.calendario)
        blocos, resumo, extras = indicadores.calcular_ativo(ctx)
        s = saude[aid]
        comum = {"symbol": aid, "name": ativo.nome, "currency": ativo.moeda, "is_benchmark": ativo.referencia,
                 "tipo": ativo.tipo, "logo": ativo.logo or f"ticker/{aid}",
                 "source": s["fonte"], "stale": bool(s["falhou"] or s["atrasado"])}
        arquivo = f"{m.id}/ativos/{safe_name(aid)}.json"
        escrever(saida / arquivo, {**comum, "stats": resumo, **blocos})
        for nome, obj in extras.items():
            escrever(saida / f"{m.id}/ativos/{safe_name(aid)}.{nome}.json", obj)
        linhas[aid] = {**comum, "file": arquivo, **resumo}

    segmentos = []
    for seg in m.segmentos:
        acoes = [a for a in seg.ativos if a in linhas]
        if not acoes:
            log(f"  segmento {seg.id}: nenhum ativo com dados, fica fora do site")
            continue
        escrever(saida / m.id / seg.id / "meta.json", {
            "market": m.id, "segment": seg.id, "name": seg.nome, "main_benchmark": principal,
            "featured": seg.destaque if seg.destaque in acoes else acoes[0],
            "tickers": [linhas[a] for a in acoes], "benchmarks": [linhas[r] for r in refs]})
        escrever(saida / m.id / seg.id / "correlations.json",
                 correlacao.do_segmento(wret, datas_semana, acoes, refs))
        segmentos.append({"id": seg.id, "nome": seg.nome, "n": len(acoes)})

    return {"id": m.id, "nome": m.nome, "moeda": m.moeda, "segmentos": segmentos,
            "ultimo_pregao": dstr(ultimo_mercado), "saude": saude,
            "total": len(m.ativos), "com_dados": len(linhas)}


def relatorio(mercados: list[dict]) -> str:
    """Resumo em Markdown para a página da execução no GitHub Actions."""
    out = ["## Saúde dos dados", ""]
    for m in mercados:
        out += [f"### {m['nome']}: {m['com_dados']} de {m['total']} ativos · último pregão {m['ultimo_pregao']}", "",
                "| Ativo | Fonte | Pregões | De | Até | Situação |", "|---|---|---|---|---|---|"]
        for aid, s in m["saude"].items():
            if s.get("sem_dados"):
                sit = "SEM DADOS"
            else:
                marcas = [t for t, on in (("fonte falhou, usando a base", s["falhou"]), ("atrasado", s.get("atrasado")),
                                          ("histórico curto", s.get("curto"))) if on] + s["avisos"]
                sit = "; ".join(marcas) or "ok"
            out.append(f"| {aid} | {s.get('fonte') or '—'} | {s.get('pregoes', '—')} | {s.get('primeiro', '—')} "
                       f"| {s.get('ultimo', '—')} | {sit} |")
        out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gera os dados do painel")
    ap.add_argument("--demo", action="store_true", help="usa dados sintéticos (teste visual)")
    ap.add_argument("--offline", action="store_true", help="não acessa a internet; usa a base salva")
    ap.add_argument("--saida", default=str(RAIZ / "site" / "data"))
    ap.add_argument("--base", default=str(RAIZ / "data" / "base"))
    ap.add_argument("--universo", default=str(RAIZ / "universo"))
    args = ap.parse_args(argv)

    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    try:
        mercados = carregar(Path(args.universo), set(FONTES) - {"demo"})
    except ErroUniverso as exc:
        log(f"ERRO no universo de ativos: {exc}")
        return 2
    env = {k: os.environ[k] for k in CHAVES_ENV if os.environ.get(k)}
    log("Chaves de reserva configuradas: " + (", ".join(sorted(env)) or "nenhuma"))
    if args.demo:
        log("MODO DEMO: séries sintéticas (não são cotações reais).")

    saida = Path(args.saida)
    tmp = saida.with_name(saida.name + ".novo")
    shutil.rmtree(tmp, ignore_errors=True)
    resultado = [processar_mercado(m, cfg, args, env, Path(args.base), tmp) for m in mercados]

    texto = relatorio(resultado)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(texto + "\n")

    total = sum(m["total"] for m in resultado)
    com_dados = sum(m["com_dados"] for m in resultado)
    falhas = [f"{m['id']}:{a}" for m in resultado for a, s in m["saude"].items()
              if s.get("sem_dados") or s.get("falhou")]
    if falhas and not args.demo:
        print(f"::warning::Fonte falhou para {len(falhas)} ativo(s): {', '.join(falhas[:20])}", flush=True)
    if com_dados == 0 or com_dados < total / 2 or not any(m["segmentos"] for m in resultado):
        log(f"\nERRO: só {com_dados} de {total} ativos têm dados. O site NÃO foi alterado.")
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    escrever(tmp / "indice.json", {
        "title": cfg.get("title", "Painel"), "generated_at": base.agora(), "demo": bool(args.demo),
        "start": cfg.get("start", "max"),
        "cycle_thresholds": [str(int(round(t * 100))) for t in cfg.get("cycle_thresholds", [0.15, 0.20, 0.30])],
        "freq_labels": {f: v["labels"] for f, v in sazonalidade.FREQS.items()},
        "logo_token": cfg.get("logo_dev_token") or "",
        "indicadores": indicadores.manifesto(),
        "mercados": [{k: m[k] for k in ("id", "nome", "moeda", "segmentos", "ultimo_pregao", "total", "com_dados")}
                     for m in resultado if m["segmentos"]]})
    escrever(tmp / "saude.json", {"generated_at": base.agora(),
                                  "mercados": [{"id": m["id"], "ativos": m["saude"]} for m in resultado]})
    shutil.rmtree(saida, ignore_errors=True)
    tmp.replace(saida)
    log(f"\nPronto: {com_dados} de {total} ativos em {os.path.relpath(saida, RAIZ)}"
        + (f" | com falha de fonte: {', '.join(falhas)}" if falhas and not args.demo else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
