/* Usado por tests/test_paridade_js.py: lê {c, v} da entrada padrão e devolve as curvas
   calculadas por site/indicadores.js, para comparar com o Python. */
const Ind = require("../site/indicadores.js");
let txt = "";
process.stdin.on("data", (b) => (txt += b));
process.stdin.on("end", () => {
  const { c, v } = JSON.parse(txt);
  const o = Ind.obv(c, v);
  const out = { dd: Ind.dd(c), rsi: Ind.rsi(c, 14), obv: o, obv_fluxo: Ind.obvFluxo(o, v, 20), obv_volatilidade: Ind.obvVolatilidade(o, v, 20) };
  for (const tipo of ["sma", "ema", "wma"]) for (const n of [50, 100, 200, 250]) out[`${tipo}${n}`] = Ind.medias[tipo](c, n);
  process.stdout.write(JSON.stringify(out));
});
