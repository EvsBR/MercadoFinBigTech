/* Curvas dos indicadores técnicos, calculadas a partir das barras (fechamento e volume).
   São as mesmas fórmulas de pipeline/indicadores/tecnica.py. O teste tests/test_paridade_js.py
   roda este arquivo no Node e compara ponto a ponto com o Python; o site ainda confere, ao
   desenhar, se o último ponto de cada curva bate com o valor "agora" que veio do pipeline.
   Valor indefinido (aquecimento do indicador) = null. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Ind = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const vazio = (n) => new Array(n).fill(null);

  /* drawdown: distância do fechamento ao maior fechamento até a data */
  function dd(c) {
    const out = new Array(c.length);
    let pico = -Infinity;
    for (let i = 0; i < c.length; i++) { if (c[i] > pico) pico = c[i]; out[i] = c[i] / pico - 1; }
    return out;
  }

  function sma(c, n) {
    const out = vazio(c.length);
    for (let i = n - 1; i < c.length; i++) {
      let s = 0;
      for (let j = i - n + 1; j <= i; j++) s += c[j];
      out[i] = s / n;
    }
    return out;
  }

  /* ponderada linear: peso n no fechamento mais recente, 1 no mais antigo */
  function wma(c, n) {
    const out = vazio(c.length);
    const den = (n * (n + 1)) / 2;
    for (let i = n - 1; i < c.length; i++) {
      let s = 0;
      for (let k = 1; k <= n; k++) s += k * c[i - n + k];
      out[i] = s / den;
    }
    return out;
  }

  /* exponencial, alfa = 2/(n+1); primeiro valor = média simples das n primeiras barras */
  function ema(c, n) {
    const out = vazio(c.length);
    if (c.length < n) return out;
    const a = 2 / (n + 1);
    let e = 0;
    for (let i = 0; i < n; i++) e += c[i];
    e /= n;
    out[n - 1] = e;
    for (let i = n; i < c.length; i++) { e = a * c[i] + (1 - a) * e; out[i] = e; }
    return out;
  }

  const rsiValor = (ag, al) => (al === 0 ? (ag > 0 ? 100 : 50) : 100 - 100 / (1 + ag / al));

  /* RSI de Wilder */
  function rsi(c, n = 14) {
    const N = c.length;
    const out = vazio(N);
    if (N <= n) return out;
    let ag = 0, al = 0;
    for (let i = 1; i <= n; i++) { const d = c[i] - c[i - 1]; if (d > 0) ag += d; else al -= d; }
    ag /= n; al /= n;
    out[n] = rsiValor(ag, al);
    for (let i = n + 1; i < N; i++) {
      const d = c[i] - c[i - 1];
      ag = (ag * (n - 1) + (d > 0 ? d : 0)) / n;
      al = (al * (n - 1) + (d < 0 ? -d : 0)) / n;
      out[i] = rsiValor(ag, al);
    }
    return out;
  }

  /* On-Balance Volume: começa em 0 */
  function obv(c, v) {
    const out = new Array(c.length);
    let o = 0;
    for (let i = 0; i < c.length; i++) {
      if (i > 0) o += Math.sign(c[i] - c[i - 1]) * v[i];
      out[i] = o;
    }
    return out;
  }

  /* saldo de volume: variação do OBV em n barras ÷ volume total das mesmas n barras */
  function obvFluxo(o, v, n = 20) {
    const out = vazio(o.length);
    for (let t = n; t < o.length; t++) {
      let s = 0;
      for (let j = t - n + 1; j <= t; j++) s += v[j];
      if (s > 0) out[t] = (o[t] - o[t - n]) / s;
    }
    return out;
  }

  /* desvio-padrão amostral da variação do OBV em n barras ÷ volume médio das mesmas n barras */
  function obvVolatilidade(o, v, n = 20) {
    const out = vazio(o.length);
    for (let t = n; t < o.length; t++) {
      let sv = 0, sd = 0;
      for (let j = t - n + 1; j <= t; j++) { sv += v[j]; sd += o[j] - o[j - 1]; }
      if (!(sv > 0)) continue;
      const md = sd / n;
      let q = 0;
      for (let j = t - n + 1; j <= t; j++) { const x = o[j] - o[j - 1] - md; q += x * x; }
      out[t] = Math.sqrt(q / (n - 1)) / (sv / n);
    }
    return out;
  }

  /* distância do fechamento à média: c ÷ média − 1 */
  function distancia(c, m) { return c.map((x, i) => (m[i] == null ? null : x / m[i] - 1)); }

  const medias = { sma, ema, wma };
  return { dd, sma, ema, wma, medias, rsi, obv, obvFluxo, obvVolatilidade, distancia };
});
