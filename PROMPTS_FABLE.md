# PROMPTS_FABLE.md — v2.1 · **Semana 10** · Gráficos vivos no app (Plotly) + football field automatizado + comparáveis reais

> **Implementador deste documento: o Claude Opus 4.8.** O Opus lê os documentos de
> contexto, **escreve e edita TODO o código Python e o front-end**, confere **cada erro e
> cada funcionalidade**, valida o **front-end do app** (Streamlit), os **gráficos e
> tabelas** (Plotly) e o **Excel gerado**, roda os testes (`pytest`/`black`/`flake8`) e
> atualiza `CONTEXT.md` + `Humano_revisar.md`. O **humano (Lucas)** é o dono do
> julgamento analítico (premissas reais, validação numérica, commits e a revisão do
> `Humano_revisar.md`).
>
> **A Semana 9.0 está CONCLUÍDA e foi REMOVIDA deste documento** (histórico completo em
> `CONTEXT.md` Seção 8 e `docs/CHANGELOG.md`). Este arquivo contém **APENAS a Semana 10**.
> Ela nasce da revisão multi-agente que fechou a Semana 9.0 e apontou como **lacuna nº 1**:
> **o app não tem gráficos**. Todos foram congelados no Prompt 9.0.0 (Enxugamento, D-053) e
> parcialmente descongelados na revisão (D-078). A Semana 10 os **religa ao app**, com o
> **football field 100% automatizado**, e fecha os achados menores da revisão.
>
> **Calendário:**
> | Semana | Período | Tema | Prompts | Status |
> |---|---|---|---|---|
> | 9.0 | 17→20/07/2026 | Automação fiel à CVM + motor "padrão Direcional" + Excel "Modelo" 8 abas | 9.0.0…9.0.5 | ✅ CONCLUÍDA (fora deste doc) |
> | **10** | 20→27/07/2026 | **Gráficos vivos no app + football field automatizado + comparáveis reais + achados da revisão** | **10.0.0…10.0.5** | 🟡 EM EXECUÇÃO |

---

## 0. ESTADO ATUAL DO REPOSITÓRIO — a fundação da Semana 10 (leia ANTES de qualquer prompt)

O Opus **não** deve re-descobrir isto por tentativa e erro. É o resultado, já entregue e
testado, da Semana 9.0:

### 0.1 Motor (fonte única de verdade — `src/projecao/` + `src/valuation/`)

- **DRE pré-D&A** (padrão Direcional): margem bruta e SG&A são de **nível EBITDA**; a D&A é
  **linha própria** (schedule PP&E) subtraída depois. A `margem_ebitda` é **derivada**
  (margem bruta − SG&A), não é mais premissa de entrada.
- **Cadeia** (ordem obrigatória): `projetor_dre → schedule_wk → schedule_ppe →
  schedule_leasing → schedule_divida → dfc_indireto → calculador_fcff → calculador_wacc →
  calculador_vt → calculador_ev → calcular_fcfe_naofinanceira → calculador_retornos →
  checklist`. Os 3 orquestradores (`main.py`, `src/pipeline.py`, `src/verificar_semana3.py`)
  chamam essa cadeia na mesma ordem.
- **Blocos persistidos** em `data/processed/<TICKER>_projecao.json` (o contrato que os
  gráficos consomem): `ano0`, `dre` (pré-D&A: `receita_bruta`, `deducoes`,
  `receita_liquida`, `cpv_cmv`, `lucro_bruto`, `sgna`, `ebit_ex_depreciacao`,
  `depreciacao_amortizacao`, `ebit`, `resultado_financeiro`, `ebt`, `ir_csll`,
  `ll_antes_minoritarios`, `participacao_minoritarios`, `lucro_liquido`, `lpa`, `margem_*`),
  `wk` (multi-driver: `contas_receber`, `estoques`, `tributos_a_recuperar`, `fornecedores`,
  `obrigacoes_sociais_trabalhistas`, `adiantamento_clientes`, `nwc`/`nwc_multi_driver`,
  `delta_nwc`), `ppe`, `divida`, `leasing`, `balanco` (com `verificacao_balanco` = check),
  `dfc` (indireto — o `dfc_simplificado` foi REMOVIDO no 9.0.5), `fcff` (com `roic`/`roiic`
  por ano), `fcfe`, `fcfe_valuation` (desconto ao Ke; `divergencia_vs_bridge` = AVISO),
  `retornos` (`tir_moic` com `cenarios` bear/base/bull e `dividendos_por_acao`; `multiplos`
  por ano), `wacc` (`wacc`, `wacc_capm_buildup`, `wacc_origem`, `wacc_manual`),
  `valor_terminal`, `ev_equity` (com `ajustes_bridge`), `checklist`.
- **WACC manual:** premissa `wacc_manual` (decimal em (0,1]) vence o build-up CAPM;
  `wacc_origem` indica a origem.
- **Sinais (regra dura):** despesas/saídas NEGATIVAS, receitas/entradas POSITIVAS.
- **Vetores de premissa:** 8 valores individuais (`_ano1..8`), nunca taxa única replicada.
- **Valores negativos são VÁLIDOS** (ROIC/FCFF/LL/target): o código NÃO trava.
- **Regressão dourada TRIPLA:** DIRR3, MGLU3, SMFT3 não mudam de target sem explicação por
  driver. Baseline atual: rode `python -m src.verificar_semana3` (deve imprimir SEMANA 3 OK).

### 0.2 Excel "Modelo" (`src/exportacao/exportador_excel.py`)

- **8 abas** na ordem `NOMES_ABAS = (Capa, Premissas, Modelo, FCFF, FCFE, Macro,
  Sensibilidades, Avisos)`. `Modelo` = 3 demonstrativos abertos + schedules com **linha
  Check** booleana; `FCFF`/`FCFE` em **abas separadas** referenciando `Modelo!`.
- **Cores de Lucas (NÃO WSP):** **histórico da CVM = AZUL** (`COR_HISTORICO`),
  **premissa que o usuário escolhe = VERDE** (`COR_PREMISSA`), **fórmula = PRETO**
  (`COR_FORMULA`).
- Fórmulas **nativas vivas** que reproduzem o motor via a classe `Aba` (método `Aba.calculo`
  grava a fórmula só se ela reproduz o valor do motor; senão grava o valor + comentário).
  Um avaliador de fórmulas em `tests/apoio_avaliador_excel.py` (classe `Avaliador`) recalcula
  o workbook célula a célula — **0 divergências** garantido.
- `montar_preview_por_aba(ticker, raiz)` devolve as 8 abas como DataFrames (o app renderiza
  na etapa ④ Exportar).

### 0.3 Front-end (`app.py`, Streamlit)

- **Fluxo guiado de 4 etapas** (radio na sidebar, `session_state["etapa"]`):
  **`① Empresa` → `② Premissas` → `③ Resultados` → `④ Exportar`**.
- **② Premissas:** as 6 premissas de Lucas em grupos colapsáveis (crescimento, margem
  BRUTA pré-D&A, SG&A, alíquota anual, WACC manual opcional, Outros). Validação em tempo
  real (g≥WACC bloqueia). **A margem EBITDA aparece derivada, read-only.**
- **③ Resultados:** 5 sub-abas hoje — `Overview, Historico, Valuation, Modelo, Retornos`.
  **NÃO há nenhum gráfico Plotly** (tudo é `st.dataframe`).
- **Regra dura (Princípio 3):** o app **NUNCA recalcula valuation em JS**. Apresenta os
  blocos persistidos; quando precisa de um número novo, chama o **motor Python**.

### 0.4 Módulos de gráficos — DESCONGELADOS e testados na revisão (D-078)

Os módulos abaixo foram descongelados, re-alinhados ao motor 9.0.x, cobertos por teste
(suíte **204 passed, 0 skipped**) e **verificados gerando figura Plotly real com dados
reais do DIRR3**. Estão prontos como bibliotecas — **falta apenas religá-los ao app**
(Prompt 10.0.4) e alimentar o football field/comparáveis com dados reais (10.0.1/10.0.2/
10.0.3). Assinaturas públicas (todas `(ticker, raiz_projeto=None) -> {"figura", "html",
"png"}` salvo indicação):

| Módulo | Função pública | Estado |
|---|---|---|
| `src/visualizacao/roic_roiic.py` | `gerar_roic_roiic` | OK real (8 traces) |
| `src/visualizacao/tornado.py` | `gerar_tornado`, `calcular_impactos` | OK real |
| `src/visualizacao/waterfall_ev.py` | `gerar_waterfall_ev` | OK real |
| `src/visualizacao/sensibilidade_wacc_g.py` | `gerar_sensibilidade_wacc_g` | OK real |
| `src/visualizacao/sensibilidade_receita_margem.py` | `gerar_sensibilidade_receita_margem` | OK real |
| `src/visualizacao/sensibilidade_setor.py` | `gerar_sensibilidade_setor` | descongelado |
| `src/visualizacao/historico_vs_projetado.py` | `gerar_historico_vs_projetado` | OK real (8 traces) |
| `src/visualizacao/dashboard_final.py` | `gerar_dashboard_final` | OK real (6 traces) |
| `src/visualizacao/comparacao_empresas.py` | `gerar_comparacao_empresas`, `montar_painel_comparacao` | descongelado |
| `src/visualizacao/tabela_comparaveis.py` | `montar_linhas_tabela` | descongelado |
| `src/visualizacao/apoio_heatmap.py` | `trace_heatmap_target`, `trace_heatmap_percentual` | descongelado |
| `src/visualizacao/football_field.py` | `gerar_football_field`, `montar_metodologias` | OK real (3 faixas) |
| `src/valuation/comparaveis.py` | `carregar_comparaveis`, `obter_peers_do_subtipo`, `coletar_multiplos_yfinance` | descongelado |
| `src/valuation/motor_cenarios.py` | `executar_cenarios(ticker, raiz) -> {bear,base,bull}` | OK real (bear<base<bull) |

Retidos no núcleo (nunca congelados): `src/visualizacao/tema_institucional.py` (tema
Plotly + `salvar_grafico` + formatação BR) e `src/visualizacao/apoio_cenarios.py`
(`carregar_projecao`, `carregar_mercado`, `recalcular_cenario`, `target_por_multiplo_saida`).
Ainda congelado (backlog v2.2): `src/exportacao/exportador_bi.py`.

### 0.5 Regras invariantes da Semana 10 (valem para TODOS os prompts)

1. **Gráfico é APRESENTAÇÃO** — nenhum número nasce num gráfico. Cada barra/ponto/célula
   vem de um bloco persistido pelo motor (ou de uma coleta de mercado explícita). Valor por
   cenário vem do bloco `cenarios` (motor de cenários), nunca de matemática solta no `.py`
   do gráfico.
2. **"Automatizado" = sem placeholder e sem hard-code.** Peers do football field vêm de
   coleta real (yfinance) por subtipo; 52 semanas vêm do mercado coletado; bear/bull vêm do
   motor de cenários rodando a cadeia de verdade. Insumo ausente → a barra/painel **omite
   com aviso amigável** (Princípio 7), nunca inventa.
3. **Tema institucional único:** todo gráfico usa `tema_institucional.py`. Zero estilo
   ad-hoc. Modo claro/escuro coerente com o app.
4. **Princípio 3:** o app não recalcula valuation em JS. "Sensibilidade viva" = o app chama
   o **motor Python** (ou lê a grade que o motor de cenários persistiu) e destaca o caso
   atual.
5. **Robustez:** gráfico/aba sem dado → mensagem amigável, **nunca exceção**. O app sobe
   para TODOS os tickers, inclusive financeiras (degradam com aviso onde não se aplicam).
6. **Determinismo dos testes:** testes sem rede (injetar Rf/preço/peers via fixtures); a
   coleta real (yfinance) só no runtime, com fallback offline.

### 0.6 Ambiente e comandos (obrigatório)

- Validação SEMPRE com a venv: `.venv/Scripts/python.exe -m pytest tests -q`,
  `... -m black src tests app.py main.py --check --workers 1` (o `--workers 1` é
  obrigatório nesta máquina), `... -m flake8 src tests app.py main.py`.
- Regressão: `.venv/Scripts/python.exe -m src.verificar_semana3` deve imprimir SEMANA 3 OK.
- App headless (teste sem navegador): `from streamlit.testing.v1 import AppTest`. App real:
  `.claude/launch.json` tem o server `dcf-app` na porta 8601.
- **Golden triplo:** DIRR3, MGLU3, SMFT3. Nenhum target muda sem explicação por driver.

### 0.7 Ordem e critério de avanço

Os prompts 10.0.0 → 10.0.5 são **progressivos**. Não abra o prompt N+1 antes do DoD do N
estar verde **e** o golden triplo explicado. Se uma sessão terminar no meio de um prompt,
registre o ponto exato no `CONTEXT.md` e retome do mesmo prompt. **Cole um prompt por vez
no Opus.**

---
---

# PROMPT 10.0.0 — Confirmar o descongelamento e blindar o re-alinhamento ao motor 9.0.x

## Papel e contexto

Você é o **Claude Opus 4.8**, implementador único do código. Leia `CONTEXT.md` (Seção 8,
sessões de 20/07), `Humano_revisar.md` (D-053 = o que foi congelado; D-078 = o
descongelamento parcial já feito) e os 14 módulos da tabela em §0.4. A revisão já removeu
os banners `# CONGELADO`, destravou os 12 testes e provou que os módulos geram figura
Plotly com dados reais do DIRR3. **Este prompt fecha a fundação:** garantir que TODO módulo
está 100% alinhado à estrutura de blocos atual, para os prompts seguintes construírem sobre
terreno sólido.

## Objetivo

Auditar linha a linha os 14 módulos descongelados contra os blocos persistidos de HOJE (não
os da v2.0), corrigir qualquer referência a campo/bloco que mudou, e cobrir cada módulo com
um teste que roda contra **dados reais dos 3 golden** (DIRR3, MGLU3, SMFT3), não só
fixtures. Sem religar no app ainda (isso é o 10.0.4).

## Especificação técnica detalhada

- **Varredura por módulo:** para cada arquivo em §0.4, confirme que ele lê APENAS campos que
  existem no contrato de §0.1. Pontos historicamente sensíveis: (a) qualquer leitura de
  `dfc_simplificado` (REMOVIDO — usar `dfc`); (b) `margem_ebitda` como *driver* de projeção
  (agora é derivada — usar `ebit_ex_depreciacao`/`ebitda` do bloco `dre`); (c) ROIC/ROIIC
  (agora vivem no bloco `fcff` por ano, não em bloco próprio); (d) `retornos.tir_moic.
  cenarios` e `retornos.multiplos` para os gráficos de retorno; (e) `wacc.wacc_origem`/
  `wacc_manual` onde o gráfico mostrar o WACC; (f) `balanco.verificacao_balanco` onde
  mostrar o check; (g) `fcfe_valuation.divergencia_vs_bridge` como AVISO.
- **Financeiras:** cada módulo deve degradar com aviso onde o conceito não se aplica (ex.:
  football field de banco usa P/L e P/VP, sem EV/EBITDA; ROIC/ROIIC bancário via
  `capital_regulatorio`). Nunca lançar exceção.
- **Tema:** confirme que todos usam `tema_institucional` (cores, fontes, layout, `salvar_
  grafico`); nada de cores/fontes hard-coded no módulo do gráfico.
- **Testes com dados reais:** para cada um dos 4 arquivos de teste já destravados
  (`test_roic_roiic`, `test_comparaveis`, `test_motor_cenarios`, `test_football_field`) e
  para os módulos sem teste dedicado (tornado, waterfall_ev, sensibilidades, dashboard_final,
  historico_vs_projetado, comparacao_empresas, tabela_comparaveis), adicione ao menos 1 teste
  que gere a figura para **DIRR3 (construtora/RET), MGLU3 (varejo) e SMFT3 (leasing alto)** a
  partir dos JSONs persistidos, com `salvar_grafico` mockado (não escrever HTML/PNG no teste),
  e asserte: nº de traces esperado, título correto, e ausência de exceção nos 3 tipos.

## Definição de Pronto (DoD)

- Nenhuma referência a `dfc_simplificado`, a `margem_ebitda`-como-driver ou a bloco ROIC
  próprio sobra nos 14 módulos. Todos geram figura para DIRR3/MGLU3/SMFT3 (e degradam com
  aviso para uma financeira, ex.: ITUB4) sem exceção.
- Testes novos verdes e SEM skip de congelamento. `pytest`/`black`/`flake8` limpos.
  `verificar_semana3` OK. Golden triplo inalterado (só apresentação muda).

## O que NÃO fazer

- NÃO religar no `app.py` (10.0.4). NÃO redesenhar os gráficos (é re-alinhamento). NÃO
  tocar no motor de valuation.

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (fechar o descongelamento — D-078 → concluído).

---
---

# PROMPT 10.0.1 — Comparáveis reais automatizados (peers → múltiplos → quartis)

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/valuation/comparaveis.py`, `config/setores.json`
(peers por subtipo) e `src/coleta/coletor_mercado.py`. O football field (10.0.3), a tabela
de comparáveis e a aba Comparáveis do app (10.0.4) dependem de peers reais — hoje a v1.0
usava placeholders (`comps_placeholder_*` em `config/parametros.json`), que a Semana 10
**elimina**.

## Objetivo

Fazer o `comparaveis.py` coletar, calcular e persistir **múltiplos reais de mercado dos
peers** por subtipo, com quartis, de forma automatizada e robusta.

## Especificação técnica detalhada

- **Peers por subtipo:** definir/consumir a lista de tickers comparáveis por subtipo em
  `config/setores.json` (ex.: `construcao_civil → [CYRE3, EZTC3, TEND3, ...]`; `varejo →
  [LREN3, ARZZ3, ...]`). Peer não listado / subtipo sem peers → **aviso + barra de comps
  omitida** (nunca placeholder).
- **Coleta via yfinance** (padrão do projeto, com fallback offline para o já persistido):
  EV/EBITDA, P/L, EV/Receita e P/VP dos peers. Peer sem dado → `_registrar_peer_excluido`
  e seguir (nunca quebrar).
- **Estatística:** **Q1 / mediana / Q3** por múltiplo (as faixas do football field).
  Persistir `data/processed/<TICKER>_comparaveis.json`: `{subtipo, peers_validos,
  peers_excluidos, multiplos_por_peer, estatisticas{multiplo:{q1,mediana,q3}}, data_coleta,
  fonte}`.
- **Denominadores do motor:** o alvo implícito por múltiplo usa o EBITDA/receita/LL/PL
  **projetado pelo motor** (bloco `dre`/`ev_equity`), nunca um número solto.
- **Financeiras:** só P/L e P/VP (sem EV/EBITDA/EV-Receita).
- Registrar todo campo novo no mapeamento se aplicável; nomes de coluna só existem se
  registrados em `config/mapeamento_cvm.json`.

## Definição de Pronto (DoD)

- `data/processed/<TICKER>_comparaveis.json` gerado para DIRR3, MGLU3, SMFT3 (não-fin.) e
  uma financeira (ITUB3/ITUB4), com **quartis reais e peers reais** (zero placeholder).
  Ticker sem peers no config → aviso, sem quebra.
- `tests/test_comparaveis.py` estendido: quartis corretos de uma amostra conhecida; exclusão
  de peer sem dado; denominadores do motor; degradação sem peers. `pytest`/`black`/`flake8`
  verdes.

## O que NÃO fazer

- NÃO usar `comps_placeholder_*`. NÃO inventar peer. NÃO indexar múltiplos a nada.

## Ao final

`CONTEXT.md` + `Humano_revisar.md`.

---
---

# PROMPT 10.0.2 — Motor de cenários Bear/Base/Bull automatizado + achado do target ≤ 0

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `src/valuation/motor_cenarios.py` (já descongelado; hoje
`executar_cenarios(ticker, raiz)` roda a cadeia e devolve `{bear, base, bull}` com
`target_price`/`taxa_desconto`) e o bloco `cenarios` de `config/parametros.json`
(`bear`/`bull` com `fator_crescimento`, `delta_margem_pp`, `delta_wacc_pp`, `delta_g_pp`).
A grade bear/base/bull e o football field dependem daqui.

## Objetivo

Consolidar Bear/Base/Bull **rodados pelo motor de verdade**, persistindo o bloco `cenarios`
na projeção, e **resolver o achado da revisão (D-073):** quando o target do caso base é
≤ 0, a grade colapsa (os três saturam em zero) e perde poder discriminante.

## Especificação técnica detalhada

- **Cada cenário** aplica os deltas de config às premissas (crescimento ×fator, margem
  ±pp — sobre a **margem bruta pré-D&A**, coerente com o motor atual —, WACC ±pp, g ±pp),
  roda a **cadeia completa** num estado ISOLADO (não poluir o caso base persistido; hoje o
  módulo já faz backup/restore das premissas — preserve isso) e coleta `ev`, `equity_value`,
  `target_price`, `upside`, `taxa_desconto`, `premissas_delta`. Persistir o bloco `cenarios`
  = `{bear, base, bull}` em `data/processed/<TICKER>_projecao.json`.
- **Achado do target ≤ 0 (D-073):** manter o **preço-alvo por ação truncado em zero**
  (responsabilidade limitada — correto), MAS **preservar a discriminação** persistindo
  também `ev` e `equity_value` por cenário (que NÃO saturam) e a flag
  `target_saturado_em_zero: true`. Assim o football field/grade mostram a dispersão real de
  EV/Equity mesmo quando o alvo por ação é 0 nos três (o usuário vê que Bull ≠ Bear no valor
  da firma).
- **Coerência:** o cenário `base` de `cenarios` tem que bater EXATAMENTE com o `ev_equity`
  persistido (mesma premissa, mesma matemática) — é regressão dourada.
- **WACC do cenário:** aplicar `delta_wacc_pp` sobre o WACC efetivo (respeitando
  `wacc_manual` quando houver).

## Definição de Pronto (DoD)

- Bloco `cenarios` persistido para DIRR3/MGLU3/SMFT3: `base` idêntico ao `ev_equity`;
  **Bull > Base > Bear em EV** para todos. Para SMFT3 (target ≤ 0), `ev`/`equity_value`
  discriminam os três cenários e a flag `target_saturado_em_zero` aparece. Premissas do
  analista SEMPRE restauradas após os cenários (backup removido). `pytest`/`black`/`flake8`
  verdes; `verificar_semana3` OK.

## O que NÃO fazer

- NÃO recalcular cenário em JS. NÃO deixar o cenário sobrescrever o caso base no disco. NÃO
  mexer no golden (o base tem que continuar idêntico).

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (registrar a resolução do achado do target ≤ 0).

---
---

# PROMPT 10.0.3 — Football field automatizado (todos os 6 critérios) + waterfall EV

## Papel e contexto

Você é o **Claude Opus 4.8**. Com peers reais (10.0.1) e cenários (10.0.2) prontos, leia
`src/visualizacao/football_field.py` (`montar_metodologias`, `gerar_football_field`),
`src/visualizacao/waterfall_ev.py` e `src/visualizacao/apoio_cenarios.py`
(`target_por_multiplo_saida`, `carregar_mercado`). Este é o **gráfico-assinatura que Lucas
pediu funcionando com TODOS os critérios automatizados**.

## Objetivo

Gerar o **Football Field** com as 6 faixas automatizadas e o **Waterfall** do bridge
EV→Equity, ambos prontos para o app (10.0.4) e para o Excel (10.0.5).

## Especificação técnica detalhada

O football field compõe (cada faixa **opcional por disponibilidade de dado**, com aviso
quando faltar — Princípio 7):

1. **DCF Bear / Base / Bull** — do bloco `cenarios` (10.0.2), em preço-alvo por ação;
   quando o alvo satura em 0, usar a **dispersão de EV/Equity** (rótulo claro, sem barras
   coladas em 0).
2. **Comps EV/EBITDA** — faixa Q1–mediana–Q3 dos peers (10.0.1) × **EBITDA projetado do
   motor** → alvo implícito por ação.
3. **Comps P/L** — Q1–mediana–Q3 × **LL projetado** (ou `lpa` × ações).
4. **Múltiplo de Saída** — `target_por_multiplo_saida` sobre o EBITDA₈.
5. **Faixa de 52 semanas** — do mercado coletado (`data/raw/mercado/<TICKER>_mercado.json`).
6. **Preço atual** — linha vertical de referência.

- **Financeiras:** substituir EV/EBITDA por **P/L e P/VP** (comps de banco); manter DCF
  (FCFE/Ke), múltiplo de saída via P/L e 52 semanas.
- **Waterfall EV→Equity** (`gerar_waterfall_ev`): `Soma VP(FCFF) → +VP(VT) → =EV → −Dívida
  bruta → +Caixa → +Aplicações → −Minoritários → +Coligadas → +Não-operacionais → =Equity`,
  usando `ev_equity.ajustes_bridge`; cada passo com % da contribuição.
- Salvar PNG em `outputs/graficos/<TICKER>_football_field.png` e `_waterfall_ev.png` (o
  Excel do 10.0.5 os reincorpora) e **devolver a figura Plotly** para o app.

## Definição de Pronto (DoD)

- Football field de DIRR3/MGLU3/SMFT3 com as 6 faixas quando há dado (omissão explícita
  quando não há), preço atual marcado, e o caso target ≤ 0 (SMFT3) mostrando dispersão por
  EV. Waterfall fechando EV→Equity nos 3. `tests/test_football_field.py` cobrindo: presença
  de barra por disponibilidade, comps a partir dos quartis reais, faixa de 52 semanas do
  mercado, financeira (P/L, P/VP, sem EV/EBITDA), e o caso target ≤ 0. `pytest`/`black`/
  `flake8` verdes.

## O que NÃO fazer

- NÃO usar placeholder de comps. NÃO inventar 52 semanas sem mercado coletado. NÃO deixar
  barra colada em 0 sem rótulo quando o target satura.

## Ao final

`CONTEXT.md` + `Humano_revisar.md`.

---
---

# PROMPT 10.0.4 — Religar os gráficos no app: sub-abas Análise / Comparáveis / Comparar + achado do capex

## Papel e contexto

Você é o **Claude Opus 4.8**. Leia `app.py` inteiro (fluxo guiado de 4 etapas do 9.0.4) e
`tests/test_app.py`. **Este é o prompt que ENTREGA o que Lucas pediu:** os gráficos vivos
dentro do app. Você implementa a UI, confere no navegador (Streamlit) e garante zero erro
de console.

## Objetivo

Reintegrar as visualizações à **etapa ③ Resultados**, com sub-abas novas, mantendo o
Princípio 3. Resolver o achado cosmético do capex.

## Especificação técnica detalhada

- **Etapa ③ Resultados** passa a ter as sub-abas (ordem): **Overview, Histórico, Valuation,
  Modelo, Retornos** (as 5 atuais) **+ Análise, Comparáveis, Comparar** (novas). Todos os
  gráficos via `st.plotly_chart(fig, use_container_width=True)` com o tema institucional
  (import tardio dos módulos de `src/visualizacao/` dentro da função da sub-aba, para o
  boot do app seguir leve):
  - **Análise:** ROIC/ROIIC (`gerar_roic_roiic`), **tornado** (`gerar_tornado` —
    sensibilidade do target às premissas), e **sensibilidade viva** WACC×g
    (`gerar_sensibilidade_wacc_g`) e Receita×Margem (`gerar_sensibilidade_receita_margem`).
    "Viva" = um controle (slider/number_input) que, ao mudar e salvar, chama o **motor
    Python** para recalcular a grade (NÃO recalcula em JS); no mínimo, lê a grade do motor
    de cenários e **destaca a célula do caso atual**.
  - **Comparáveis:** o **football field** (`gerar_football_field`), a **tabela de
    comparáveis** (`tabela_comparaveis.montar_linhas_tabela` — peers, múltiplos, quartis do
    10.0.1) e o **waterfall** EV→Equity (`gerar_waterfall_ev`).
  - **Comparar:** painel multi-empresa lado a lado (`comparacao_empresas.
    montar_painel_comparacao`/`gerar_comparacao_empresas`) + watchlist das empresas já
    analisadas (as com `data/processed/<TICKER>_projecao.json`).
  - (Opcional) o **dashboard_final** (`gerar_dashboard_final`) como visão executiva no
    Overview.
- **Achado do capex (D-073, cosmético):** no editor de premissas da etapa ②, **mover o
  vetor `capex_receita` para o grupo "⑥ Outros"** (a lista de premissas de Lucas coloca o
  capex em "Outros"); o editor de vetores "①②③" fica só com crescimento, margem bruta e
  SG&A. Sem mudança de comportamento, só de agrupamento.
- **Financeiras:** as sub-abas de gráficos degradam com aviso claro onde não se aplicam
  (football field de banco = P/L e P/VP; sem EV/EBITDA). O app sobe para todos os tickers.
- **Robustez:** gráfico sem dado → `st.info`/`st.warning` amigável, nunca exceção
  (envolva cada geração em try/except que reporta na UI).
- **Cache:** os gráficos são funções puras dos JSONs persistidos — use `@st.cache_data`
  com chave de invalidação por mtime da projeção (como o preview do Excel já faz).

## Definição de Pronto (DoD)

- No navegador (preview_start `dcf-app`, porta 8601) com SMFT3 e mais um ticker: etapa ③
  com as **8 sub-abas**; football field, tornado, waterfall, ROIC/ROIIC e sensibilidade
  renderizam como **gráficos Plotly reais**; Comparar mostra ≥ 3 empresas; capex agora no
  grupo "Outros". **Zero erro de console** (`read_console_messages onlyErrors`). Screenshot
  anexado no relatório.
- `tests/test_app.py` estendido (AppTest headless): as 8 sub-abas existem e renderizam sem
  exceção; o grupo "Outros" contém o capex; nenhuma das 5 sub-abas antigas nem as 4 etapas
  perdidas. `pytest` geral verde; `black`/`flake8` limpos.

## O que NÃO fazer

- NÃO recalcular valuation em JS (sensibilidade viva chama o motor Python). NÃO remover as
  tabelas atuais — os gráficos SOMAM às tabelas. NÃO importar `src/visualizacao/` no topo do
  `app.py` (import tardio dentro das sub-abas).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`.

---
---

# PROMPT 10.0.5 — Gráficos no Excel + granularidade do mapeamento + auditoria dupla + fechamento da Semana 10

## Papel e contexto

Você é o **Claude Opus 4.8**. Fecha a Semana 10 e a v2.1. Leia
`src/exportacao/exportador_excel.py` (8 abas do 9.0.5), `tests/apoio_avaliador_excel.py`
(avaliador de fórmulas) e `config/mapeamento_cvm.json`.

## Objetivo

(1) Reincorporar os gráficos ao Excel; (2) resolver o achado da cobertura de mapeamento
> 5%; (3) auditoria dupla do Excel recalculado; (4) universalização B3 e fechamento.

## Especificação técnica detalhada

- **Gráficos no Excel:** embutir os PNGs (football field, waterfall, ROIC/ROIIC,
  dashboard) numa aba (reforçar `Sensibilidades`/`Avisos` ou criar uma aba `Gráficos`
  antes de Avisos), via `openpyxl.drawing.image.Image` + `kaleido`, como a Direcional faz —
  **sem quebrar o recálculo das fórmulas** nas abas de números (imagens ficam em aba
  própria ou em região sem fórmulas). Regenerar os PNGs no fluxo do exportador quando
  ausentes.
- **Achado da cobertura > 5% (D-073, BAIXO):** granularizar `config/mapeamento_cvm.json`
  para os residuais nomeados que a auditoria da **ABEV3** (passivo 5,6–8,6%) e **VALE3**
  (ativo 2023 6,03%) expôs — mapear as subcontas reais ("Imposto de Renda a Recuperar",
  "Provisão para Benefícios/Assistência Médica", "Outros Passivos" etc.) por CD_CONTA/nome,
  reduzindo o residual **sem mudar nenhum total** (o balanço já fecha — é só granularidade).
  Re-rodar o auditor (`auditor_cvm.py`) e mostrar a cobertura melhorando (residual < 5% ou
  o restante explicado linha a linha).
- **Auditoria dupla do Excel:** rodar o `Avaliador` sobre os 5 golden + 3 tickers novos,
  confirmando **0 divergências** e Check "Ok"×8; deixar como teste permanente
  (`tests/test_exportador_excel.py`).
- **Universalização B3:** lote de ≥ 12 empresas de setores variados ponta a ponta
  (coleta → motor → Excel → app com gráficos), casos de borda catalogados; **premissa→efeito
  provado** (mudar 1 premissa muda os 3 demonstrativos + FCFF + FCFE + os gráficos e o
  football field).

## Definição de Pronto (DoD)

- Excel dos 5 golden com gráficos embutidos abrindo no Excel real sem reparo e recalculando
  sem mudar valores; cobertura de mapeamento da ABEV3/VALE3 abaixo de 5% (ou explicada linha
  a linha); lote de ≥ 12 empresas verde; `pytest`/`black`/`flake8` limpos; `verificar_
  semana3` OK; golden triplo explicado.
- **A Semana 10 fecha o "DCF Automatizado" COMPLETO:** dados automáticos e fiéis à CVM →
  motor por tipo → Excel "Modelo" com FCFF/FCFE e gráficos embutidos → app guiado com
  **gráficos vivos** (football field/comparáveis/sensibilidades automatizados).

## O que NÃO fazer

- NÃO mudar nenhum total do balanço ao granularizar o mapeamento (é só nomear residual).
  NÃO reintroduzir unit economics / build-up de receita (segue v3.0).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. **Fecha a Semana 10 e a v2.1.**

---
---

## Apêndice A — Fluxo de trabalho dos 2 atores

> **Humano (Lucas):** julgamento (premissas reais, validação numérica contra RI/Status
> Invest), descrição de bugs, commits/tags, revisão do `Humano_revisar.md`. → **Claude Opus
> 4.8:** implementa TODO o código e o front-end, confere cada erro e funcionalidade, valida
> gráficos/tabelas/Excel/app, testa (`pytest`/`black`/`flake8`), atualiza `CONTEXT.md`. →
> **Humano** fecha (revisa e commita).

## Apêndice B — Critério de avanço

Não abra o prompt N+1 antes de o DoD do prompt N estar verde **e** o golden triplo
(DIRR3/MGLU3/SMFT3) explicado. Cada prompt deixa o repositório consistente e testável. Se
uma sessão terminar no meio de um prompt, registre o ponto exato no `CONTEXT.md` e retome do
mesmo prompt.

## Apêndice C — Backlog explícito (NÃO fazer na Semana 10)

| Item | Alvo |
|---|---|
| Excel bancário completo (FCFE/capital regulatório para financeiras) | v2.2 |
| `exportador_bi.py` + Power BI (`.pbix`) + nota PDF + Projetado vs. Realizado | v2.2 |
| Colunas trimestrais 1Q–4Q + LTM | v2.2 |
| Conversão automática de moeda de instrumentos de dívida | v2.2 |
| Integração dos fluxos de caixa do leasing (principal) ao DFC/BP (hoje só os juros) | v2.2 |
| Unit economics setorial / build-up de receita (VGV×VSO×PoC, academias×ticket, coortes) | v3.0 |
| LBO simplificado, research report multipágina, consenso de analistas | v3.0 |

## Apêndice D — Checklist do HUMANO na Semana 10 (Lucas)

1. **Colar um prompt por vez** (10.0.0 → 10.0.5) no Opus e conferir o DoD antes do próximo.
2. **Commitar** ao fim de cada prompt (mensagem sugerida: `claude semana 10.0.N`).
3. **Revisar `Humano_revisar.md`** ao fim da semana (decisões D-075+ e as novas).
4. **Conferir os gráficos no app** (`streamlit run app.py` → etapa ③ → Análise/Comparáveis/
   Comparar) em 1-2 empresas que você conheça: o football field faz sentido? Os comps
   batem com o mercado?
5. **Premissas reais** de DIRR3/MGLU3/SMFT3 quando quiser que o Target e o football field
   sejam tese (o pipeline gera automáticas; a comparação só faz sentido com as suas).
6. Se discordar de qualquer decisão, reverter via `Humano_revisar.md` — nada é definitivo
   até você aprovar.
