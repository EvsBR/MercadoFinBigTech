/* Painel Big Techs — front-end estático (sem build). Lê os JSON gerados em data/ */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

const state = {
  meta: null, corr: null, cache: {},
  tab: "resumo", sym: null,
  th: "20", freq: "M", mode: "abs", bench: null, since: null, win: "3a",
  sortKey: "dd_current", sortDir: 1,
};
const charts = {};
const TABS = ["resumo", "drawdowns", "ciclos", "sazonalidade", "correlacoes", "metodologia"];

/* ---------------------------------------------------------------- formatação pt-BR */
const nf = (d) => new Intl.NumberFormat("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 1) => (v == null || !isFinite(v) ? "—" : nf(d).format(v * 100) + "%");
const spct = (v, d = 1) => (v == null || !isFinite(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + nf(d).format(Math.abs(v) * 100) + "%");
const fnum = (v, d = 2) => (v == null || !isFinite(v) ? "—" : nf(d).format(v));
const money = (v, cur = "US$") => (v == null ? "—" : (cur ? cur + " " : "") + nf(v < 1 ? 4 : 2).format(v));
const fdate = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : "—");
const fdays = (d) => {
  if (d == null) return "—";
  if (d >= 365) return nf(1).format(d / 365.25) + " anos";
  if (d >= 60) return nf(0).format(d / 30.44) + " meses";
  return d + " dias";
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* ---------------------------------------------------------------- tema / cores */
const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function T() {
  return {
    s: [cssVar("--series-1"), cssVar("--series-2"), cssVar("--series-3")],
    red: cssVar("--series-red"), text: cssVar("--text-primary"), text2: cssVar("--text-secondary"),
    muted: cssVar("--muted"), grid: cssVar("--grid"), axis: cssVar("--axis"),
    surface: cssVar("--surface-1"), mid: cssVar("--div-mid"), ghost: cssVar("--ghost-bar"),
    font: cssVar("--font"),
  };
}
function hexRgb(h) {
  h = h.replace("#", "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const rgba = (hex, a) => { const [r, g, b] = hexRgb(hex); return `rgba(${r},${g},${b},${a})`; };
function mix(a, b, t) {
  const A = hexRgb(a), B = hexRgb(b);
  return `rgb(${A.map((x, i) => Math.round(x + (B[i] - x) * t)).join(",")})`;
}
/* divergente azul (+) ↔ vermelho (−) com cinza neutro no meio */
function divCell(v, cap, th) {
  if (v == null || !isFinite(v)) return { bg: "", fg: "" };
  const t = Math.max(-1, Math.min(1, v / cap));
  const pole = t >= 0 ? th.s[0] : th.red;
  return { bg: mix(th.mid, pole, Math.abs(t)), fg: Math.abs(t) > 0.62 ? "#ffffff" : th.text };
}

/* ---------------------------------------------------------------- dados */
async function getJSON(path) {
  const r = await fetch(path, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
}
const allRows = () => [...state.meta.tickers, ...state.meta.benchmarks];
const rowOf = (sym) => allRows().find((r) => r.symbol === sym);
async function loadSym(sym) {
  if (!state.cache[sym]) state.cache[sym] = await getJSON("data/" + rowOf(sym).file);
  return state.cache[sym];
}

/* ---------------------------------------------------------------- ECharts base */
function chart(id) {
  const el = document.getElementById(id);
  if (!charts[id]) {
    charts[id] = echarts.init(el, null, { renderer: "canvas" });
  }
  return charts[id];
}
function disposeCharts() { Object.keys(charts).forEach((k) => { charts[k].dispose(); delete charts[k]; }); }
function base(th) {
  return {
    animation: false,
    textStyle: { fontFamily: th.font, color: th.text2 },
    tooltip: {
      trigger: "axis", confine: true,
      backgroundColor: th.surface, borderColor: th.axis, borderWidth: 1,
      textStyle: { color: th.text, fontSize: 12 },
      axisPointer: { type: "line", lineStyle: { color: th.muted, width: 1 } },
    },
  };
}
function xTime(th, extra = {}) {
  return Object.assign({
    type: "time", axisLine: { lineStyle: { color: th.axis } }, axisTick: { show: false },
    axisLabel: { color: th.muted, hideOverlap: true }, splitLine: { show: false },
  }, extra);
}
function yVal(th, extra = {}) {
  return Object.assign({
    type: "value", axisLine: { show: false }, axisTick: { show: false },
    axisLabel: { color: th.muted }, splitLine: { lineStyle: { color: th.grid, width: 1 } },
    nameTextStyle: { color: th.muted, fontSize: 11 },
  }, extra);
}
const dateOf = (p) => echarts.time.format(p.value[0], "{dd}/{MM}/{yyyy}", false);
const swatch = (c) => `<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${c};margin-right:6px"></span>`;

/* ---------------------------------------------------------------- navegação */
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  if (TABS.includes(h.get("aba"))) state.tab = h.get("aba");
  const s = h.get("ativo");
  if (s && rowOf(s)) state.sym = s;
}
function writeHash() {
  const h = new URLSearchParams({ aba: state.tab, ativo: state.sym });
  history.replaceState(null, "", "#" + h.toString());
}
function setTab(tab) {
  state.tab = tab;
  $$(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  TABS.forEach((t) => { $("#tab-" + t).hidden = t !== tab; });
  writeHash();
  render();
}

/* ---------------------------------------------------------------- RESUMO */
const SUMMARY_COLS = [
  { k: "symbol", t: "Ativo", l: true },
  { k: "first_date", t: "Desde" },
  { k: "last_price", t: "Último" },
  { k: "ytd", t: "No ano" },
  { k: "ret_1y", t: "12 meses" },
  { k: "cagr", t: "CAGR" },
  { k: "dd_current", t: "Drawdown atual" },
  { k: "dd_max", t: "Pior drawdown" },
  { k: "phase", t: "Fase (regra 20%)", l: true },
  { k: "vol_1y", t: "Vol. 12m" },
  { k: "corr_1y", t: "Correl. 12m" },
  { k: "beta_3y", t: "Beta 3a" },
];
function summaryCell(r, k) {
  switch (k) {
    case "symbol": return `<strong>${esc(r.symbol)}</strong><span class="name">${esc(r.name)}</span>`;
    case "first_date": return fdate(r.first_date);
    case "last_price": return money(r.last_price, r.currency);
    case "ytd": case "ret_1y": case "cagr":
      return `<span class="${r[k] < 0 ? "neg" : ""}">${spct(r[k])}</span>`;
    case "dd_current": return r.dd_current > -0.0005 ? "no recorde" : pct(r.dd_current);
    case "dd_max": return `${pct(r.dd_max, 0)} <span class="name">${r.dd_max_trough ? r.dd_max_trough.slice(0, 4) : ""}</span>`;
    case "phase": return r.phase ? `<span class="tag ${r.phase}">${r.phase}</span> <span class="name">${fdays(r.phase_days)} · ${spct(r.phase_ret, 0)}</span>` : "—";
    case "vol_1y": return pct(r.vol_1y, 0);
    case "corr_1y": case "beta_3y": return fnum(r[k], 2);
    default: return esc(r[k] ?? "—");
  }
}
function renderResumo() {
  const th = T();
  const mb = state.meta.main_benchmark || "";
  const cols = SUMMARY_COLS.map((c) => ({ ...c, t: (c.k === "corr_1y" || c.k === "beta_3y") ? `${c.t} vs ${mb}` : c.t }));
  const sorter = (a, b) => {
    const x = a[state.sortKey], y = b[state.sortKey];
    if (x == null) return 1; if (y == null) return -1;
    return (x > y ? 1 : x < y ? -1 : 0) * state.sortDir;
  };
  const head = "<thead><tr>" + cols.map((c) =>
    `<th class="${c.l ? "l" : ""}" data-k="${c.k}" tabindex="0" aria-sort="${state.sortKey === c.k ? (state.sortDir > 0 ? "ascending" : "descending") : "none"}">${esc(c.t)}${state.sortKey === c.k ? ` <span class="arrow">${state.sortDir > 0 ? "▲" : "▼"}</span>` : ""}</th>`).join("") + "</tr></thead>";
  const rows = (list) => list.slice().sort(sorter).map((r) =>
    `<tr class="click" data-sym="${esc(r.symbol)}" tabindex="0">` + cols.map((c) => `<td class="${c.l ? "l" : ""}">${summaryCell(r, c.k)}</td>`).join("") + "</tr>").join("");
  const tbl = $("#summaryTable");
  tbl.innerHTML = head + `<tbody>${rows(state.meta.tickers)}</tbody><tbody class="bench">${rows(state.meta.benchmarks)}</tbody>`;
  $$("th[data-k]", tbl).forEach((h) => {
    const go = () => { const k = h.dataset.k; state.sortDir = state.sortKey === k ? -state.sortDir : 1; state.sortKey = k; renderResumo(); };
    h.onclick = go; h.onkeydown = (e) => { if (e.key === "Enter") go(); };
  });
  $$("tr.click", tbl).forEach((tr) => {
    const go = () => { state.sym = tr.dataset.sym; $("#symSel").value = state.sym; setTab("drawdowns"); };
    tr.onclick = go; tr.onkeydown = (e) => { if (e.key === "Enter") go(); };
  });

  // barras: drawdown atual (frente) sobre o pior drawdown (fundo)
  const list = state.meta.tickers.slice().sort((a, b) => (a.dd_current ?? 0) - (b.dd_current ?? 0)).reverse();
  const c = chart("chDdBars");
  c.setOption({
    ...base(th),
    tooltip: { ...base(th).tooltip, trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: rgba(th.muted, 0.08) } },
      formatter: (ps) => {
        const r = list[ps[0].dataIndex];
        return `<strong>${esc(r.symbol)}</strong> · ${esc(r.name)}<br>${swatch(th.red)}Drawdown atual: <strong>${pct(r.dd_current)}</strong><br>${swatch(th.ghost)}Pior da história: ${pct(r.dd_max)} (fundo em ${fdate(r.dd_max_trough)})`;
      } },
    legend: { top: 0, left: 0, itemWidth: 12, itemHeight: 10, textStyle: { color: th.text2 }, data: ["Drawdown atual", "Pior drawdown da história"] },
    grid: { left: 64, right: 24, top: 36, bottom: 28 },
    xAxis: yVal(th, { max: 0, min: -1, axisLabel: { color: th.muted, formatter: (v) => pct(v, 0) } }),
    yAxis: { type: "category", data: list.map((r) => r.symbol), axisTick: { show: false }, axisLine: { lineStyle: { color: th.axis } }, axisLabel: { color: th.text2, fontWeight: 600 } },
    series: [
      { name: "Pior drawdown da história", type: "bar", data: list.map((r) => r.dd_max), barWidth: 16, itemStyle: { color: th.ghost, borderRadius: [4, 0, 0, 4] }, z: 1 },
      { name: "Drawdown atual", type: "bar", data: list.map((r) => r.dd_current), barWidth: 16, barGap: "-100%", itemStyle: { color: th.red, borderRadius: [4, 0, 0, 4] }, z: 2 },
    ],
  }, true);
}

/* ---------------------------------------------------------------- DRAWDOWNS */
function tile(k, v, s = "") { return `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ""}</div>`; }
async function renderDrawdowns() {
  const d = await loadSym(state.sym); const th = T(); const st = d.stats; const dd = d.drawdown;
  $("#ddTitle").textContent = `${d.symbol} · ${d.name}: preço e drawdown desde ${fdate(st.first_date)}`;
  const cur = dd.current;
  $("#ddTiles").innerHTML =
    tile("Drawdown atual", st.dd_current > -0.0005 ? "0%" : pct(st.dd_current), cur ? `pico em ${fdate(cur.peak)} · há ${fdays(cur.days_total)}` : "no recorde histórico") +
    tile("Pior drawdown", pct(st.dd_max), `${fdate(st.dd_max_peak)} → ${fdate(st.dd_max_trough)}`) +
    tile("Recuperação do pior", st.dd_max_recovery ? fdays(dd.episodes[0]?.days_recover) : "não recuperou", st.dd_max_recovery ? `voltou ao pico em ${fdate(st.dd_max_recovery)}` : "ainda abaixo do pico daquela época") +
    tile("Quedas ≥ 20% / ≥ 30%", `${dd.count_20} / ${dd.count_30}`, `episódios desde ${st.first_date.slice(0, 4)}`);

  const S = d.series;
  const price = S.d.map((x, i) => [x, S.p[i]]);
  const ddv = S.d.map((x, i) => [x, S.dd[i]]);
  const worst = dd.episodes[0];
  let worstPt = null;
  if (worst) { // ponto semanal mais próximo do fundo
    const i = S.d.findIndex((x) => x >= worst.trough);
    if (i >= 0) worstPt = [S.d[i], S.dd[i]];
  }
  const c = chart("chPriceDd");
  c.setOption({
    ...base(th),
    tooltip: { ...base(th).tooltip, formatter: (ps) => {
      const i = ps[0].dataIndex;
      return `<strong>${dateOf(ps[0])}</strong><br>${swatch(th.s[0])}Preço ajustado: <strong>${money(S.p[i], d.currency)}</strong><br>${swatch(th.red)}Drawdown: <strong>${pct(S.dd[i])}</strong>`;
    } },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [{ left: 72, right: 24, top: 16, height: "50%" }, { left: 72, right: 24, top: "64%", bottom: 70 }],
    xAxis: [xTime(th, { gridIndex: 0, axisLabel: { show: false } }), xTime(th, { gridIndex: 1 })],
    yAxis: [
      yVal(th, { type: "log", logBase: 10, gridIndex: 0, axisLabel: { color: th.muted, formatter: (v) => (v < 1 ? nf(2).format(v) : nf(0).format(v)) } }),
      yVal(th, { gridIndex: 1, max: 0, axisLabel: { color: th.muted, formatter: (v) => pct(v, 0) } }),
    ],
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }, { type: "slider", xAxisIndex: [0, 1], bottom: 14, height: 22, borderColor: th.grid, textStyle: { color: th.muted }, fillerColor: rgba(th.s[0], 0.12), dataBackground: { lineStyle: { color: th.axis }, areaStyle: { color: rgba(th.axis, 0.3) } } }],
    series: [
      { name: "Preço ajustado", type: "line", data: price, showSymbol: false, lineStyle: { width: 2, color: th.s[0] }, itemStyle: { color: th.s[0] } },
      { name: "Drawdown", type: "line", xAxisIndex: 1, yAxisIndex: 1, data: ddv, showSymbol: false, lineStyle: { width: 1.5, color: th.red }, itemStyle: { color: th.red }, areaStyle: { color: rgba(th.red, 0.18) },
        markPoint: worstPt ? { symbol: "circle", symbolSize: 9, itemStyle: { color: th.red, borderColor: th.surface, borderWidth: 2 },
          label: { show: true, position: "bottom", color: th.text2, fontSize: 11, formatter: () => `pior: ${pct(worst.depth, 0)}` },
          data: [{ coord: worstPt }] } : undefined },
    ],
  }, true);

  $("#ddTable").innerHTML = "<thead><tr><th class='l'>#</th><th>Queda</th><th>Pico</th><th>Fundo</th><th>Tempo de queda</th><th>Recuperação</th><th>Tempo para recuperar</th><th>Duração total</th></tr></thead><tbody>" +
    dd.episodes.map((e, i) => `<tr><td class="l">${i + 1}</td><td class="neg"><strong>${pct(e.depth)}</strong></td><td>${fdate(e.peak)}</td><td>${fdate(e.trough)}</td><td>${fdays(e.days_down)}</td><td>${e.recovery ? fdate(e.recovery) : "<em>em andamento</em>"}</td><td>${e.recovery ? fdays(e.days_recover) : "—"}</td><td>${fdays(e.days_total)}</td></tr>`).join("") + "</tbody>";
}

/* ---------------------------------------------------------------- CICLOS */
async function renderCiclos() {
  const d = await loadSym(state.sym); const th = T();
  const seg = $("#thSeg");
  seg.innerHTML = state.meta.cycle_thresholds.map((t) => `<button data-v="${t}" aria-pressed="${t === state.th}">${t}%</button>`).join("");
  $$("button", seg).forEach((b) => (b.onclick = () => { state.th = b.dataset.v; renderCiclos(); }));
  const cy = d.cycles[state.th] || Object.values(d.cycles)[0];
  const cur = cy.current;
  $("#cycTitle").textContent = `${d.symbol}: fases de alta e baixa (regra de ${state.th}%)`;
  const pctile = cy.current_days_pctile;
  $("#cycTiles").innerHTML =
    (cur ? tile("Fase atual",
      `<span class="pill"><span class="dot" style="background:${cur.type === "alta" ? th.s[0] : th.red}"></span>${cur.type === "alta" ? "Alta" : "Baixa"}</span>`,
      `desde ${fdate(cur.start)} · ${fdays(cur.days)} · ${spct(cur.ret)}${pctile != null ? ` · mais longa que ${pct(pctile, 0)} das ${cur.type === "alta" ? "altas" : "baixas"} anteriores` : ""}`) : "") +
    (cur ? tile(cur.type === "baixa" ? "Pior ponto da fase" : "Melhor ponto da fase", spct(cur.extreme), `em ${fdate(cur.extreme_date)}`) : "") +
    tile("Alta típica (mediana)", cy.bull.n ? spct(cy.bull.ret_median, 0) : "—", cy.bull.n ? `${fdays(cy.bull.days_median)} · ${cy.bull.n} altas completas` : "sem fases completas") +
    tile("Baixa típica (mediana)", cy.bear.n ? spct(cy.bear.ret_median, 0) : "—", cy.bear.n ? `${fdays(cy.bear.days_median)} · ${cy.bear.n} baixas completas` : "sem fases completas");

  const S = d.series;
  const price = S.d.map((x, i) => [x, S.p[i]]);
  const areas = cy.phases.map((ph) => [{ xAxis: ph.start, itemStyle: { color: rgba(ph.type === "alta" ? th.s[0] : th.red, ph.type === "alta" ? 0.10 : 0.14) } }, { xAxis: ph.end }]);
  const phaseAt = (date) => cy.phases.find((ph) => date >= ph.start && date <= ph.end);
  chart("chCycles").setOption({
    ...base(th),
    tooltip: { ...base(th).tooltip, formatter: (ps) => {
      const i = ps[0].dataIndex; const ph = phaseAt(S.d[i]);
      return `<strong>${dateOf(ps[0])}</strong><br>${swatch(th.s[0])}Preço: <strong>${money(S.p[i], d.currency)}</strong>` +
        (ph ? `<br>Fase: <strong>${ph.type}</strong> (${fdate(ph.start)} → ${ph.ongoing ? "hoje" : fdate(ph.end)}, ${spct(ph.ret, 0)})` : "");
    } },
    grid: { left: 72, right: 24, top: 16, bottom: 70 },
    xAxis: xTime(th),
    yAxis: yVal(th, { type: "log", logBase: 10, axisLabel: { color: th.muted, formatter: (v) => (v < 1 ? nf(2).format(v) : nf(0).format(v)) } }),
    dataZoom: [{ type: "inside" }, { type: "slider", bottom: 14, height: 22, borderColor: th.grid, textStyle: { color: th.muted }, fillerColor: rgba(th.s[0], 0.12) }],
    series: [{ name: "Preço", type: "line", data: price, showSymbol: false, lineStyle: { width: 2, color: th.s[0] }, itemStyle: { color: th.s[0] },
      markArea: { silent: true, data: areas } }],
  }, true);

  const r1 = S.d.map((x, i) => [x, S.r1[i]]); const r3 = S.d.map((x, i) => [x, S.r3[i]]);
  chart("chRolling").setOption({
    ...base(th),
    tooltip: { ...base(th).tooltip, formatter: (ps) => `<strong>${dateOf(ps[0])}</strong>` + ps.map((p) => `<br>${swatch(p.color)}${p.seriesName}: <strong>${spct(p.value[1])}</strong>`).join("") },
    legend: { top: 0, left: 0, itemWidth: 14, itemHeight: 3, textStyle: { color: th.text2 } },
    grid: { left: 64, right: 110, top: 34, bottom: 60 },
    xAxis: xTime(th), yAxis: yVal(th, { axisLabel: { color: th.muted, formatter: (v) => pct(v, 0) } }),
    dataZoom: [{ type: "inside" }, { type: "slider", bottom: 10, height: 20, borderColor: th.grid, textStyle: { color: th.muted }, fillerColor: rgba(th.s[0], 0.12) }],
    series: [
      { name: "12 meses", type: "line", data: r1, showSymbol: false, lineStyle: { width: 1.5, color: th.s[0] }, itemStyle: { color: th.s[0] },
        endLabel: { show: true, color: th.text2, fontSize: 11, formatter: (p) => `12m ${spct(p.value[1], 0)}` },
        markLine: { silent: true, symbol: "none", lineStyle: { color: th.axis, width: 1, type: "solid" }, label: { show: false }, data: [{ yAxis: 0 }] } },
      { name: "3 anos (ao ano)", type: "line", data: r3, showSymbol: false, lineStyle: { width: 2, color: th.s[1] }, itemStyle: { color: th.s[1] },
        endLabel: { show: true, color: th.text2, fontSize: 11, formatter: (p) => `3a ${spct(p.value[1], 0)}` } },
    ],
  }, true);

  const allPh = cy.phases.slice().reverse();
  const shown = state.allPhases ? allPh : allPh.slice(0, 20);
  $("#cycTable").innerHTML = "<thead><tr><th class='l'>Fase</th><th>Início</th><th>Fim</th><th>Variação</th><th>Duração</th><th class='l'>Obs.</th></tr></thead><tbody>" +
    shown.map((ph) => `<tr><td class="l"><span class="tag ${ph.type}">${ph.type}</span></td><td>${fdate(ph.start)}</td><td>${ph.ongoing ? "hoje" : fdate(ph.end)}</td><td class="${ph.ret < 0 ? "neg" : ""}"><strong>${spct(ph.ret)}</strong></td><td>${fdays(ph.days)}</td><td class="l">${ph.ongoing ? "em andamento" : ph.truncated ? "início dos dados (fora das medianas)" : ""}</td></tr>`).join("") + "</tbody>" +
    (allPh.length > 20 ? `<tfoot><tr><td class="l" colspan="6"><button class="ghost" id="morePh" type="button">${state.allPhases ? "Mostrar só as 20 mais recentes" : `Mostrar todas as ${allPh.length} fases`}</button></td></tr></tfoot>` : "");
  const more = $("#morePh");
  if (more) more.onclick = () => { state.allPhases = !state.allPhases; renderCiclos(); };
}

/* ---------------------------------------------------------------- SAZONALIDADE */
const CAPS = { abs: { M: 0.15, B: 0.20, Q: 0.25, Y: 0.6 }, rel: { M: 0.08, B: 0.11, Q: 0.14, Y: 0.35 } };
function median(a) { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
async function renderSazonalidade() {
  const d = await loadSym(state.sym); const th = T();
  const benches = state.meta.benchmarks.filter((b) => b.symbol !== state.sym);
  const bsel = $("#benchSel");
  if (!state.bench || !benches.find((b) => b.symbol === state.bench)) state.bench = (benches.find((b) => b.symbol === state.meta.main_benchmark) || benches[0] || {}).symbol;
  bsel.innerHTML = benches.map((b) => `<option value="${esc(b.symbol)}">${esc(b.name)}</option>`).join("");
  bsel.value = state.bench || "";
  const rel = state.mode === "rel" && state.bench;
  bsel.disabled = state.mode !== "rel";
  $$("#freqSeg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === state.freq)));
  $$("#modeSeg button").forEach((b) => { b.setAttribute("aria-pressed", String(b.dataset.v === state.mode)); b.disabled = b.dataset.v === "rel" && !benches.length; });

  const tbl = d.seasonality[state.freq];
  const labels = state.meta.freq_labels[state.freq];
  let years = tbl.years.slice(), values = tbl.values.map((r) => r.slice()), annual = tbl.annual.slice();
  const partial = new Set(tbl.partial.map(([y, p]) => `${tbl.years[y]}-${p}`));
  const annualPartial = tbl.annual_partial.slice();
  if (rel) {
    const bd = await loadSym(state.bench); const bt = bd.seasonality[state.freq];
    const by = new Map(bt.years.map((y, i) => [y, i]));
    values = values.map((row, yi) => row.map((v, p) => {
      const j = by.get(years[yi]); const b = j == null ? null : bt.values[j][p];
      return v == null || b == null ? null : v - b;
    }));
    annual = annual.map((v, yi) => { const j = by.get(years[yi]); const b = j == null ? null : bt.annual[j]; return v == null || b == null ? null : v - b; });
  }

  // filtro "desde"
  const ssel = $("#sinceSel");
  const yOpts = years.slice();
  if (state.since == null || !yOpts.includes(+state.since)) state.since = yOpts[0];
  ssel.innerHTML = yOpts.map((y) => `<option value="${y}">${y}${y === yOpts[0] ? " (início)" : ""}</option>`).join("");
  ssel.value = String(state.since);
  const keep = years.map((y) => y >= +state.since);
  years = years.filter((_, i) => keep[i]); values = values.filter((_, i) => keep[i]);
  annual = annual.filter((_, i) => keep[i]); const aPart = annualPartial.filter((_, i) => keep[i]);

  // estatísticas só com períodos completos
  const stats = labels.map((_, p) => {
    const xs = []; values.forEach((row, yi) => { const v = row[p]; if (v != null && !partial.has(`${years[yi]}-${p}`)) xs.push(v); });
    const n = xs.length; const mean = n ? xs.reduce((a, b) => a + b, 0) / n : null;
    return { n, mean, med: median(xs), pos: n ? xs.filter((x) => x > 0).length / n : null, best: n ? Math.max(...xs) : null, worst: n ? Math.min(...xs) : null };
  });
  const ys = annual.filter((v, i) => v != null && !aPart[i]);
  const ystat = { n: ys.length, mean: ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : null, med: median(ys), pos: ys.length ? ys.filter((x) => x > 0).length / ys.length : null };

  const fname = { M: "mês", B: "bimestre", Q: "trimestre" }[state.freq];
  $("#seasTitle").textContent = rel ? `${d.symbol} menos ${state.bench}: diferença média por ${fname}` : `${d.symbol}: retorno médio por ${fname}`;
  $("#seasHint").textContent = rel
    ? `Retorno do ativo menos o da referência no mesmo período (períodos completos desde ${state.since}). "% positivo" = % de vezes que o ativo superou a referência.`
    : `Média dos períodos completos desde ${state.since}. Passe o mouse para ver mediana, % de vezes positivo, melhor e pior.`;

  chart("chSeas").setOption({
    ...base(th),
    tooltip: { ...base(th).tooltip, trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: rgba(th.muted, 0.08) } },
      formatter: (ps) => { const s = stats[ps[0].dataIndex];
        return `<strong>${labels[ps[0].dataIndex]}</strong><br>Média: <strong>${spct(s.mean)}</strong><br>Mediana: ${spct(s.med)}<br>${rel ? "Superou a referência" : "Positivo"}: ${pct(s.pos, 0)} das vezes<br>Melhor: ${spct(s.best)} · Pior: ${spct(s.worst)}<br><span style="color:${th.muted}">${s.n} períodos</span>`; } },
    grid: { left: 60, right: 16, top: 16, bottom: 30 },
    xAxis: { type: "category", data: labels, axisTick: { show: false }, axisLine: { lineStyle: { color: th.axis } }, axisLabel: { color: th.text2 } },
    yAxis: yVal(th, { axisLabel: { color: th.muted, formatter: (v) => pct(v, 0) } }),
    series: [{ name: "Média", type: "bar", barMaxWidth: 38,
      data: stats.map((s) => ({ value: s.mean, itemStyle: { color: s.mean >= 0 ? th.s[0] : th.red, borderRadius: s.mean >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] } })) }],
  }, true);

  // tabela ano × período
  const cap = CAPS[rel ? "rel" : "abs"]; const capP = cap[state.freq];
  const cell = (v, isPart, capv, cls = "") => {
    if (v == null) return `<td class="empty ${cls}">·</td>`;
    const { bg, fg } = divCell(v, capv, th);
    return `<td class="${cls}${isPart ? " partial" : ""}" style="background:${bg};color:${fg}" title="${isPart ? "período em andamento" : ""}">${spct(v)}${isPart ? "*" : ""}</td>`;
  };
  let html = `<thead><tr><th class="yr">Ano</th>${labels.map((l) => `<th>${esc(l)}</th>`).join("")}<th>Ano todo</th></tr></thead><tbody>`;
  for (let yi = years.length - 1; yi >= 0; yi--) {
    html += `<tr><td class="yr">${years[yi]}</td>` + values[yi].map((v, p) => cell(v, partial.has(`${years[yi]}-${p}`), capP)).join("") +
      cell(annual[yi], aPart[yi], cap.Y, "total") + "</tr>";
  }
  html += "</tbody><tfoot>" +
    `<tr><td class="yr">Média</td>${stats.map((s) => `<td>${spct(s.mean)}</td>`).join("")}<td>${spct(ystat.mean)}</td></tr>` +
    `<tr><td class="yr">Mediana</td>${stats.map((s) => `<td>${spct(s.med)}</td>`).join("")}<td>${spct(ystat.med)}</td></tr>` +
    `<tr><td class="yr">${rel ? "% acima" : "% positivos"}</td>${stats.map((s) => `<td>${pct(s.pos, 0)}</td>`).join("")}<td>${pct(ystat.pos, 0)}</td></tr>` +
    `<tr><td class="yr">Nº de períodos</td>${stats.map((s) => `<td>${s.n}</td>`).join("")}<td>${ystat.n}</td></tr></tfoot>`;
  $("#seasTable").innerHTML = html;
}

/* ---------------------------------------------------------------- CORRELAÇÕES */
async function renderCorrelacoes() {
  const th = T(); const C = state.corr;
  const seg = $("#winSeg");
  const wl = { "1a": "1 ano", "3a": "3 anos", "5a": "5 anos", "10a": "10 anos", "tudo": "Tudo" };
  seg.innerHTML = C.windows.map((w) => `<button data-v="${w}" aria-pressed="${w === state.win}">${wl[w] || w}</button>`).join("");
  $$("button", seg).forEach((b) => (b.onclick = () => { state.win = b.dataset.v; renderCorrelacoes(); }));
  const M = C.matrices[state.win]; const syms = C.symbols;
  let html = `<thead><tr><th></th>${syms.map((s) => `<th>${esc(s)}</th>`).join("")}</tr></thead><tbody>`;
  syms.forEach((a, i) => {
    html += `<tr><td class="yr"><strong>${esc(a)}</strong></td>` + syms.map((b, j) => {
      const v = M[i][j];
      if (i === j) return `<td class="empty">—</td>`;
      if (v == null) return `<td class="empty" title="dados insuficientes nesta janela">·</td>`;
      const { bg, fg } = divCell(v, 1, th);
      const hl = a === state.sym || b === state.sym ? "font-weight:700;" : "";
      return `<td style="background:${bg};color:${fg};${hl}" title="${esc(a)} × ${esc(b)}: ${fnum(v, 2)}">${fnum(v, 2)}</td>`;
    }).join("") + "</tr>";
  });
  $("#corrTable").innerHTML = html + "</tbody>";

  const d = await loadSym(state.sym);
  const benches = state.meta.benchmarks.map((b) => b.symbol);
  $("#rollCorrTitle").textContent = `${d.symbol}: correlação móvel de 52 semanas com as referências`;
  const rc = chart("chRollCorr");
  if (!d.corr || !d.corr.d) {
    rc.setOption({ title: { text: "Selecione uma ação (não uma referência) para ver este gráfico.", left: "center", top: "middle", textStyle: { color: th.muted, fontSize: 13, fontWeight: 400 } }, series: [] }, true);
  } else {
    rc.setOption({
      ...base(th),
      tooltip: { ...base(th).tooltip, formatter: (ps) => `<strong>${dateOf(ps[0])}</strong>` + ps.map((p) => `<br>${swatch(p.color)}${p.seriesName}: <strong>${fnum(p.value[1], 2)}</strong>`).join("") },
      legend: { top: 0, left: 0, itemWidth: 14, itemHeight: 3, textStyle: { color: th.text2 } },
      grid: { left: 52, right: 70, top: 34, bottom: 60 },
      xAxis: xTime(th), yAxis: yVal(th, { min: -0.4, max: 1, interval: 0.2, axisLabel: { color: th.muted, formatter: (v) => fnum(v, 1) } }),
      dataZoom: [{ type: "inside" }, { type: "slider", bottom: 10, height: 20, borderColor: th.grid, textStyle: { color: th.muted }, fillerColor: rgba(th.s[0], 0.12) }],
      series: benches.filter((b) => d.corr[b]).map((b, k) => {
        const idx = benches.indexOf(b); const col = th.s[idx % 3];
        return { name: b, type: "line", data: d.corr.d.map((x, i) => [x, d.corr[b][i]]), showSymbol: false, connectNulls: false,
          lineStyle: { width: 1.5, color: col }, itemStyle: { color: col },
          endLabel: { show: true, color: th.text2, fontSize: 11, formatter: (p) => `${b} ${fnum(p.value[1], 2)}` } };
      }),
    }, true);
  }

  const A = C.avg_pairwise;
  const vals = A.v.filter((x) => x != null); const med = median(vals);
  chart("chAvgCorr").setOption({
    ...base(th),
    tooltip: { ...base(th).tooltip, formatter: (ps) => `<strong>${dateOf(ps[0])}</strong><br>${swatch(th.s[0])}Correlação média: <strong>${fnum(ps[0].value[1], 2)}</strong><br><span style="color:${th.muted}">${A.n[ps[0].dataIndex]} ações com dados</span>` },
    grid: { left: 52, right: 130, top: 20, bottom: 60 },
    xAxis: xTime(th), yAxis: yVal(th, { axisLabel: { color: th.muted, formatter: (v) => fnum(v, 1) } }),
    dataZoom: [{ type: "inside" }, { type: "slider", bottom: 10, height: 20, borderColor: th.grid, textStyle: { color: th.muted }, fillerColor: rgba(th.s[0], 0.12) }],
    series: [{ name: "Correlação média", type: "line", data: A.d.map((x, i) => [x, A.v[i]]), showSymbol: false, lineStyle: { width: 2, color: th.s[0] }, itemStyle: { color: th.s[0] },
      markLine: med == null ? undefined : { silent: true, symbol: "none", lineStyle: { color: th.muted, width: 1, type: "solid" },
        label: { color: th.text2, fontSize: 11, formatter: () => `mediana histórica\n${fnum(med, 2)}`, position: "end" }, data: [{ yAxis: med }] } }],
  }, true);
}

/* ---------------------------------------------------------------- ciclo de render */
async function render() {
  try {
    if (state.tab === "resumo") renderResumo();
    else if (state.tab === "drawdowns") await renderDrawdowns();
    else if (state.tab === "ciclos") await renderCiclos();
    else if (state.tab === "sazonalidade") await renderSazonalidade();
    else if (state.tab === "correlacoes") await renderCorrelacoes();
    requestAnimationFrame(() => Object.values(charts).forEach((c) => c.resize()));
  } catch (e) {
    console.error(e);
    $("#tab-" + state.tab).insertAdjacentHTML("afterbegin", `<p class="err">Erro ao montar esta seção: ${esc(e.message)}</p>`);
  }
}

/* ---------------------------------------------------------------- tema */
function applyTheme(mode) {
  if (mode === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", mode);
  $("#themeBtn").textContent = "Tema: " + { auto: "automático", light: "claro", dark: "escuro" }[mode];
  try { localStorage.setItem("tema", mode); } catch (_) { /* sem storage: tudo bem */ }
  disposeCharts(); render();
}

/* ---------------------------------------------------------------- início */
async function init() {
  try {
    [state.meta, state.corr] = await Promise.all([getJSON("data/meta.json"), getJSON("data/correlations.json")]);
  } catch (e) {
    $("#subtitle").innerHTML = `<span class="err">Não encontrei os dados (${esc(e.message)}). Rode <code>python scripts/build_data.py</code> e abra o site por um servidor (veja o README).</span>`;
    return;
  }
  const M = state.meta;
  document.title = `${M.title} — drawdowns, ciclos, sazonalidade e correlações`;
  $("#title").textContent = M.title;
  const gen = new Date(M.generated_at);
  const lastClose = M.tickers.map((t) => t.last_date).sort().pop();
  $("#subtitle").textContent = `Último fechamento: ${fdate(lastClose)} · atualizado em ${gen.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · histórico ${M.start === "max" ? "completo (desde o IPO)" : "desde " + fdate(M.start)}`;
  const stale = allRows().filter((r) => r.stale && !M.demo);
  const banner = $("#banner");
  if (M.demo) { banner.hidden = false; banner.innerHTML = "<strong>DADOS SINTÉTICOS.</strong> Este painel foi gerado em modo de teste (<code>--demo</code>). Os números não são cotações reais."; }
  else if (stale.length) { banner.hidden = false; banner.innerHTML = `<strong>Atenção:</strong> a fonte de dados falhou na última atualização para ${stale.map((r) => esc(r.symbol)).join(", ")}. Mostrando o último dado salvo.`; }
  const sources = [...new Set(allRows().map((r) => r.source).filter(Boolean))];
  $("#footNote").textContent = `Fonte: ${sources.join(", ") || "—"} · preços ajustados por dividendos e desdobramentos · gerado em ${gen.toISOString().slice(0, 16).replace("T", " ")} UTC · uso educacional, não é recomendação de investimento.`;

  const sel = $("#symSel");
  sel.innerHTML = `<optgroup label="Ações">${M.tickers.map((t) => `<option value="${esc(t.symbol)}">${esc(t.symbol)} · ${esc(t.name)}</option>`).join("")}</optgroup>` +
    `<optgroup label="Referências">${M.benchmarks.map((t) => `<option value="${esc(t.symbol)}">${esc(t.symbol)} · ${esc(t.name)}</option>`).join("")}</optgroup>`;
  state.sym = (M.tickers.find((t) => t.symbol === "NVDA") || M.tickers[0] || M.benchmarks[0]).symbol;
  state.th = M.cycle_thresholds.includes("20") ? "20" : M.cycle_thresholds[0];
  readHash();
  sel.value = state.sym;
  sel.onchange = () => { state.sym = sel.value; state.since = null; writeHash(); render(); };

  $$(".tabs button").forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
  $$("#freqSeg button").forEach((b) => (b.onclick = () => { state.freq = b.dataset.v; renderSazonalidade(); }));
  $$("#modeSeg button").forEach((b) => (b.onclick = () => { state.mode = b.dataset.v; renderSazonalidade(); }));
  $("#benchSel").onchange = (e) => { state.bench = e.target.value; renderSazonalidade(); };
  $("#sinceSel").onchange = (e) => { state.since = +e.target.value; renderSazonalidade(); };
  window.addEventListener("hashchange", () => { readHash(); $("#symSel").value = state.sym; setTab(state.tab); });
  window.addEventListener("resize", () => Object.values(charts).forEach((c) => c.resize()));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (!document.documentElement.dataset.theme) { disposeCharts(); render(); } });

  let mode = "auto";
  try { mode = localStorage.getItem("tema") || "auto"; } catch (_) { /* ok */ }
  $("#themeBtn").onclick = () => { const order = ["auto", "light", "dark"]; mode = order[(order.indexOf(mode) + 1) % 3]; applyTheme(mode); };
  if (mode !== "auto") document.documentElement.setAttribute("data-theme", mode);
  $("#themeBtn").textContent = "Tema: " + { auto: "automático", light: "claro", dark: "escuro" }[mode];

  setTab(state.tab);
}
document.addEventListener("DOMContentLoaded", init);
