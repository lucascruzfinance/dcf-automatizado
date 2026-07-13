# PROMPTS_FABLE.md — Planejamento v2.0 "Universalização" · 5 prompts progressivos para o Claude Fable 5

> **Público-alvo deste documento: o Claude Fable 5 (IA de implementação do projeto).**
> A partir da v2.0, o Fable 5 assume o papel que antes era do Codex — ele lê os
> documentos de contexto, escreve/edita o código Python e o front-end, roda os testes e
> atualiza o `CONTEXT.md`. O **humano (Lucas)** continua sendo o dono do julgamento
> analítico (premissas reais, validação numérica) e o **Claude Code** continua sendo o
> gerador/curador destes prompts e o revisor final.
>
> **Como usar:** os 5 prompts abaixo são **progressivos e sequenciais**. Cada um só
> começa depois que o anterior fechou a sua "Definição de Pronto". Cada prompt é
> auto-contido: reafirma os princípios invariantes, lista os arquivos a criar/editar,
> especifica os contratos entre módulos e define os critérios objetivos de aceite.
> **Cole um prompt por vez no Claude Fable 5.** Não pule etapas — a ordem existe porque
> cada onda destrava a seguinte (dados → motor → triangulação → front-end → export/automação).
>
> **Regra de precedência:** se um prompt conflitar com o `ROTEIRO.md`/`CONTEXT.md`, o
> pedido explícito do humano na sessão vence, mas o Fable deve avisar sobre o conflito
> antes de executar.
>
> **Protocolo de decisões autônomas (instrução permanente de Lucas, 12/07/2026):** quando
> o Fable encontrar erro, ambiguidade, conflito ou escolha que caberia ao humano, ele NÃO
> para para perguntar: escolhe sozinho a melhor opção disponível, executa e registra em
> **`Humano_revisar.md`** (data, situação, escolha, alternativas, justificativa). O humano
> revisa esse arquivo e pode reverter qualquer decisão registrada.

---

## 0. Onde chegamos (v1.0) e para onde vamos (v2.0)

### 0.1 O que a v1.0 entregou (estado real do repositório, tag `versao 1.0`)

A v1.0 cumpriu a filosofia de **profundidade antes de amplitude**. Está PRONTO e VALIDADO:

- **Pipeline de 5 módulos ponta a ponta** para **DIRR3 (construção)** e **MGLU3 (varejo)** —
  ambas não-financeiras — rodando via `python main.py --ticker <T> --setor <S> --usar-premissas-existentes`.
- **Coleta** (`src/coleta/`): CVM (DFP/ITR de DRE, BP, DFC), yfinance (preço, beta, ações,
  market cap, faixa 52 semanas, T-Bond 10Y), BACEN (Selic, IPCA, Focus).
- **Métricas históricas** (`src/metricas/metricas_historicas.py`): trilha não-financeira
  validada (CAGR, margens, ROIC/DuPont, ROIIC, DSO/DIO/DPO/CCC, dívida líquida/EBITDA,
  cobertura, beta Hamada). Trilha financeira apenas como esqueleto **não validado**.
- **Projeção** (`src/projecao/`): DRE 8 anos com 8 taxas individuais de crescimento,
  margem e CAPEX; schedules de WK (modo `dias` e `percentual_receita`), PP&E e Dívida;
  balanço fecha `Ativo = Passivo + PL` nos 8 anos.
- **Valuation** (`src/valuation/`): FCFF, FCFE, WACC completo, VT (Gordon), bridge
  EV→Equity→Target Price→Upside→Recomendação, ROIC/ROIIC projetados, checklist de
  consistência (U1–U5, NF1–NF5).
- **Visualização** (`src/visualizacao/`): 7+ gráficos Plotly institucionais (Football
  Field, Waterfall, sensibilidades WACC×g / Receita×Margem / setorial, histórico vs.
  projetado, ROIC/ROIIC, dashboard final) em HTML+PNG.
- **Front-end** (`app.py` + `.streamlit/config.toml`): Streamlit com 6 seções (Overview,
  Histórico, Premissas, Valuation, Análise, Excel Preview), tema navy institucional,
  edição de premissas com histórico ao lado e validação em tempo real.
- **Excel** (`src/exportacao/exportador_excel.py`): 7 abas com **fórmulas nativas**,
  convenção de cor WSP (azul=input, preto=fórmula, verde=link), nomes definidos, PNGs
  embutidos, validado célula a célula no Excel real.
- **Testes:** ~73 testes verdes; `black` e `flake8` limpos.

### 0.2 O que ficou por fechar / é dívida técnica da v1.0

- **`src/exportacao/exportador_bi.py` NÃO existe** — o contrato de export para Power BI
  (tabelas planas em `outputs/bi/<TICKER>/`) ainda não foi implementado.
- **Aba "Excel Preview" do app** é um stub declarado (não renderiza as 7 abas nem baixa o `.xlsx`).
- **Comps do Football Field são placeholders** (EV/EBITDA e P/L falsos — não há peers reais).
- **Trilha financeira (FCFE/Ke) nunca foi validada** contra um banco real.
- Simplificações do motor v1: **dívida bruta constante sem amortização, payout 0%, caixa
  como plug, aplicações constantes, sem receita financeira sobre caixa, minoritários /
  coligadas / ativos não-operacionais zerados**, RET sobre Receita Líquida (proxy, não Bruta).
- **`config/mapeamento_cvm.json` cobre só 64 campos**, curados à mão para 2 empresas.

### 0.3 O objetivo original (o "porquê" desde o início)

O README e os roteiros deixam explícito: construir um **sistema de valuation por DCF que
aceita o ticker de QUALQUER empresa da B3**, detecta o tipo (financeira/não-financeira e
subtipo setorial), coleta os dados oficiais, calcula o valuation pelo método correto,
apresenta tudo num front-end institucional e exporta um modelo Excel de nível profissional —
automatizando o trabalho mecânico e preservando o julgamento humano nas premissas.
A v1.0 provou a **arquitetura** com 2 empresas. Faltava a **universalidade real**.

### 0.4 A meta da v2.0 "Universalização" (o que estes 5 prompts perseguem)

> **Rodar `python main.py --ticker <QUALQUER_TICKER_B3>` (ou selecionar a empresa no
> front-end) e obter um DCF completo, correto para o tipo da empresa, com dados reais,
> comparáveis reais, front-end multi-empresa e Excel/BI profissionais — sem editar código
> nem o mapeamento à mão para cada nova empresa.**

Não precisa ficar perfeito ao fim dos 5 prompts. O objetivo é **estender e redirecionar**
o sistema para chegar o mais perto possível dessa meta, nesta ordem:

| Prompt | Onda | Destrava |
|--------|------|----------|
| **1** | Coleta e mapeamento CVM universais | Qualquer empresa entra no pipeline com dados limpos |
| **2** | Motor de valuation universal e completo | Números reais e método correto por tipo (inclui financeiras) |
| **3** | Comparáveis / CCA + triangulação + dados de mercado | Football Field e múltiplos deixam de ser placeholder |
| **4** | Front-end institucional multi-empresa de próxima geração | Analista usa qualquer ticker, compara empresas, ajusta ao vivo |
| **5** | Excel/BI/PDF profissionais + automação e orquestração de dados | Entregáveis completos e pipeline automatizado em lote |

---

## Princípios invariantes (valem para TODOS os 5 prompts — releia sempre)

Estes princípios não mudam. Violá-los é bug, mesmo que o código rode.

1. **Idioma do código:** nomes de função, variável e comentário em **português**.
2. **Fonte única de verdade nos nomes de coluna:** toda coluna de DataFrame usa o nome
   padronizado em `config/mapeamento_cvm.json`. A mesma grandeza tem o MESMO nome em
   coleta, projeção, valuation e exportação. **Nunca** introduzir um nome novo sem registrá-lo lá.
3. **Fonte única de verdade no cálculo:** o motor Python calcula uma vez. Streamlit, Excel,
   Power BI e PDF apenas **apresentam** o mesmo resultado. **Zero recálculo** em JavaScript ou DAX.
4. **Sinais:** despesas e saídas de caixa negativas; receitas e entradas positivas.
5. **8 valores individuais:** crescimento de receita, margem e CAPEX têm 8 campos por ano
   (`..._ano1` a `..._ano8`). **Nunca** replicar uma taxa única pelos 8 anos.
6. **Negativos são válidos:** ROIC, FCFF e LL podem ser negativos. Não travar.
7. **Robustez de dados externos:** todo acesso a campo da CVM/API trata campo ausente ou
   renomeado **sem quebrar silenciosamente**. Campo não mapeado vai para log, não derruba o pipeline.
8. **Qualidade por etapa:** toda função com docstring; todo cálculo financeiro com comentário
   da fórmula; `black` e `flake8` limpos; teste `pytest` correspondente antes de considerar pronto.
9. **Configuração, não hard-code:** o que varia por setor/empresa vive em `config/*.json`
   ou nas premissas (JSON), nunca embutido no código.
10. **Continuidade:** ao final de cada prompt, atualizar a seção "Estado Atual" do `CONTEXT.md`
    com o que foi feito, decisões tomadas, bugs conhecidos e a próxima tarefa.
11. **Design institucional:** paleta navy (`#0A1628` fundo, `#0F1E33` superfície, `#1B4F8C`
    azul âncora), **verde `#16A34A` = upside / vermelho `#DC2626` = downside** (uso semântico
    estrito), texto em sans (Inter/IBM Plex Sans), números em mono (IBM Plex Mono). Cada
    elemento se justifica; todo Target Price expõe o WACC e o g que o geraram.
12. **Compatibilidade retroativa:** DIRR3 e MGLU3 continuam sendo o teste de regressão dourado.
    Nenhuma mudança pode quebrar o resultado validado dessas duas empresas. Antes de fechar
    cada prompt, rode as duas e confirme que o Target Price não regrediu sem explicação.

---
---

# PROMPT 1 — Coleta e Mapeamento CVM Universais (a fundação de dados)

## Papel e contexto

Você é o **Claude Fable 5**, IA de implementação do projeto **DCF Automatizado**. Antes de
escrever qualquer linha, leia integralmente `CONTEXT.md`, `ROTEIRO.md`, a Seção 0 e os
Princípios Invariantes deste arquivo, `config/mapeamento_cvm.json`, `config/setores.json`,
`config/parametros.json` e `src/coleta/coletor_cvm.py`. Você está iniciando a **v2.0 —
Universalização**. Esta é a **Onda 1 de 5**.

## Objetivo desta onda

Transformar a camada de coleta — hoje curada à mão para DIRR3 e MGLU3 — em uma camada
**universal e resiliente** que aceita **qualquer ticker da B3** e entrega dados limpos,
padronizados e auditáveis, com um relatório de qualidade por empresa. Ao fim desta onda,
qualquer empresa listada deve **entrar no pipeline** (mesmo que o valuation completo dela
só amadureça nas ondas seguintes).

## Por que agora / o que destrava

O maior bloqueador de "qualquer empresa" é o **mapeamento de contas da CVM**. Hoje, mapear
por `DS_CONTA` (o nome-texto da conta) é frágil: cada empresa escreve o nome de um jeito.
A DFP/ITR da CVM, porém, traz um **código de conta padronizado (`CD_CONTA`)** hierárquico
(ex.: `3.01` = Receita, `3.02` = Custo, `3.11` = Lucro Líquido, `1` = Ativo, `2` = Passivo).
Esse código é a chave universal. Nesta onda migramos o mapeamento para ser **primariamente
por `CD_CONTA`**, com fallback por nome e classificação automática de contas não mapeadas.

## Especificação técnica detalhada

### 1.1 Resolvedor universal de ticker → CD_CVM

- **Arquivo:** `src/coleta/resolvedor_ticker.py` (novo).
- Dado qualquer ticker B3 (ex.: `VALE3`, `ITUB4`, `PETR4`, `WEGE3`, `BBAS3`, `RENT3`,
  `RADL3`, `SUZB3`, `PRIO3`, `EQTL3`...), resolver o `CD_CVM` cruzando o cadastro de
  companhias abertas (`cad_cia_aberta`) e os arquivos FCA da CVM (via `CNPJ_Companhia` ↔
  `CNPJ_CIA`), como já faz o `coletor_cvm.py` hoje — mas extraído para um módulo reutilizável.
- Suportar múltiplos tickers da mesma empresa (ON/PN/UNIT: `PETR3`/`PETR4`, `ITUB3`/`ITUB4`).
- Cachear o mapa ticker→CD_CVM em `data/raw/cvm/_cadastro_b3.parquet` para não rebaixar a CVM a cada run.
- Ticker inexistente/deslistado → erro claro e acionável, sem stack trace cru.

### 1.2 Detecção universal do tipo e subtipo de empresa

- **Arquivo:** `src/coleta/classificador_empresa.py` (novo).
- A partir do setor de atividade da CVM (`SETOR_ATIV` do FCA) e/ou classificação setorial,
  classificar a empresa em:
  - `tipo`: `nao_financeira` | `financeira`.
  - `subtipo`: `banco`, `seguradora`, `holding`, `utility_energia`, `saneamento`, `telecom`,
    `mineracao`, `oleo_gas`, `construcao_civil`, `varejo`, `industria`, `consumo`, `saude`,
    `agro`, `papel_celulose`, `transporte_logistica`, `tecnologia`, `outros`.
- Mapa setor CVM → subtipo em `config/setores.json` (estender — ver 1.5). Setor não
  reconhecido cai em `outros` com `metodo_valuation = FCFF` (default seguro) e vai para log.
- Persistir `tipo` e `subtipo` no `_meta.json`. Todos os módulos posteriores leem daí.

### 1.3 Mapeamento CVM por CD_CONTA (a mudança estrutural)

- **Arquivo:** reescrever `config/mapeamento_cvm.json` para o esquema:
  ```json
  {
    "versao": "2.0",
    "descricao": "...",
    "por_codigo": {
      "dre": { "3.01": "receita_liquida", "3.02": "cpv_cmv", "3.11": "lucro_liquido", ... },
      "bp_ativo": { "1": "ativo_total", "1.01.01": "caixa_equivalentes", ... },
      "bp_passivo": { "2.01.04": "divida_cp", "2.02.01": "divida_lp", "2.03": "patrimonio_liquido", ... },
      "dfc": { "6.01": "fco", "6.02": "fci", "6.03": "fcf", ... }
    },
    "por_nome_fallback": { "receita_liquida": ["receita de venda", "receita operacional líquida", ...] },
    "campos": { ...manter o dicionário atual de nomes padronizados como catálogo... }
  }
  ```
- **Arquivo:** `src/coleta/mapeador_contas.py` (novo). Função de mapeamento em cascata:
  1. Match exato por `CD_CONTA` no bloco da demonstração correta.
  2. Se não houver código, match por prefixo hierárquico mais próximo.
  3. Fallback por normalização de `DS_CONTA` (lowercase, sem acento) contra `por_nome_fallback`.
  4. Nada encontrado → registra em `logs/contas_cvm_nao_mapeadas.log` com ticker, código, nome,
     demonstração e valor, **sem quebrar**.
- Contas de bancos/seguradoras têm plano diferente (ex.: `3.01` de banco = Receita de
  Intermediação Financeira). Mapear os blocos financeiros também, marcados por tipo.

### 1.4 Coletor CVM universal + limpeza real

- **Editar** `src/coleta/coletor_cvm.py`: usar o resolvedor (1.1), o classificador (1.2) e o
  mapeador (1.3). Coletar DFP + ITR (7 anos) de DRE, BP Ativo, BP Passivo, DFC **e DVA**
  (a DVA ajuda em bancos). Preferir demonstrações **consolidadas**; cair para individuais
  com aviso se não houver consolidada. Sempre usar o **exercício anual (31/12)** como Ano 0.
- **Implementar de fato** `src/processamento/limpeza.py` (hoje o pacote existe mas o módulo
  não): normaliza sinais, separa dívida financeira de passivos operacionais (NIBCLs),
  flag booleana de itens não-recorrentes (sem remover), e grava **Parquet** em
  `data/processed/<TICKER>_<demonstracao>.parquet`. A decisão v1 de ler JSON bruto direto
  fica substituída aqui: a partir da v2, a projeção lê Parquet limpo (com fallback ao JSON
  bruto documentado para não quebrar o que já roda).

### 1.5 Config de setores estendida e dirigida por dados

- **Editar** `config/setores.json`: incluir **todos os subtipos** de 1.2, cada um com:
  `nome`, `metodo_valuation` (FCFF|FCFE), `taxa_desconto` (WACC|Ke), `aliquota_padrao`,
  regras de `tributacao`, `modo_capital_giro` default (`dias`|`percentual_receita`),
  `peers` (lista de tickers para a Onda 3), `vetor_sensibilidade_setorial` (os 2 eixos de
  incerteza do setor — ex.: mineração = preço da commodity × custo C1) e defaults de premissa
  plausíveis. Manter compatível com o schema atual (não quebrar DIRR3/MGLU3).

### 1.6 Relatório de qualidade de dados e coleta em lote

- **Arquivo:** `src/coleta/relatorio_qualidade.py` (novo). Para cada empresa coletada, gerar
  `data/raw/cvm/<TICKER>_qualidade.json` com: nº de anos coletados, contas-chave presentes
  (receita, EBIT, LL, ativo, PL, dívida, caixa), contas não mapeadas, avisos (consolidado
  ausente, ITR usado como proxy, sinais suspeitos), e um `score_confiabilidade` 0–100.
- **Arquivo:** `src/coleta/coleta_lote.py` (novo). Aceita uma lista de tickers (arquivo ou
  argumento), coleta todos, e imprime uma tabela-resumo (ticker, tipo, subtipo, anos, score).
  Falha em um ticker não derruba o lote — registra e segue.

## Contratos de interface (o que esta onda garante para as próximas)

- `data/raw/cvm/<TICKER>_meta.json` passa a conter `tipo`, `subtipo`, `metodo_valuation`,
  `taxa_desconto`, `consolidado` (bool) e `score_confiabilidade`.
- `data/processed/<TICKER>_<demonstracao>.parquet` existe, com nomes padronizados e sinais normalizados.
- Todos os nomes de coluna novos estão registrados em `config/mapeamento_cvm.json`.

## Definição de Pronto (DoD)

- `python -m src.coleta.coleta_lote --tickers DIRR3 MGLU3 VALE3 WEGE3 ITUB4 BBAS3 RADL3 RENT3`
  coleta as 8 empresas, classifica tipo/subtipo corretos (ITUB4/BBAS3 = `financeira/banco`),
  e imprime a tabela-resumo com score.
- DIRR3 e MGLU3 mantêm exatamente o mesmo Ano 0, receita e LL de antes (**regressão dourada**).
- Parquets limpos gerados em `data/processed/` para pelo menos essas 8 empresas.
- `pytest tests/ -q` verde (incluir novos testes — ver abaixo); `black`/`flake8` limpos.

## Testes e validação

- `tests/test_resolvedor_ticker.py`: resolve tickers ON/PN/UNIT; ticker inexistente levanta erro claro.
- `tests/test_mapeador_contas.py`: match por código, por prefixo, por nome-fallback e caminho
  "não mapeado → log" (com fixtures sintéticas, sem rede).
- `tests/test_classificador_empresa.py`: setores CVM conhecidos → tipo/subtipo esperados.
- `tests/test_limpeza.py`: sinais normalizados, dívida separada de operacional, Parquet lido de volta.
- Atualizar `tests/test_coleta.py` para o novo contrato do `_meta.json`.

## O que NÃO fazer nesta onda

- Não mexer no motor de valuation, no front-end nem nos exportadores (são as próximas ondas).
- Não tentar "consertar" o valuation de bancos aqui — apenas garantir que **coletam e classificam**.
- Não quebrar o caminho atual de DIRR3/MGLU3.

## Ao final: atualizar `CONTEXT.md`

Acrescente uma sessão datada descrevendo: mapeamento migrado para `CD_CONTA`, novos módulos,
empresas que passaram a coletar, decisões (consolidado vs. individual, score de qualidade),
bugs conhecidos e a próxima tarefa (Prompt 2).

---
---

# PROMPT 2 — Motor de Valuation Universal e Completo (todos os dados do DCF)

## Papel e contexto

Você é o **Claude Fable 5**. A Onda 1 está fechada: qualquer empresa da B3 coleta e classifica.
Leia `CONTEXT.md` (estado após a Onda 1), os Princípios Invariantes e a Seção 2 do
`ROTEIRO.md` (fórmulas canônicas). Esta é a **Onda 2 de 5**.

## Objetivo desta onda

Fazer o motor produzir **números economicamente reais para qualquer tipo de empresa**, não
apenas "estruturalmente executáveis". Isso significa: (a) **ativar e validar a trilha
financeira (FCFE/Ke)** para bancos/seguradoras; (b) **remover as simplificações v1** que
distorcem o valuation; (c) **completar os itens faltantes do DCF** (bridge completo,
não-recorrentes, políticas de dívida e dividendos reais, etc.).

## Por que agora / o que destrava

Sem um motor completo e correto por tipo, "rodar qualquer empresa" produz um Target Price sem
sentido (foi o que aconteceu com bancos e com o caixa-plug). Esta onda é o coração analítico
da universalização.

## Especificação técnica detalhada

### 2.1 Trilha financeira validada (FCFE/Ke) — bancos e seguradoras

- **Editar** `src/metricas/metricas_historicas.py`: implementar de verdade a trilha
  financeira (ROE, ROA, NIM, índice de eficiência, NPL, coverage, Basileia) lendo o plano
  de contas bancário mapeado na Onda 1.
- **Novo:** `src/projecao/projetor_financeiro.py` — projeta a DRE bancária (margem financeira,
  PDD, receitas de serviços, despesas) e o capital regulatório retido. **Novo:**
  `src/valuation/calculador_fcfe.py` (ou estender o `calculador_fcff.py`): FCFE = LL −
  ΔCapital Regulatório Mínimo Retido; VT = FCFE₈×(1+g)/(Ke−g); Equity direto **sem** bridge EV→Equity.
- **Editar** `src/valuation/calculador_wacc.py`: quando `metodo_valuation = FCFE`, calcular
  **apenas Ke** (CAPM com ajuste Brasil, beta de peers bancários da config).
- **Editar** `src/valuation/checklist.py`: ativar as verificações financeiras (Basileia > 10,5%,
  Coverage > 100%, ROE projetado > Ke).
- **Validar** contra **ITUB4** e **BBAS3** (Target Price na mesma ordem de magnitude do preço
  de mercado; validação numérica pelo humano).

### 2.2 Remover as simplificações v1 (motor não-financeiro completo)

Substituir, cada uma governada por config/premissa (não hard-code):

- **Schedule de dívida real:** cronograma de amortização por instrumento (ou perfil de
  vencimento CP/LP), captações novas para financiar déficit de caixa, **receita financeira
  sobre caixa/aplicações** (`caixa_medio × taxa_aplicacao`). `delta_divida` deixa de ser 0.
- **Política de dividendos real:** `payout` como premissa por empresa/setor; PL projetado
  passa a refletir `PL_t = PL_(t-1) + LL_t − dividendos_t`.
- **Caixa deixa de ser plug arbitrário:** o caixa passa a ser o **resultado do DFC**
  (caixa inicial + FCO + FCI + FCF); o fechamento do balanço vira uma **verificação**, não
  um plug. Se não fechar, é alerta explícito no checklist.
- **Bridge EV→Equity completo:** `Equity = EV − Dívida Bruta (inclui leasing IFRS16) + Caixa +
  Aplicações − Minoritários + Investimentos em Coligadas + Ativos Não Operacionais`. Cada
  componente lido dos dados reais (não zerado).
- **RET sobre Receita Bruta real:** coletar/derivar a linha de Receita Bruta (a Onda 1 deve
  expor Receita Bruta quando disponível); usar Receita Líquida como proxy só com aviso.

### 2.3 Qualidade do lucro e normalização de não-recorrentes

- **Novo:** `src/metricas/qualidade_lucro.py` — FCO/EBITDA histórico, accruals (LL − FCO),
  itens não-recorrentes sinalizados na limpeza. Oferece um **EBITDA/NOPAT normalizado** que
  o motor pode usar como base do VT (já previsto para FCFF₈ negativo — generalizar).

### 2.4 Motor de cenários de primeira classe

- **Novo:** `src/valuation/motor_cenarios.py` — Bear / Base / Bull como cenários completos
  (não só ajustes lineares no gráfico). Cada cenário roda o pipeline com um conjunto de
  premissas e persiste um resultado. Alimenta Football Field, sensibilidades e o front-end.
- Parâmetros dos cenários por setor em `config/parametros.json`.

### 2.5 Impostos, mid-year convention e stub

- Convenção de meio de período (mid-year) opcional para o desconto (parâmetro global).
- Período-stub (fração do ano corrente até a data-base) tratado explicitamente.
- Impostos diferidos e alíquota efetiva vs. marginal documentados no cálculo do NOPAT.

## Contratos de interface

- A estrutura de resultado do motor (`data/processed/<TICKER>_projecao.json`) ganha os blocos
  novos (`fcfe` validado para financeiras, `cenarios`, `qualidade_lucro`, bridge completo,
  `dividendos`, `receita_financeira_caixa`) — sempre com nomes padronizados registrados no mapeamento.
- Visualização, Excel e BI (ondas 3–5) consomem essa mesma estrutura — **não recalculam nada**.

## Definição de Pronto (DoD)

- ITUB4 e BBAS3 rodam pela trilha FCFE/Ke e produzem Target Price plausível; checklist financeiro ativo.
- DIRR3/MGLU3 rodam pela trilha FCFF/WACC com o bridge completo, dívida amortizando, payout real
  e caixa vindo do DFC — e o balanço fecha (ou o desvio é sinalizado).
- Bear/Base/Bull persistidos para as 4 empresas.
- **Regressão dourada:** o Target Price de DIRR3/MGLU3 muda de forma **explicável** (documentar o
  porquê no CONTEXT — ex.: agora há receita financeira sobre caixa e payout real). Sem mudanças inexplicadas.
- `pytest` verde; `black`/`flake8` limpos.

## Testes e validação

- `tests/test_calculador_fcfe.py`, `tests/test_projetor_financeiro.py` (fixtures bancárias sintéticas).
- `tests/test_bridge_completo.py`: minoritários/coligadas/ativos não operacionais entram no Equity.
- `tests/test_schedule_divida.py` estendido: amortização, captação nova, receita financeira sobre caixa.
- `tests/test_motor_cenarios.py`: Bear < Base < Bull em Target Price para caso monotônico.
- Atualizar `tests/test_valuation.py` e `tests/test_checklist.py`.

## O que NÃO fazer

- Não construir comparáveis/CCA aqui (Onda 3). Não mexer no front-end nem nos exportadores.
- Não hard-codar payout, taxa de aplicação ou perfil de dívida — tudo é premissa/config.

## Ao final: atualizar `CONTEXT.md` (sessão datada, decisões, bugs, próxima tarefa = Prompt 3).

---
---

# PROMPT 3 — Comparáveis / CCA, Triangulação e Dados de Mercado Automáticos

## Papel e contexto

Você é o **Claude Fable 5**. As Ondas 1–2 entregaram coleta universal e motor completo por
tipo. Leia `CONTEXT.md` atualizado, os Princípios Invariantes e a Seção 7.2 do `ROTEIRO.md`
(especificação de Comparáveis). Esta é a **Onda 3 de 5**.

## Objetivo desta onda

**Eliminar os placeholders** do Football Field e fechar o "DCF **+** CCA" do valuation
profissional: comparáveis reais de mercado, múltiplos por peers, preço implícito e
triangulação do DCF por múltiplos — tudo automático e robusto a dados faltantes.

## Por que agora / o que destrava

Hoje as barras de Comps EV/EBITDA e P/L do Football Field são inventadas. Um valuation
institucional triangula o DCF com múltiplos de mercado. Isso também torna as sensibilidades e
o "cerco" do preço-alvo confiáveis para qualquer empresa.

## Especificação técnica detalhada

### 3.1 Módulo de comparáveis

- **Novo:** `src/valuation/comparaveis.py`. Para o subtipo da empresa, lê a lista de `peers`
  em `config/setores.json` (definida na Onda 1) e coleta, via yfinance e/ou CVM:
  `EV/EBITDA`, `P/L`, `P/VP`, `EV/Sales`, `EV/EBIT`, e (para bancos) `P/VP` e `P/L` como
  principais. Calcula mediana e quartis (Q1/Q3) do conjunto de peers.
- Deriva **preço implícito por múltiplo**: aplica a mediana do peer group ao denominador da
  empresa-alvo (ex.: EBITDA da empresa × EV/EBITDA mediano → EV → Equity → preço/ação).
- **Robustez:** peer sem múltiplo disponível vai para log e é excluído da mediana, não quebra.
  Múltiplos negativos (P/L de empresa com prejuízo) são descartados com aviso.

### 3.2 Football Field com comps reais

- **Editar** `src/visualizacao/football_field.py`: substituir os placeholders EV/EBITDA e P/L
  pelas faixas reais (Q1–mediana–Q3) vindas de `comparaveis.py`. Manter DCF Bear/Base/Bull
  (agora do motor de cenários da Onda 2), Múltiplo de Saída e faixa 52 semanas.

### 3.3 Tabela de comparáveis e triangulação

- **Novo:** `src/visualizacao/tabela_comparaveis.py` — tabela peer-a-peer (ticker, market cap,
  EV/EBITDA, P/L, P/VP...) com a empresa-alvo destacada e as linhas de mediana/quartis.
- **Novo:** seção "Triangulação" no resultado — resume DCF (base) vs. faixa por múltiplos vs.
  preço atual, com um veredito textual (DCF acima/abaixo do que o mercado precifica).

### 3.4 Export para BI e contrato

- **Editar/criar** o export para incluir `fato_comparaveis.csv` (peer, múltiplo, valor) em
  `outputs/bi/<TICKER>/` (o exportador completo é finalizado na Onda 5, mas a tabela nasce aqui).

## Contratos de interface

- `comparaveis.py` grava `data/processed/<TICKER>_comparaveis.json` (peers, múltiplos, medianas,
  preços implícitos) consumido pelo Football Field, pela tabela, pelo front-end e pelo BI.
- Peers configuráveis por setor; nenhum ticker de peer hard-coded no código.

## Definição de Pronto (DoD)

- DIRR3, MGLU3, VALE3 e ITUB4 mostram Football Field com **comps reais** (barras derivadas de
  peers de verdade) e uma tabela de comparáveis coerente.
- Rodar com um peer indisponível **não quebra** (cai no log e segue).
- `pytest` verde; `black`/`flake8` limpos.

## Testes e validação

- `tests/test_comparaveis.py`: mediana/quartis corretos; peer sem dado é excluído; P/L negativo descartado.
- `tests/test_football_field.py` atualizado: barras de comps vêm de `comparaveis.json`, não de placeholder.

## O que NÃO fazer

- Não reescrever o motor de DCF. Não construir o `.pbix` (Onda 5). Não redesenhar o app (Onda 4).
- Não deixar múltiplo negativo ou peer quebrado contaminar a mediana.

## Ao final: atualizar `CONTEXT.md` (sessão datada, decisões, bugs, próxima tarefa = Prompt 4).

---
---

# PROMPT 4 — Front-end Institucional Multi-Empresa de Próxima Geração

## Papel e contexto

Você é o **Claude Fable 5** — e aqui o seu diferencial de front-end importa mais que nunca.
As Ondas 1–3 tornaram os dados, o motor e os comparáveis universais e reais. Leia `CONTEXT.md`,
os Princípios Invariantes (especialmente o 11, design institucional), `app.py` e
`.streamlit/config.toml`. Esta é a **Onda 4 de 5**.

## Objetivo desta onda

Elevar o `app.py` de "front-end de 2 empresas pré-coletadas" para uma **estação de trabalho de
analista institucional que funciona com QUALQUER empresa da B3**, com gráficos, tabelas e
sensibilidades de nível profissional, comparação entre empresas e recálculo ao vivo.

## Por que agora / o que destrava

O motor já é universal; o front-end ainda assume DIRR3/MGLU3. Esta onda entrega a experiência
que um recrutador/analista realmente vê e usa.

## Especificação técnica detalhada

### 4.1 Seletor universal de empresa (o destravamento central do front)

- Caixa de busca por ticker/razão social na sidebar. Ao escolher um ticker novo, o app
  **dispara o pipeline** (coleta → motor → comparáveis) com feedback de progresso (`st.status`/spinner),
  **cacheando** o resultado (`@st.cache_data`) para não recoletar a cada interação.
- Tratar graciosamente empresa sem dados suficientes (mensagem clara + score de qualidade da Onda 1).
- Manter DIRR3/MGLU3 como atalhos rápidos ("empresas de referência").

### 4.2 Sensibilidades vivas e tabelas editáveis

- **Sensibilidade WACC×g e Receita×Margem** recalculando **ao vivo** conforme o analista move
  sliders — heatmaps com formatação condicional pelos limiares de recomendação; caso base destacado.
- **Tornado chart** (impacto de cada premissa no Target Price) — novo gráfico institucional.
- Tabelas de premissas e de demonstrações **editáveis** via `streamlit-aggrid`: editar uma
  célula de premissa recalcula o motor (fonte única de verdade — o app **não** recalcula em JS).
- Todas as tabelas com números em fonte mono e alinhamento decimal.

### 4.3 Comparação entre empresas (multi-empresa)

- **Nova seção "Comparar"**: escolher 2–5 tickers e ver lado a lado Target Price, upside, WACC/Ke,
  múltiplos, ROIC vs. WACC (spread/MOAT), margens. Tabela + gráfico de barras agrupadas institucional.
- **Watchlist/portfólio** persistida em `data/watchlist.json`: lista de tickers acompanhados com
  seu último Target Price e recomendação.

### 4.4 Seções novas e refino das existentes

- Integrar a **seção de Comparáveis/Triangulação** (Onda 3) e a de **Cenários** (Onda 2:
  alternar Bear/Base/Bull recarrega todo o dashboard).
- Refinar Overview (capa viva com KPIs de decisão), Histórico (métricas por tipo — bancárias
  aparecem para bancos), Valuation (decomposição completa do bridge e do WACC/Ke).
- **Responsividade e tema:** garantir legibilidade em telas largas; respeitar a paleta navy e a
  semântica verde/vermelho; loading/erro tratados em toda seção.

### 4.5 Aba Excel Preview funcional (dívida técnica da v1.0)

- Implementar de verdade a aba **Excel Preview**: renderizar as abas do `.xlsx` (via
  `streamlit-aggrid`/tabelas) e um **botão de download** do arquivo gerado.

## Contratos de interface

- O app consome **exclusivamente** os JSONs persistidos pelo motor e pelos comparáveis; nenhuma
  lógica de valuation é reimplementada no front-end.
- Novo estado de sessão para empresa selecionada e cenário ativo.

## Definição de Pronto (DoD)

- `streamlit run app.py`: buscar um ticker novo (ex.: `WEGE3`, `RADL3`, `ITUB4`) roda o pipeline
  e renderiza todas as seções, incluindo Football Field com comps reais.
- Mover um slider recalcula sensibilidade e Target Price ao vivo; editar premissa na tabela recalcula.
- Seção "Comparar" mostra ≥3 empresas lado a lado. Excel Preview renderiza e baixa o `.xlsx`.
- `tests/test_app.py` (AppTest) atualizado e verde; `black`/`flake8` limpos.

## Testes e validação

- `tests/test_app.py`: seleção de ticker novo renderiza Overview; g≥WACC bloqueia salvar;
  seção Comparar renderiza N empresas; Excel Preview expõe botão de download.
- Validação visual pelo humano (screenshots das seções principais para o README na Onda 5).

## O que NÃO fazer

- Não recalcular valuation em JavaScript. Não quebrar o fluxo de premissas existente.
- Não sacrificar densidade/hierarquia institucional por "bonito e vazio" (Princípio 11).

## Ao final: atualizar `CONTEXT.md` (sessão datada, decisões, bugs, próxima tarefa = Prompt 5).

---
---

# PROMPT 5 — Excel/BI/PDF Profissionais + Automação e Orquestração de Dados

## Papel e contexto

Você é o **Claude Fable 5**. As Ondas 1–4 entregaram coleta universal, motor completo,
comparáveis reais e front-end multi-empresa. Leia `CONTEXT.md`, os Princípios Invariantes e as
Seções 5 e 7 do `ROTEIRO.md` (Excel nível Direcional, camada de BI, backlog). Esta é a
**Onda 5 de 5** — o fechamento da v2.0.

## Objetivo desta onda

Entregar os **outputs de nível profissional para qualquer empresa** (Excel dinâmico por tipo,
tabelas de BI, painel Power BI, nota em PDF) e **automatizar a camada de dados** (orquestração
em lote, cache com invalidação, base de empresas processadas), fechando o ciclo da universalização.

## Especificação técnica detalhada

### 5.1 Exportador de BI (fecha a dívida técnica da v1.0)

- **Novo:** `src/exportacao/exportador_bi.py` — consome a estrutura de resultado do motor e grava
  as tabelas planas star-schema em `outputs/bi/<TICKER>/`: `dim_empresa`, `dim_valuation`,
  `fato_demonstracoes`, `fato_fcff` (ou `fato_fcfe`), `fato_sensibilidade_wacc_g`,
  `fato_sensibilidade_receita_margem`, `fato_football_field`, `fato_historico_vs_projetado`,
  `fato_comparaveis`, `fato_cenarios`. Formato tidy/long, nomes de coluna do `mapeamento_cvm.json`,
  sem células mescladas. Opcional: consolidar em `modelo_bi.xlsx` (uma tabela por aba).

### 5.2 Excel dinâmico por tipo de empresa

- **Editar** `src/exportacao/exportador_excel.py`: as 7 abas passam a se **adaptar ao tipo**
  (não-financeira = DRE/BP/DFC + schedules FCFF; financeira = DRE bancária + capital regulatório
  + FCFE, **sem** aba de dívida operacional). Manter fórmulas nativas, convenção de cor WSP e
  nomes definidos. Adicionar **abas de cenário** (ou um seletor de cenário) e **Data Tables
  nativas** para WACC×g usando os nomes definidos. Incluir uma aba/seção de Comparáveis (Onda 3).
- Garantir que o Excel gera para **qualquer** das empresas testadas nas ondas anteriores.

### 5.3 Nota de research em PDF (1 página)

- **Novo:** `src/exportacao/exportador_pdf.py` (usa `reportlab` — adicionar ao `requirements.txt`):
  Target Price, Recomendação, Upside, 3 bullets de tese (placeholders editáveis), mini Football
  Field, tabela-resumo e decomposição do WACC/Ke — com identidade visual institucional (navy).

### 5.4 Projetado vs. Realizado (variância/FP&A)

- **Novo:** `src/analise/projetado_vs_realizado.py` — quando o realizado de um ano projetado sai
  na CVM, compara projetado × realizado (receita, margem, LL), calcula variância e classifica
  favorável/desfavorável. Grava `fato_variancia.csv` em `outputs/bi/` e alimenta uma seção do app.

### 5.5 Automação e orquestração de dados

- **Editar** `main.py`: aceitar `--tickers` (lista) e `--lote <arquivo>`; orquestrar
  coleta→motor→comparáveis→gráficos→Excel→BI→PDF para cada empresa; **cache com invalidação por
  data-base** (não recoletar CVM se os dados do exercício já estão frescos); resumo consolidado
  em tabela ao final.
- **Novo:** `src/orquestracao/base_empresas.py` — mantém um índice `data/processed/_indice.parquet`
  das empresas já processadas (ticker, tipo, data-base, Target Price, upside, recomendação, score),
  consumido pela watchlist do app e pela seção Comparar.
- Documentar como agendar uma atualização periódica (ex.: script `atualizar_base.py`) — sem
  acoplar a nenhum serviço externo pago.

### 5.6 Painel Power BI (`.pbix`)

- **Novo:** `powerbi/dcf_dashboard.pbix` + `powerbi/tema.json` — conectado a `outputs/bi/` via
  "Get Data → Folder", modelo estrela, páginas: Overview executivo, Demonstrações, Valuation,
  Sensibilidades, Football Field, Comparar empresas. **Zero cálculo de valuation em DAX** —
  refresh = rodar o Python e clicar Refresh. (Se o ambiente não tiver Power BI Desktop, deixar o
  `tema.json`, o layout documentado e as tabelas prontas; o `.pbix` é o único item que pode ficar
  como entregável manual do humano.)

### 5.7 Fechamento da v2.0

- Rodar o pipeline completo em lote para o conjunto de teste (≥8 empresas de ≥5 setores, incluindo
  ≥1 banco). `pytest` verde geral. Atualizar `README.md`, `CHANGELOG.md` e `ROTEIRO.md` para a v2.0.
  Screenshots do app e do Power BI no topo do README (prova visual). Criar a tag `v2.0`.

## Definição de Pronto (DoD)

- `python main.py --lote tickers_teste.txt` processa ≥8 empresas e gera, para cada, Excel (adaptado
  ao tipo), tabelas de BI, gráficos e PDF, com um resumo consolidado ao final.
- `outputs/bi/<TICKER>/` carrega no Power BI Desktop via "Get Data → Folder" sem erro de schema;
  KPIs batem célula a célula com Excel e Streamlit.
- Nota PDF de 1 página gerada para ≥2 empresas. Projetado vs. Realizado gera relatório para ≥1 ano
  já realizado de DIRR3.
- `pytest` verde; `black`/`flake8` limpos; tag `v2.0` criada.

## Testes e validação

- `tests/test_exportador_bi.py`: schema das tabelas planas; nomes de coluna do mapeamento; long format.
- `tests/test_exportador_excel.py` estendido: abas adaptadas ao tipo (financeira vs. não-financeira).
- `tests/test_exportador_pdf.py`: PDF de 1 página gerado sem erro.
- `tests/test_projetado_vs_realizado.py`: variância favorável/desfavorável em fixtures.
- `tests/test_base_empresas.py`: índice atualiza e é lido de volta.

## O que NÃO fazer

- Não reimplementar valuation em DAX (Power BI só apresenta). Não recolher dados frescos sem necessidade.
- Não deixar o Excel financeiro exibir abas de dívida operacional que não se aplicam a bancos.

## Ao final: atualizar `CONTEXT.md`

Marcar a **v2.0 "Universalização" como concluída**, listar as empresas/setores cobertos, as
decisões estruturais (Excel dinâmico, base de empresas, Power BI), os bugs conhecidos e o próximo
horizonte (v3.0 — ver README/ROTEIRO). Criar a tag `v2.0`.

---
---

## Apêndice A — Fluxo de trabalho dos 3 atores (permanece)

> **Humano (Lucas)** faz o julgamento (premissas reais, validação numérica contra RI/Status Invest,
> descrição de bugs, commit, atualização final do `CONTEXT.md`) → **Claude Code** lê `CONTEXT.md` +
> `ROTEIRO.md` e **cura/gera estes prompts** e faz a revisão final → **Claude Fable 5** implementa o
> código e roda os testes → **Humano** testa e fecha.

## Apêndice B — Ordem obrigatória e critério de avanço

Não abra o Prompt N+1 antes de a "Definição de Pronto" do Prompt N estar verde **e** a regressão
dourada (DIRR3 + MGLU3) confirmada. Cada onda deixa o repositório em estado consistente e testável.

## Apêndice C — Mapa da meta

Ao fim dos 5 prompts, o sistema deve permitir: **escolher/rodar qualquer empresa da B3 → obter DCF
completo pelo método correto do tipo → com comparáveis reais → visto num front-end institucional
multi-empresa → exportado em Excel, BI, Power BI e PDF profissionais → tudo automatizável em lote.**
Não precisa estar perfeito; precisa estar **substancialmente mais perto** disso do que a v1.0 estava.
