/* Aba "Análise Técnica": Drawdown, Médias Móveis, RSI 14 e OBV, cada um com gráfico,
   tabela "Agora × histórico" e tabela "Preços-alvo".
   Os números das tabelas vêm prontos do pipeline (data/<mercado>/ativos/<ATIVO>.tecnica.<D|S|M>.json).
   As curvas são calculadas aqui por indicadores.js a partir das mesmas barras, e o último ponto
   de cada curva é conferido contra o valor "agora" do pipeline antes de desenhar.
   Usa os utilitários globais de app.js (state, $, T, chart, base, xTime, yVal, formatadores). */
"use strict";

const TEC_BARRAS = { D: "diárias", S: "semanais", M: "mensais" };
const TEC_UNIDADE = { D: "pregão", S: "semana", M: "mês" };
const TEC_SIGLA = { sma: "MMS", ema: "MME", wma: "MMP" };
const TEC_CHARTS = ["chTecDd", "chTecMm", "chTecRsi", "chTecObv"];

const fbig = (v) => {
  if (v == null || !isFinite(v)) return "—";
  const a = Math.abs(v);
  const [div, suf] = a >= 1e12 ? [1e12, " tri"] : a >= 1e9 ? [1e9, " bi"] : a >= 1e6 ? [1e6, " mi"] : a >= 1e3 ? [1e3, " mil"] : [1, ""];
  return (v < 0 ? "−" : "") + nf(div > 1 ? 1 : 0).format(a / div) + suf;
};
const fquando = (d) => (/^\d{4}-\d{2}-\d{2}$/.test(d || "") ? fdate(d) : d || "—");
const quando = (d) => `<span class="quando">${fquando(d)}</span>`;
const posicao = (p) => (p == null ? "—" : `acima de ${pct(p, 0)}`);
const fpx = (v) => (v < 1 ? nf(2).format(v) : v < 20 ? nf(1).format(v) : nf(0).format(v));

async function loadTec(sym, tf) {
  const f = rowOf(sym).file.replace(/\.json$/, `.tecnica.${tf}.json`);
  if (!state.cache[f]) state.cache[f] = await getJSON("data/" + f);
  return state.cache[f];
}

/* curvas calculadas uma vez por arquivo (as médias, uma vez por tipo) */
function tecCurvas(a) {
  if (!a._s) {
    const o = Ind.obv(a.c, a.v);
    a._s = { dd: Ind.dd(a.c), rsi: Ind.rsi(a.c, a.parametros.rsi), obv: o, fluxo: Ind.obvFluxo(o, a.v, a.parametros.obv), volat: Ind.obvVolatilidade(o, a.v, a.parametros.obv), mm: {} };
  }
  const tipo = state.mmTipo;
  if (!a._s.mm[tipo]) {
    a._s.mm[tipo] = {};
    a.parametros.mm.forEach((n) => { const m = Ind.medias[tipo](a.c, n); a._s.mm[tipo][n] = { m, dist: Ind.distancia(a.c, m) }; });
  }
  return a._s;
}

/* o último ponto de cada curva tem de ser o "agora" que o pipeline publicou */
function tecConferir(a, S) {
  const ruins = [];
  const ok = (nome, visto, esperado) => {
    if (visto == null && esperado == null) return;
    if (visto == null || esperado == null || Math.abs(visto - esperado) > 1e-5 * Math.max(1, Math.abs(esperado))) ruins.push(nome);
  };
  const fim = (arr) => arr[arr.length - 1];
  const ag = (m) => (m ? m.agora : null);
  if (a.drawdown) ok("drawdown", fim(S.dd), ag(a.drawdown.medida));
  ok("RSI", fim(S.rsi), ag(a.rsi.medida));
  if (!a.obv.sem_volume) { ok("OBV", fim(S.obv), ag(a.obv.nivel)); ok("saldo de volume", fim(S.fluxo), ag(a.obv.fluxo)); ok("volatilidade do OBV", fim(S.volat), ag(a.obv.volatilidade)); }
  const tipo = state.mmTipo;
  a.parametros.mm.forEach((n) => ok(`${TEC_SIGLA[tipo]} ${n}`, fim(S.mm[tipo][n].dist), ag(a.mm[tipo][n].medida)));
  return ruins;
}

function tecJanela(a) {
  const r = state.range[state.tf];
  if (r === "max") return { start: 0, end: 100 };
  const fim = a.d[a.d.length - 1];
  const ini = `${+fim.slice(0, 4) - +r}${fim.slice(4)}`;
  return { startValue: echarts.number.parseDate(ini).getTime(), endValue: echarts.number.parseDate(fim).getTime() };
}

/* linhas horizontais de referência (mínima, média, máxima) com o rótulo na ponta direita */
function tecFaixas(th, itens, fmt) {
  return {
    silent: true, symbol: "none", animation: false,
    lineStyle: { color: th.muted, width: 1, type: "dashed" },
    label: { color: th.text2, fontSize: 11, position: "end", formatter: (p) => `${p.name} ${fmt(p.value)}` },
    data: itens.filter((x) => x.v != null).map((x) => ({ yAxis: x.v, name: x.n, lineStyle: x.cor ? { color: x.cor, type: x.tipo || "dashed" } : undefined })),
  };
}

/* gráfico de dois andares: preço em cima (log), indicador embaixo; zoom compartilhado */
function tecOpcao(a, th, cfg) {
  const pares = (arr) => a.d.map((x, i) => [x, arr[i]]);
  const dz = tecJanela(a);
  const topo = cfg.legenda ? 34 : 12;
  const estreito = window.innerWidth < 600, esq = estreito ? 46 : 64, dir = estreito ? 86 : 104;
  return {
    ...base(th),
    tooltip: { ...base(th).tooltip, formatter: (ps) => { const i = ps[0].dataIndex; return `<strong>${fdate(a.d[i])}</strong><br>${swatch(th.text2)}Preço: <strong>${money(a.c[i], a.currency)}</strong>${cfg.dica(i)}`; } },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    legend: cfg.legenda ? { top: 0, left: 0, itemWidth: 14, itemHeight: 3, textStyle: { color: th.text2 }, data: cfg.legenda } : undefined,
    grid: [{ left: esq, right: dir, top: topo, height: "42%" }, { left: esq, right: dir, top: "57%", bottom: 62 }],
    xAxis: [xTime(th, { gridIndex: 0, axisLabel: { show: false } }), xTime(th, { gridIndex: 1 })],
    yAxis: [
      // histórico inteiro: escala logarítmica; janelas de 1, 3 e 10 anos: escala linear ajustada à janela
      state.range[state.tf] === "max"
        ? yVal(th, { type: "log", logBase: 10, gridIndex: 0, axisLabel: { color: th.muted, formatter: fpx } })
        : yVal(th, { scale: true, gridIndex: 0, axisLabel: { color: th.muted, formatter: fpx } }),
      yVal(th, { gridIndex: 1, ...cfg.eixo }),
    ],
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1], ...dz },
      { type: "slider", xAxisIndex: [0, 1], bottom: 12, height: 20, borderColor: th.grid, textStyle: { color: th.muted }, fillerColor: rgba(th.s[0], 0.12),
        dataBackground: { lineStyle: { color: th.axis }, areaStyle: { color: rgba(th.axis, 0.3) } }, ...dz }],
    series: [
      { name: "Preço", type: "line", data: pares(a.c), showSymbol: false, lineStyle: { width: 1.5, color: th.text2 }, itemStyle: { color: th.text2 } },
      ...(cfg.sobrePreco || []).map((s) => ({ type: "line", showSymbol: false, connectNulls: false, ...s, data: pares(s.data) })),
      ...cfg.indicador.map((s) => ({ type: "line", xAxisIndex: 1, yAxisIndex: 1, showSymbol: false, connectNulls: false, ...s, data: pares(s.data) })),
    ],
  };
}

/* ------------------------------------------------------------- tabelas */
const TEC_HEAD = (primeira, extra = "") => `<thead><tr><th class="l">${primeira}</th>${extra}<th>Agora</th><th>Mínima</th><th>Média</th><th>Máxima</th><th>Posição<span class="quando">no histórico</span></th></tr></thead>`;
function tecHistCelulas(m, fmt, o = {}) {
  return `<td><strong>${o.agora || fmt(m.agora)}</strong>${o.agoraSub ? quando(o.agoraSub) : ""}</td><td>${fmt(m.min.v)}${quando(m.min.d)}</td><td>${o.semMedia ? "—" : fmt(m.media)}</td><td>${o.max || `${fmt(m.max.v)}${quando(m.max.d)}`}</td><td>${posicao(m.pctl)}</td>`;
}
function tecAlvos(alvos, agora, fmtNivel, cur, rotuloNivel) {
  const linhas = [...alvos, { id: "agora", nome: "Agora", nivel: agora.nivel, preco: agora.preco, var: null }]
    .sort((x, y) => (y.nivel - x.nivel) || (x.id === "agora" ? 1 : -1));
  return `<thead><tr><th class="l">Nível</th><th>${rotuloNivel}</th><th>Preço</th><th>Do preço atual</th></tr></thead><tbody>` + linhas.map((x) => {
    if (x.id === "agora") return `<tr class="agora"><td class="l">Agora</td><td>${fmtNivel(x.nivel)}</td><td>${money(x.preco, cur)}</td><td>—</td></tr>`;
    if (x.preco == null) return `<tr><td class="l">${esc(x.nome)}</td><td>${fmtNivel(x.nivel)}</td><td colspan="2" class="fora">${x.erro ? "em revisão" : "fora de alcance em 1 pregão"}</td></tr>`;
    return `<tr><td class="l">${esc(x.nome)}</td><td>${fmtNivel(x.nivel)}</td><td><strong>${money(x.preco, cur)}</strong></td><td class="${x.var < 0 ? "neg" : ""}">${spct(x.var)}</td></tr>`;
  }).join("") + "</tbody>";
}

/* ------------------------------------------------------------- render */
async function renderTecnica() {
  const sym = state.sym, tf = state.tf;
  $$("#tfSeg button").forEach((b) => { b.setAttribute("aria-pressed", String(b.dataset.v === tf)); b.onclick = () => { state.tf = b.dataset.v; writeHash(); renderTecnica(); }; });
  $$("#rangeSeg button").forEach((b) => { b.setAttribute("aria-pressed", String(b.dataset.v === state.range[tf])); b.onclick = () => { state.range[state.tf] = b.dataset.v; renderTecnica(); }; });
  $$("#mmTipoSeg button").forEach((b) => { b.setAttribute("aria-pressed", String(b.dataset.v === state.mmTipo)); b.onclick = () => { state.mmTipo = b.dataset.v; renderTecnica(); }; });

  const a = await loadTec(sym, tf);
  if (sym !== state.sym || tf !== state.tf || state.tab !== "tecnica") return;   // o usuário já trocou de tela
  if (!a.drawdown) throw new Error("histórico curto demais para a análise técnica");
  const th = T(), cur = a.currency, P = a.parametros, tipo = state.mmTipo, sigla = TEC_SIGLA[tipo];
  if (!P.mm.includes(state.mmN)) state.mmN = P.mm.includes(200) ? 200 : P.mm[0];
  const S = tecCurvas(a);
  const ruins = tecConferir(a, S);
  if (ruins.length) console.error("Análise técnica: curva e tabela não batem em", ruins);

  const nSeg = $("#mmNSeg");
  nSeg.innerHTML = P.mm.map((n) => `<button data-v="${n}" aria-pressed="${n === state.mmN}">${n}</button>`).join("");
  $$("button", nSeg).forEach((b) => (b.onclick = () => { state.mmN = +b.dataset.v; renderTecnica(); }));

  const r = rowOf(sym);
  const barra = TEC_UNIDADE[tf];
  const prox = `próximo pregão, ${fdate(a.proximo.d)}` + (tf === "D" ? "" : a.proximo.mesma_barra ? `, ainda dentro ${tf === "S" ? "da semana" : "do mês"} em andamento` : `, que abre ${tf === "S" ? "uma semana nova" : "um mês novo"}`);
  $("#tecContexto").innerHTML =
    (ruins.length ? `<span class="err"><strong>Inconsistência detectada</strong> entre curvas e tabelas (${esc(ruins.join(", "))}). Os números desta tela estão em revisão.</span><br>` : "") +
    `${logo(r)}<strong>${esc(a.symbol)}</strong> · ${esc(a.name)} · fechamento <strong>${money(a.ultimo.preco, cur)}</strong> em ${fdate(a.ultimo.d)} · ${nf(0).format(a.d.length)} barras ${TEC_BARRAS[tf]} desde ${fdate(a.d[0])} · preços-alvo para o ${prox}`;
  const cap = `Fechamento necessário no próximo pregão, ${fdate(a.proximo.d)}.`;

  /* ---------- resumo no topo ---------- */
  const D = a.drawdown, M = a.mm[tipo][state.mmN], R = a.rsi, O = a.obv;
  const zona = (v) => (v >= 70 ? "sobrecompra" : v <= 30 ? "sobrevenda" : "zona neutra");
  const cartao = (alvo, k, v, s) => `<button type="button" class="tile tile-btn" data-alvo="${alvo}"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></button>`;
  $("#tecTiles").innerHTML =
    cartao("blk-dd", "Drawdown", D.medida.agora > -0.0005 ? "no recorde" : pct(D.medida.agora), `${posicao(D.medida.pctl)} do histórico`) +
    cartao("blk-mm", `Preço vs ${sigla} ${state.mmN}`, M.medida ? spct(M.medida.agora) : "—", M.medida ? `${posicao(M.medida.pctl)} do histórico` : `faltam ${M.faltam} barras`) +
    cartao("blk-rsi", `RSI ${P.rsi}`, R.medida ? fnum(R.medida.agora, 1) : "—", R.medida ? `${zona(R.medida.agora)} · ${posicao(R.medida.pctl)} do histórico` : `faltam ${R.faltam} barras`) +
    cartao("blk-obv", `Saldo de volume · ${P.obv} barras`, O.fluxo ? spct(O.fluxo.agora) : "—", O.fluxo ? `${posicao(O.fluxo.pctl)} do histórico` : "sem dados de volume");
  $$("#tecTiles .tile-btn").forEach((b) => (b.onclick = () => document.getElementById(b.dataset.alvo).scrollIntoView({ behavior: "smooth", block: "start" })));

  /* ---------- 1. Drawdown ---------- */
  const dm = D.medida, da = D.medida_ano;
  chart("chTecDd").setOption(tecOpcao(a, th, {
    dica: (i) => `<br>${swatch(th.red)}Drawdown: <strong>${pct(S.dd[i])}</strong>`,
    eixo: { min: Math.floor(dm.min.v * 20) / 20, max: 0, axisLabel: { color: th.muted, formatter: (v) => pct(v, 0) } },
    indicador: [{ name: "Drawdown", data: S.dd, lineStyle: { width: 1.5, color: th.red }, itemStyle: { color: th.red }, areaStyle: { color: rgba(th.red, 0.18) },
      markLine: tecFaixas(th, [{ n: "média", v: dm.media }, { n: "média/ano", v: da ? da.media : null }, { n: "mínima", v: dm.min.v }], (v) => pct(v, 0)) }],
  }), true);
  $("#tDdHist").innerHTML = TEC_HEAD("Medida") + "<tbody>" +
    `<tr><td class="l">Drawdown</td>${tecHistCelulas(dm, pct, { agora: dm.agora > -0.0005 ? "0%" : null, agoraSub: dm.agora > -0.0005 ? "no recorde" : null, max: `0%${quando("recorde")}` })}</tr>` +
    (da ? `<tr><td class="l">Pior drawdown do ano</td>${tecHistCelulas(da, pct, { agoraSub: String(da.ano) })}</tr>` : "") + "</tbody>";
  $("#capDd").textContent = `${cap} Queda medida a partir de ${money(D.pico_alvo.v, cur)}, o maior fechamento (${fdate(D.pico_alvo.d)}).`;
  $("#tDdAlvos").innerHTML = tecAlvos(D.alvos, { nivel: dm.agora, preco: a.ultimo.preco }, pct, cur, "Drawdown");
  $("#tDdEps").innerHTML = D.episodios.length
    ? "<thead><tr><th class='l'>#</th><th>Queda</th><th>Pico</th><th>Fundo</th><th>Tempo de queda</th><th>Recuperação</th><th>Tempo para recuperar</th><th>Duração total</th></tr></thead><tbody>" +
      (state.ddTodos ? D.episodios : D.episodios.slice(0, 10)).map((e, i) => `<tr><td class="l">${i + 1}</td><td class="neg"><strong>${pct(e.depth)}</strong></td><td>${fdate(e.peak)}</td><td>${fdate(e.trough)}</td><td>${fdays(e.days_down)}</td><td>${e.recovery ? fdate(e.recovery) : "<em>em andamento</em>"}</td><td>${e.recovery ? fdays(e.days_recover) : "—"}</td><td>${fdays(e.days_total)}</td></tr>`).join("") + "</tbody>" +
      (D.episodios.length > 10 ? `<tfoot><tr><td class="l" colspan="8"><button class="ghost" id="ddMais" type="button">${state.ddTodos ? "Mostrar só as 10 maiores" : `Mostrar as ${D.episodios.length} maiores`}</button></td></tr></tfoot>` : "")
    : `<tbody><tr><td class="l fora">Nenhuma queda de 10% ou mais em barras ${TEC_BARRAS[tf]}.</td></tr></tbody>`;

  const mais = $("#ddMais");
  if (mais) mais.onclick = () => { state.ddTodos = !state.ddTodos; renderTecnica(); };

  /* ---------- 2. Médias móveis ---------- */
  const mm = a.mm[tipo], cores = th.s;
  const comDados = P.mm.filter((n) => mm[n].medida);
  const sel = mm[state.mmN], iSel = P.mm.indexOf(state.mmN), corSel = cores[iSel % cores.length];
  chart("chTecMm").setOption(tecOpcao(a, th, {
    legenda: ["Preço", ...comDados.map((n) => `${sigla} ${n}`)],
    dica: (i) => comDados.map((n) => { const v = S.mm[tipo][n].m[i]; return v == null ? "" : `<br>${swatch(cores[P.mm.indexOf(n) % cores.length])}${sigla} ${n}: <strong>${money(v, cur)}</strong>`; }).join("") +
      (sel.medida && S.mm[tipo][state.mmN].dist[i] != null ? `<br>Distância à ${sigla} ${state.mmN}: <strong>${spct(S.mm[tipo][state.mmN].dist[i])}</strong>` : ""),
    sobrePreco: comDados.map((n) => { const c = cores[P.mm.indexOf(n) % cores.length]; return { name: `${sigla} ${n}`, data: S.mm[tipo][n].m, lineStyle: { width: n === state.mmN ? 2 : 1.5, color: c }, itemStyle: { color: c } }; }),
    eixo: sel.medida ? { min: Math.floor(sel.medida.min.v * 10 - 0.5) / 10, max: Math.ceil(sel.medida.max.v * 10 + 0.5) / 10, axisLabel: { color: th.muted, formatter: (v) => spct(v, 0) } } : { axisLabel: { color: th.muted } },
    indicador: sel.medida ? [{ name: `Distância à ${sigla} ${state.mmN}`, data: S.mm[tipo][state.mmN].dist, lineStyle: { width: 1.5, color: corSel }, itemStyle: { color: corSel },
      markLine: tecFaixas(th, [{ n: "máxima", v: sel.medida.max.v }, { n: "média", v: sel.medida.media }, { n: "", v: 0, cor: th.axis, tipo: "solid" }, { n: "mínima", v: sel.medida.min.v }], (v) => (v === 0 ? "" : spct(v, 0))) }] : [],
  }), true);
  $("#tMmHist").innerHTML = TEC_HEAD("Média móvel", "<th>Valor</th>") + "<tbody>" + P.mm.map((n) => {
    const b = mm[n];
    const nome = `<td class="l"><span class="dot" style="background:${cores[P.mm.indexOf(n) % cores.length]}"></span> ${sigla} ${n}</td>`;
    if (!b.medida) return `<tr>${nome}<td colspan="6" class="l fora">faltam ${b.faltam} barras ${TEC_BARRAS[tf]} de histórico</td></tr>`;
    return `<tr class="click${n === state.mmN ? " sel" : ""}" data-n="${n}" tabindex="0">${nome}<td>${money(b.valor, cur)}</td>${tecHistCelulas(b.medida, spct)}</tr>`;
  }).join("") + "</tbody>";
  $$("#tMmHist tr.click").forEach((tr) => { const go = () => { state.mmN = +tr.dataset.n; renderTecnica(); }; tr.onclick = go; tr.onkeydown = (e) => { if (e.key === "Enter") go(); }; });
  $("#capMm").textContent = `${cap} Embaixo de cada preço, a distância até ele a partir do preço atual.`;
  const ordem = ["min", "toque", "media", "max"], titulo = { min: "Mínima histórica", toque: "Preço igual à média", media: "Média histórica", max: "Máxima histórica" };
  $("#tMmAlvos").innerHTML = `<thead><tr><th class="l">Média móvel</th>${ordem.map((k) => `<th>${titulo[k]}</th>`).join("")}</tr></thead><tbody>` + P.mm.map((n) => {
    const b = mm[n];
    const nome = `<td class="l"><span class="dot" style="background:${cores[P.mm.indexOf(n) % cores.length]}"></span> ${sigla} ${n}</td>`;
    if (!b.medida) return `<tr>${nome}<td colspan="4" class="l fora">faltam ${b.faltam} barras ${TEC_BARRAS[tf]} de histórico</td></tr>`;
    return `<tr class="${n === state.mmN ? "sel" : ""}">${nome}` + ordem.map((k) => {
      const x = b.alvos.find((y) => y.id === k);
      if (!x || x.preco == null) return `<td class="fora">${x && x.erro ? "em revisão" : "fora de alcance"}</td>`;
      return `<td title="distância de ${spct(x.nivel)} até a média"><strong>${money(x.preco, cur)}</strong><br><span class="var ${x.var < 0 ? "neg" : ""}">${spct(x.var)}</span></td>`;
    }).join("") + "</tr>";
  }).join("") + "</tbody>";

  /* ---------- 3. RSI ---------- */
  const rm = R.medida;
  chart("chTecRsi").setOption(tecOpcao(a, th, {
    dica: (i) => (S.rsi[i] == null ? "" : `<br>${swatch(th.s[0])}RSI ${P.rsi}: <strong>${fnum(S.rsi[i], 1)}</strong>`),
    eixo: { min: 0, max: 100, interval: 10, axisLabel: { color: th.muted, formatter: (v) => (v % 20 === 0 ? v : "") } },
    indicador: [{ name: `RSI ${P.rsi}`, data: S.rsi, lineStyle: { width: 1.5, color: th.s[0] }, itemStyle: { color: th.s[0] },
      markLine: rm ? tecFaixas(th, [{ n: "máxima", v: rm.max.v }, { n: "70", v: 70, cor: th.axis, tipo: "solid" }, { n: "média", v: rm.media }, { n: "30", v: 30, cor: th.axis, tipo: "solid" }, { n: "mínima", v: rm.min.v }],
        (v) => (v === 70 || v === 30 ? "" : fnum(v, 0))) : undefined }],
  }), true);
  $("#tRsiHist").innerHTML = rm
    ? TEC_HEAD("Medida") + `<tbody><tr><td class="l">RSI ${P.rsi}</td>${tecHistCelulas(rm, (v) => fnum(v, 1))}</tr></tbody>`
    : `<tbody><tr><td class="l fora">faltam ${R.faltam} barras ${TEC_BARRAS[tf]} de histórico</td></tr></tbody>`;
  $("#capRsi").textContent = rm ? cap : "";
  $("#tRsiAlvos").innerHTML = rm ? tecAlvos(R.alvos, { nivel: rm.agora, preco: a.ultimo.preco }, (v) => fnum(v, 1), cur, `RSI ${P.rsi}`) : "";

  /* ---------- 4. OBV ---------- */
  const on = O.nivel;
  chart("chTecObv").setOption(tecOpcao(a, th, {
    dica: (i) => `<br>${swatch(th.s[0])}OBV: <strong>${fbig(S.obv[i])}</strong><br>Volume ${barra === "pregão" ? "do pregão" : barra === "semana" ? "da semana" : "do mês"}: ${fbig(a.v[i])}`,
    eixo: { scale: true, axisLabel: { color: th.muted, formatter: fbig } },
    indicador: O.sem_volume ? [] : [{ name: "OBV", data: S.obv, lineStyle: { width: 1.5, color: th.s[0] }, itemStyle: { color: th.s[0] },
      markLine: tecFaixas(th, [{ n: "máxima", v: on.max.v }, { n: "mínima", v: on.min.v }], fbig) }],
  }), true);
  $("#tObvHist").innerHTML = O.sem_volume
    ? `<tbody><tr><td class="l fora">Sem dados de volume para este ativo.</td></tr></tbody>`
    : TEC_HEAD("Medida") + "<tbody>" +
      `<tr><td class="l">OBV</td>${tecHistCelulas(on, fbig, { semMedia: true })}</tr>` +
      (O.fluxo ? `<tr><td class="l">Saldo de volume · ${P.obv} barras</td>${tecHistCelulas(O.fluxo, spct)}</tr>` : "") +
      (O.volatilidade ? `<tr><td class="l">Volatilidade do OBV · ${P.obv} barras</td>${tecHistCelulas(O.volatilidade, (v) => fnum(v, 2))}</tr>` : "") + "</tbody>";

  /* zoom e cursor andam juntos nos quatro gráficos */
  TEC_CHARTS.forEach((id) => { if (charts[id]) charts[id].group = "tecnica"; });
  echarts.connect("tecnica");
}

/* fecha as caixas de ajuda ao clicar fora */
document.addEventListener("click", (e) => {
  $$("details.ajuda[open]").forEach((d) => { if (!d.contains(e.target)) d.removeAttribute("open"); });
});
