# Roteiro do projeto

Memória do projeto entre conversas. Cada fase começa lendo este arquivo e `ARQUITETURA.md`.

## Decisões já tomadas

- **Ordem:** Análise Técnica (Fase 2) antes de Ciclos por eventos (Fase 3).
- **OBV:** fica fora da tabela de preços-alvo; mostra só a comparação com mínima, máxima e média históricas. Drawdown, médias móveis e RSI têm preço-alvo.
- **Eleições EUA:** "Presidenciais" (padrão) e "Presidenciais + Midterms". Não há 1º e 2º turno nos EUA. Nas midterms, o vencedor é o partido que ficou com Câmara e Senado.
- **Direita/Esquerda/Centro:** rótulo em arquivo editável, revisado pelo dono do projeto antes de publicar.
- **Filtros 24h e 7d:** só para cripto (dados horários). Ações começam em 30d.
- **Logotipos:** Logo.dev (chave publicável em `config.json`), com crédito no rodapé; sem chave, o site mostra as iniciais do ticker.
- **B3:** histórico pelo Yahoo (`.SA`); brapi só para logotipos.

## Fases

| Fase | Entrega | Situação |
|---|---|---|
| 0 | Site no ar com cotações reais | Feita (14/11/2026) |
| 1 | Estrutura para expandir: universo por mercado/segmento, fontes com reserva, base OHLCV, validações, indicadores em módulos, testes, logotipos | Feita (14/11/2026) |
| 2 | Aba "Análise Técnica": Drawdown, Médias Móveis (SMA/EMA/WMA 50/100/200/250), RSI 14, OBV; tabelas "Agora × histórico" e "Preços-alvo"; filtro D/S/M | Feita (16/11/2026) |
| 3 | Ciclos por eventos: recessões EUA/Brasil, eleições EUA/Brasil, crises globais; Ciclo BTC como "Em desenvolvimento" | A fazer |
| 4 | Mais segmentos dos EUA, B3, botão Nominal/Real (CPI e IPCA) | A fazer |
| 5 | Cripto (Binance), filtros 24h/7d, indicador Bitcoin Halving Cycle Profit | A fazer |
| 6 | Design: mockup aprovado, tons de verde, animações, zoom, legenda clicável | A fazer |
| 7 | Aba Fundamentalista (SEC e CVM) | A fazer |

## Regras da Análise Técnica (Fase 2)

- **Preço:** fechamento de tela (`close`, ajustado só por desdobramentos), arredondado em 7 algarismos. O drawdown do Resumo usa o mesmo preço. Retornos, ciclos e sazonalidade seguem em `adj_close`.
- **Barras:** D, S (semana terminada na sexta) e M; fechamento = último pregão; volume = soma. A barra em andamento usa o último fechamento.
- **Preço-alvo:** fechamento necessário no próximo pregão. Se o próximo pregão cai na mesma semana ou mês da última barra, ele substitui o fechamento dela; se não, abre uma barra nova. O próximo pregão vem de `pipeline/calendario.py` (`calendario` do mercado: `nyse`, `dias_uteis` ou `24x7`).
- **Conferência:** cada alvo é recalculado do zero antes de publicar (`_Alvos.add`); reprovado sai sem preço e a execução avisa. RSI que pediria preço negativo sai como "fora de alcance em 1 pregão".
- **Curvas no site:** o pipeline publica barras e números; `site/indicadores.js` desenha as curvas. `tests/test_paridade_js.py` compara as duas implementações e o site confere o último ponto de cada curva contra o "agora" do pipeline.
- **OBV:** três medidas (nível, saldo de volume em 20 barras, volatilidade em 20 barras), sem preço-alvo.
- **Pior drawdown do ano:** mínimo da curva de drawdown em cada ano; a média exclui o ano em andamento e o ano inicial quando os dados começam depois de 10 de janeiro.

## Conferido em 16/11/2026 (Fase 2)

- Revisão independente (agente que não viu o código) recalculou NVDA, MSFT, TSLA, META e SPY em D, S e M a partir da base: 134.820 comparações, 1 diferença, na 6ª casa da coluna de variação (corrigida: a variação agora sai do preço publicado). Os 804 preços-alvo reproduzem o nível pedido e batem com busca por bisseção.
- SMA, EMA, WMA e RSI idênticos à TA-Lib; OBV difere só pela constante inicial.
- Varredura no navegador: 15 ativos × 3 períodos × 3 tipos de média sem inconsistência entre curvas e tabelas.

## Conferido em 14/11/2026

- Tiingo: histórico completo bate com o Yahoo (diferença mediana do preço ajustado abaixo de 0,002% em AAPL, NVDA, MSFT). Começa mais tarde em AMD (1983) e MU (1989) e ajusta TSM de outro jeito antes de 2003; nesses casos a validação mantém a base do Yahoo.
- Twelve Data: fechamentos idênticos aos da base; emenda dos últimos pregões funcionou.
- Ensaio com o Yahoo desligado (`PAINEL_PULAR_FONTES=yahoo`): 15 de 15 ativos pela Tiingo.

## Pendências do dono do projeto

- [x] Chaves da Tiingo e da Twelve Data salvas como segredos (14/11/2026).
- [x] Chave publicável da Logo.dev em `config.json` (14/11/2026).
- [x] Repositório privado `MercadoFinBigTech-dados` + segredo `DADOS_TOKEN` (14/11/2026). O token vence em um ano e precisa ser renovado.
- [ ] Confirmar a definição de "volatilidade do OBV" adotada na Fase 2 (desvio-padrão da variação do OBV em 20 barras ÷ volume médio das mesmas barras).

## Especificação guardada: Bitcoin Halving Cycle Profit (Fase 5)

Overlay só de tempo (não usa preço nos cálculos), em JavaScript com ECharts.

- Halvings (UTC): 2012-11-28 15:24, 2016-07-09 16:46, 2020-05-11 19:23, 2024-04-20 00:09; 5º projetado 2028-04-10 00:00 (configurável); 6º = 5º + 208 semanas (só como limite).
- Parâmetros: `profitStartWeeks` 40, `profitEndWeeks` 80, `dcaStartWeeks` 110, `dcaIntervalWeeks` 12; liga/desliga por camada.
- Zona de lucro: fundo verde RGB(0,255,8) entre H+40 e H+80 semanas, alfa de 0,10 a 0,45 conforme o progresso.
- Marcadores por ciclo: halving (linha tracejada laranja RGB(255,123,0), rótulo "Nth Halving / MM/DD/YYYY", "(Projected)" se futuro); início do lucro (pontilhada verde, "Profit START +40w"); fim do lucro (pontilhada vermelha RGB(255,0,0), "Profit END +80w"); DCA (rótulo amarelo "→ DCA +110w" e pontos a cada 12 semanas até o próximo halving, de amarelo RGB(251,226,0) a verde RGB(38,255,0) nos 5 primeiros).
- Eixo Y: halving dentro de um candle existente ancora rótulos de cima na máxima e os de baixo na mínima; halving futuro ancora tudo no último fechamento.
