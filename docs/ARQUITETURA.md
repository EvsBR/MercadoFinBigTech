# Arquitetura

## Caminho dos dados

```
universo/*.json ──► fontes (Yahoo → Tiingo → Twelve Data) ──► validação ──► base OHLCV (data/base)
                                                                               │
                                              site/data/*.json ◄── indicadores ┘
```

Tudo roda em `python -m pipeline.construir`, chamado pelo GitHub Actions todo dia útil.

## Pastas

| Pasta | O que tem |
|---|---|
| `universo/` | Quais ativos existem. `mercados.json` lista os mercados; cada mercado tem um arquivo com referências e segmentos. |
| `pipeline/universo.py` | Lê e confere o universo. Erro de preenchimento interrompe a atualização com mensagem clara. |
| `pipeline/fontes/` | Um arquivo por fonte de cotações, todos com o mesmo contrato (`base.py`). |
| `pipeline/base.py` | Base em disco: um CSV por ativo com abertura, máxima, mínima, fechamento, fechamento ajustado, volume, dividendo e desdobramento. |
| `pipeline/validacao.py` | Conferências que impedem dado ruim de entrar na base e no site. |
| `pipeline/indicadores/` | Um arquivo por indicador. `__init__.py` tem o registro e o manifesto. `tecnica.py` faz a Análise Técnica. |
| `pipeline/calendario.py` | Próximo pregão de cada mercado (feriados da NYSE, dias úteis ou 24x7). |
| `pipeline/construir.py` | Orquestra tudo e escreve `site/data/`. |
| `site/` | Site estático (HTML, CSS, JS, ECharts). `app.js` cuida das abas; `tecnica.js`, da Análise Técnica. Todo número de tabela vem do pipeline. `indicadores.js` só desenha as curvas da Análise Técnica a partir das barras, com as mesmas fórmulas do pipeline (conferidas por teste). |
| `tests/` | Testes automáticos (`python -m pytest`). |

## Como a atualização resiste a falhas

1. **Ordem de fontes por mercado.** Para cada ativo, tenta a primeira fonte; se falhar ou for reprovada na validação, tenta a seguinte.
2. **Fontes completas e de emenda.** Yahoo e Tiingo devolvem o histórico inteiro ajustado. A Twelve Data só completa os últimos pregões de uma base que já existe (`base.emendar`), inclusive reescalando a base se houve desdobramento.
3. **Base salva.** Se nenhuma fonte responder, o site usa a base e mostra um aviso com a data do último dado.
4. **Trava de publicação.** Se menos da metade dos ativos tiver dados, o site não é alterado e a execução falha (o GitHub avisa por e-mail).
5. **Duas camadas de backup da base.** Cache do GitHub Actions (automático) e, opcionalmente, um repositório privado com histórico versionado (`DADOS_TOKEN`).
6. **Relatório.** Cada execução publica a tabela "Saúde dos dados" na página do Actions e grava `site/data/saude.json`.

## Validações

Bloqueiam a tabela nova (o pipeline tenta a próxima fonte): menos de 30 pregões; último pregão com mais de 10 dias; datas repetidas, fora de ordem ou no futuro; preço não positivo; volume negativo; salto recente com cara de desdobramento não ajustado; histórico mais curto ou mais antigo que o da base.

Só avisam: máxima/mínima incoerentes; variações diárias acima de 60% no histórico; intervalos sem pregão acima de 15 dias; retornos diferentes dos que estavam na base.

## Arquivos que o site lê

| Arquivo | Conteúdo |
|---|---|
| `data/indice.json` | Mercados, segmentos, manifesto de indicadores, configurações gerais. |
| `data/<mercado>/<segmento>/meta.json` | Tabela de resumo do segmento (ações e referências). |
| `data/<mercado>/<segmento>/correlations.json` | Matrizes de correlação e média entre pares. |
| `data/<mercado>/ativos/<ATIVO>.json` | Um bloco por indicador (`series`, `drawdown`, `cycles`, `seasonality`, `corr`) e `stats`. |
| `data/<mercado>/ativos/<ATIVO>.tecnica.<D\|S\|M>.json` | Análise Técnica de um período: barras (`d`, `c`, `v`), `drawdown`, `mm`, `rsi`, `obv` com medidas e preços-alvo. O site baixa só o período escolhido. |
| `data/saude.json` | Fonte usada, datas e avisos de cada ativo. |

## Receitas

**Adicionar uma ação:** uma linha em `universo/eua.json`, dentro do segmento: `{"id": "NFLX", "nome": "Netflix"}`.

**Adicionar um segmento:** um bloco novo em `segmentos` com `id`, `nome` e `ativos`. O mesmo ativo pode estar em mais de um segmento.

**Adicionar um mercado:** uma entrada em `mercados.json` (id, nome, moeda, arquivo, fontes, referência principal) e o arquivo do mercado.

**Adicionar uma fonte:** um arquivo em `pipeline/fontes/` com `NOME`, `COMPLETA`, `PAUSA`, `disponivel(env)` e `baixar(ticker, env)`; uma linha em `FONTES`; o nome na lista `fontes` do mercado.

**Adicionar um indicador:** um arquivo em `pipeline/indicadores/` com `ID`, `NOME`, `CHAVE`, `VERSAO` e `calcular(ctx)`; incluir em `POR_ATIVO`; um teste com caso calculado à mão; o desenho correspondente em `site/app.js`.

## Convenções

- `open/high/low/close` da base são ajustados por desdobramento; `adj_close` também por proventos. Indicadores de retorno usam `adj_close`; drawdown e Análise Técnica usam `close` (`util.preco_tela`).
- Um indicador pode devolver `arquivos` além de `dados`: blocos grandes gravados à parte, que o site só baixa quando precisa.
- Nomes de arquivos, funções e mensagens em português; chaves dos JSON do site em inglês (herdadas da primeira versão).
- Nenhuma cotação bruta vai para o repositório público: `data/` e `site/data/` estão no `.gitignore`.
