# Painel Big Techs

Site gratuito, que se atualiza sozinho, com o **histórico completo** (desde o IPO) das big techs e de ações de IA e computação:

- **Drawdowns:** distância do recorde, as maiores quedas da história, o tempo de queda e o tempo de recuperação.
- **Ciclos:** fases de alta e baixa pela regra de 15%, 20% ou 30%; duração e retorno típicos; onde a fase atual está em relação às anteriores; retorno móvel de 12 meses e de 3 anos.
- **Sazonalidade:** tabela ano a ano **mensal, bimestral e trimestral**, com média, mediana e % de vezes positivo, em retorno absoluto ou contra uma referência (QQQ, SPY, SMH). Inclui o filtro "desde o ano X".
- **Correlações:** matriz por janela (1, 3, 5 e 10 anos, ou todo o período), correlação móvel com as referências e a **correlação média entre as big techs**, um termômetro de "comportamento de manada".

![Exemplo de drawdowns (dados sintéticos)](docs/exemplo-drawdowns.png)

> As imagens deste README foram geradas com **dados sintéticos** (`--demo`). O site publicado usa cotações reais.

---

## Como colocar no ar (cerca de 15 minutos, tudo grátis)

Você só precisa de uma conta gratuita no [GitHub](https://github.com).

### Opção A: pelo navegador, sem instalar nada

1. No GitHub, clique em **New repository**. Use o nome `painel-bigtechs`, marque **Public** e clique em **Create repository**.
2. Na página do repositório vazio, clique em **uploading an existing file**. Arraste **todo o conteúdo** desta pasta (`config.json`, `requirements.txt`, `README.md` e as pastas `scripts`, `site` e `docs`) e clique em **Commit changes**.
3. A pasta `.github` costuma ficar oculta no computador, então crie o arquivo de automação à mão:
   **Add file → Create new file**. No nome, digite `.github/workflows/atualizar.yml`. Cole o conteúdo do arquivo de mesmo nome deste pacote (abra-o num editor de texto) e clique em **Commit changes**.
4. Vá em **Settings → Pages**. Em **Build and deployment → Source**, escolha **GitHub Actions**.
5. Vá na aba **Actions**. Se aparecer um aviso, clique para ativar os workflows. Abra **Atualizar dados e publicar** e clique em **Run workflow**.
6. Depois de 3 a 5 minutos, o endereço aparece em **Settings → Pages**:
   `https://SEU-USUARIO.github.io/painel-bigtechs/`

### Opção B: com git (se você já usa)

```bash
cd painel-bigtechs
git init -b main
git add .
git commit -m "Painel Big Techs"
git remote add origin https://github.com/SEU-USUARIO/painel-bigtechs.git
git push -u origin main
```

Depois siga os passos 4 a 6 da opção A.

---

## Como funciona a atualização automática

- Todo **dia útil às 19h17 (Brasília)**, depois do fechamento de Nova York, o GitHub Actions:
  1. baixa o histórico diário ajustado (dividendos e desdobramentos) de todos os ativos;
  2. recalcula todas as métricas;
  3. publica o site de novo.
- Fontes, nesta ordem:
  1. Yahoo Finance via `yfinance`;
  2. Yahoo Finance via o endpoint direto `v8/chart`;
  3. **Tiingo**, se você configurar a chave (veja abaixo);
  4. o último dado salvo. Nesse caso, o site mostra um aviso no topo.
- O GitHub às vezes atrasa execuções agendadas em alguns minutos. Você pode rodar na hora quando quiser, pela aba **Actions → Run workflow**.
- Repositórios públicos têm agendamentos desligados após 60 dias sem atividade. Para evitar isso, o workflow faz um pequeno commit por mês em `status/`.

### Fonte reserva (opcional, recomendado): Tiingo

O Yahoo não tem API oficial e às vezes bloqueia acessos automáticos. Para ter um plano B gratuito:

1. Crie uma conta grátis em [tiingo.com](https://www.tiingo.com) e copie o seu **API Token**.
2. No repositório, vá em **Settings → Secrets and variables → Actions → New repository secret**.
   - Nome: `TIINGO_API_KEY`
   - Valor: o token.

A Tiingo cobre ações e ETFs dos EUA, mas não índices (símbolos com `^`).

---

## Personalizar (`config.json`)

| Campo | O que faz |
|---|---|
| `tickers` | Lista de ações. Use o símbolo do Yahoo Finance: `NVDA`, `PETR4.SA` (B3), `ASML` etc. |
| `benchmarks` | Referências usadas na sazonalidade relativa e nas correlações (ex.: `QQQ`, `SPY`, `SMH`, `BOVA11.SA`). |
| `main_benchmark` | Referência da correlação e do beta na aba Resumo. |
| `start` | `"max"` para todo o histórico, ou uma data como `"2000-01-01"`. |
| `cycle_thresholds` | Limiares dos ciclos (ex.: `[0.15, 0.20, 0.30]`). |
| `currency` | Moeda exibida (`"US$"`). Também pode ser definida por ativo, por exemplo `{"symbol": "PETR4.SA", "name": "Petrobras", "currency": "R$"}`. |
| `yahoo` / `tiingo` | (opcional, por ativo) símbolo diferente em cada fonte, por exemplo `{"symbol": "BRK-B", "tiingo": "brk-b"}`. |

Editou e salvou (commit)? O site se reconstrói sozinho em poucos minutos.

---

## Ver no seu computador (opcional)

```bash
pip install -r requirements.txt
python scripts/build_data.py           # dados reais
# ou: python scripts/build_data.py --demo   (dados sintéticos, só para ver o visual)
python -m http.server 8000 -d site
```

Depois, abra `http://localhost:8000`. Abrir o `index.html` com duplo clique não funciona, porque o navegador bloqueia a leitura dos arquivos de dados direto do disco.

## Compartilhar

O endereço do GitHub Pages é público. Os links guardam a aba e o ativo, por exemplo:
`https://SEU-USUARIO.github.io/painel-bigtechs/#aba=ciclos&ativo=NVDA`

---

## Sobre os dados (leia antes de divulgar amplamente)

- O Yahoo Finance não oferece API oficial. O `yfinance` usa endpoints públicos que podem mudar ou limitar acessos, e os termos do Yahoo falam em **uso pessoal**.
- Este projeto **não guarda as cotações brutas no repositório**: elas ficam só no cache privado do GitHub Actions. O site exibe gráficos e métricas derivadas.
- Para uma página educacional, sem fins comerciais, essa é a prática comum de projetos pessoais. Se quiser **monetizar ou distribuir em larga escala**, use uma fonte licenciada para redistribuição (por exemplo, um plano comercial da Tiingo). Isto não é orientação jurídica.
- Material educacional. Não é recomendação de investimento.

## Estrutura

```
config.json                  ← lista de ativos e parâmetros
requirements.txt
scripts/build_data.py        ← baixa os dados e calcula todas as métricas
site/index.html, app.js, style.css
site/vendor/echarts.min.js   ← biblioteca de gráficos (Apache-2.0), embutida
site/data/                   ← gerado automaticamente (não versionado)
.github/workflows/atualizar.yml
```

## Problemas comuns

- **A etapa "Baixar dados" falhou:** o Yahoo pode ter bloqueado temporariamente. Rode de novo mais tarde ou configure a Tiingo.
- **O site dá 404:** confira se **Settings → Pages → Source** está em **GitHub Actions** e se a primeira execução terminou (ícone verde em Actions).
- **A atualização diária parou:** na aba **Actions**, abra o workflow e clique em **Enable workflow**.
- **Um ativo não aparece:** confira se o símbolo existe no Yahoo Finance (pesquise em finance.yahoo.com).
