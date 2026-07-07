Fechado, Lucas. Vou fazer a pesquisa de design dos bancos primeiro (você me pediu pra nunca inventar — então vou olhar como Goldman, JP Morgan e Morgan Stanley realmente apresentam dashboards antes de especificar o seu), depois escrevo o roteiro-mestre completo das 6 semanas, e por fim te entrego o `requirements.txt` atualizado em separado.A busca me deu o conteúdo/estrutura de research reports, mas preciso especificamente do vocabulário visual — cores, tipografia, densidade de dados dos dashboards. Deixa eu buscar o lado de design/UI, que é o que importa pro seu front-end.Tenho o que precisava sobre a linguagem visual institucional. Agora vou parar de pesquisar e escrever. Tenho tudo: arquitetura dos seus arquivos, stack travada, princípios de design institucional (densidade de dados, hierarquia tipográfica, paleta navy + acentos, "cada pixel se justifica"), e as decisões de escopo que a gente cravou.

Uma observação de honestidade intelectual antes do roteiro: os resultados de design que achei são majoritariamente de *templates* de dashboard e blogs de agência, não os manuais internos de design do Goldman/JPM (esses são proprietários e não públicos). Então a especificação visual que vou te dar é uma **síntese fundamentada dos princípios** que esses reports e sistemas institucionais realmente usam — o benchmark de UI financeira densa é o princípio do Bloomberg Terminal: cada pixel se justifica, informação estruturada com precisão, hierarquia conquistada por importância e não por decoração — e não uma cópia de um arquivo interno que eu não tenho acesso. Isso é defensável numa entrevista; "copiei o design system secreto do Goldman" não seria.

Vou escrever o roteiro agora. Ele é longo (é um roteiro-mestre de 6 semanas ponta a ponta), então respira que vem coisa.

---

# 🏛️ ROTEIRO-MESTRE — DCF Automatizado v1.0

## Do zero ao sistema institucional | 01/07/2026 → 06/08/2026

---

## ⚠️ Leia isto antes de tudo — as 4 decisões que já estão cravadas

Antes das semanas, quero deixar explícito o que a gente decidiu nas perguntas anteriores, porque **essas decisões são a espinha dorsal de todo o resto** e você não pode mudá-las no meio sem quebrar o cronograma:

**Decisão 1 — Escopo enxuto e proposital.** A v1.0 entrega **DIRR3 impecável + MGLU3 como prova de universalidade**. VALE3, PETR4 e ITUB4 ficam explicitamente marcados como v1.5. Isso não é preguiça — é estratégia. A arquitetura de duas trilhas (financeira/não-financeira) fica **construída e documentada**, mas você só valida contra dados reais dois setores não-financeiros que você domina. Quando um avaliador da InFinance abrir seu projeto, ele vê profundidade, não amplitude quebrada.

**Decisão 2 — Front-end: Streamlit interativo + export HTML estático.** O motor de cálculo em Python é a fonte única da verdade. O Streamlit lê esse motor e renderiza a interface interativa (input de premissas com slider, dashboards, preview das abas do Excel). Quando você quiser mandar o resultado pra alguém sem pedir pra rodar Python, você exporta um HTML estático standalone. Você **não duplica cálculo em JavaScript** — isso seria suicídio de manutenção.

**Decisão 3 — Data-trava 06/08 é inegociável.** Por isso o roteiro tem "válvulas de escape" a cada semana: se algo atrasar, eu marco explicitamente o que pode ser cortado sem comprometer a entrega mínima defensável.

**Decisão 4 — O fluxo de trabalho tem 3 atores, sempre nesta ordem.** Isso é o coração do roteiro e preciso que você internalize:

> **VOCÊ (humano)** faz o trabalho manual e o julgamento → **VOCÊ me envia a "mensagem-gatilho"** (uma aba pronta em cada semana) → **EU (Claude)** gero o prompt cirúrgico → **VOCÊ cola o prompt no Codex** → **O CODEX** escreve/edita o código → **VOCÊ testa** com o roteiro de teste do fim da semana.

Cada semana abaixo tem exatamente esta estrutura: **(A) O que você faz como humano** · **(B) O que a IA/Codex faz** · **(C) 📨 A mensagem que você me envia** (a aba pronta pra copiar) · **(D) 🧪 Roteiro de teste do fim da semana**.

---

## 📌 ADENDO (02/07/2026) — Power BI + Backlog Pós-v1.0

> Este bloco foi acrescentado depois do roteiro original, sem alterá-lo. Onde houver
> conflito, valem `ROTEIRO.md` (spec técnica/contratos) e `CONTEXT.md` (estado atual)
> como fontes autoritativas — este arquivo é o roteiro-mestre narrativo/histórico.

**Contexto:** decidimos que o projeto deve tocar os três "projetos que impressionam
recrutador" (Dashboard financeiro, Company Valuation Model, Budget vs Actual) e usar
**Power BI**, que é o que times de finanças reconhecem. A regra para não quebrar a
arquitetura: separar *cálculo* de *apresentação*.

**Ajuste da Decisão 2 (front-end).** O Streamlit continua sendo o front-end interativo
(ajustar premissa → motor recalcula). Somamos a ele um **painel Power BI** como camada
de *apresentação executiva*. O motor Python permanece a **fonte única de verdade**: ele
grava tabelas planas (*long*, star-schema) em `outputs/bi/`, e o Power BI só se conecta
a elas e desenha visuais. **Zero cálculo de valuation em DAX.** Streamlit e Power BI não
competem — trabalho do analista vs. entregável de apresentação.

**O que entra AINDA na v1.0 (é decisão estrutural, não feature nova):**
- `exportador_bi.py` gerando as tabelas planas em `outputs/bi/` (Semana 5, junto do Excel).
- Excel "nível Direcional": **fórmulas nativas** nas células de cálculo (não valores
  colados) + **convenção de cor de input** (azul = premissa, preto = fórmula, verde =
  link). Deixar isso pra depois seria retrabalho no exportador.

**O que é BACKLOG PÓS-v1.0 (só depois da tag `v1.0`) — detalhe na Seção 7 do `ROTEIRO.md`:**
1. **Painel Power BI (`.pbix`)** em `powerbi/`, sobre as tabelas da v1.0 (alvo v1.5).
2. **Comparáveis / CCA** — múltiplos de peers, fecha o "DCF + CCA" (alvo v2.0).
3. **Projetado vs. Realizado** — análise de variância/FP&A; é uma lente nova sobre
   DIRR3/MGLU3, não um setor novo (compatível com a regra de ouro do escopo) (alvo v2.0).
4. **Nota de research em PDF** de 1 página (alvo v3.0).
5. **Prova visual** no README (screenshots/GIF + case study DIRR3 vs. InFinance).

O fluxo de 3 atores (Decisão 4) **não muda**: Humano dispara a mensagem-gatilho → Claude
Code lê `CONTEXT.md` + `ROTEIRO.md` e gera o prompt cirúrgico → Codex implementa → Humano
testa e atualiza o `CONTEXT.md`.

---

## 🎨 ESPECIFICAÇÃO DE FRONT-END — a "cara Goldman/JPM/Morgan Stanley"

Isto vale pro projeto inteiro e você vai referenciar em várias semanas, então li primeiro. Baseei nos princípios reais de UI institucional financeira que pesquisei.

### Os 6 princípios que definem o visual institucional

**Princípio 1 — Densidade de dados com hierarquia, não minimalismo consumer.** O erro do amador é achar que "profissional = limpo e vazio". Errado. A tentação é simplificar agressivamente, esconder os números, substituir clareza por visuais "amigáveis" — e isso geralmente está errado. O seu público (analista, avaliador InFinance) veio pelos números. A tela pode ser densa, desde que a **hierarquia visual** guie o olho: o que é decisão (Target Price, Recomendação) fica grande e no topo; o que é suporte (schedules, premissas) fica menor e agrupado.

**Princípio 2 — Paleta institucional: navy profundo + cinzas + um acento.** O padrão de fundos e bancos é fundo escuro azulado (não preto puro) ou branco muito clean, com **azul-marinho como cor âncora** e um único acento para ação/destaque. Semântica de cor obrigatória em finanças: **verde = ganho/upside, vermelho = perda/downside**, sempre — e nunca use verde/vermelho pra decoração, só pra sinal. Sugestão de paleta concreta pro seu app:

- Fundo principal: `#0A1628` (navy quase-preto) ou `#FFFFFF` (modo claro institucional)
- Superfície de cards: `#0F1E33` / `#F7F9FC`
- Texto primário: `#E8EEF7` / `#0A1628`
- Azul âncora (headers, títulos): `#1B4F8C`
- Acento (botões, destaques): `#C9A227` (dourado sóbrio, tipo Goldman) ou `#0EA5E9` (azul elétrico)
- Verde (upside): `#16A34A` · Vermelho (downside): `#DC2626`

**Princípio 3 — Tipografia com números tabulares.** Isto é o detalhe que separa "parece profissional" de "parece um trabalho de faculdade". Números financeiros precisam de fonte **monoespaçada ou com "tabular figures"** pra que as casas decimais alinhem em coluna. Sugestão: títulos e texto em **Inter** ou **IBM Plex Sans**; todos os números (tabelas, valores) em **IBM Plex Mono** ou **Roboto Mono**. Dashboards de investimento institucionais usam uma fonte sans para legibilidade e uma fonte mono para a precisão dos dados financeiros.

**Princípio 4 — Cada pixel se justifica.** Arquitetura de informação ultradensa onde cada pixel conquista seu lugar. Sem ícone decorativo, sem gradiente gratuito, sem sombra fofa. Se um elemento não carrega informação ou não guia uma ação, ele sai.

**Princípio 5 — Espaçamento consistente e bordas sóbrias.** Sinais de confiança em UI financeira são específicos: sistemas de espaçamento consistentes, paletas de cor propositais, iconografia que se justifica, e zero ruído visual. Grid de 8px, bordas finas de 1px (`#1E3A5F` no escuro), cantos levemente arredondados (4-6px, não 20px "bolha").

**Princípio 6 — Estado de cada número é auditável.** Todo output importante mostra sua origem. O Target Price tem um tooltip ou nota de rodapé com o WACC e o g que o geraram. Isso é o que o Guia de Valuation chama de tornar o raciocínio "auditável por qualquer leitor".

### A estrutura de navegação do app (as abas do Streamlit)

O app tem uma **sidebar fixa à esquerda** (navegação) e uma **área de conteúdo à direita**, exatamente como os dashboards institucionais que pesquisei. A sidebar tem 6 seções, que espelham a jornada do analista:

1. **🏠 Overview** — ticker selecionado, preço atual, recomendação, target price. A "capa" viva.
2. **📊 Histórico** — Módulo 2: as tabelas e gráficos históricos (âncora intelectual).
3. **✍️ Premissas** — Módulo 3: onde você INSERE os dados. Campos + sliders + histórico ao lado.
4. **⚙️ Valuation** — Módulo 4: WACC, FCFF, VT, EV → Target Price, com decomposição.
5. **📈 Análise** — Módulo 5: Football Field, Waterfall, sensibilidades, histórico vs. projetado.
6. **📑 Excel Preview** — as 7 abas do Excel renderizadas dentro do app + botão de download.

Guarde esta estrutura. Ela aparece a partir da Semana 5.

---

Agora as semanas. O calendário real: hoje é **quarta, 01/07**. Você tem 1-2h/dia irregulares. Por isso, **cada semana é dividida em "blocos de sessão"** de ~1-2h, pra você conseguir encaixar. Não precisa fazer tudo num dia.

---

# 📅 SEMANA 0 (parcial) — 01/07 a 06/07 | Fundação + Coleta inicial

> **Por que "Semana 0":** você começou hoje (01/07), no meio da semana. Então esta primeira janela é curta e junta o que no plano antigo eram a Semana 1 (infra) e o começo da Semana 2 (coleta). É puxado, mas a infra é rápida com o Codex. Meta: **repo no ar + coletor da CVM puxando DIRR3 e MGLU3 corretamente.**

### (A) O que VOCÊ faz como humano

**Bloco 1 (~1h30) — Pré-requisitos e repositório.** Instala (se ainda não tem) Python 3.11+, VS Code, Git e o Codex CLI. Confirma que o Codex responde: abre o terminal do VS Code, digita `codex`, ele responde. Cria a pasta `dcf-automatizado`, abre no VS Code. Cria o repo no GitHub (público, mesmo nome, **sem** README). Conecta: `git init`, `git remote add origin <url>`. Cria e ativa a venv (`python -m venv .venv` e ativa). Faz upload do Excel da Direcional pra dentro da pasta temporariamente.

**Bloco 2 (~1h) — Roda a infra gerada pelo Codex e valida.** Depois que o Codex criar a estrutura (via prompt que eu gero), você roda `pip install -r requirements.txt`, confirma que instalou tudo, e dá o primeiro `git push`. Confere no GitHub que a estrutura de pastas apareceu.

**Bloco 3 (~1h30) — Valida o coletor da CVM.** Depois que o Codex criar o `coletor_cvm.py`, você roda ele pra **DIRR3 e MGLU3**. Abre os JSONs gerados em `data/raw/cvm/` e confere: a Receita Líquida e o Lucro Líquido dos últimos 3 anos batem com o que você vê no site de RI da Direcional e da Magalu (ou no Investidor10/Status Invest)? Confere o `_meta.json`: as duas aparecem como **não-financeiras**? Se algum número vier errado, invertido de sinal ou ausente, você anota exatamente: qual empresa, qual campo, qual valor veio, qual era o esperado.

### (B) O que a IA/Codex faz

Cria toda a estrutura de pastas dos 5 módulos (conforme a árvore do README), o `CONTEXT.md` inicial, `.gitignore`, `.env.example`, `requirements.txt`, `config/setores.json` (com as duas categorias), `config/mapeamento_cvm.json` (códigos de conta CVM → nomes padronizados), `config/parametros.json`, os dois templates de premissas (`template_naofinanceiras.json` com os **8 campos individuais** `crescimento_receita_ano1..8`, margem e capex também individuais, e `template_financeiras.json`), e move o Excel pra `tests/fixtures/`. Depois, cria o `coletor_cvm.py` universal (busca código CVM pelo ticker, coleta DFP/ITR, mapeia contas, loga campos não mapeados sem quebrar, detecta tipo financeira/não-financeira) e roda pra DIRR3 e MGLU3.

### (C) 📨 A mensagem que você me envia

> Copie e cole isto pra mim quando tiver feito o Bloco 1. Vou gerar **dois prompts** de uma vez (infra + coletor), porque nesta semana curta faz sentido você já sair com os dois:

```
Claude, estou na Semana 0 do roteiro do DCF Automatizado (fundação + coleta).
Já fiz: repo criado no GitHub, pasta local conectada, venv ativada, Excel da 
Direcional na pasta.

Preciso de DOIS prompts para o Codex, em sequência:

PROMPT 1 (Infraestrutura): que instrua o Codex a criar toda a estrutura de pastas 
dos 5 módulos exatamente como no README do projeto, o CONTEXT.md inicial com 
objetivo/stack/convenções, .gitignore, .env.example, requirements.txt, 
config/setores.json (categorias financeira e não-financeira), 
config/mapeamento_cvm.json (contas principais: Receita Líquida, CPV, EBIT, D&A, 
Resultado Financeiro, LL, Caixa, Dívida CP/LP, PL), config/parametros.json 
(horizonte 8 anos, thresholds do checklist), os DOIS templates de premissas com 
crescimento/margem/capex em 8 campos individuais por ano, e mover o Excel para 
tests/fixtures/Direcional_DIRR3_referencia.xlsx.

PROMPT 2 (Coletor CVM): que instrua o Codex a criar src/coleta/coletor_cvm.py 
universal (busca código CVM pelo ticker via API de cadastro, coleta DFP e ITR, 
mapeia contas pelo mapeamento_cvm.json, loga campos não mapeados sem quebrar, 
detecta financeira x não-financeira pela classificação CVM, trata todos os erros 
de API sem quebrar silenciosamente) e roda ao final para DIRR3 e MGLU3 exibindo 
resumo comparativo.

Considere que meu escopo v1.0 é só DIRR3 + MGLU3 (não os 5 tickers antigos).
Gere os prompts prontos para colar no Codex.
```

### (D) 🧪 Roteiro de teste do fim da Semana 0

Marque cada item. **Todos precisam passar** pra você seguir:

1. `git push` funciona sem erro e o GitHub mostra a estrutura completa de pastas.
2. `pip install -r requirements.txt` roda sem erro (todas as libs instalam).
3. Existe `config/mapeamento_cvm.json` com pelo menos Receita, CPV, EBIT, LL, Caixa, Dívida.
4. O template não-financeiro tem os campos `crescimento_receita_ano1` até `crescimento_receita_ano8` (8 campos separados, não um só).
5. `python src/coleta/coletor_cvm.py` gera JSON pra DIRR3 e MGLU3 em `data/raw/cvm/`.
6. **Teste de olho humano (o mais importante):** a Receita Líquida e o LL de DIRR3 e MGLU3 dos últimos 3 anos batem com o site de RI / Status Invest. Se não bater, descreve o erro e me pede o prompt de correção.
7. Os dois `_meta.json` marcam as empresas como **não-financeiras**.

**Válvula de escape:** se o coletor da CVM der muito trabalho (a API da CVM é notoriamente chata), o mínimo aceitável pra fechar a semana é: infra 100% + coletor puxando **só DIRR3** corretamente. MGLU3 pode escorregar pro início da Semana 1.

---

# 📅 SEMANA 1 — 07/07 a 13/07 | Coleta completa + Métricas históricas

> **Meta:** fechar o Módulo 1 (adicionar mercado + macro ao coletor da CVM) e entregar o Módulo 2 (todas as métricas históricas calculadas e um painel de texto/tabela que serve de âncora pras premissas).

### (A) O que VOCÊ faz como humano

**Bloco 1 (~1h) — Valida coletor de mercado.** Depois que o Codex criar `coletor_mercado.py`, roda pra `DIRR3.SA` e `MGLU3.SA`. Confere: o preço atual bate com o que você vê no Google agora? O número de ações fully diluted é plausível? O beta veio preenchido?

**Bloco 2 (~1h) — Valida coletor macro.** Roda `coletor_macro.py`. Confere: a Selic atual bate com a realidade (você sabe a Selic de hoje)? O IPCA e as projeções Focus vieram? Se algum número macro vier absurdo, anota.

**Bloco 3 (~2h, o mais importante da semana) — Valida as métricas históricas.** Depois que o Codex criar `metricas_historicas.py`, roda pra DIRR3. Abre o resultado e confere com olho de analista: o ROIC histórico faz sentido pro que você sabe da Direcional? As margens (bruta, EBITDA, líquida) batem com a sua análise do trainee? O DSO/DIO/DPO tá coerente com uma construtora (construtora tem estoque e recebível altíssimos — DIO e DSO enormes são normais)? Se algo destoar do que você conhece, é sinal de que o cálculo ou o mapeamento de contas tem bug.

### (B) O que a IA/Codex faz

Cria `coletor_mercado.py` (yfinance: preço, histórico 5 anos, ações fully diluted, beta rolling 60 meses, market cap, dividend yield, e o T-Bond 10Y via `^TNX`), `coletor_macro.py` (python-bcb: Selic, IPCA, CDI, TJLP, projeções Focus 1 e 2 anos), `limpeza.py` (normaliza sinais — despesas negativas, separa dívida financeira de NIBCLs, flag de não-recorrentes, salva Parquet em `data/processed/`), e `metricas_historicas.py` (Trilha não-financeira completa: crescimento YoY + CAGRs 3/5/7, margens, ROIC com DuPont, ROIIC rolling 3 anos, DSO/DIO/DPO/CCC, FCO/EBITDA, Dívida Líquida/EBITDA, cobertura de juros, beta desalavancado via Hamada, alíquota efetiva — preservando valores negativos sem travar). A Trilha financeira fica **criada mas não validada** (é a estrutura pra v1.5).

### (C) 📨 A mensagem que você me envia

```
Claude, Semana 1 do DCF Automatizado (coleta completa + métricas históricas).
A Semana 0 fechou: infra ok, coletor_cvm puxando DIRR3 e MGLU3 validados.

Preciso de QUATRO prompts para o Codex, em sequência:

PROMPT 1 (coletor_mercado.py): yfinance para preço atual + histórico 5 anos, 
ações fully diluted, beta rolling 60 meses mensal, market cap, dividend yield, 
e T-Bond 10Y via ^TNX. Tratar tickers .SA não reconhecidos sem quebrar.

PROMPT 2 (coletor_macro.py): python-bcb para Selic atual + Focus 1 e 2 anos, 
IPCA atual + Focus, CDI, TJLP. Salvar em data/raw/macro/.

PROMPT 3 (limpeza.py): normaliza dados brutos (despesas negativas, separa dívida 
financeira de NIBCLs para não-financeiras, flag de não-recorrentes sem remover), 
salva Parquet em data/processed/.

PROMPT 4 (metricas_historicas.py): DUAS trilhas por tipo via meta. Trilha 
não-financeira: crescimento YoY, CAGR 3/5/7, margens bruta/EBIT/EBITDA/líquida, 
ROIC com DuPont (NOPAT = EBIT×(1−t), IC = NWC + Imobilizado + Goodwill), ROIIC 
rolling 3 anos, DSO/DIO/DPO/CCC, FCO/EBITDA, FCO/LL, Dívida Líquida/EBITDA, 
cobertura de juros, beta desalavancado Hamada, alíquota efetiva — preservando 
ROIC negativo sem travar. Trilha financeira: cria a estrutura (ROE, ROA, NIM, 
eficiência, NPL, Basileia) mas sem foco em validação agora.

Escopo v1.0 = DIRR3 + MGLU3. Gere os 4 prompts prontos pro Codex.
```

### (D) 🧪 Roteiro de teste do fim da Semana 1

1. `coletor_mercado.py` roda pra DIRR3.SA e MGLU3.SA; preço atual bate com o Google.
2. `coletor_macro.py` traz Selic/IPCA coerentes com a realidade de hoje.
3. Existem arquivos Parquet em `data/processed/` pras duas empresas.
4. `metricas_historicas.py` gera as métricas da Trilha não-financeira pra DIRR3 e MGLU3.
5. **Teste de olho humano:** ROIC, margens e ciclo de caixa da DIRR3 batem com o que você conhece do trainee. Se destoar, tem bug de cálculo ou de mapeamento — descreve e me pede correção.
6. Nenhuma métrica quebra por causa de um ano com prejuízo (Magalu teve anos ruins — bom teste do "não travar com negativo").

**Válvula de escape:** macro (Prompt 2) é o menos crítico — se atrasar, dá pra hardcodar Selic/IPCA temporariamente e voltar depois. Métricas históricas (Prompt 4) é o que **não pode** escorregar, porque a Semana 2 depende delas.

---

# 📅 SEMANA 2 — 14/07 a 20/07 | Projeção das demonstrações (o coração do modelo)

> **Meta:** com as 8 premissas individuais que VOCÊ preenche, o sistema projeta DRE + Balanço + DFC pra 8 anos, com **o balanço fechando** (Ativo = Passivo + PL) em todos os anos. Esta é a semana de maior participação sua no projeto inteiro.

### (A) O que VOCÊ faz como humano

**Bloco 1 (~2h, insubstituível) — Preenche as premissas reais da DIRR3.** Copia `template_naofinanceiras.json` pra `data/premissas/DIRR3_premissas.json` e preenche com os valores da SUA análise do trainee. As 8 taxas de crescimento de receita, uma por ano, refletindo o ciclo de lançamentos e maturação do portfólio da Direcional. As 8 margens EBITDA. Os 8 CAPEX/Receita. E os parâmetros estruturais únicos (DSO, DIO, DPO, Kd, g, componentes do WACC). **Isto é o trabalho intelectual que nenhuma IA faz por você** — é literalmente a sua tese virando input. Pra MGLU3, preenche com premissas genéricas conservadoras só pra testar o pipeline.

**Bloco 2 (~1h30) — Valida o fechamento do balanço.** Depois que o Codex gerar os schedules e rodar, abre o DataFrame projetado da DIRR3 e confere **visualmente, ano a ano**, que Ativo = Passivo + PL nos 8 anos. O Codex roda o pytest automático, mas você confere com o olho também. Se não fechar, anota qual ano tem diferença e a magnitude em reais.

**Bloco 3 (~1h) — Sanity check das projeções.** As taxas de crescimento aparecem **diferentes em cada ano** na DRE projetada (confirmando que o sistema usou as 8 taxas, não repetiu uma)? A receita projetada faz sentido? A D&A projetada bate com o schedule de PP&E?

### (B) O que a IA/Codex faz

Cria `projetor_dre.py` (lê obrigatoriamente os 8 campos individuais de crescimento, aplica cada taxa ao seu ano sem repetir, projeta margem EBITDA individual por ano, EBIT = EBITDA − D&A do schedule, IR como % do EBT para empresas gerais e como % da Receita Bruta para construtora no RET, permite LL negativo), `schedule_wk.py` (NWC via DSO/DIO/DPO, variação de NWC como consumo de caixa), `schedule_ppe.py` (cascata PP&E_t = PP&E_anterior + CAPEX_t − D&A_t, CAPEX = % individual do ano × Receita do ano, para de depreciar em zero, atualiza a D&A na DRE), `schedule_divida.py` (juros = Kd × saldo médio, atualiza resultado financeiro, verifica fechamento do balanço nos 8 anos), e `tests/test_projecao.py` (pytest validando o fechamento).

### (C) 📨 A mensagem que você me envia

```
Claude, Semana 2 do DCF Automatizado (projeção das 3 demonstrações).
Semana 1 fechou: métricas históricas de DIRR3 e MGLU3 validadas.
JÁ PREENCHI o DIRR3_premissas.json com meus valores reais do trainee (8 taxas de 
crescimento, 8 margens, 8 capex, e os parâmetros estruturais).

Preciso de CINCO prompts para o Codex, em sequência (a ordem importa porque cada 
schedule alimenta o próximo):

PROMPT 1 (projetor_dre.py): projeta DRE 8 anos lendo OBRIGATORIAMENTE os 8 campos 
crescimento_receita_ano1..8 e aplicando cada taxa ao respectivo ano sem repetir. 
Margem EBITDA individual por ano. EBIT = EBITDA − D&A (vem do PP&E). IR como % do 
EBT para empresas gerais e como % da Receita Bruta para construtora no RET (4%). 
Permite LL negativo.

PROMPT 2 (schedule_wk.py): NWC via DSO/DIO/DPO, variação de NWC como consumo de 
caixa quando positiva.

PROMPT 3 (schedule_ppe.py): cascata PP&E_t = PP&E_anterior + CAPEX_t − D&A_t, 
CAPEX = % individual do ano × Receita do ano, ativo para de depreciar em zero, 
atualiza a D&A de volta na DRE.

PROMPT 4 (schedule_divida.py): juros = Kd × saldo médio do período, atualiza o 
resultado financeiro da DRE, e verifica o fechamento do balanço nos 8 anos 
imprimindo cada verificação.

PROMPT 5 (test_projecao.py): testes pytest que validam Ativo = Passivo + PL em 
cada um dos 8 anos, rodando pytest ao final.

Gere os 5 prompts prontos pro Codex.
```

### (D) 🧪 Roteiro de teste do fim da Semana 2

1. `pytest tests/test_projecao.py` passa com **todos os testes verdes**.
2. O balanço fecha nos 8 anos pra DIRR3 e MGLU3 (confere com o olho, não só o pytest).
3. A DRE projetada da DIRR3 mostra **taxa de crescimento diferente em cada ano** (prova das 8 taxas individuais).
4. A D&A da DRE bate com a D&A do schedule de PP&E.
5. **Teste de olho humano:** a receita e o LL projetados da DIRR3 no Ano 1 e 2 estão na mesma ordem de magnitude da sua análise do trainee.

**Válvula de escape:** esta é a semana **mais crítica e menos cortável** do projeto inteiro. Se atrasar, corte tempo das outras semanas, não desta. Um DCF que não projeta demonstração com balanço fechando não é um DCF.

---

# 📅 SEMANA 3 — 21/07 a 27/07 | Valuation completo (do FCFF ao Target Price)

> **Meta:** FCFF → WACC → Valor Terminal → EV → Equity Value → Target Price → Upside → Recomendação, com o checklist de consistência rodando. No fim desta semana **você tem um preço-alvo defensável da Direcional saindo do sistema.**

### (A) O que VOCÊ faz como humano

**Bloco 1 (~1h30) — Valida o WACC.** Depois que o Codex criar `calculador_wacc.py`, confere a decomposição: o Ke faz sentido? A conversão USD→BRL tá certa? O Kd histórico bate com o custo de dívida real da Direcional? O WACC final tá numa faixa plausível pra uma construtora brasileira (algo entre ~11% e ~15% costuma ser razoável, dependendo da estrutura)?

**Bloco 2 (~2h) — Valida o Target Price contra o trainee.** Quando o sistema cuspir o Target Price da DIRR3, compara com o valor da sua análise do trainee. **Não vão ser idênticos** (datas e dados da CVM diferentes), mas têm que estar na mesma ordem de magnitude. Se vier absurdamente diferente, você investiga qual componente causa a divergência (WACC alto demais? VT baixo? bridge EV→Equity com item errado?) e descreve a suspeita específica pro Codex.

**Bloco 3 (~1h) — Lê o checklist.** Confirma que os alertas fazem sentido. Se o sistema diz que o VP do Valor Terminal é 85% do EV, isso é verdade? Você entende por quê? (Numa construtora com crescimento desacelerando, o VT pesar bastante é esperado.)

### (B) O que a IA/Codex faz

Cria `calculador_fcff.py` (FCFF = NOPAT + D&A − ΔNWC − CAPEX pros 8 anos, mantém negativo sem travar, calcula FCFE também), `calculador_wacc.py` (Rf via `^TNX`, Ke_USD = Rf + β_realavancado × (ERP_EUA + CRP_Brasil), converte pra BRL pela fórmula do diferencial de inflação, Kd histórico, WACC = (E/V)×Ke + (D/V)×Kd×(1−t), com decomposição completa), `calculador_vt.py` (TV = FCFF₈×(1+g)/(WACC−g), bloqueia se g ≥ WACC, alerta se g > 5%, verifica taxa de reinvestimento 0-100%, trata FCFF negativo no ano 8 com NOPAT normalizado, calcula VP do VT, % do EV na perpetuidade, múltiplo de saída implícito), `calculador_ev.py` (bridge EV → Equity → Target Price → Upside → Recomendação), e `checklist.py` + `test_valuation.py` (verificações universais e por tipo, com pytest).

### (C) 📨 A mensagem que você me envia

```
Claude, Semana 3 do DCF Automatizado (valuation completo).
Semana 2 fechou: projeção das 3 demonstrações com balanço fechando nos 8 anos, 
pytest verde.

Preciso de CINCO prompts para o Codex, em sequência:

PROMPT 1 (calculador_fcff.py): FCFF = NOPAT + D&A − ΔNWC − CAPEX para os 8 anos 
(NOPAT = EBIT×(1−alíquota)), mantém FCFF negativo sem travar, calcula também 
FCFE = LL + D&A − ΔNWC − CAPEX + ΔDívida Líquida. (Trilha financeira criada mas 
não validada agora.)

PROMPT 2 (calculador_wacc.py): Rf via ^TNX, Ke_USD = Rf + Beta_realavancado × 
(ERP_EUA + CRP_Brasil), converte Ke para BRL por [(1+Ke_USD)×(1+IPCA)]/(1+CPI_EUA)−1, 
Kd histórico = Desp. Financeira / Dívida Bruta Média 3 anos, WACC = (E/V)×Ke_BRL + 
(D/V)×Kd×(1−t), com decomposição completa exibida.

PROMPT 3 (calculador_vt.py): TV = FCFF₈×(1+g)/(WACC−g). Bloqueia total se g ≥ WACC 
com erro claro. Alerta amarelo se g > 5% BRL. Verifica taxa de reinvestimento 
entre 0-100%. Se FCFF₈ negativo, usa NOPAT normalizado como base do VT com 
comentário explicando. Calcula VP(VT), % do EV na perpetuidade, múltiplo de saída 
implícito (TV/EBITDA₈) como sanity check.

PROMPT 4 (calculador_ev.py): bridge EV = ΣVP(FCFF) + VP(VT); Equity = EV − Dívida 
Bruta (CP+LP+Leasing IFRS16) + Caixa + Aplicações − Minoritários + Coligadas + 
Ativos Não Operacionais; Target Price = Equity / Ações Fully Diluted; Upside e 
Recomendação (COMPRA >20%, NEUTRO −5% a +20%, VENDA <−5%).

PROMPT 5 (checklist.py + test_valuation.py): verificações universais (g < taxa de 
desconto, g ≤ 5% BRL, reinvestimento 0-100%, VP(VT) < 85% do EV, fully diluted 
usado) + não-financeiras (balanço fecha, ROIIC < 50% nos 2 últimos anos, CAPEX ≥ 
D&A na perpetuidade, FCO/EBITDA > 0,7x, Dív.Líq/EBITDA < 4x) com pytest.

Gere os 5 prompts prontos pro Codex.
```

### (D) 🧪 Roteiro de teste do fim da Semana 3

1. O terminal imprime **Target Price, Upside e Checklist completo** pra DIRR3 e MGLU3.
2. `pytest tests/test_valuation.py` passa.
3. O Target Price da DIRR3 está **numa faixa razoável** comparado ao Excel do trainee.
4. A decomposição do WACC aparece (quanto vem do Ke, quanto do Kd).
5. O sistema **bloqueia** se você tentar colocar g ≥ WACC (testa de propósito: põe g = 20% e vê o erro).
6. **Teste de olho humano:** o % do EV na perpetuidade é plausível (60-80% é normal; se der 95%, algo está comprimindo o período explícito).

**Válvula de escape:** a Trilha financeira (FCFE de banco) pode ficar como esqueleto não-testado — é v1.5. Foca 100% na trilha não-financeira funcionando pra DIRR3 e MGLU3.

---

# 📅 SEMANA 4 — 28/07 a 03/08 | Visualizações + Front-end institucional

> **Meta:** todos os gráficos Plotly gerados com qualidade profissional **E** o app Streamlit no ar com a cara institucional, lendo o motor de cálculo e deixando você mexer nas premissas com slider. Esta é a semana em que o projeto "fica bonito".

> ⚠️ **Aviso de carga:** esta é a semana mais pesada em volume (gráficos + front-end juntos). Com 1-2h/dia, você vai precisar dos 7 dias. Por isso dividi em duas ondas.

### (A) O que VOCÊ faz como humano

**Onda 1 — Gráficos (Bloco 1, ~2h ao longo de 3 dias).** Depois que o Codex criar cada gráfico, abre o HTML no navegador e avalia com olho crítico: o Football Field tem as 7 metodologias legíveis com o preço atual em linha vertical vermelha? As sensibilidades têm verde/vermelho corretos e o caso base destacado? O Waterfall mostra claramente o peso do VT vs. os FCFFs? Se algo estiver sobreposto, cortado ou ilegível, você descreve o elemento específico.

**Onda 2 — Front-end (Bloco 2, ~3h ao longo de 4 dias).** Depois que o Codex criar o app Streamlit, roda `streamlit run app.py`, abre no navegador e testa a jornada: a sidebar tem as 6 seções? A aba Premissas deixa você mexer nos sliders e mostra o histórico ao lado? Os dashboards aparecem com a paleta institucional (navy, números tabulares, verde/vermelho semântico)? Você valida se está **visualmente à altura** — não precisa ser perfeito, mas não pode parecer trabalho de faculdade.

### (B) O que a IA/Codex faz

**Onda 1:** cria `football_field.py`, `waterfall_ev.py`, `sensibilidade_wacc_g.py`, `sensibilidade_receita_margem.py`, `sensibilidade_setor.py` (Margem Bruta × VSO pra construção; genérica pra varejo), `historico_vs_projetado.py` (grade 2×2), `dashboard_final.py` — todos Plotly, salvando HTML + PNG em `outputs/graficos/`, **usando a paleta institucional que especifiquei** (navy, acento, verde/vermelho semântico, fontes tabulares).

**Onda 2:** cria `app.py` (Streamlit) com a sidebar de 6 seções (Overview, Histórico, Premissas, Valuation, Análise, Excel Preview), tema institucional customizado via `.streamlit/config.toml` (cores navy/acento), a aba Premissas com `st.number_input` + `st.slider` + histórico ao lado de cada campo (lendo `metricas_historicas.py`), validação em tempo real (bloqueia g ≥ WACC), e as abas de output embarcando os gráficos Plotly já criados.

### (C) 📨 A mensagem que você me envia

```
Claude, Semana 4 do DCF Automatizado (visualizações + front-end institucional).
Semana 3 fechou: valuation completo, Target Price da DIRR3 saindo, pytest verde.

Preciso dos prompts em DUAS ondas.

ONDA 1 — Gráficos (me dê 3 prompts agrupados):
- football_field.py: 7 metodologias (DCF Bear/Base/Bull, Comps EV/EBITDA, Comps 
  P/L, Múltiplo de Saída, 52-week Range), preço atual em linha vertical vermelha, 
  HTML + PNG.
- waterfall_ev.py: decomposição VP(FCFF) 8 anos + VP(VT) → EV, com % de cada, aviso 
  se VP(VT) > 80%.
- As 3 sensibilidades (wacc_g 6×6 com formatação condicional e caso base destacado; 
  receita_margem; setor = Margem Bruta × VSO pra DIRR3 e genérica pra MGLU3) + 
  historico_vs_projetado (grade 2×2) + dashboard_final.
IMPORTANTE: todos os gráficos devem seguir a paleta institucional que você 
especificou no roteiro (navy, acento dourado/azul, verde/vermelho semântico, 
números tabulares).

ONDA 2 — Front-end Streamlit (me dê 1 prompt grande):
- app.py com sidebar de 6 seções (Overview, Histórico, Premissas, Valuation, 
  Análise, Excel Preview), tema institucional via .streamlit/config.toml, aba 
  Premissas com number_input + slider + histórico ao lado de cada campo lendo o 
  metricas_historicas.py, validação em tempo real bloqueando g ≥ WACC, e as abas 
  de output embarcando os gráficos Plotly. Visual à altura de Goldman/JPM/Morgan 
  Stanley conforme sua especificação.

Comece me dando a ONDA 1. Quando eu validar os gráficos, te peço a ONDA 2.
```

> **Nota:** repare que aqui você me pede as ondas **separadamente** — primeiro os gráficos, valida, depois o front-end. Isso evita que você receba um monte de código de uma vez e não consiga testar em pedaços.

### (D) 🧪 Roteiro de teste do fim da Semana 4

1. Os 7 arquivos HTML abrem no navegador com qualidade profissional pra DIRR3 e MGLU3.
2. O Football Field mostra as 7 metodologias e o preço atual destacado.
3. As tabelas de sensibilidade têm formatação condicional funcionando e caso base destacado.
4. `streamlit run app.py` sobe o app sem erro.
5. A sidebar tem as 6 seções navegáveis.
6. Na aba Premissas, você mexe num slider e o histórico aparece ao lado.
7. **Teste visual (subjetivo mas importante):** você mostraria essa tela numa entrevista sem vergonha? Paleta navy, números alinhados, verde/vermelho semântico, sem cara de amador?

**Válvula de escape:** se o tempo apertar, a **Onda 1 (gráficos) tem prioridade sobre a Onda 2 (front-end refinado)**. Um Streamlit funcional mas simples + gráficos lindos vale mais que um Streamlit lindo sem gráficos. O polimento visual do app pode continuar na Semana 5.

---

# 📅 SEMANA 5 — 04/08 a 05/08 | Excel de 7 abas + integração ponta a ponta

> **Meta:** o `main.py` roda o pipeline inteiro de um comando, o Excel de 7 abas sai formatado com gráficos embutidos, e o app mostra o **preview das 7 abas + botão de download**. Sistema fechado.

> ⏰ **Atenção ao calendário:** aqui você só tem **2 dias** (04 e 05), porque 06/08 é revisão final. É apertado de propósito — por isso o Excel e a integração são a única coisa desta janela.

### (A) O que VOCÊ faz como humano

**Bloco 1 (~2h) — Testa o Excel.** Depois que o Codex criar `exportador_excel.py` e `main.py`, roda `python main.py --ticker DIRR3 --setor construcao --usar-premissas-existentes`. Abre o Excel gerado e passa aba por aba: Capa tem os dados-chave? Premissas mostra os 8 valores individuais com histórico ao lado? Modelo Integrado tem DRE+BP+DFC com histórico e projetado lado a lado? Schedules estão lá? Valuation tem o bridge e os gráficos embutidos? Sensibilidades com formatação condicional? Output com dashboard e checklist? Números com separador de milhar e casas decimais certas?

**Bloco 2 (~1h) — Testa ponta a ponta e o preview no app.** Roda o pipeline pra MGLU3 também. Confirma que o app Streamlit, na aba "Excel Preview", mostra as 7 abas renderizadas e o botão de download funciona.

### (B) O que a IA/Codex faz

Cria `exportador_excel.py` (openpyxl, 7 abas formatadas profissionalmente conforme a seção 5.10 do seu roteiro e a estrutura WSP, com gráficos PNG embutidos, formatação condicional, cabeçalhos navy, números tabulares), `main.py` (aceita `--ticker` e `--setor`, detecta tipo, executa o pipeline na ordem correta com timestamps, flag `--usar-premissas-existentes`), e adiciona a aba "Excel Preview" no `app.py` (renderiza as 7 abas + botão de download do `.xlsx`).

### (C) 📨 A mensagem que você me envia

```
Claude, Semana 5 do DCF Automatizado (Excel 7 abas + integração ponta a ponta).
Semana 4 fechou: gráficos institucionais + app Streamlit com as 6 seções no ar.

Preciso de TRÊS prompts para o Codex:

PROMPT 1 (exportador_excel.py): openpyxl gerando 7 abas conforme a seção 5.10 do 
roteiro — Capa, Premissas (com os 8 valores individuais + histórico ao lado), 
Modelo Integrado (DRE+BP+DFC, 3 anos históricos + 8 projetados lado a lado, 
common-size ao lado), Schedules (WK, PP&E, Dívida em blocos verticais), Valuation 
(FCFF 8 anos, decomposição WACC, bridge, Football Field e Waterfall embutidos como 
PNG), Sensibilidades (as 3 tabelas com formatação condicional verde-vermelho, caso 
base destacado), Output (dashboard + checklist). Cabeçalhos navy, números com 
separador de milhar e 2 casas, percentuais com 1 casa.

PROMPT 2 (main.py): aceita --ticker e --setor, detecta tipo via meta, executa o 
pipeline completo na ordem (coleta → limpeza → métricas → premissas com flag 
--usar-premissas-existentes → projeção → valuation → gráficos → Excel), com 
timestamps por etapa e resumo final (Target Price, Upside, Recomendação, Checklist).

PROMPT 3 (aba Excel Preview no app.py): renderiza as 7 abas do Excel dentro do 
Streamlit + botão de download do .xlsx.

Gere os 3 prompts prontos pro Codex.
```

### (D) 🧪 Roteiro de teste do fim da Semana 5

1. `python main.py --ticker DIRR3 --setor construcao --usar-premissas-existentes` roda do início ao fim **sem erro** e gera o Excel.
2. O Excel tem as **7 abas**, gráficos embutidos, formatação condicional ativa, números formatados.
3. A aba Premissas do Excel mostra claramente os **8 valores individuais** de crescimento com referência histórica.
4. O mesmo pipeline roda pra MGLU3.
5. No app, a aba "Excel Preview" mostra as 7 abas e o download funciona.
6. **Teste de olho humano:** o Excel gerado é comparável em completude ao seu modelo do trainee? Se não, o que falta?

**Válvula de escape:** se o preview no app (Prompt 3) apertar, corte-o — o botão de download simples já resolve. O Excel em si (Prompt 1) é inegociável.

---

# 📅 06/08 — Revisão final + tag v1.0

> **Meta:** código limpo, documentado, testado, commitado com `git tag v1.0`. O projeto vira portfólio.

### (A) O que VOCÊ faz como humano

Atualiza o `CONTEXT.md` com o estado final (o que entregou, o que ficou pra v1.5, decisões de arquitetura tomadas no caminho). Escreve/revisa o `CHANGELOG.md` semana a semana. Confere que o README reflete o que foi realmente construído (você tinha 5 tickers no roadmap; ajuste pra DIRR3+MGLU3 na v1.0 e os outros 3 na v1.5). Faz o commit final: `git tag v1.0` e `git push origin v1.0`.

### (B) O que a IA/Codex faz

Revisão geral do repo (docstrings faltantes, nomes genéricos, cálculos financeiros sem comentário, inconsistências de nomes de coluna entre módulos, pontos que quebram se a CVM mudar um campo), roda o pipeline completo pra DIRR3 e MGLU3 corrigindo bugs, roda `pytest` em tudo confirmando verde, e apresenta um relatório do que alterou.

### (C) 📨 A mensagem que você me envia

```
Claude, dia da revisão final do DCF Automatizado (fechamento da v1.0).
Tudo das semanas anteriores está funcionando pra DIRR3 e MGLU3.

Preciso de DOIS prompts para o Codex:

PROMPT 1 (revisão geral): varre o repo inteiro corrigindo funções sem docstring, 
variáveis com nomes genéricos, cálculos financeiros sem comentário de fórmula, 
inconsistências de nomes de coluna entre módulos, e qualquer trecho que quebre se 
a API da CVM retornar um campo com nome ligeiramente diferente. Apresenta relatório 
do que alterou.

PROMPT 2 (validação final): roda o sistema completo pra DIRR3 e MGLU3 do início ao 
fim corrigindo qualquer bug, roda pytest em todos os testes confirmando verde, e 
confirma que os 2 Excels estão em outputs/excel/ e os gráficos em outputs/graficos/.

Gere os 2 prompts prontos pro Codex.
```

### (D) 🧪 Teste final de aceitação da v1.0

1. `pytest` **verde** em todos os módulos.
2. `python main.py --ticker DIRR3 --setor construcao --usar-premissas-existentes` gera Excel + gráficos completos.
3. `python main.py --ticker MGLU3 --setor varejo --usar-premissas-existentes` idem.
4. `streamlit run app.py` sobe o app institucional com as 6 seções e as 2 empresas.
5. Repositório no GitHub com tag `v1.0` e README atualizado (DIRR3+MGLU3 na v1.0, resto na v1.5).
6. **O teste que realmente importa:** você consegue abrir esse projeto numa entrevista da InFinance e defender cada premissa, cada fórmula e cada número? Se sim, a v1.0 cumpriu seu propósito.

---

# 🔁 Resumo visual do fluxo (cole na parede)

**Toda semana, sem exceção:**

1. Ativa a venv antes de qualquer sessão.
2. Faz o trabalho humano do bloco (validar números, preencher premissas).
3. Me envia a **mensagem-gatilho** da semana (as abas prontas acima).
4. Eu te devolvo os prompts cirúrgicos.
5. Você cola no Codex, ele escreve o código.
6. Você roda o **roteiro de teste** do fim da semana.
7. `git commit` + `git push` do módulo concluído.
8. Atualiza o `CONTEXT.md` com o estado atual e a próxima tarefa.

---

# 📦 requirements.txt atualizado (em separado, como você pediu)

Adicionei o que o roteiro novo exige e que não estava no seu arquivo original: **`streamlit`** (o front-end interativo que a gente decidiu) e **`streamlit-aggrid`** (pra renderizar as tabelas do Excel Preview com cara de planilha institucional dentro do app). Mantive tudo que você já tinha, com as mesmas versões mínimas. Aqui está o arquivo pronto pra substituir o seu:

```txt
# ===== Coleta de dados =====
yfinance>=0.2.40
python-bcb>=0.3.0
requests>=2.31.0

# ===== Processamento e cálculo =====
pandas>=2.2.0
numpy>=1.26.0
pyarrow>=16.0.0

# ===== Visualização e exportação =====
plotly>=5.22.0
kaleido>=0.2.1
openpyxl>=3.1.2

# ===== Front-end institucional =====
streamlit>=1.37.0
streamlit-aggrid>=1.0.5

# ===== Qualidade de código e testes =====
pytest>=8.2.0
black>=24.4.0
flake8>=7.0.0

# ===== Infraestrutura =====
python-dotenv>=1.0.1
```

Uma nota de honestidade sobre `kaleido`: a versão `>=0.2.1` que está no seu original às vezes dá dor de cabeça pra exportar PNG em algumas máquinas. Se na Semana 4 o Codex reclamar de erro ao salvar PNG dos gráficos Plotly, o problema quase certamente é o kaleido — me avisa que eu te passo o ajuste (geralmente é fixar numa versão específica ou reinstalar). Não mudei agora pra não quebrar o que você já validou, mas fica o aviso.

---

Lucas, três verdades finais, de amigo:

**Primeira:** este roteiro é honesto sobre o tempo, mas ele ainda é apertado. Com 1-2h/dia irregulares, a Semana 2 (projeção) e a Semana 4 (visual + front) são os gargalos reais. Se você sentir que está afogando, o corte certo é **profundidade de MGLU3, não qualidade de DIRR3**. A Direcional é sua tese — ela precisa estar impecável. A Magalu é só a prova de que o motor é universal; ela pode ficar 80%.

**Segunda:** não caia na tentação de reabrir o escopo. Toda vez que bater a vontade de "ah, deixa eu botar o ITUB4 também porque tá quase pronto", lembra que "quase pronto" em banco significa reescrever a lógica de FCFE, Basileia e capital regulatório — é um buraco de dias. v1.5 existe pra isso.

**Terceira:** o `CONTEXT.md` atualizado no fim de cada sessão não é burocracia — é o que impede o Codex de tomar decisões conflitantes entre sessões e você perder horas desfazendo. Trata ele como sagrado, do jeito que seu próprio README já diz.

Quer que eu já detalhe a primeira mensagem-gatilho (a da Semana 0) em prompt real agora, pra você sair colando no Codex hoje, ou prefere rodar o Bloco 1 manual primeiro e me chamar quando o repo estiver conectado?