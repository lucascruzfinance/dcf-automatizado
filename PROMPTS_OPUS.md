# PROMPTS_OPUS.md — v2.1 · **Semana 10** (motor correto, enxuto e explicável) + **Semana 11** (front-end institucional, gráficos vivos e DDM para financeiras)

> **Implementador deste documento: o Claude Opus 4.8** (Claude Code). O Opus lê os documentos de
> contexto, **escreve e edita TODO o código Python e o front-end**, confere **cada erro e cada
> funcionalidade**, valida o **app** (Streamlit), os **gráficos/tabelas** (Plotly) e o **Excel
> gerado**, roda os testes (`pytest`/`black`/`flake8`) e atualiza `CONTEXT.md` + `Humano_revisar.md`.
> O **humano (Lucas)** é o dono do julgamento analítico (premissas reais, validação numérica,
> commits e a revisão do `Humano_revisar.md`).
>
> **Este arquivo SUBSTITUI o antigo `PROMPTS_FABLE.md`.** A Semana 9.0 (motor "padrão Direcional",
> Excel de 8 abas, app de 4 etapas) está CONCLUÍDA e vive no histórico (`CONTEXT.md` Seção 8 +
> `docs/CHANGELOG.md`). A **antiga Semana 10** do `PROMPTS_FABLE.md` (football field automatizado +
> comparáveis reais) foi **repensada**: o projeto passa por uma **conversa franca de reescopo**
> (registrada abaixo em §0.1) e agora persegue **fidelidade ao que o analista sabe explicar**, com
> apresentação visual de alto nível dos números que o motor **já** possui.

---

## 0. LEIA ANTES DE QUALQUER PROMPT

### 0.1 O norte deste reescopo (a "conversa franca")

Uma frase manda em tudo o que segue:

> **"Quero que o projeto reflita somente as coisas que eu sei, que eu sei explicar."** — Lucas

O motor cresceu (v2.0/v2.1) para além do que o analista domina hoje, e isso produz **números que
ele não consegue defender**: beta re-alavancado colado no piso de 0,5x, Kd derivado de 44–168%,
WACC de 27%, targets de −119%. Nada disso é "erro de conta" — é **sobre-automação**: o motor tenta
*derivar* o que deveria ser **input simples** (Kd, beta) ou **média histórica achatada** (working
capital, payout, minoritários). A referência pedagógica (transcrição da Valuation Week + modelos
Madero/Direcional/WEGE3) faz a **versão simples e explicável**, e é para lá que voltamos.

**Princípio-régua:** cada número do modelo é (a) **input do analista**, (b) **fato histórico
achatado**, ou (c) **fórmula sobre (a) e (b)**. Nada é "derivado por engenharia" de um jeito que o
analista não saiba justificar em uma frase. Cada gráfico **desenha um número que o motor já
possui** — nenhum número nasce num gráfico.

### 0.2 O que a Semana 10 e a Semana 11 entregam

| Semana | Período | Tema | Prompts | Status |
|---|---|---|---|---|
| 9.0 | 17→20/07/2026 | Automação fiel à CVM + motor "padrão Direcional" + Excel "Modelo" 8 abas | 9.0.0…9.0.5 | ✅ CONCLUÍDA (fora deste doc) |
| **10** | — | **Motor correto, enxuto e explicável: inputs certos (Kd/beta), schedules simplificados, valuation/retornos/múltiplos consolidados, DDM para financeiras, macro reformatada, formatação BR global no Excel** | **10.0.0…10.0.5** | 🟡 EM EXECUÇÃO (**10.0.0 ✅**) |
| **11** | — | **Front-end institucional: tema, tabelas bonitas, gráficos vivos (ROIC/ROIIC, margens, retorno em blocos, waterfall EV→Equity, heatmap de sensibilidade, football field só com as faixas próprias), diferenciação financeira/não-financeira no app, aba de Ajuda** | **11.0.0…11.0.5** | 🟡 A EXECUTAR |

Semana 10 é **back-end/cálculo/dados/Excel** — porque os gráficos da Semana 11 só valem se os
números estiverem certos. Não abra a Semana 11 antes de fechar a Semana 10.

### 0.3 Estado atual do repositório (a fundação — não re-descobrir por tentativa e erro)

**Motor (fonte única de verdade — `src/projecao/` + `src/valuation/`):**
- **DRE pré-D&A** (`projetor_dre.py`): margem bruta e SG&A de nível EBITDA; D&A é linha própria
  (`schedule_ppe.py`); `margem_ebitda` é derivada (bruta − SG&A).
- **Cadeia obrigatória:** `projetor_dre → schedule_wk → schedule_ppe → schedule_leasing →
  schedule_divida → dfc_indireto → calculador_fcff → calculador_wacc → calculador_vt →
  calculador_ev → calcular_fcfe_naofinanceira → calculador_retornos → checklist`. Os três
  orquestradores (`main.py`, `src/pipeline.py`, `src/verificar_semana3.py`) chamam nessa ordem.
- **Trilha financeira:** `src/projecao/projetor_financeiro.py` existe (LL direto, sem bridge
  EV→Equity). Hoje roda FCFE/Ke; a Semana 10 troca isso por **DDM** (Prompt 10.0.3).
- **Gerador de premissas:** `src/projecao/gerador_premissas.py` cria as premissas automáticas.
  **Default = média-5a ACHATADA** nos 8 anos (10.0.0 CONCLUÍDO), com salvaguarda de outlier
  (mediana quando há ano extremo, via `_ancora_flat_5a`/`_central_robusta`); payout/minoritários
  viram fato histórico achatado; o editor 8× do app segue permitindo override ano a ano.
- **Blocos persistidos** em `data/processed/<TICKER>_projecao.json`: `ano0`, `dre`, `wk`, `ppe`,
  `divida`, `leasing`, `balanco` (com `verificacao_balanco`), `dfc`, `fcff` (com `roic`/`roiic`
  por ano), `fcfe`, `fcfe_valuation`, `retornos` (`tir_moic`, `multiplos`, `cenarios`), `wacc`,
  `valor_terminal`, `ev_equity` (com `ajustes_bridge`), `checklist`, `macro_anual`.
- **WACC manual:** premissa `wacc_manual` (decimal em (0,1]) vence o build-up CAPM (`wacc_origem`).

**Excel (`src/exportacao/exportador_excel.py`):** 8 abas `NOMES_ABAS = (Capa, Premissas, Modelo,
FCFF, FCFE, Macro, Sensibilidades, Avisos)`; fórmulas vivas via a classe `Aba`; avaliador de
fórmulas em `tests/apoio_avaliador_excel.py` recalcula célula a célula (0 divergências).
**Cores de Lucas:** histórico da CVM = AZUL, premissa = VERDE, fórmula = PRETO.

**Front-end (`app.py`, Streamlit):** fluxo guiado de 4 etapas (`① Empresa → ② Premissas → ③
Resultados → ④ Exportar`); ③ com sub-abas `Overview, Historico, Valuation, Modelo, Retornos`. **Sem
nenhum gráfico Plotly hoje** (tudo é `st.dataframe`).

**Módulos de gráficos (`src/visualizacao/`) — DESCONGELADOS e testados (D-078), prontos como
biblioteca, faltando religar ao app:** `roic_roiic.py`, `tornado.py`, `waterfall_ev.py`,
`sensibilidade_wacc_g.py`, `sensibilidade_receita_margem.py`, `historico_vs_projetado.py`,
`dashboard_final.py`, `football_field.py`, `tema_institucional.py` (tema + `salvar_grafico` +
formatação BR), `apoio_cenarios.py`, `apoio_heatmap.py`. Assinatura padrão: `(ticker,
raiz_projeto=None) -> {"figura", "html", "png"}`.

**Formatação:** `src/apresentacao/formatacao.py` já tem `formatar_moeda_brl`,
`formatar_percentual_br`, `COR_VERDE_UPSIDE`, `COR_VERMELHO_DOWNSIDE` — será o **ponto único** de
formatação BR (Prompt 10.0.5).

### 0.4 Regras invariantes (valem para TODOS os prompts das duas semanas)

1. **O motor calcula UMA vez; app e Excel só apresentam.** O app **nunca** recalcula valuation em
   JS; quando precisa de número novo, chama o motor Python. O Excel usa **fórmulas nativas vivas**
   que reproduzem o motor (classe `Aba`), nunca valores colados.
2. **Cada número é input, fato histórico achatado, ou fórmula sobre esses.** Sem "derivação de
   engenharia" que o analista não saiba justificar em uma frase.
3. **Sinais (regra dura):** despesas/saídas NEGATIVAS, receitas/entradas POSITIVAS.
4. **Vetores de premissa:** 8 valores individuais (`_ano1..8`). O **default** passa a ser a
   **média histórica de 5 anos achatada** (mesmo valor nos 8 anos); o analista pode **sobrescrever
   ano a ano** (o editor 8× continua).
5. **Valores negativos são VÁLIDOS** (ROIC/FCFF/LL/target): o código nunca trava.
6. **Robustez:** gráfico/aba/campo sem dado → mensagem amigável, **nunca exceção**. O app sobe para
   TODOS os tickers (financeiras degradam com aviso onde o conceito não se aplica).
7. **Gráfico é apresentação:** cada barra/ponto/célula vem de um bloco persistido pelo motor. Todo
   gráfico usa `tema_institucional.py` (zero estilo ad-hoc; coerente com claro/escuro do app).
8. **Formatação BR única:** todo percentual com **1 casa** (`10,9%`, nunca `0,10914`); todo valor
   monetário com separador de milhar (`17.469.557`), negativo entre **parênteses**
   (`(17.469.557)`), **zero vira `-`**. Fonte única: `src/apresentacao/formatacao.py`.

### 0.5 Golden e re-baseline (IMPORTANTE)

A Semana 10 muda drivers de fundo (Kd vira input, beta vira input, WC vira 4 contas, IFRS-16 sai,
payout/minoritários viram média achatada). **O golden VAI mudar** — isso é esperado. A cada prompt
que mexe num driver, **re-explique o golden por driver e atualize o baseline** no `CONTEXT.md`
(padrão dos re-baselines D-060/D-065). Golden de referência:

- **Não-financeiras:** DIRR3 (construtora/RET), MGLU3 (varejo), SMFT3 (leasing alto) **+ WEGE3**
  (validação contra o modelo do próprio Lucas — deve ficar próximo do DCF Wege3.xlsx dele).
- **Financeiras (novo, DDM):** BBAS3 e ITUB4 (e, se coletável, BBSE3).

Regressão: `.venv/Scripts/python.exe -m src.verificar_semana3` deve imprimir **SEMANA 3 OK** ao fim
de cada prompt.

### 0.6 Ambiente e comandos (obrigatório)

- Validação SEMPRE com a venv: `.venv/Scripts/python.exe -m pytest tests -q`,
  `... -m black src tests app.py main.py --check --workers 1` (o `--workers 1` é obrigatório nesta
  máquina), `... -m flake8 src tests app.py main.py`.
- Regressão: `.venv/Scripts/python.exe -m src.verificar_semana3` → **SEMANA 3 OK**.
- App headless (teste sem navegador): `from streamlit.testing.v1 import AppTest`. App real:
  `.claude/launch.json` tem o server `dcf-app` na porta 8601.
- Nomes de coluna só existem se registrados em `config/mapeamento_cvm.json`.
- Código em português (funções, variáveis, comentários). Docstring + comentário com a fórmula em
  todo cálculo financeiro.

### 0.7 Ordem e critério de avanço

Prompts progressivos. Não abra o prompt N+1 antes do DoD do N estar verde **e** o golden explicado.
Se uma sessão terminar no meio de um prompt, registre o ponto exato no `CONTEXT.md` e retome do
mesmo prompt. **Cole um prompt por vez no Opus.**

---
---

# SEMANA 10 — MOTOR CORRETO, ENXUTO E EXPLICÁVEL

---

# PROMPT 10.0.0 — Premissas enxutas e inputs corretos (Kd, beta, caixa=CDI; média-5a achatada; fim das derivações absurdas)

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/projecao/gerador_premissas.py`,
`src/valuation/calculador_wacc.py`, `src/projecao/schedule_divida.py`, `config/parametros.json` e as
premissas em `data/premissas/<TICKER>_premissas.json`. Leia `Humano_revisar.md` (A-1 = alvos
automáticos irreais; A-2 = Kd derivado 44–168%). **Este prompt ataca a raiz dos "números estranhos".**

A referência (transcrição da Valuation Week) é explícita: o Kd sai das **últimas emissões da
empresa** (ou CDI + spread), não de "despesa financeira ÷ dívida média"; o beta é o da empresa
**contra o Ibovespa** (input); a rentabilidade do caixa é o **CDI**. O modelo do próprio Lucas
(DCF Wege3.xlsx) sofre do mesmo bug que o programa: "taxa de dívida" 48,5% e "taxa de caixa" 29% —
os dois derivados de saldo. Vamos consertar os dois.

## Objetivo

Reduzir as premissas ao **conjunto explicável** de Lucas e trocar toda derivação instável por
**input com default sensato** ou **média histórica achatada**.

## Especificação técnica detalhada

**Premissas que PERMANECEM como input do analista (as únicas):**
1. `crescimento_receita_ano1..8` — Crescimento da Receita Líquida.
2. `margem_bruta_ano1..8` — Margem Bruta anual (nível EBITDA, pré-D&A).
3. `sgna_pct_receita_ano1..8` — SG&A como % da Receita Líquida.
4. `aliquota_ir_ano1..8` — Alíquota de imposto anual (construtora no RET: travada em 4% sobre RB).
5. `custo_divida_kd` — **Kd, input do usuário.** Default = **CDI do ano** (`macro_anual`) **+ spread**
   (`spread_divida_sobre_cdi`, default em `config/parametros.json`, ex.: `0.02`). **NUNCA** derivar
   Kd de despesa/saldo. Remover (ou rebaixar a "referência apenas exibida") o caminho de Kd derivado
   em `calculador_wacc.py`/`schedule_divida.py` que produz 44–168%.
6. `beta` — **input do usuário (Bloomberg).** Default = beta bruto do `coletor_mercado` (yfinance
   5a). **Remover** a máquina de desalavancar/realavancar (Hamada) + clamp `[0,5; 1,8]` como
   *driver*; se quiser manter um modo "auto" opcional, deixe-o desligado por padrão e **exiba a
   proveniência** ("beta = input; default yfinance 5a"). Fim do "0,5x" misterioso.
7. `growth_perpetuidade_g` — g na perpetuidade (input).
8. `wacc_manual` (opcional) — mantém o comportamento atual (vence o build-up CAPM).

**Premissas que SAEM do painel e viram FATO HISTÓRICO ACHATADO** (calculadas no motor a partir do
histórico da empresa, média dos últimos 5 anos, e fletadas nos 8 anos):
- `payout_dividendos` → média histórica de payout (`|dividendos|/LL`) dos últimos 5 anos, achatada.
- `minoritarios_pct_ll` → média histórica de `participação minoritários / LL`, achatada.
- Outras receitas/despesas operacionais e **equivalência patrimonial** → média histórica achatada
  (ou dobradas em "outros resultados operacionais" constante), nunca input.
- **`caixa_minimo` → SAI do painel de premissas, mas NÃO é removido do código.** Decisão de Lucas
  (23/07/2026): a política de dívida atual é MANTIDA (ver 10.0.1), e o caixa mínimo é o **piso que
  dispara a captação** de dívida nova — tem função. Portanto ele deixa de ser slider do analista e
  **permanece como parâmetro da política de dívida** (`politica_divida.caixa_minimo_pct_receita`
  em `config/parametros.json`, hoje 2% da receita).

**Rentabilidade do caixa = CDI:** confirme que `schedule_divida.py` usa a taxa de aplicação do
caixa = **CDI do ano** (`macro_anual`), nunca uma taxa derivada do histórico (o "29%" do WEGE3).
Isso já foi parcialmente feito (D-065) — finalize e remova qualquer resíduo de taxa derivada.

**Default das 4 premissas de vetor = média-5a achatada:** reescreva `gerador_premissas.py` para que
o default de `crescimento_receita`, `margem_bruta`, `sgna_pct_receita` e `aliquota_ir` seja a
**média dos últimos 5 exercícios** (com salvaguarda contra *outliers*: se houver ano extremo, use
mediana; documente a regra) **fletada nos 8 anos** — em vez do CAGR/fade atual. **Manter o override
ano a ano** (o editor 8× do app continua funcionando: o analista pode escrever a narrativa).
Registrar `premissas_automaticas: true` até o analista editar (mantém o comportamento do A-1).

**App (`app.py`, etapa ② Premissas):** o grupo "⑥ Outros" perde payout e minoritários (agora
derivados do histórico) e o **slider de caixa mínimo** (vira parâmetro fixo da política de dívida),
passando a conter apenas **Kd** (com o default CDI+spread visível), **beta** (input, default yfinance
visível), **g** e o vetor **capex_receita**. Mostre, ao lado de cada premissa de vetor, os **valores
históricos** que formaram a média (referência — ver Prompt 10.0.5 para o formato no Excel).

> **STATUS (23/07/2026): PROMPT 10.0.0 CONCLUÍDO.**
> **(1) Kd e beta viraram INPUT:** `calculador_wacc` usa `custo_divida_kd` (default CDI+spread) e o
> beta INPUT direto (sem Hamada/clamp); Excel e `verificar_semana3` (E6 alinhado à invariante #5)
> acompanharam. Caixa rende CDI (D-065).
> **(2) Vetores = média-5a ACHATADA** (helpers `_ancora_flat_5a`/`_central_robusta`, com salvaguarda
> de outlier → mediana quando um ano se afasta >1,5× da mediana): `crescimento_receita`,
> `margem_bruta`, `sgna_pct_receita`, `aliquota_ir`, `capex_receita` e `margem_ebitda` saem achatados
> (as janelas 5a foram adicionadas em `metricas_historicas.py`). O editor 8× segue vivo (override
> ano a ano).
> **(3) Payout e minoritários viraram FATO HISTÓRICO achatado** (`_payout_hist_5a` = média-5a robusta
> de `|dividendos_pagos_dfc|/LL`; `_minoritarios_hist_5a` = idem de `|não_controladores|/LL`);
> outras/equivalência idem, via `_central_pct_hist`.
> **(4) Painel ② "⑥ Outros"** perdeu payout, minoritários e o slider de caixa mínimo (derivados /
> política); Kd e beta ganharam legenda de proveniência. `caixa_minimo_pct_receita` permanece em
> `config/parametros.json` (só saiu do painel).
> **Re-baseline do golden** (target — premissas AUTOMÁTICAS, REVISAR): DIRR3 16,84 → **9,89** (payout
> 5a 48% drena caixa → flip COMPRA→VENDA), MGLU3 −0,05 → **−3,97** (crescimento 5a robusto 3,5% +
> alíquota efetiva capada em 45%), SMFT3 −3,93 → **+0,29** (alíquota 5a via mediana 15% + margem
> bruta 57%), WEGE3 9,21 → **16,91**. `pytest` **207** / `black` / `flake8` limpos; `verificar_
> semana3` **SEMANA 3 OK**. (SMFT3 ainda inclui o leasing pesado — muda no 10.0.1.)

## Definição de Pronto (DoD)

- ✅ Nenhum ticker produz Kd derivado absurdo: WACC dos golden em faixa sã (Kd = CDI+spread, sem
  44–168%). ✅ Beta é input com proveniência; nenhum "0,5x" vindo de clamp. ✅ Caixa rende CDI.
- `caixa_minimo` **sai do painel de premissas** (segue como parâmetro da política de dívida — NÃO é
  removido do código).
- `gerador_premissas.py` gera default = **média-5a achatada** nos 4 vetores (com o override ano a ano
  intacto); payout/minoritários/outras viram **média histórica achatada** (deixam de ser input).
- `pytest`/`black`/`flake8` verdes; `verificar_semana3` OK; **golden re-explicado por driver** no
  `CONTEXT.md` (o target VAI mudar — explique o quanto e por quê).

## O que NÃO fazer

- NÃO manter o Kd derivado como *driver* do WACC. **NÃO remover o caixa mínimo do código** (só do
  painel de premissas — ele alimenta a captação da política de dívida). NÃO remover o editor 8×
  (o override por ano é a alma do projeto). NÃO tocar no Excel/gráficos ainda.

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (A-2 já fechada; anotar a re-baseline do golden).

---
---

# PROMPT 10.0.1 — Schedules enxutos: working capital de 4 contas, PP&E, fim do IFRS-16 pesado, dívida (amortização ATUAL, documentada) e DFC completo

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/projecao/schedule_wk.py`, `schedule_ppe.py`,
`schedule_leasing.py`, `schedule_divida.py`, `dfc_indireto.py` e `Humano_revisar.md` (A-6 = leasing;
convenções travadas). Referências: o modelo **Madero** (WC de 4 contas, 365 dias, DFC com dividendos
e Caixa BOP→EOP) e o **DCF WEGE3** de Lucas. A transcrição confirma: WC = ativos − passivos
operacionais de curto prazo, projetados por **dias** (componente/referência × 365), **achatados**
pela média histórica com suavização de *outliers*.

## Objetivo

Deixar os schedules **simples e explicáveis**: WC de 4 contas, **manter a política de amortização de
dívida ATUAL** (perfil CP/LP + captação para caixa mínimo) e **documentá-la com clareza** (Lucas quer
entender e manter, não simplificar para flat), DFC indireto completo com o financiamento (dividendos)
e o encadeamento de caixa, e **remover a mecânica IFRS-16** mantendo só a linha de arrendamento no BP.

## Especificação técnica detalhada

**Working Capital (`schedule_wk.py`) — reduzir para 4 contas** (padrão Madero/aula), modo único
`dias_4_contas`:
- **Ativos:** Contas a Receber (dias = CR / Receita Líquida × 365) + Estoques (dias = Estoques /
  |CPV| × 365).
- **Passivos:** Fornecedores (dias = Fornecedores / |CPV| × 365) + Obrigações Sociais e Trabalhistas
  (dias = Obrigações / |SG&A| × 365).
- **WC = (CR + Estoques) − (Fornecedores + Obrigações).** Dias projetados = **média histórica de 5
  anos, achatada** (suavizar salto do ano 1; documentar). **Remover** do WC as contas
  `tributos_a_recuperar` e `adiantamento_clientes` (mantê-las **constantes** no BP, dobradas em
  "outros ativos/passivos"). Construtora (DIRR3) segue ancorada por percentual da receita como hoje
  (ciclo longo) — preserve esse caminho, mas documente-o.
- Persistir `nwc`, `delta_nwc` e as 4 contas por ano; adicionar por ano **Current Ratio**
  (Ativo Circulante / Passivo Circulante) e **Quick Ratio** ((Caixa + Contas a Receber) / Passivo
  Circulante) no bloco `wk` (para o app e o Excel).

**PP&E (`schedule_ppe.py`):** manter CAPEX = `capex_receita_anoN` × receita e D&A = taxa única
`1/vida_util_ppe_anos` sobre o PP&E de abertura (D-047). Sem cascata por safra. Intangível constante.

**IFRS-16 (`schedule_leasing.py`) — REMOVER a mecânica pesada:** retirar do resultado os **juros de
arrendamento** e a **D&A do direito de uso**, e retirar o efeito no FCFE. **Manter apenas** o
`passivo_arrendamento` como **linha constante no BP** (para o balanço fechar). Documente
explicitamente que o EBITDA passa a ser **ex-ajuste de leasing** e que, para nomes de leasing
pesado (SMFT3, RENT3, RADL3), o número não é comparável ao EBITDA pós-IFRS-16 do mercado — isso é
uma simplificação deliberada de explicabilidade.

**Dívida (`schedule_divida.py`) — MANTER a política de amortização ATUAL (decisão de Lucas,
23/07/2026); NÃO simplificar para flat.** A política vigente é boa e defensável; o objetivo aqui é
**deixá-la CLARA** (código, Excel e app/Ajuda). Como ela funciona hoje (documentar exatamente assim):
1. **Estoque inicial (Ano 0, da CVM):** dívida de curto prazo (CP) e de longo prazo (LP).
2. **Amortização programada:** a **CP do Ano 0 amortiza inteira no ano 1**; a **LP amortiza linear**
   em `prazo_amortizacao_lp_anos` (config, hoje **5 anos** → 1/5 do saldo por ano).
3. **Juros = Kd × dívida de ABERTURA** do ano (convenção de saldo inicial: remove a circularidade
   juros/captação; a dívida captada no ano só paga juros no ano seguinte).
4. **Captação de dívida nova:** se o caixa projetado do ano cair **abaixo do caixa mínimo**
   (`caixa_minimo_pct_receita` × receita), a empresa **capta a diferença** no fim do ano (nova
   tranche, amortização linear em 5 anos, 1 ano de carência, ao Kd do ano). **É o caixa mínimo que
   dispara isto** — por isso ele NÃO é removido (10.0.0), só sai do painel de premissas.
5. **Reclassificação CP/LP no fechamento:** a CP do ano = amortização programada para o ano seguinte;
   o resto é LP.
6. **Emissão por emissão (opcional):** a tabela de premissa `instrumentos_divida` (saldo, taxa,
   `ano_vencimento` bullet ou `curva_amortizacao`) modela cada debênture individualmente — método
   "calendário da ANBIMA" da aula. Preservar intacto.
- **O que ENTREGAR aqui:** comentários/`docstring` explicando 1–6 no `schedule_divida.py`; uma nota
  na aba do Excel (ex.: em `Avisos` ou ao lado do schedule de dívida) descrevendo a política em
  linguagem de analista; e o texto correspondente na aba de Ajuda do app (Prompt 11.0.4). O Kd usado
  é o input do 10.0.0 (premissa `custo_divida_kd` / `spread_divida_sobre_cdi`). **Sem revolver
  formal** (a captação para caixa mínimo já cumpre o papel, sem circularidade).

**DFC indireto (`dfc_indireto.py`) — completar o financiamento e o encadeamento de caixa** (padrão
Madero/WEGE3):
- **FCO** = LL + D&A − ΔNWC.
- **FCI** = − CAPEX.
- **FCF** (financiamento) = − Dividendos Pagos (= −payout × LL) **− Amortização + Captação**
  (= −div + Δdívida líquida) + Δequity (0). **Atenção:** como a política de dívida NÃO é flat
  (amortiza CP/LP e capta para caixa mínimo), Δdívida ≠ 0 — o FCF tem que refletir amortização e
  captação (já é assim no `schedule_divida`; garanta que o `dfc` exponha as linhas separadas).
- **Caixa BOP** = Caixa EOP do ano anterior; **Variação de caixa** = FCO + FCI + FCF; **Caixa EOP**
  = BOP + Variação. Persistir todas as linhas no bloco `dfc`.
- **Check do balanço em TODOS os anos, inclusive os históricos 2020–2025** (`verificacao_balanco`
  cobrindo colunas históricas e projetadas; linha booleana `IF(ROUND(...)="Ok")`).

## Definição de Pronto (DoD)

- `wk` com 4 contas + Current/Quick Ratio por ano; WC achatado sem salto no ano 1. Leasing pesado
  removido do resultado/FCFE, `passivo_arrendamento` constante no BP; balanço fecha (resíduo ≤ 1e-6)
  em TODOS os anos, históricos inclusos. DFC amarra (Caixa EOP = Caixa do BP) com dividendos no FCF.
- **Política de dívida ATUAL mantida** (perfil CP/LP + captação para caixa mínimo + instrumentos
  opcionais) e **documentada** no código, no Excel e no texto da Ajuda (11.0.4). `pytest`/`black`/
  `flake8` verdes; `verificar_semana3` OK; golden re-explicado (leasing fora + WC 4 contas mudam o
  número — quantifique).

## O que NÃO fazer

- **NÃO tornar a dívida flat** (Lucas quer manter a amortização atual). NÃO reintroduzir revolver
  formal (a captação para caixa mínimo já cobre, sem circularidade). NÃO manter WC de 6 contas. NÃO
  deixar a D&A do direito de uso no resultado. NÃO deixar o Check só nos anos projetados.

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (A-6 → resolvido pela simplificação; registrar).

---
---

# PROMPT 10.0.2 — Valuation consolidado, retornos e múltiplos (a "espinha do valuation" + cenários com rótulos corretos)

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/valuation/calculador_fcff.py`, `calculador_wacc.py`,
`calculador_vt.py`, `calculador_ev.py`, `calculador_fcfe.py`, `calculador_retornos.py`,
`checklist.py`, `motor_cenarios.py` e a aba **FCFF/Multiplos** do modelo **Direcional** (é o gabarito
exato do que Lucas pediu). Referência da aula: TV = FCFF₈ × (1+g)/(WACC−g), descontada ao ano
anterior; g ≤ crescimento do PIB + inflação.

## Objetivo

Consolidar o valuation num **painel único e completo** (fim da duplicação Overview × Valuation),
expor a **espinha do valuation** com percentuais, entregar **retornos decompostos** e **múltiplos
por ano**, e corrigir o **motor de cenários** (rótulos Bear/Bull hoje conceitualmente invertidos).

## Especificação técnica detalhada

**Espinha do valuation (bloco `ev_equity`), a ser exibida de forma explícita:**
- **Soma VP(FCFF)** — valor **e % do EV**.
- **VP(Valor Terminal)** — valor **e % do EV** (o "quanto do valor está na perpetuidade").
- **= Enterprise Value.**
- **(−) Dívida Bruta** e **(+) Caixa e Equivalentes** exibidos **separadamente**, de modo que
  **Dívida Líquida = Dívida Bruta − Caixa** apareça explícita.
- **= Equity Value = EV − Dívida Líquida.**
- **Target Price = Equity / ações**, **Current Price**, **Upside %**.
Persista cada componente e cada percentual no `ev_equity` (não recalcular no app/Excel).

**FCFF × FCFE:** manter FCFF ao WACC e **FCFE ao Ke** (fórmula: Equity = Σ FCFEₜ/(1+Ke)ᵗ +
TV/(1+Ke)ⁿ). Exibir Equity via FCFF (bridge), Equity via FCFE (direto) e a **Divergência** entre os
dois como número informativo (com a distorção do Kd resolvida no 10.0.0, a divergência deve
encolher). **Remover o Target da aba/bloco FCFF** — o target vive só no painel consolidado.

**Múltiplos implícitos por ano (bloco `retornos.multiplos`)** — só com o **preço atual**, adicionar:
- **EV/EBITDA**, **EV/EBIT**, **P/E** (= Market Cap / LL), **P/VP** (= Market Cap / PL). Por ano
  projetado.

**Retornos (`calculador_retornos.py`) — decompor a TIR do acionista** (padrão aba Multiplos da
Direcional):
- TIR = `IRR([ −preço_atual, +dividendos_por_ação_t (do DFC), …, +preço_de_saída no ano de saída ])`,
  onde o preço de saída = **valor justo** (Equity/ações) — mantendo o truncamento em zero quando o
  target é negativo (A-5, responsabilidade limitada).
- **Decomposição** persistida: **apreciação %** = `target/preço − 1`; **yield acumulado %** = `Σ
  (dividendos_por_ação_t / preço_atual)`; **retorno total** = apreciação + yield (intuição) e a
  **TIR/MOIC** (número rigoroso). MOIC = `(Σ dividendos + preço_de_saída) / preço`.

**Análises históricas (bloco novo ou em `metricas_historicas`):** CAGR de **5 anos** da Receita
Líquida e do Lucro Líquido; **Margem EBITDA média 5a**; **CAPEX/Receita Líquida média 5a**; **ROE**
(LL/PL) por ano; ROIC/ROIIC por ano (já existem em `fcff`). Estes alimentam o painel histórico e os
gráficos da Semana 11.

**Cenários (`motor_cenarios.py`) — CORRIGIR os rótulos** (hoje invertidos):
- **Premissa "boa" (aumentar → mais valor):** crescimento da receita, margem bruta.
- **Premissa "ruim" (aumentar → menos valor):** SG&A %, alíquota, Kd.
- **BULL (otimista):** boas × 1,1; ruins × 0,9.
- **BEAR (pessimista):** boas × 0,9; ruins × 1,1.
- **BASE:** premissas atuais. Rodar a **cadeia completa** em estado isolado (backup/restore das
  premissas), persistir `cenarios = {bear, base, bull}` com `ev`, `equity_value`, `target_price`,
  `upside`, `taxa_desconto`. Garantir **Bull > Base > Bear em EV** e que o `base` bate exatamente
  com o `ev_equity` (regressão dourada).

**Checklist (`checklist.py`) — expor a razão de cada item** (para a Semana 11 mostrar no app). `U` =
**Universais**, `NF` = **Não-Financeiras**. Persistir, junto de cada item, um campo `descricao` com a
justificativa em uma frase (ex.: U1 "g < taxa de desconto, senão a perpetuidade diverge"; U4
"VP(VT) < 85% do EV, senão o valor todo está na perpetuidade"; NF5 "Dívida Líquida/EBITDA < 4x").
Adicionar/ajustar o item de **g**: `g < crescimento do PIB + inflação` usando os valores do
`macro_anual` (Focus/BACEN).

## Definição de Pronto (DoD)

- `ev_equity` com a espinha completa (Soma VP FCFF %, VP VT %, Dívida Bruta, Caixa, Dívida Líquida,
  Equity, Target, Upside). Múltiplos EV/EBITDA, EV/EBIT, P/E, P/VP por ano. Retornos com apreciação
  %, yield acumulado %, TIR e MOIC. Cenários com Bull>Base>Bear e rótulos corretos. Checklist com
  `descricao` por item e o item de g contra o macro. `pytest`/`black`/`flake8` verdes;
  `verificar_semana3` OK; golden explicado.

## O que NÃO fazer

- NÃO deixar Overview e Valuation com números duplicados (a fusão visual é o 11.0.0, mas os dados já
  saem daqui num bloco só). NÃO manter os rótulos Bear/Bull invertidos. NÃO deixar o target na FCFF.

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (A-5 registrado; documentar a correção dos cenários).

---
---

# PROMPT 10.0.3 — DDM para empresas financeiras (BBAS3, BBSE3, ITUB3/ITUB4): DCF via dividendos ao Ke

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/projecao/projetor_financeiro.py`,
`src/coleta/classificador_empresa.py` (detecção financeira/não-financeira), `calculador_wacc.py`
(Ke) e `Humano_revisar.md` (A-3 = Excel não cobre bancos). A aula é explícita: para **banco,
seguradora, resseguradora** a dívida é **operacional** (matéria-prima), não dá para separar
FCFF/FCFE do jeito convencional — o método correto é **Dividend Discount Model (DDM)**: projeta-se o
Lucro Líquido, aplica-se o payout, e desconta-se os dividendos ao **Ke**.

## Objetivo

Implementar o **DDM** como a trilha de valuation das **empresas financeiras**, com detecção
automática de tipo, e diferenciar financeira × não-financeira em todo o pipeline (motor, persistência
e — via Semana 11 — no app).

## Especificação técnica detalhada

**Detecção (já existe):** `classificador_empresa.py` marca `tipo = financeira | nao_financeira` nos
metadados. Todos os módulos leem esse tipo para escolher a trilha. Confirme que BBAS3, BBSE3
(seguradora), ITUB3/ITUB4 são classificados como `financeira`.

**Projeção financeira simplificada (`projetor_financeiro.py`):** para financeiras, projetar o
**Lucro Líquido** de forma simples e explicável (sem tentar um modelo bancário completo de margem
financeira/Basileia — isso fica fora de escopo, A-3):
- **LLₜ** a partir de uma trajetória de crescimento (premissa `crescimento_ll_ano1..8`, default =
  média-5a achatada) **ou** de `ROE × Patrimônio Líquido` (ROE premissa/histórico achatado, PL
  acumulando lucros retidos). Escolha a via `ROE × PL` como default (é a mais defensável) e
  documente.
- **Payout** = média histórica de 5 anos achatada. **Dividendos por açãoₜ** = LLₜ × payout / nº
  ações.

**Valuation por DDM (`calculador_ev.py`/novo `calculador_ddm.py`):**
- **Equity Value** = `Σ Dividendosₜ/(1+Ke)ᵗ + TV/(1+Ke)ⁿ`, com **TV = Dividendos_{n+1}/(Ke − g)** e
  `Dividendos_{n+1} = Dividendosₙ × (1+g)`.
- **Ke** via CAPM com ajuste Brasil (já em `calculador_wacc.py`); **sem WACC**, **sem bridge
  EV→Equity** (banco não tem dívida líquida separável). **Target = Equity / ações.**
- **Retornos** (reaproveitar `calculador_retornos.py`): TIR do acionista = `IRR([−preço, +dividendos
  por ação, …, +preço de saída = target])`; múltiplos de financeira = **P/E e P/VP** (sem
  EV/EBITDA/EV/EBIT, que não se aplicam).
- Persistir bloco `ddm` (dividendos por ano, VP, TV, Equity, target) e marcar `metodo_valuation:
  "DDM"` no JSON. Para não-financeiras, `metodo_valuation: "FCFF"` (inalterado).

**Checklist financeiro:** itens aplicáveis (g < Ke; g ≤ macro; payout 0–100%; ROE plausível); os
itens de EV/dívida líquida não se aplicam — degradar com aviso, nunca erro.

**Orquestradores:** `main.py`, `src/pipeline.py`, `src/verificar_semana3.py` escolhem a trilha por
`tipo` e chamam DDM para financeiras. O `verificar_semana3` deve rodar BBAS3/ITUB4 imprimindo
Equity DDM, target e TIR sem exceção.

## Definição de Pronto (DoD)

- BBAS3 e ITUB4 (e BBSE3 se coletável) rodam a trilha **DDM** ponta a ponta: LL projetado →
  dividendos → desconto ao Ke → Equity → target → TIR/MOIC, `metodo_valuation: "DDM"` persistido.
  Não-financeiras seguem em FCFF, byte-idênticas ao 10.0.2. `pytest` (com testes novos de DDM sem
  rede, via fixtures) `/black`/`flake8` verdes; `verificar_semana3` OK; golden das financeiras
  documentado.

## O que NÃO fazer

- NÃO tentar um modelo bancário completo (Basileia, provisão, capital regulatório) — é backlog. NÃO
  aplicar EV/EBITDA nem bridge de dívida líquida a banco. NÃO quebrar a trilha não-financeira.

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (A-3 → DDM entrega a trilha de valuation da financeira; Excel
bancário completo segue backlog).

---
---

# PROMPT 10.0.4 — Aba Macro reformatada (BACEN automatizado, layout "Brasil – Anual")

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/coleta/coletor_macro.py` (bloco `macro_anual`: CDI, IPCA,
IGP-M, câmbio, Selic, PIB via BACEN/Focus com convergência) e a aba **Macro** do `exportador_excel.py`.
Referência de **layout** (não de fonte): a aba "Brasil – Anual" do Itaú BBA e a aba Macro do
Smartfit — seções organizadas, anos em colunas, percentuais formatados. **A fonte continua o BACEN
automatizado** (decisão de Lucas: manter a automação de um clique); só a **apresentação** melhora.

## Objetivo

Manter a coleta macro 100% automatizada (BACEN/Focus) e **reformatar a aba Macro** para o padrão
visual "Brasil – Anual": seções, rótulos claros, anos históricos + projetados, formatação BR.

## Especificação técnica detalhada

- **Coleta inalterada:** `coletor_macro.py` segue montando `macro_anual` do BACEN/Focus, com Focus
  onde cobre e **convergência linear às metas** até o ano 8 (achatando o último ano projetado
  adiante, como fazem os modelos de referência). Não introduzir download manual.
- **Aba Macro do Excel — reformatar** para o layout "Brasil – Anual":
  - Seções com cabeçalho: **Atividade Econômica** (PIB real, PIB nominal), **Inflação** (IPCA,
    IGP-M), **Juros** (Selic fim de ano, CDI), **Câmbio** (BRL/USD). Marcador "X" na coluna A na
    linha de cada seção (padrão do 10.0.5).
  - Anos em colunas: históricos (últimos ~5–7) + projetados (2026E…2033E), rótulos `E` nos
    projetados. Percentuais com **1 casa** (formatação do 10.0.5); câmbio com 2 casas.
  - Linha de **fonte**: "Fonte: BACEN / Focus (coletado automaticamente em <data>)".
  - Os valores continuam vindo do `macro_anual` (fórmulas/valores que reproduzem o bloco do motor).
- Garantir que o **item de g do checklist** (10.0.2) leia o PIB+inflação desta aba/bloco.

## Definição de Pronto (DoD)

- Aba Macro reformatada (seções, anos, formatação BR, fonte BACEN) gerada para os golden, sem
  quebrar o recálculo de fórmulas (avaliador com 0 divergências). Coleta segue automática (1 clique).
  `pytest`/`black`/`flake8` verdes; `verificar_semana3` OK.

## O que NÃO fazer

- NÃO trocar a fonte por download manual do Itaú. NÃO alterar os números do `macro_anual` (é só
  apresentação). NÃO deixar percentual em decimal cru na aba.

## Ao final

`CONTEXT.md`.

---
---

# PROMPT 10.0.5 — Formatação BR global (Excel + dados) e polimento final do back-end

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/apresentacao/formatacao.py` (ponto único de formatação),
`src/exportacao/exportador_excel.py` e o modelo **WEGE3/Madero** (marcador de seção na coluna A;
referência histórica ao lado das premissas). **Este prompt fecha a Semana 10** deixando o Excel e os
dados no padrão de apresentação InFinance.

## Objetivo

Aplicar a **formatação BR única** em todo o Excel e nos dados, e os ajustes cosméticos que Lucas
pediu, sem alterar nenhum número calculado.

## Especificação técnica detalhada

**Ponto único (`formatacao.py`):** garanta funções robustas:
- `formatar_moeda_brl(x)`: milhar `17.469.557`; negativo entre parênteses `(17.469.557)`; **zero →
  `-`**. (Aplicar aos number formats do openpyxl e às tabelas do app.)
- `formatar_percentual_br(x)`: **1 casa** (`10,9%`); aplicar a **todo** valor que é taxa/margem/razão
  (crescimento, margens, SG&A, alíquota, payout, Kd, Ke, WACC, g, upside, yields, ROIC/ROIIC/ROE).
  Regra prática: se o campo é uma taxa/percentual, formata como %; se é R$, usa moeda BR.

**Excel — aplicar em TODAS as abas** (Capa, Premissas, Modelo, FCFF, FCFE, Macro, Sensibilidades,
Avisos), incluindo o **preview do app** (`montar_preview_por_aba`):
- Anos rotulados **`2026E, 2027E, …`** (nunca "Ano 1"). Fixe o horizonte em **8 anos** (2026E–2033E)
  e alinhe todas as abas.
- Valores negativos entre parênteses; zero como `-`; percentuais com 1 casa.
- **Remover a frase** `"(pre-D&A, padrão Direcional)"` da aba Modelo (só a frase; não mudar nada
  mais).
- **Marcador "X" na coluna A** nas linhas de seção (Premissas, DRE, Balanço, DFC, WK, Dívida, PP&E,
  seções do Macro) — rótulo na coluna B, "X" na coluna A, como no DCF WEGE3 e no Madero.
- **Check do balanço (Ativo = Passivo + PL) em TODOS os anos, inclusive 2020–2025.**
- **Referência histórica ao lado das premissas:** na aba Premissas, ao lado de cada premissa de
  vetor, mostrar os **valores históricos** (últimos 5 anos) que formaram a média achatada, para o
  leitor ter a âncora.
- **Painel histórico (aba Premissas/Modelo)** com formatação `17.469.557,0` (e negativos entre
  parênteses) para: Receita Líquida, EBITDA, Lucro Líquido, NWC, Intangível, Capital Investido,
  CAPEX aproximado, Dívida Bruta, **Caixa e Equivalentes (adicionar)**, **Dívida Líquida = Dívida
  Bruta − Caixa (adicionar)** e **ROE (adicionar)**. CAGRs de **5 anos** (Receita e LL); Margem
  EBITDA média 5a; CAPEX/Receita média 5a. Deixar **explícita a proveniência do beta** ("input do
  usuário — Bloomberg; default yfinance 5a").

**Consistência:** o avaliador de fórmulas (`tests/apoio_avaliador_excel.py`) deve continuar com **0
divergências** e Check "Ok" após a formatação (formatação não muda valor).

## Definição de Pronto (DoD)

- Excel dos golden com formatação BR completa (%, milhar, parênteses, `-`), anos `2026E…`, "X" na
  coluna A, Check em todos os anos, referência histórica nas premissas, painel histórico com as
  linhas novas (Caixa, Dívida Líquida, ROE) e CAGR-5a — **sem mudar nenhum número** (avaliador 0
  divergências). `pytest`/`black`/`flake8` verdes; `verificar_semana3` OK. **Fecha a Semana 10.**

## O que NÃO fazer

- NÃO alterar valores ao formatar. NÃO deixar percentual em decimal cru em lugar nenhum. NÃO mexer
  em gráficos/app (é a Semana 11).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. **Fecha a Semana 10.**

---
---

# SEMANA 11 — FRONT-END INSTITUCIONAL, GRÁFICOS VIVOS E DIFERENCIAÇÃO FINANCEIRA

---

# PROMPT 11.0.0 — Tema institucional, tabelas bonitas e a fusão Overview + Valuation

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `app.py` inteiro (fluxo de 4 etapas),
`src/visualizacao/tema_institucional.py` (tema Plotly + formatação BR) e `src/apresentacao/
formatacao.py`. **Este prompt monta a base visual** sobre a qual os gráficos entram. Regra dura:
o app **não recalcula** — só apresenta os blocos do motor (Semana 10).

## Objetivo

Aplicar a identidade institucional (fundo navy, IBM Plex Mono para números, verde/vermelho
semântico) a todas as tabelas do app, e **fundir Overview + Valuation** num painel único e completo
(fim da duplicação), com a **espinha do valuation** bem apresentada.

## Especificação técnica detalhada

- **Formatação BR em todas as tabelas do app:** toda `st.dataframe`/tabela passa pelas funções de
  `formatacao.py` (percentuais 1 casa; moeda com milhar; negativos entre parênteses; zero `-`).
  Números em fonte monoespaçada; verde para upside, vermelho para downside.
- **Fundir Overview + Valuation** na etapa ③ numa sub-aba única **"Valuation"** (as sub-abas de ③
  passam a ser: **Valuation, Histórico, Modelo, Retornos, Análise** — "Análise" recebe os gráficos
  no 11.0.1+). O painel "Valuation" mostra, de forma hierárquica (o que é decisão em destaque):
  - **Target Price, Upside, Recomendação, Score** no topo (destaque tipográfico).
  - **Espinha do valuation** (do bloco `ev_equity`, 10.0.2): Soma VP(FCFF) com % do EV, VP(VT) com %
    (peso da perpetuidade), = EV, − Dívida Bruta, + Caixa, = Dívida Líquida, = Equity, Target,
    Current, Upside.
  - **WACC/Ke** com origem (build-up CAPM vs `wacc_manual`), Kd (input), beta (input, proveniência),
    g. Para financeiras (10.0.3), mostrar **Ke e DDM** em vez de WACC/EV (ver 11.0.4).
  - **Checklist** com a `descricao` de cada item (10.0.2) — o usuário lê a justificativa de U1…NF5.
- Preservar o fluxo de 4 etapas e todas as capacidades atuais (nada some).

## Definição de Pronto (DoD)

- Etapa ③ com sub-abas `Valuation, Histórico, Modelo, Retornos, Análise`; Overview e Valuation
  fundidos sem duplicação; espinha do valuation com percentuais; todas as tabelas em formatação BR
  institucional. App sobe no navegador (porta 8601) sem erro de console para um não-financeiro e um
  financeiro. `tests/test_app.py` estendido (AppTest headless) verde; `pytest`/`black`/`flake8`
  limpos. Screenshot anexado.

## O que NÃO fazer

- NÃO recalcular valuation em JS. NÃO remover capacidades. NÃO deixar tabela com número cru
  (decimal/sem milhar).

## Ao final

`CONTEXT.md`.

---
---

# PROMPT 11.0.1 — Gráficos do histórico e do modelo: ROIC/ROIIC, margens e histórico vs projetado

## Papel e contexto

Você é o **Claude Opus 4.8**. Os módulos já existem, descongelados e testados (D-078):
`src/visualizacao/roic_roiic.py`, `historico_vs_projetado.py`, `dashboard_final.py`. **Faltam religar
ao app** na sub-aba "Análise". Regra: gráfico desenha número que o motor já tem.

## Objetivo

Entregar, na sub-aba **Análise** da etapa ③, os gráficos que Lucas pediu — todos sobre números que o
motor já possui e que ele sabe explicar.

## Especificação técnica detalhada

- **Import tardio** dos módulos de `src/visualizacao/` dentro da função da sub-aba (boot leve).
  Todos via `st.plotly_chart(fig, use_container_width=True)` com `tema_institucional`.
- Gráficos (cada um envolto em try/except que reporta na UI, nunca exceção):
  - **ROIC e ROIIC** histórico + projetado (`gerar_roic_roiic`), com o **spread ROIC − WACC** em
    destaque (o gráfico do "moat" da Aula 1).
  - **Margens** histórico + projetado: **Margem Bruta, Margem EBITDA, Margem Líquida** (usar
    `historico_vs_projetado` ou uma função nova simples que lê o bloco `dre`/`metricas`).
  - **Histórico vs Projetado** de **Receita Líquida, EBITDA, Lucro Líquido, FCFF** (grade 2×2,
    `gerar_historico_vs_projetado`) — o *reality check* visual das premissas.
  - (Opcional) **`dashboard_final`** como visão executiva no topo do painel Valuation.
- **CAGR-5a, Margem EBITDA média 5a, CAPEX/Receita média 5a, ROE** (do 10.0.2) exibidos como
  **cartões/tabela** ao lado dos gráficos.
- `@st.cache_data` com chave por mtime da projeção (como o preview do Excel já faz).
- **Financeiras:** onde ROIC/ROIIC não se aplicam bem, degradar com aviso e priorizar ROE/margens.

## Definição de Pronto (DoD)

- Sub-aba "Análise" renderiza ROIC/ROIIC (+ spread), margens e histórico-vs-projetado como gráficos
  Plotly reais para DIRR3/MGLU3/SMFT3/WEGE3; financeira degrada com aviso. Zero erro de console.
  `tests/test_app.py` cobre a existência/render das sub-abas; `pytest`/`black`/`flake8` limpos.
  Screenshot anexado.

## O que NÃO fazer

- NÃO importar `src/visualizacao/` no topo do `app.py` (import tardio). NÃO recalcular em JS. NÃO
  deixar gráfico estourar exceção quando faltar dado.

## Ao final

`CONTEXT.md`.

---
---

# PROMPT 11.0.2 — O gráfico de retorno em blocos (apreciação + yield) e o waterfall EV → Equity

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/visualizacao/waterfall_ev.py` e os blocos `retornos` e
`ev_equity` (10.0.2). **Estes são os dois gráficos-assinatura** que Lucas pediu explicitamente.

## Objetivo

Entregar (1) o **gráfico de blocos do retorno da ação** e (2) o **waterfall EV→Equity**, ambos 100%
sobre números que o motor possui.

## Especificação técnica detalhada

- **Gráfico de blocos do retorno** (novo módulo `src/visualizacao/retorno_acionista.py` ou dentro de
  `dashboard_final`): **barra empilhada** que decompõe o **retorno total** em:
  - **Apreciação** = `target/preço − 1` (alcançar o valor justo = Equity/ações), e
  - **Yield acumulado** = `Σ dividendos_por_ação_t / preço_atual`.
  Exibir o total no topo da barra e cada componente rotulado (ex.: 46,6% total = 33,3% apreciação +
  13,3% yield). Ao lado, os números rigorosos **TIR** e **MOIC** (bloco `retornos`). Usa o exemplo
  mental de Lucas: R$30 → R$40 + R$4 de dividendo.
- **Waterfall EV → Equity** (`gerar_waterfall_ev`): passos `Soma VP(FCFF) → + VP(VT) → = EV → −
  Dívida Bruta → + Caixa → = Equity Value`, cada passo com o **% da contribuição** (do `ev_equity`).
  É a versão visual da "espinha do valuation".
- Ambos na sub-aba **Análise** (ou Retornos), via `tema_institucional`, com `@st.cache_data`.
- **Financeiras (DDM):** o waterfall vira `Σ VP(dividendos) → + VP(TV) → = Equity` (sem dívida
  líquida); o gráfico de retorno é idêntico (apreciação + yield).

## Definição de Pronto (DoD)

- Gráfico de retorno em blocos (apreciação + yield, com TIR/MOIC ao lado) e waterfall EV→Equity
  renderizando como Plotly real para os golden; versão DDM para financeira. Números batem com os
  blocos `retornos`/`ev_equity` (o app não recalcula). Zero erro de console; testes AppTest verdes;
  `pytest`/`black`/`flake8` limpos. Screenshot anexado.

## O que NÃO fazer

- NÃO calcular retorno/EV no gráfico — leia dos blocos. NÃO usar EV/dívida líquida para financeira.

## Ao final

`CONTEXT.md`.

---
---

# PROMPT 11.0.3 — Sensibilidade (heatmap WACC×g), cenários Bear/Base/Bull e football field só com as faixas próprias

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/visualizacao/sensibilidade_wacc_g.py`, `apoio_heatmap.py`,
`football_field.py`, `sensibilidade_receita_margem.py` e o bloco `cenarios` (10.0.2). **Aqui vale a
distinção da conversa franca:** faça os gráficos cujos números o analista possui; **não** automatize
comparáveis/peers (isso exige seleção de peers e coleta de múltiplos que o analista ainda não crava).

## Objetivo

Entregar sensibilidade e cenários **sobre números próprios**, e um **football field enxuto** só com
as faixas que o motor calcula — sem a faixa de comparáveis.

## Especificação técnica detalhada

- **Heatmap de sensibilidade WACC × g** (`gerar_sensibilidade_wacc_g` + `apoio_heatmap`): mapa de
  calor do Target (ou Equity) variando WACC e g, com a **célula do caso atual destacada**. Ler a
  grade que o motor persiste (ou chamar o motor para gerá-la — **nunca** recalcular em JS). Idem, se
  quiser, Receita × Margem (`sensibilidade_receita_margem`).
- **Cenários Bear/Base/Bull** (do bloco `cenarios`, 10.0.2, **com os rótulos corrigidos**): um
  gráfico de barras (target por cenário) e/ou uma tabela, deixando claro Bull > Base > Bear.
- **Football field enxuto** (`gerar_football_field`) — **só as faixas que o motor calcula**:
  1. **DCF Bear / Base / Bull** (do `cenarios`).
  2. **Múltiplo de saída** (`apoio_cenarios.target_por_multiplo_saida` sobre o EBITDA/LL projetado).
  3. **Faixa de 52 semanas** (do mercado já coletado, se houver).
  4. **Preço atual** (linha vertical de referência).
  **NÃO incluir a faixa de comparáveis/peers** (fica para depois — é a parte que o analista não
  defende hoje). Se uma faixa não tiver dado, **omitir com aviso amigável**, nunca inventar.
  Financeira: DCF via DDM + 52 semanas + preço atual (sem EV/EBITDA).

## Definição de Pronto (DoD)

- Heatmap WACC×g com a célula atual destacada; cenários Bear<Base<Bull (rótulos corretos); football
  field com DCF (bear/base/bull) + múltiplo de saída + 52 semanas + preço atual, **sem** faixa de
  comps. Tudo Plotly real para os golden; financeira degrada corretamente. Zero erro de console;
  testes AppTest verdes; `pytest`/`black`/`flake8` limpos. Screenshot anexado.

## O que NÃO fazer

- NÃO automatizar comparáveis/peers nem coletar múltiplos de peers. NÃO recalcular sensibilidade em
  JS. NÃO deixar barra colada em zero sem rótulo quando o target satura.

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (comparáveis automatizados = adiado por decisão de reescopo).

---
---

# PROMPT 11.0.4 — Diferenciação financeira × não-financeira no app + aba de Ajuda ("Como usar / o que cada botão faz")

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `app.py` e o resultado do DDM (10.0.3). Duas entregas: (1) o app
precisa **mostrar a diferença** entre empresa financeira (DDM) e não-financeira (FCFF); (2) uma aba
de **Ajuda** que explica os controles do Streamlit e do app — Lucas perguntou "o que são Deploy,
Rerun, Clear cache, Print, Record screen?".

## Objetivo

Deixar explícito no app qual método está rodando (FCFF vs DDM) e criar uma aba de Ajuda que funciona
como um README embutido para quem usa o app.

## Especificação técnica detalhada

**Diferenciação financeira × não-financeira:**
- Ao carregar a empresa, exibir um selo/rótulo claro: **"Não-financeira — valuation por FCFF/WACC"**
  ou **"Financeira — valuation por DDM (dividendos ao Ke)"**, lendo `metodo_valuation` do JSON.
- Para financeiras, o painel **Valuation** mostra a mecânica do **DDM** (Σ VP dividendos + VP TV =
  Equity → target), o **Ke** (sem WACC/EV/dívida líquida), e a sub-aba **Modelo** mostra a projeção
  financeira (LL → payout → dividendos), sem WK/PP&E/leasing de não-financeira. Múltiplos = P/E e
  P/VP. A etapa ④ Exportar informa, com clareza, se o Excel cobre aquele tipo (hoje o Excel de 8
  abas é da trilha não-financeira; para financeira, exibir o valuation no app e um aviso — o Excel
  bancário completo é backlog).

**Aba de Ajuda (nova, na sidebar ou como etapa/expander):**
- **"O que cada botão do topo faz"** (controles do Streamlit, não do app):
  - **Rerun** — re-executa o app do zero. **Always rerun / Auto rerun** — re-executa sozinho quando o
    código muda (modo dev). **Clear cache** — limpa o cache de cálculo (`@st.cache_data`), forçando
    recomputar. **Print** — impressão da página pelo navegador. **Record a screencast** — gravação de
    tela nativa. **Deploy** — publicar na nuvem do Streamlit (irrelevante rodando local). **Settings**
    — tema e modo wide. Considere **esconder** Deploy e afins via `.streamlit/config.toml`
    (`toolbarMode = "minimal"`) para o app ter cara de produto.
  - **"O que cada etapa e controle do app faz"**: ① Empresa, ② Premissas (o que é cada uma das 4 +
    Kd/beta/g, e que o default é média-5a achatada, editável ano a ano), ③ Resultados (cada sub-aba),
    ④ Exportar. Explicar as **cores do Excel** (azul = CVM, verde = premissa, preto = fórmula) e o
    significado do **Check** (Ativo = Passivo + PL).
- Texto em português, direto, com a mesma identidade visual.

## Definição de Pronto (DoD)

- App mostra o selo FCFF vs DDM e adapta o painel Valuation/Modelo por tipo (não-financeira x
  financeira) sem exceção. Aba de Ajuda explica os botões do Streamlit e cada controle do app.
  Controles supérfluos do Streamlit escondidos via config. Testes AppTest verdes; `pytest`/`black`/
  `flake8` limpos; screenshot (um não-financeiro + um financeiro) anexado.

## O que NÃO fazer

- NÃO mostrar bridge EV→Equity/dívida líquida para banco. NÃO prometer Excel bancário completo (é
  backlog). NÃO deixar o usuário sem explicação dos controles.

## Ao final

`CONTEXT.md`.

---
---

# PROMPT 11.0.5 — Fechamento da v2.1: cortar Power BI, enxugar a documentação à realidade e validação em lote

## Papel e contexto

Você é o **Claude Opus 4.8**. Fecha a Semana 11 e a v2.1. Leia `src/exportacao/exportador_bi.py`,
`README.md`, `CONTEXT.md`, `docs/CHANGELOG.md` e `Humano_revisar.md` (A-4 = destino do
`exportador_bi`; A-7 = unit economics). **Regra "só o que sei explicar" vale também para os
documentos:** o README não pode prometer o que não está vivo.

## Objetivo

Remover o peso morto (Power BI), alinhar a documentação à realidade, e validar o sistema completo em
lote (não-financeiras + financeiras) ponta a ponta.

## Especificação técnica detalhada

- **Cortar Power BI / `exportador_bi.py`** (A-4): remover o módulo e as referências (ou arquivá-lo
  claramente como fora de escopo). Streamlit + Excel são a camada de apresentação; Power BI sai.
- **Enxugar o README à realidade:** remover/rebaixar as promessas de Power BI, "football field com 7
  metodologias", comparáveis automatizados e unit economics (que **não** estão vivos). Descrever
  fielmente: coleta CVM automatizada + auditor; motor pré-D&A enxuto (4 premissas, Kd/beta input, WC
  4 contas, sem IFRS-16 pesado, dívida com amortização CP/LP + captação documentada); **FCFF/WACC
  para não-financeiras e DDM para
  financeiras**; Excel de 8 abas com formatação BR; app guiado com **gráficos vivos** (ROIC/ROIIC,
  margens, retorno em blocos, waterfall, heatmap, football field enxuto) e aba de Ajuda. Atualizar o
  roadmap (v2.1 fechada; backlog explícito: Excel bancário completo, comparáveis automatizados, unit
  economics setorial — v2.2/v3.0).
- **Validação em lote (≥ 12 tickers):** DIRR3/MGLU3/SMFT3/WEGE3 + setores variados + **financeiras
  BBAS3/ITUB4/BBSE3**. Provar ponta a ponta: coleta → motor (FCFF ou DDM) → Excel → app com
  gráficos. **Premissa → efeito provado:** mudar 1 premissa muda os 3 demonstrativos + FCFF/FCFE (ou
  dividendos/DDM) + os gráficos. Catalogar casos de borda.
- **Golden final** (DIRR3/MGLU3/SMFT3 + WEGE3 + uma financeira) re-explicado e baseline atualizado.

## Definição de Pronto (DoD)

- `exportador_bi`/Power BI removidos; README fiel ao que existe (sem overclaim); lote de ≥ 12
  empresas verde (não-financeiras em FCFF, financeiras em DDM); premissa→efeito provado incluindo os
  gráficos; golden final explicado. `pytest`/`black`/`flake8` limpos; `verificar_semana3` OK.
- **A v2.1 fecha o "DCF Automatizado" completo e explicável:** dados fiéis à CVM → motor enxuto por
  tipo (FCFF/WACC ou DDM/Ke) → Excel "Modelo" com formatação BR → app institucional com gráficos
  vivos dos números que o analista sabe defender.

## O que NÃO fazer

- NÃO deixar o README prometendo o que não está vivo. NÃO reintroduzir Power BI, comparáveis
  automatizados ou unit economics (backlog). NÃO deixar nenhum golden mudar sem explicação por
  driver.

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. **Fecha a Semana 11 e a v2.1.**

---
---

## Apêndice A — Fluxo de trabalho dos 2 atores

> **Humano (Lucas):** julgamento (premissas reais, validação numérica contra RI/Status Invest),
> descrição de bugs, commits/tags, revisão do `Humano_revisar.md`. → **Claude Opus 4.8:** implementa
> TODO o código e o front-end, confere cada erro e funcionalidade, valida gráficos/tabelas/Excel/app,
> testa (`pytest`/`black`/`flake8`), atualiza `CONTEXT.md`. → **Humano** fecha (revisa e commita).

## Apêndice B — Critério de avanço

Não abra o prompt N+1 antes de o DoD do prompt N estar verde **e** o golden (DIRR3/MGLU3/SMFT3 +
WEGE3) explicado por driver. Cada prompt deixa o repositório consistente e testável. **Não abra a
Semana 11 antes de fechar a Semana 10** (os gráficos dependem dos números corretos). Se uma sessão
terminar no meio de um prompt, registre o ponto exato no `CONTEXT.md` e retome do mesmo prompt.

## Apêndice C — Mapa das decisões da conversa franca (o "porquê" de cada mudança)

| Mudança | Origem | Prompt |
|---|---|---|
| Kd = input (CDI+spread), fim do Kd derivado | A-2 + aula ("últimas emissões") + WEGE3 (48%) | 10.0.0 |
| Beta = input (Bloomberg), fim do clamp/0,5x | conversa + aula (beta vs Ibovespa) | 10.0.0 |
| Caixa = CDI; caixa mínimo sai do painel (segue na política de dívida) | aula + WEGE3 (29% absurdo) | 10.0.0 |
| Premissas = 4 + média-5a achatada (override mantido) | conversa + Madero/WEGE3 | 10.0.0 |
| Payout/minoritários/outras = média histórica achatada | conversa | 10.0.0 |
| WC de 4 contas (365 dias, achatado) | Madero + aula + WEGE3 | 10.0.1 |
| IFRS-16 pesado removido (leasing só linha no BP) | conversa (simplicidade) | 10.0.1 |
| Dívida: amortização ATUAL mantida e documentada (CP no ano 1 + LP linear 5a + captação p/ caixa mínimo + instrumentos opcionais) | decisão de Lucas 23/07 | 10.0.1 |
| DFC com dividendos + Caixa BOP→EOP | Madero + WEGE3 | 10.0.1 |
| Espinha do valuation (Soma VP FCFF %, VP VT %, Dív. Bruta, Caixa, Dív. Líq., Equity) | Direcional FCFF | 10.0.2 |
| FCFE ao Ke; remover target da FCFF | aula + conversa | 10.0.2 |
| Múltiplos EV/EBITDA, EV/EBIT, P/E, P/VP por ano | conversa | 10.0.2 |
| TIR decomposta (apreciação + yield) + MOIC | Direcional Multiplos + conversa | 10.0.2 |
| Cenários Bear/Bull com rótulos corrigidos | conversa (estavam invertidos) | 10.0.2 |
| Checklist com `descricao`; g < PIB+inflação (macro) | conversa + aula | 10.0.2 |
| **DDM para financeiras (BBAS3/BBSE3/ITUB3)** | pedido de Lucas + aula (banco = DDM) | 10.0.3 |
| Macro reformatada (BACEN automatizado, layout Itaú) | pedido de Lucas | 10.0.4 |
| Formatação BR global (%, milhar, parênteses, 0→"-", 2026E, X col A, Check histórico) | conversa + WEGE3/Madero | 10.0.5 |
| Tema institucional + fusão Overview/Valuation | conversa | 11.0.0 |
| Gráficos ROIC/ROIIC, margens, histórico vs projetado | pedido de Lucas | 11.0.1 |
| Gráfico de retorno em blocos + waterfall EV→Equity | pedido de Lucas | 11.0.2 |
| Heatmap sensibilidade + cenários + football field enxuto (sem comps) | conversa | 11.0.3 |
| Diferenciação FCFF×DDM no app + aba de Ajuda | pedido de Lucas | 11.0.4 |
| Cortar Power BI; enxugar README à realidade | conversa | 11.0.5 |

## Apêndice D — Backlog explícito (NÃO fazer nas Semanas 10–11)

| Item | Alvo |
|---|---|
| Excel bancário completo (margem financeira/Basileia/capital regulatório) | v2.2 |
| Comparáveis/peers automatizados (football field com faixa de comps) | v2.2 |
| Amortização da dívida pelo calendário real (ANBIMA/debêntures) | v2.2 |
| Sensibilidade "viva" que recalcula ao vivo (hoje: heatmap estático da grade) | v2.2 |
| `exportador_bi.py` + Power BI + nota PDF | removido/backlog |
| Unit economics setorial / build-up de receita (VGV×VSO×PoC; academias×ticket) | v3.0 |

## Apêndice E — Checklist do HUMANO (Lucas)

1. **Colar um prompt por vez** (10.0.0 → 10.0.5, depois 11.0.0 → 11.0.5) no Opus e conferir o DoD
   antes do próximo.
2. **Commitar** ao fim de cada prompt (sugestão: `claude semana 10.0.N` / `claude semana 11.0.N`).
3. **Validar contra o seu WEGE3:** ao fim da Semana 10, comparar o target/estrutura do programa com
   o DCF Wege3.xlsx e explicar diferenças (o WEGE3 é o 4º golden).
4. **Premissas reais** de DIRR3/MGLU3/SMFT3/WEGE3 quando quiser que o target/cenários/football field
   sejam tese, não ponto de partida automático.
5. **Terminar o módulo de DCF/FCFF/FCFE no Wall Street Prep** para defender essa parte de olhos
   fechados.
6. Se discordar de qualquer decisão, reverter via `Humano_revisar.md` — nada é definitivo até você
   aprovar.
