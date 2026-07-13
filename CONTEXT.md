# CONTEXT.md — Estado do Projeto DCF Automatizado

> **Este é o documento de continuidade entre sessões de IA (OpenAI Codex).**
> É colado no início de cada sessão do Codex e atualizado obrigatoriamente ao final de cada sessão.
> Sem ele, cada sessão de IA começa do zero e toma decisões de arquitetura conflitantes.
> **Trate este arquivo como a fonte única de verdade sobre o estado do projeto.**

---

## 1. Identidade do Projeto

- **Nome:** DCF Automatizado — Sistema de Valuation para Ações da B3
- **Autor:** Lucas Cruz — Ciências da Computação, Insper (2026)
- **Objetivo:** Automatizar o trabalho mecânico de um valuation por DCF (coleta, cálculo, visualização, exportação) preservando o trabalho intelectual (premissas) nas mãos do analista.
- **Benchmarks de qualidade:** os modelos Excel de referência em `referencias/modelos_excel/` — Direcional (DIRR3, benchmark da v1.0) e Smartfit (SMFT3, benchmark da v2.1 "Padrão Smartfit", enviado pelo mentor em 13/07/2026). Mapas estruturais: `ESTRUTURA_DIRECIONAL.md` e `ESTRUTURA_SMARTFIT.md` na mesma pasta.

---

> 🚦 **ATUALIZAÇÃO 11/07/2026 — v1.0 CONCLUÍDA; início do planejamento da v2.0
> "Universalização".** A v1.0 (DIRR3 + MGLU3, trilha não-financeira, Excel 7 abas,
> Streamlit, gráficos) está fechada. A partir de agora o projeto persegue a
> **universalização** — rodar QUALQUER empresa da B3. O plano está em **5 prompts
> progressivos** no arquivo **[`PROMPTS_FABLE.md`](PROMPTS_FABLE.md)**, direcionados ao
> **Claude Fable 5** (a IA de implementação a partir da v2.0, que assume o papel antes
> exercido pelo Codex). A Seção 2 abaixo descreve o escopo HISTÓRICO da v1.0 e permanece
> como referência; o escopo v2.0 e a próxima tarefa estão na Seção 8 e no `PROMPTS_FABLE.md`.

## 2. Escopo da v1.0 (histórico — CONCLUÍDA em 11/07/2026)

A v1.0 foi **deliberadamente enxuta**. O objetivo era profundidade, não amplitude.

- **DIRR3 (construção civil):** implementação de referência, validada contra o Excel do trainee.
- **MGLU3 (varejo):** prova de universalidade, segundo setor não-financeiro.
- **Trilha financeira (FCFE/Ke):** a arquitetura é construída, mas a validação contra banco real fica para a v1.5. Não invista tempo tentando validar ITUB4 na v1.0.
- **Tickers fora de escopo na v1.0:** VALE3, PETR4, ITUB4 (todos v1.5).

> ⚠️ **Regra de ouro:** se surgir a tentação de "já que está quase pronto, adiciona mais um setor", NÃO faça. Cada setor novo é um poço de casos de borda de dados da CVM. Mantenha o foco em DIRR3 impecável + MGLU3 como prova.

> ℹ️ **Power BI e itens pós-v1.0:** a v1.0 entrega apenas o *contrato de export* para BI
> (as tabelas planas em `outputs/bi/`, via `exportador_bi.py`). O painel `.pbix`, o
> módulo de Comparáveis (CCA), o Projetado vs. Realizado e a nota em PDF são **backlog
> pós-v1.0** — ver Seção 10. Não implementar nada disso antes de fechar a tag `v1.0`.

---

## 3. Stack Técnica

- **Linguagem:** Python 3.11+
- **Coleta:** yfinance, python-bcb, requests
- **Processamento:** pandas, numpy, pyarrow (Parquet)
- **Visualização:** plotly, kaleido (PNG)
- **Exportação:** openpyxl (Excel 7 abas), pandas/pyarrow (tabelas planas para BI)
- **Front-end:** streamlit, streamlit-aggrid
- **Camada de BI:** Power BI Desktop (ferramenta EXTERNA, gratuita) — apenas apresenta,
  consumindo as tabelas planas geradas pelo motor. Não é dependência pip.
- **Qualidade:** pytest, black, flake8
- **Infra:** python-dotenv

**Decisão de front-end travada:** Streamlit interativo + export HTML estático + painel
Power BI executivo. O motor Python é a fonte única de verdade — NÃO reimplementar
cálculo em JavaScript (Streamlit) nem em DAX (Power BI). O mesmo código que gera o Excel
gera o dashboard e grava as tabelas planas (`outputs/bi/`) que o Power BI consome. Na
v1.0 entra apenas o EXPORT das tabelas (`exportador_bi.py`); o arquivo `.pbix` é backlog
pós-v1.0 (ver Seção 10).

---

## 4. Arquitetura — 5 Módulos Sequenciais

1. **Coleta** (`src/coleta/`) → CVM, yfinance, BACEN. Detecta financeira x não-financeira.
2. **Métricas históricas** (`src/metricas/`) → duas trilhas por tipo. Âncora para premissas.
3. **Interface de premissas** (`app.py` / `interface/`) → único input humano. 8 valores individuais por ano.
4. **Motor de cálculo** (`src/projecao/`, `src/valuation/`) → DRE/BP/DFC projetados, FCFF/FCFE, WACC/Ke, VT, EV, Target Price.
5. **Dashboard e outputs** (`src/visualizacao/`, `src/exportacao/`, `app.py`) → gráficos, Excel, front-end.

A ordem de cálculo do Módulo 4 é obrigatória: DRE → schedule WK → schedule PP&E → schedule Dívida → FCFF → WACC → VT → EV → Target Price.

---

## 5. Convenções de Código (SEGUIR EM TODO O PROJETO)

- **Idioma:** nomes de função, variável e comentário em português (o domínio é financeiro brasileiro). Ex.: `calcular_wacc`, `receita_liquida`, `divida_bruta`.
- **Nomes de colunas de DataFrame:** padronizados via `config/mapeamento_cvm.json`. Nunca inventar um nome de coluna novo sem registrar no mapeamento. Nomes consistentes entre TODOS os módulos (a mesma coluna se chama igual na coleta, na projeção e na exportação).
- **Sinais:** despesas e saídas de caixa sempre negativas. Receitas e entradas positivas.
- **Anos de projeção:** sempre 8, nomeados `ano1` a `ano8`. Crescimento, margem e CAPEX têm 8 campos individuais — NUNCA uma taxa única replicada.
- **Robustez da CVM:** todo acesso a campo da CVM trata o caso de campo ausente/renomeado sem quebrar silenciosamente. Campo não mapeado vai para log, não derruba o pipeline.
- **Valores negativos válidos:** ROIC, FCFF e LL podem ser negativos (empresa com prejuízo/crescimento agressivo). Não travar nesses casos.
- **Docstrings:** toda função tem docstring. Todo cálculo financeiro tem comentário com a fórmula.
- **Formatação:** black + flake8 antes de cada commit.
- **Testes:** cálculos financeiros têm teste pytest correspondente.

---

## 6. Fórmulas de Referência (fonte: Damodaran, McKinsey, Assaf Neto)

```
FCFF   = NOPAT + D&A − ΔNWC − CAPEX          onde NOPAT = EBIT × (1 − t)
FCFE   = LL + D&A − ΔNWC − CAPEX + ΔDívida Líquida
ROIC   = NOPAT / IC, com IC = Working Capital + PP&E + Intangível
ROIIC  = ΔNOPAT_t / ΔIC_(t−1), usando o capital comprometido antes do retorno
Ke_USD = Rf + Beta_realavancado × (ERP_EUA + CRP_Brasil)
Ke_BRL = [(1 + Ke_USD) × (1 + IPCA)] / (1 + CPI_EUA) − 1
WACC   = (E/V) × Ke_BRL + (D/V) × Kd × (1 − t)
TV     = FCFF₈ × (1 + g) / (WACC − g)         [não-financeira]
TV     = FCFE₈ × (1 + g) / (Ke − g)           [financeira]
EV     = Σ VP(FCFF_t) + VP(TV)
Equity = EV − Dívida Bruta + Caixa + Aplicações − Minoritários + Coligadas + Ativos Não Operacionais
Target Price = Equity Value / Ações Fully Diluted
```

**Regra tributária:** empresas gerais IR/CSLL sobre o EBT (34%). Construtoras no RET: 4% sobre a Receita Bruta.

**Tratamento de FCFF₈ negativo:** usar NOPAT normalizado do último ano como base do VT, com comentário explicando o ajuste.

---

## 7. Checklist de Consistência (Módulo 4)

Universais: g < taxa de desconto; g ≤ 5% BRL; taxa de reinvestimento 0-100%; VP(VT) < 85% do EV; ações fully diluted usadas.
Não-financeiras: balanço fecha nos 8 anos; ROIIC < 50% nos 2 últimos anos; CAPEX ≥ D&A na perpetuidade; FCO/EBITDA > 0,7x; Dívida Líquida/EBITDA < 4x.

---

## 8. Estado Atual do Projeto

> **ATUALIZAR ESTA SEÇÃO AO FINAL DE CADA SESSÃO.**

- **Data da última atualização:** 13/07/2026
- **Versão alvo:** v2.0 "Universalização" (5 ondas do `PROMPTS_FABLE.md`; v1.0 concluída em 11/07/2026)
- **Fase atual:** v2.0 — **ONDAS 1, 2, 3 e 4 CONCLUÍDAS em 12/07/2026 e
  VALIDADAS em 13/07/2026** (suíte 135 verde, auditoria da cadeia de dados,
  figuras conferidas contra os JSONs e app real validado no navegador seção a
  seção; 2 bugs visuais corrigidos — D-025/D-026). Qualquer ticker da B3 roda
  coleta → motor correto por tipo (FCFF/WACC ou FCFE/Ke) → comparáveis reais
  → app multi-empresa. Próxima: **Onda 5 — Prompt 5** (Excel dinâmico por
  tipo, exportador BI completo, Power BI, PDF e automação/orquestração de
  dados). Decisões autônomas pendentes de revisão humana:
  **`Humano_revisar.md`** (D-001+).
- **O que está PRONTO e VALIDADO:**
  - Estrutura inicial de pastas e pacotes Python criada.
  - Arquivos de configuração criados: `config/setores.json`, `config/mapeamento_cvm.json` e `config/parametros.json`.
  - Templates de premissas criados em `data/premissas/` com campos individuais por ano.
  - `src/coleta/coletor_cvm.py` implementado para descobrir CD_CVM via dados da CVM, coletar DFP/ITR, mapear contas, registrar contas não mapeadas e persistir JSONs em `data/raw/cvm/`.
  - Coletor CVM validado localmente para DIRR3 e MGLU3: gera `_meta.json`, DRE, BP e DFC em JSON para as duas empresas.
  - DIRR3 e MGLU3 foram detectadas como `nao_financeira`.
  - Ambiente Python 3.11.9 com `.venv` criado; `pip check`, `black`, `flake8` e `pytest` executados com sucesso.
  - Excels de referência (Direcional e Smartfit) em `referencias/modelos_excel/` com mapas estruturais (movidos em 13/07/2026; antes o da Direcional vivia em `tests/fixtures/`).
  - `src/projecao/projetor_dre.py` criado: lê 8 premissas individuais de crescimento de receita e 8 de margem EBITDA, usa Ano 0 diretamente de `data/raw/cvm/` quando não há Parquet em `data/processed/`, projeta DRE de `ano1` a `ano8` e grava `data/processed/<TICKER>_projecao.json`.
  - `src/projecao/schedule_wk.py` criado: lê DSO/DIO/DPO de `data/premissas/<TICKER>_premissas.json`, usa a receita projetada em `data/processed/<TICKER>_projecao.json`, calcula contas a receber, estoques, fornecedores, NWC e ΔNWC de `ano1` a `ano8`, e grava o schedule em `wk` no JSON de projeção.
  - `src/projecao/schedule_ppe.py` criado: lê obrigatoriamente `capex_receita_ano1..8`, usa a receita projetada, carrega o imobilizado histórico de `data/raw/cvm/<TICKER>_bp.json`, calcula CAPEX, D&A e PP&E de `ano1` a `ano8`, grava o bloco `ppe` em `data/processed/<TICKER>_projecao.json` e devolve a D&A para a DRE projetada.
  - `src/projecao/schedule_divida.py` criado: lê `custo_divida_kd`, carrega dívida CP/LP, caixa, aplicações e PL do Ano 0, calcula juros por saldo médio, atualiza resultado financeiro da DRE, monta `balanco`, `divida` e `dfc` em `data/processed/<TICKER>_projecao.json` e verifica `Ativo = Passivo + PL` nos 8 anos.
  - `data/premissas/MGLU3_premissas.json` criado a partir do template de não-financeiras com premissas genéricas conservadoras e campos anuais individuais para testar o pipeline.
  - `data/premissas/DIRR3_premissas.json` criado com premissas simples e explicáveis apenas para teste do pipeline: crescimento de receita de 1% ao ano, margem EBITDA de 10%, CAPEX/Receita de -1% ao ano, prazos de giro de 30 dias e parâmetros básicos de custo de capital. Não usar como tese real de valuation.
  - `config/parametros.json` ampliado com `vida_util_ppe_anos`, usado pelo schedule PP&E para calcular a taxa de depreciação sem hard-code, e `payout_dividendos`, usado no fechamento do PL.
  - `config/mapeamento_cvm.json` ampliado com nomes padronizados usados pela DRE projetada, WK, PP&E, dívida, balanço e DFC.
  - Testes do projetor de DRE criados em `tests/test_projetor_dre.py`; `black --check`, `flake8` e `pytest tests -v` passaram.
  - Testes do schedule WK criados em `tests/test_schedule_wk.py`; `black --check`, `flake8` e `pytest tests -v` passaram.
  - Testes do schedule PP&E criados em `tests/test_schedule_ppe.py`, cobrindo premissas anuais obrigatórias, piso de PP&E em zero e igualdade entre D&A da DRE e D&A do schedule; `black --check`, `flake8` e `pytest tests -v` passaram.
  - Testes do schedule de dívida criados em `tests/test_schedule_divida.py`, cobrindo juros, resultado financeiro, recálculo da DRE, DFC simplificado e fechamento do balanço; `schedule_divida.py` rodou direto para DIRR3 e MGLU3 imprimindo diferença zero nos 8 anos.
  - `src/valuation/calculador_wacc.py`, `src/valuation/calculador_vt.py` e `src/valuation/calculador_ev.py` existentes no repositório, com testes dedicados cobrindo WACC, valor terminal e bridge EV -> Equity -> Target Price.
  - `src/valuation/checklist.py` criado: lê os blocos já persistidos em `data/processed/<TICKER>_projecao.json`, executa verificações universais e de empresas não-financeiras, persiste o bloco `checklist` e imprime tabela ASCII.
  - `tests/test_checklist.py` criado com fixtures sintéticas em `tmp_path`, sem rede e sem rodar pipeline, cobrindo U1, U2, U4, NF1, NF5 e cenário aprovado.
  - `src/projecao/schedule_wk.py` ajustado para suportar dois modos de capital de giro: `dias` para empresas de ciclo curto e `percentual_receita` para construtoras/ciclo longo.
  - O schedule WK agora persiste `modo_capital_giro` em cada ano e aplica salvaguarda no `delta_nwc` do ano 1 quando o salto excede `teto_delta_nwc_receita` (default 50% da receita do ano 1).
  - Testes de WK ampliados para construtora ancorada, preservação do modo por dias e truncamento do `delta_nwc` do ano 1.
  - Validação atualizada: `pytest tests\ -v` verde com 47 testes; `flake8 .` verde; `src/verificar_semana2.py` rodou DIRR3 e MGLU3 com balanço fechado nos 8 anos.
  - `src/verificar_semana3.py` criado: executa DRE -> WK -> PP&E -> dívida -> FCFF -> WACC -> VT -> EV -> checklist para DIRR3 e MGLU3, imprime FCFF anual, painel-resumo e classificações E1-E8/S1-S4.
  - Validação de qualidade atual: `pytest tests\ -v` verde com 47 testes; `flake8 src\ tests\` verde.
- **O que está EM PROGRESSO:**
  - Validação humana dos números coletados e das premissas reais de DIRR3 e MGLU3
    (as premissas atuais são plausíveis mas ainda não são tese de investimento).
  - Validação visual humana dos 14 gráficos em `outputs/graficos/` e da jornada
    completa no `streamlit run app.py`.
- **PRÓXIMA TAREFA:**
  - SEMANA 5 / Etapa 5 (restante): `exportador_bi.py` (tabelas planas para
    Power BI em `outputs/bi/<TICKER>/`) e aba Excel Preview funcional no
    `app.py` (renderizar as 7 abas + botão de download do `.xlsx`).
- **Decisões de arquitetura tomadas nesta sessão:**
  - O coletor usa o cadastro de companhias abertas e os arquivos FCA da CVM para relacionar ticker negociado ao `CD_CVM`.
  - Como o FCA recente traz `CNPJ_Companhia` em vez de `CD_CVM`, o coletor cruza `FCA.CNPJ_Companhia` com `cad_cia_aberta.CNPJ_CIA` para obter o `CD_CVM`.
  - A persistência do Módulo 1 fica em `data/raw/cvm/<TICKER>_meta.json`, `data/raw/cvm/<TICKER>_dre.json`, `data/raw/cvm/<TICKER>_bp.json` e `data/raw/cvm/<TICKER>_dfc.json`.
  - Contas CVM fora de `config/mapeamento_cvm.json` são registradas em `logs/contas_cvm_nao_mapeadas.log` sem interromper a coleta.
  - Os dados persistidos mantêm campos brutos da CVM e adicionam `nome_padronizado`, `sinal_esperado` e `valor_padronizado`.
  - `.gitignore` foi ajustado para ignorar dados gerados (`data/raw`, `data/processed`, `outputs`, `logs`) e manter templates/estrutura via `.gitkeep`.
  - O projetor de DRE usa `data/processed/<TICKER>*.parquet` se existir; se não existir, usa diretamente `data/raw/cvm/<TICKER>_dre.json` com `nome_padronizado` e `valor_padronizado`.
  - A D&A fica como placeholder explícito em `depreciacao_amortizacao = 0.0` até o schedule PP&E sobrescrever a coluna.
  - O resultado financeiro fica como placeholder explícito em `resultado_financeiro = 0.0` até o schedule de dívida sobrescrever a coluna.
  - O IR/CSLL é gravado com sinal negativo; para empresas gerais usa 34% sobre EBT positivo, e para construtoras em RET usa 4% sobre receita.
  - O schedule WK mantém `fornecedores` como passivo negativo no BP; por isso o NWC é calculado como `contas_receber + estoques + fornecedores`, equivalente a `contas_receber + estoques - fornecedores_abs`.
  - O `delta_nwc` é gravado como variação aritmética (`NWC_t - NWC_(t-1)`); quando positivo, representa consumo de caixa e deve entrar no FCF como `-delta_nwc`.
  - Enquanto a DRE projetada não trouxer CPV/CMV projetado, o schedule WK usa o índice histórico `abs(cpv_cmv_ano0) / receita_ano0` como base de CPV para estoques e fornecedores; se não houver CPV histórico, cai para margem bruta opcional ou receita líquida como proxy comentada no código.
  - O schedule PP&E trata `depreciacao_amortizacao` como valor positivo calculado sobre o PP&E; ao devolver a série para a DRE, recalcula `EBIT = EBITDA - D&A`, depois `EBT`, `IR/CSLL` e `lucro_liquido`.
  - `vida_util_ppe_anos` é parâmetro global em `config/parametros.json`; a taxa anual usada no schedule é `1 / vida_util_ppe_anos`.
  - O CAPEX projetado preserva o sinal informado em `capex_receita_anoN`: `CAPEX_t = capex_receita_anoN * receita_t`.
  - O schedule de dívida usa a política v1 `divida_bruta_constante_sem_amortizacao`: mantém a dívida bruta do Ano 0 constante, preservando a proporção CP/LP inicial; logo `delta_divida = 0` nesta versão.
  - O resultado financeiro projetado é `-juros`, com `juros = custo_divida_kd x saldo_medio_divida`; receita financeira sobre caixa não é modelada nesta versão.
  - O payout escolhido em `config/parametros.json` é `payout_dividendos = 0`; assim `PL_t = PL_(t-1) + LL_t` enquanto a política de dividendos real não for definida.
  - O balanço usa `caixa_equivalentes` como plug de fechamento: `caixa = passivo_total + PL - ativos_sem_caixa`. Aplicações financeiras ficam constantes no saldo do Ano 0; outros ativos e outros passivos ficam zerados nesta versão.
  - Para o balanço projetado, fornecedores e dívida entram como magnitudes positivas no passivo; o schedule WK continua preservando fornecedores negativo para cálculo de NWC.
  - O DFC simplificado gravado em `dfc` usa `LL + D&A - ΔNWC - CAPEX + ΔDívida`; como o PP&E salva CAPEX assinado, o DFC subtrai a magnitude `capex_saida_caixa = abs(capex)`.
  - O checklist de valuation é consumidor puro da projeção persistida: não recalcula FCFF, WACC, valor terminal nem EV.
  - No checklist, `taxa_reinvestimento` ausente em `valor_terminal` fica `OK` com valor `n/d`; campos estruturais inválidos nos demais itens viram `ERRO`.
  - As verificações NF aplicam a empresas com `tipo = nao_financeira`; o RET não remove a empresa das verificações, apenas zera a alíquota usada no proxy de FCO/EBITDA.
  - Para construtoras, WK passa a ancorar `NWC_t` no percentual histórico `NWC_ano0 / receita_ano0`, preservando a composição de contas a receber, estoques e fornecedores em vez de substituir o ciclo longo por DSO/DIO/DPO curto.
  - A salvaguarda do ano 1 trunca apenas o choque inicial de `delta_nwc`; os anos seguintes usam o `NWC` ajustado como base anterior, preservando a coerência temporal do schedule.
  - O verificador da Semana 3 reprova estruturalmente se `target_price <= 0`, mesmo que o calculador EV consiga persistir o resultado; isso separa execução técnica de sanidade mínima de valuation.
- **Bugs conhecidos / pendências:**
  - A validação numérica de Receita Líquida e Lucro Líquido contra RI/Status Invest ainda depende de conferência humana.
  - O RET deveria incidir sobre Receita Bruta, mas o coletor atual só traz Receita Líquida (CVM 3.01); a DRE projetada usa Receita Líquida como proxy até existir uma linha confiável de Receita Bruta.
  - Com o WK ancorado para DIRR3, o `soma_vp_fcff` recalculado ficou negativo nas premissas-teste atuais; isso corrige o caixa fictício do ano 1, mas exige revisão humana das premissas de crescimento/margem/capital de giro antes de usar como tese real.
  - `python -m src.verificar_semana3` roda a cadeia completa, mas no estado atual imprime `SEMANA 3 COM FALHAS`: DIRR3 e MGLU3 falham em E6 por `target_price` negativo; ambos alertam S3 por múltiplo de saída abaixo de 3x.

### Sessão 13/07/2026 — VALIDAÇÃO COMPLETA das Ondas 3–4 (4 frentes) + 2 correções visuais

- **Frente 1 — suíte automatizada:** `pytest tests -q` reexecutado do zero →
  **135 verdes** (117s); `black --check --workers 1` (82 arquivos) e `flake8`
  limpos, incluindo as edições desta sessão; `tests/test_app.py` reexecutado
  após as correções → 9/9 verdes.
- **Frentes 2–3 (sessão anterior, mesma validação):** auditoria programática
  da cadeia CVM → Parquet → motor → gráficos → BI → watchlist e conferência
  dos dados DENTRO das figuras Plotly contra os JSONs persistidos — 100%.
- **Frente 4 — validação visual REAL no navegador (porta 8601):**
  - **8/8 seções renderizando para DIRR3** com números idênticos aos JSONs:
    Overview (17,04/13,01/+31%/COMPRA/WACC 14,97%), Historico (âncoras CAGR
    26,2%, margem 23,4%), Premissas (tabela editável + 7 sliders com valores
    persistidos), Valuation (VP(VT) 4.399.075 = 44,8% do EV; waterfall soma
    ao EV; football field "comps reais de 4 peers"; checklist APROVADO),
    Comparaveis (mediana EV/EBITDA 8,4x correta SEM o alvo; n/d gracioso;
    veredito DENTRO da faixa), Analise, Comparar, Excel Preview.
  - **Interações vivas:** cenário Bull → 23,51/+80,7% (valores exatos do
    bloco `cenarios`); slider Δ WACC +0,25pp → Target 16,65 IGUAL ao
    `recalcular_cenario` chamado direto; heatmaps WACC×g (35 células) e
    Crescimento×Margem (25 células) conferidos 100% contra o motor;
    watchlist add→persistiu JSON com valores do `ev_equity`→remove→vazia;
    Excel Preview com 7 abas = abas reais do `.xlsx` no disco (631 KB).
  - **Multi-empresa/multi-tipo:** ITUB4 renderiza a trilha financeira
    correta (rótulo Ke 15,90%, tabela FCFE, football field com P/L e P/VP,
    54,33/+22,6% idêntico ao persistido; Excel Preview com aviso "modelo
    bancário na Onda 5"). **Busca de ticker novo validada de ponta a ponta:
    RENT3 rodou o pipeline completo PELO APP em 21,1s (score 96)** e
    renderizou Overview (Localiza, FCFF, WACC 11,72%, Target 21,95 vs 41,10
    = VENDA −46,6% por premissas automáticas conservadoras — padrão D-024).
- **Bugs visuais achados e CORRIGIDOS (só `app.py`; motor intocado):**
  - **D-025:** painel de decisão mostrava WACC/g do caso BASE com cenário
    Bear/Bull ativo, embora `cenarios.*.taxa_desconto/g` estejam persistidos
    → painel agora reflete a taxa/g do cenário ativo (Bull exibe
    13,90%/1,50%). Dashboard Executivo permanece caso base (arte do motor).
  - **D-026:** metric "Faixa por multiplos (Q1-Q3)" com dois `R$` na mesma
    string → o markdown do `st.metric` tratava o par de `$` como math inline
    e engolia os símbolos; corrigido com escape `\$` (validado no DOM).
- **Observações sem ação (já cobertas por decisões registradas):** preço
  13,01 (ev_equity, 08/07) vs 13,28 (comparáveis, 12/07) entre seções —
  consequência de D-011/D-022, sincroniza na Onda 5; screenshot da aba do
  navegador embutido trava com os Plotly pesados (validação feita por
  DOM/texto + conferência numérica, que é mais forte que pixel).
- **Artefatos novos no working tree:** `data/premissas/RENT3_premissas.json`
  (premissas automáticas geradas pelo pipeline) e `data/watchlist.json`
  (vazio, criado pelo teste add/remove); `data/processed/RENT3_*` ficam fora
  do git (ignorado). Nada commitado nesta sessão (humano decide o commit).
- **PRÓXIMA TAREFA:** Prompt 5 do `PROMPTS_FABLE.md` (Onda 5).

### Sessão 12/07/2026 (4ª) — v2.0 ONDA 4 CONCLUÍDA: front-end multi-empresa

- **`src/pipeline.py` (orquestrador universal):** coleta CVM (com reuso de
  cache) → limpeza Parquet → qualidade → mercado → métricas → premissas
  automáticas (não sobrescreve as do analista) → motor pelo MÉTODO do tipo →
  qualidade do lucro → comparáveis → cenários; etapas opcionais não derrubam
  (viram avisos); `rodar_motor_valuation` reusado pelo app ao salvar
  premissas (Rf/preço injetados dos JSONs persistidos, sem rede).
- **`app.py` reescrito (estação de trabalho multi-empresa, 8 seções):**
  - Sidebar universal: selectbox das empresas analisadas + busca de ticker
    novo que dispara o pipeline com `st.status` (progresso por etapa),
    atalhos DIRR3/MGLU3, "Recalcular motor" e "Recoletar tudo"; cache de
    leitura invalidado por mtime.
  - Overview: capa viva com seletor de cenário Bear/Base/Bull (bloco
    `cenarios` do motor), score de qualidade, método, aviso de premissas
    automáticas; financeiras mostram FCFE projetado + football field.
  - Historico por tipo: métricas bancárias (ROE/ROA/NIM/eficiência) para
    financeiras; trilha clássica para não-financeiras.
  - Premissas EDITÁVEIS EM TABELA (`st.data_editor`, vetores 8 anos ×
    3 linhas por trilha — decisão D-005: nativo/testável no lugar do
    aggrid) + sliders escalares; validação em tempo real (g ≥ WACC/Ke
    bloqueia; margem > máx histórica +5pp alerta; Basileia < 10,5% alerta);
    salvar remove a flag `premissas_automaticas` e dispara o motor.
  - Valuation por método: decomposição do WACC (não-fin) ou do Ke (fin),
    VT, waterfall/bridge, football field e checklist.
  - Comparaveis (nova): triangulação DCF vs faixa Q1–Q3 vs preço com
    veredito, tabela de peers, preços implícitos e avisos; botão de
    atualização via yfinance.
  - Analise: **tornado chart** novo (choques padronizados ordenados por
    amplitude) + **sensibilidade viva** (sliders ΔWACC/Δg/Δcrescimento/
    Δmargem recalculam Target na hora via derivação do caso base — zero
    JS) + heatmaps v1; financeiras veem os cenários do motor.
  - Comparar (nova): multiselect 2–5 empresas, painel comparativo (target,
    upside, taxa, g, ROIC−WACC, medianas de peers) + barras agrupadas
    institucionais (`comparacao_empresas.py`) + **watchlist persistida** em
    `data/watchlist.json`.
  - Excel Preview: mantido para não-financeiras (download + 7 abas);
    financeiras recebem aviso (modelo bancário na Onda 5).
- **DoD:** ticker novo roda pipeline e renderiza (WEGE3 R$ 13,08 e RADL3
  R$ 1,08 em ~14s cada — VENDA por premissas automáticas genéricas em ações
  de múltiplo alto; a triangulação existe para expor isso e o analista
  revisa); slider recalcula ao vivo; Comparar mostra 3+ empresas (7
  analisadas no repo: DIRR3, MGLU3, VALE3, WEGE3, RADL3, ITUB4, BBAS3);
  Excel Preview renderiza e baixa. `tests/test_app.py` ampliado (9 jornadas
  AppTest, incl. triangulação, comparação e seletor de cenários).
- **Validação final:** 135 testes verdes; `black`/`flake8` limpos;
  `python -m src.verificar_semana3` → `SEMANA 3 OK`.
- **Pendências:** premissas automáticas produzem extremos a revisar
  (BBAS3 +98%; WEGE3/RADL3 VENDA); RENT3 coletada sem valuation (rodar
  pipeline quando quiser); Excel bancário e sensibilidades bancárias na
  Onda 5; validação visual humana do app (screenshots para o README na
  Onda 5).
- **PRÓXIMA TAREFA:** Prompt 5 do `PROMPTS_FABLE.md` (Onda 5).

### Sessão 12/07/2026 (3ª) — v2.0 ONDA 3 CONCLUÍDA: comparáveis reais e triangulação

- **`src/valuation/comparaveis.py`:** peers do subtipo (config/setores.json,
  zero hard-code), múltiplos via yfinance (EV/EBITDA, P/L, P/VP, EV/Sales e
  EV/EBIT best-effort), mediana/Q1/Q3 com descarte de múltiplo ≤ 0 (aviso) e
  peer sem dado (log `logs/comparaveis_peers.log`), preço implícito por
  múltiplo com denominadores da CVM (Ano 0 oficial; EV-múltiplos passam por
  dívida líquida), alvo EXCLUÍDO da mediana do próprio peer group, bloco
  `triangulacao` com veredito textual. Persiste
  `data/processed/<TICKER>_comparaveis.json`. Financeiras usam só P/L e P/VP.
- **Football Field sem placeholders:** barras de comps = Q1–Q3 reais com
  marcador na mediana; barras OPCIONAIS por disponibilidade (ticker sem DCF
  renderiza field parcial); DCF Bear/Base/Bull preferem o bloco `cenarios`
  do motor (fallback na derivação rápida). `tabela_comparaveis.py` nova
  (peer a peer, alvo destacado, linhas Q1/MEDIANA/Q3, tema institucional).
- **`exportador_bi.py` criado (semente da Onda 5):** `fato_comparaveis.csv`
  long/tidy em `outputs/bi/<TICKER>/` (utf-8-sig p/ Power BI).
- **DoD executado COM REDE (5 empresas):** DIRR3 (4 peers válidos), MGLU3
  (4; PETZ3 deslistada caiu no log e o lote seguiu — robustez demonstrada),
  VALE3 (3), ITUB4 (4) e BBAS3 (4) com Football Field + tabela + BI reais.
  **VALE3 rodou o DCF universal completo do zero** (mercado → métricas →
  premissas automáticas → motor v2 → cenários): Target R$ 110,50 vs
  R$ 74,18 (+49%, COMPRA, checklist aprovado, Bear/Base/Bull
  83,54/110,50/152,54) — a triangulação alerta "DCF ACIMA da faixa dos
  múltiplos", coerente com premissas automáticas agressivas (revisão
  humana). Medianas: DIRR3 EV/EBITDA 8,4x; ITUB4 P/L 11,4x, P/VP 1,0x.
- **Testes:** 132 passando (novos: test_comparaveis com mediana/quartis/
  descartes/triangulação; test_football_field com comps do JSON, field
  parcial e cenários do motor); `black`/`flake8` limpos. Campos de múltiplos
  registrados no mapeamento.
- **Pendência menor:** peer cujo yfinance devolve info parcial (sem raise)
  entra com múltiplos nulos em vez de ir para `peers_excluidos` (o efeito
  nas medianas é o mesmo: excluído por múltiplo); refinar na Onda 5.
- **PRÓXIMA TAREFA:** Onda 4 — front-end multi-empresa.

### Sessão 12/07/2026 (2ª) — v2.0 ONDA 2 CONCLUÍDA: motor de valuation universal

- **Ordem do humano:** executar a Onda 2 ANTES das Ondas 3–4 (que haviam sido
  solicitadas primeiro); decisões e desvios registrados em `Humano_revisar.md`
  (D-014 a D-022).
- **Motor não-financeiro completo (`schedule_divida.py` reescrito):**
  amortização por perfil (CP do Ano 0 no ano 1; LP linear em
  `prazo_amortizacao_lp_anos`; captações novas viram tranches com carência de
  1 ano), captação automática para o caixa mínimo (`caixa_minimo_pct_receita`),
  receita financeira sobre caixa (premissa > Selic coletada > fallback),
  payout real (premissa > default do subtipo > global) com
  `PL_t = PL_(t-1) + LL − dividendos`, caixa = resultado do DFC
  (FCO/FCI/FCF explícitos) e fechamento do balanço como VERIFICAÇÃO
  (residuais `outros_ativos`/`outros_passivos` do BP REAL do Ano 0; alerta +
  NF1 em desvio, sem plug). Juros/receita financeira por convenção de saldo
  inicial (sem circularidade — D-015).
- **BUG REAL da v1 corrigido (D-014):** o PP&E somava capex ASSINADO
  (negativo) — o ativo encolhia a cada investimento e o plug escondia. Agora
  PP&E cresce por |capex|; o vazamento de 2×|capex|/ano que apareceu no
  balanço-verificação foi o que revelou o bug.
- **Bridge EV→Equity completo:** minoritários (2.03.09), coligadas (1.02.02)
  e leasing IFRS16 (passivo_arrendamento) lidos do BP real do Ano 0 e
  persistidos em `ano0.balanco`; premissa `leasing_ifrs16` sobrepõe quando
  informada. RET da DIRR3 sobre Receita BRUTA real (razão RB/RL da DVA
  7.01.01; proxy pela líquida só com aviso).
- **Trilha financeira FCFE/Ke validada (ITUB4 e BBAS3):**
  `metricas_historicas` com trilha bancária real (ROE/ROA/NIM
  aproximada/eficiência/margem líquida; Basileia/NPL viram aviso de premissa
  — não existem na DFP); `projetor_financeiro.py` (DRE bancária por
  receitas de intermediação × margem do resultado bruto × despesas
  operacionais, com alíquota financeira; capital regulatório retido com RWA
  proxy e capital nunca liberado — D-018); `calcular_ke` (CAPM Brasil com
  beta ALAVANCADO, sem Hamada); `calculador_fcfe.py` (FCFE = LL − ΔCapital;
  VT Gordon com payout sustentável quando FCFE₈ ≤ 0; equity DIRETO sem
  bridge); checklist financeiro F1–F3 ativo (Basileia ≥ 10,5%, ROE médio vs
  Ke, payout implícito 0–100%) e checklist agora type-aware.
  **Resultados:** ITUB4 Target R$ 54,33 vs R$ 44,30 (+22,6%, COMPRA);
  BBAS3 R$ 40,77 vs R$ 20,58 (+98%, premissas automáticas agressivas —
  ordem de grandeza correta; revisão humana pendente). Calibração bancária
  pela margem líquida histórica + clamp de alíquota [20%,50%] (D-017 — a
  alíquota efetiva do BBAS3 saía 74,5% por artefato da DFP).
- **`gerador_premissas.py` (antecipado da Onda 4):** premissas AUTOMÁTICAS
  de partida para as duas trilhas (âncoras históricas + defaults do subtipo,
  interpolação linear com 8 valores individuais, flag
  `premissas_automaticas: true` até revisão do analista).
- **`qualidade_lucro.py`:** FCO/EBITDA por ano (DIRR3 0,04x — WK de
  construtora consome o caixa; MGLU3 4,74x), accruals LL−FCO, itens
  não-recorrentes do Parquet da limpeza (MGLU3: R$ −456M flagados) e
  EBITDA/NOPAT normalizados do Ano 0.
- **`motor_cenarios.py`:** Bear/Base/Bull rodando o PIPELINE COMPLETO com
  premissas ajustadas por config (`cenarios`), Δ de taxa aplicado ao bloco
  persistido (D-019), preço/Rf congelados do mercado coletado, premissas do
  analista sempre restauradas. Persistidos para DIRR3 (12,50/17,04/23,51),
  MGLU3 (0,92/8,10/19,03), ITUB4 (42,95/54,33/70,51) e BBAS3
  (30,15/40,77/57,14) — monotônicos. Football Field passa a preferir o bloco
  `cenarios` (fallback na derivação rápida).
- **Mid-year/stub (2.5):** config `desconto` (default DESLIGADO — golden
  preservada), aplicada em VT/EV/FCFE; alíquota do NOPAT segue marginal com
  justificativa documentada (D-021).
- **Regressão dourada EXPLICADA (D-022):** DIRR3 15,25→17,04; MGLU3
  5,97→8,10 (preço congelado 08/07). Drivers: correção do PP&E (tax shield),
  dívida amortizando (WACC DIRR3 →~14,9%), bridge completo, RET sobre bruta,
  payout/receita financeira (FCFE/caixa). `python -m src.verificar_semana3`
  → `SEMANA 3 OK`; balanço fecha com dif < 1e-6.
- **Testes:** 123 passando (novos: test_calculador_fcfe,
  test_projetor_financeiro, test_bridge_completo, test_motor_cenarios;
  test_schedule_divida reescrito p/ v2; test_schedule_ppe e
  test_metricas_historicas atualizados); `black`/`flake8` limpos.
- **Campos novos registrados** em `config/mapeamento_cvm.json` (dívida v2,
  capital regulatório, trilha bancária, convenção de desconto).
- **Bugs conhecidos / pendências:** premissas automáticas de bancos são
  ponto de PARTIDA (BBAS3 +98% upside exige revisão humana);
  `apoio_cenarios` continua fim-de-período (diverge do motor apenas se o
  humano ligar mid-year — D-021); Excel exporter ainda espelha o schedule
  v1 por campos de compatibilidade (revisão na Onda 5).
- **PRÓXIMA TAREFA:** Ondas 3 e 4 (já solicitadas pelo humano).

### Sessão 12/07/2026 — v2.0 ONDA 1 CONCLUÍDA: coleta e mapeamento CVM universais

- **Objetivo da onda cumprido:** qualquer ticker da B3 agora entra no pipeline com
  dados limpos, padronizados e auditáveis, com relatório de qualidade por empresa.
- **Módulos novos em `src/coleta/`:**
  - `apoio_cvm.py` — HTTP/ZIP defensivo com cache de ZIPs em disco
    (`data/raw/cvm/_cache_zips/`; TTL 24h só para o ano corrente, anos encerrados
    não expiram). Sem ele, o lote rebaixaria o mesmo ZIP dezenas de vezes.
  - `resolvedor_ticker.py` — ticker→CD_CVM cruzando FCA (`CNPJ_Companhia`) ×
    cadastro (`CNPJ_CIA`); suporta ON/PN/UNIT; cache `data/raw/cvm/_cadastro_b3.parquet`
    (validade 7 dias, 1 reconstrução automática se o ticker não estiver no cache);
    ticker inexistente/deslistado → `TickerNaoEncontradoErro` acionável.
  - `classificador_empresa.py` — tipo/subtipo a partir do `SETOR_ATIV` via
    `config/setores.json`; setores `"Emp. Adm. Part. - X"` classificam pelo
    segmento X (WEGE3 → industria) com fallback holding quando não há segmento
    reconhecível (ITSA4 "Sem Setor Principal" → holding); desconhecido → `outros`
    (FCFF/WACC) + `logs/setores_nao_reconhecidos.log`.
  - `mapeador_contas.py` — cascata universal: CD_CONTA exato (só no bloco do
    tipo) → nome normalizado (ANTES do prefixo) → prefixo hierárquico → 
    `logs/contas_cvm_nao_mapeadas.log` sem quebrar. Blocos `*_financeira`
    para o plano de contas de bancos/seguradoras.
  - `relatorio_qualidade.py` — `data/raw/cvm/<TICKER>_qualidade.json` com anos
    coletados, contas-chave, contas não mapeadas, avisos e
    `score_confiabilidade` 0–100 (fórmula documentada: 40 contas-chave +
    30 anos + 15 consolidado + 15 linhas mapeadas); grava o score no `_meta.json`.
  - `coleta_lote.py` — `--tickers`/`--arquivo`; coleta → limpeza → qualidade;
    falha em um ticker NÃO derruba o lote; tabela-resumo (ticker, tipo,
    subtipo, anos, score); exit 0 só com lote 100% OK.
- **`src/processamento/limpeza.py` implementado de fato:** normaliza sinais
  (idempotente), flags `eh_divida_financeira`/`eh_passivo_operacional` (NIBCL) e
  `eh_nao_recorrente` (padrões em `config/parametros.json`, sem remover linha),
  dtypes estáveis e Parquet em `data/processed/<TICKER>_<demonstracao>.parquet`.
  O `projetor_dre` passou a ler o Ano 0 do Parquet limpo (glob já existente);
  os schedules seguem lendo o JSON bruto (fallback documentado, muda na Onda 2).
- **`config/mapeamento_cvm.json` reescrito no esquema v2.0:** `por_codigo`
  (dre/bp_ativo/bp_passivo/dfc/dva + `dre_financeira`/`bp_*_financeira`),
  `por_nome_fallback`, bloco `cascata` com `prefixos_nao_expandem`
  (6.01–6.05) e o catálogo `campos` como fonte única de nomes.
- **`config/setores.json` estendido (v2.0):** 18 subtipos com
  `metodo_valuation`, `taxa_desconto`, tributação, `modo_capital_giro`,
  `peers` (para a Onda 3) e `vetor_sensibilidade_setorial`;
  `mapa_setor_cvm` por palavras-chave (primeiro match vence);
  `prefixo_holding_cvm`. Blocos v1 preservados para retrocompatibilidade.
- **`coletor_cvm.py` universal:** DFP+ITR de DRE, BP (BPA/BPP), DFC (MI/MD) e
  DVA; prefere CONSOLIDADO com fallback INDIVIDUAL por empresa/ano/arquivo
  (aviso + `consolidado=false` no meta); o lote abre cada ZIP UMA vez e filtra
  todas as empresas; `_meta.json` no contrato v2.0 (`tipo`, `subtipo`,
  `metodo_valuation`, `taxa_desconto`, `consolidado`, `score_confiabilidade`,
  com score preservado em recoleta sem relatório novo).
- **DoD executado COM REDE:** `python -m src.coleta.coleta_lote --tickers DIRR3
  MGLU3 VALE3 WEGE3 ITUB4 BBAS3 RADL3 RENT3` → **8/8 OK**; ITUB4/BBAS3 =
  `financeira/banco` (FCFE/Ke); 7 anos para todos; scores 79–96; 32 Parquets
  limpos (8 empresas × dre/bp/dfc/dva).
- **Regressão dourada:** Ano 0 (31/12/2025), receita (DIRR3 4.343.008; MGLU3
  38.703.387) e LL (DIRR3 979.692; MGLU3 204.603) **IDÊNTICOS** após recoleta
  com o mapeador novo; `python -m src.verificar_semana3` → `SEMANA 3 OK`.
  Diferenças explicadas: Target Price +0,09%/+0,21% e WACC −1bp porque a
  dívida média/PL médio históricos ficaram ligeiramente diferentes (o
  mapeamento por código cobre mais linhas/anos que o por-nome da v1); o
  upside/recomendação (MGLU3 COMPRA→NEUTRO; DIRR3 17,1%→14,9%) mudou porque o
  `calculador_ev` usa preço AO VIVO do yfinance (12/07: R$ 13,28/5,22 vs
  08/07: R$ 13,01/4,36) — movimento de mercado, não regressão de código.
- **Bug real capturado por teste novo:** em `mapear_demonstracao`, conta NÃO
  mapeada ganhava `valor_padronizado` (o pandas converte None→NaN ao
  materializar a coluna e `nome is not None` deixava passar); corrigido com
  `pd.notna(nome)`.
- **Testes:** 111 passando (38 novos: resolvedor, mapeador, classificador,
  limpeza, relatório de qualidade, coleta em lote e contrato do `_meta.json`);
  `black --check` e `flake8` limpos.
- **Ambiente:** `requirements.txt` instalado TAMBÉM no Python 3.11.9 global do
  sistema a pedido do humano (pandas 3.0.3 etc.); a `.venv` (Python 3.11.9,
  pandas 2.x) continua sendo o ambiente de validação oficial do projeto.
- **Decisões de arquitetura tomadas nesta sessão:**
  - Mapeamento primário por `CD_CONTA`; o fallback por nome roda ANTES do
    prefixo (agregados 6.01+ absorveriam linhas de ajuste como D&A); prefixo
    nunca expande nível 1 nem 6.01–6.05; código exato consulta apenas o bloco
    do tipo (o 3.01 de banco ≠ `receita_liquida`).
  - "Anos coletados" = exercícios anuais (31/12) distintos na DRE via DFP,
    incluindo o PENÚLTIMO comparativo (7 anos = 2019–2025 com DFPs 2020–2025).
  - Score de qualidade com fórmula fixa 40/30/15/15; avisos são qualitativos
    e não subtraem pontos.
  - DVA passa a ser coletada para expor `receita_bruta` (7.01.01) — base do
    RET real na Onda 2.
  - Contas-chave de financeiras não exigem EBIT nem dívida (bancos captam via
    depósitos, não via empréstimos clássicos).
- **Bugs conhecidos / pendências:**
  - BBAS3 com consolidado parcial (score 79; individuais usadas em parte dos
    exercícios) — investigar quais anos antes de validar a trilha FCFE na Onda 2.
  - `logs/contas_cvm_nao_mapeadas.log` acumula pares únicos para curadoria
    incremental do mapeamento (planos bancários detalhados em especial).
  - Pendências v1 permanecem: Kd histórico da MGLU3 alto; RET sobre receita
    líquida como proxy (a DVA agora traz `receita_bruta` para resolver na Onda 2).
- **PRÓXIMA TAREFA:** Prompt 2 do `PROMPTS_FABLE.md` — motor de valuation
  universal e completo (trilha FCFE/Ke validada para ITUB4/BBAS3, schedule de
  dívida real, payout real, caixa via DFC, bridge EV→Equity completo,
  qualidade do lucro e cenários Bear/Base/Bull).

### Sessão 11/07/2026 — Fechamento da v1.0 e planejamento da v2.0 "Universalização"

- **v1.0 marcada como concluída** (commit `versao 1.0`). O pipeline roda ponta a ponta
  para DIRR3 e MGLU3.
- **Objetivo redefinido:** universalizar o sistema para QUALQUER empresa da B3 (não só
  DIRR3/MGLU3), pelo método correto do tipo, com dados e comparáveis reais, front-end
  multi-empresa e exportações profissionais.
- **Entregável desta sessão:** `PROMPTS_FABLE.md` — 5 prompts progressivos e extensos,
  direcionados ao **Claude Fable 5**, cobrindo (1) coleta e mapeamento CVM universais por
  `CD_CONTA`; (2) motor de valuation completo e correto por tipo (trilha financeira FCFE/Ke
  validada, bridge completo, dívida/dividendos/caixa reais, cenários); (3) Comparáveis/CCA
  e triangulação (Football Field com comps reais); (4) front-end multi-empresa de próxima
  geração; (5) Excel dinâmico por tipo, `exportador_bi.py`, Power BI, PDF e automação de dados.
- **Dívida técnica da v1.0 catalogada** para a v2.0 endereçar na ordem: `exportador_bi.py`
  e aba Excel Preview inexistentes; comps do Football Field são placeholders; trilha
  financeira não validada; simplificações do motor (dívida constante, payout 0%, caixa plug).
- **Documentos atualizados:** `README.md` (Roadmap reescrito para v2.0 + Claude Fable 5 no
  stack), este `CONTEXT.md`, `CHANGELOG.md`. O `ROTEIRO.md` permanece como spec técnica da
  v1.0; a spec da v2.0 vive no `PROMPTS_FABLE.md`.
- **PRÓXIMA TAREFA:** Prompt 1 do `PROMPTS_FABLE.md` — coleta e mapeamento CVM universais
  (resolvedor de ticker, classificador de tipo/subtipo, mapeamento por `CD_CONTA`,
  `limpeza.py` real com Parquet, relatório de qualidade e coleta em lote). Fechar a
  regressão dourada (DIRR3 + MGLU3 inalterados) antes de avançar para o Prompt 2.

### Sessão 07/07/2026 — Fechamento da Semana 3 + Semana 4 completa (Ondas 1 e 2)

- **Bug raiz corrigido (Semana 3):** o Ano 0 do pipeline vinha do ITR trimestral
  (31/03/2026) em vez do exercício anual — a receita-base era 1/4 da real enquanto
  o bridge subtraía a dívida bruta inteira, produzindo Target Price negativo.
  `selecionar_ultimo_exercicio` em `projetor_dre.py` agora prefere linhas de
  fechamento anual (31/12) quando existem, com fallback ao comportamento antigo
  para fixtures sintéticas. Como todos os schedules reutilizam essa função, um
  único fix corrigiu o pipeline inteiro.
- **Semana 3 fechada:** `python -m src.verificar_semana3` imprime `SEMANA 3 OK`.
  DIRR3: Target R$ 15,31 vs preço R$ 13,57 (+12,8%, NEUTRO), WACC 16,59%,
  perpetuidade 40,9% do EV, múltiplo de saída 4,84x. MGLU3: Target R$ 6,02 vs
  R$ 4,46 (+35,6%, COMPRA), WACC 19,38%, perpetuidade 59,3%. Resta apenas o
  alerta não-bloqueante S3 da MGLU3 (múltiplo de saída 2,59x < 3x).
- **Checklist auditado contra o PROMPT 5:** U1-U5 e NF1-NF5 já cobertos em
  `checklist.py`; testes novos em `tests/test_checklist.py` para U3, U5, NF2,
  NF3 e NF4 (antes só U1, U2, U4, NF1, NF5 tinham teste).
- **`src/metricas/metricas_historicas.py` criado (trilha não-financeira):**
  crescimento YoY, CAGR 3/5/7, margens bruta/EBITDA/EBIT/líquida, alíquota
  efetiva, DSO/DIO/DPO/CCC, NWC/receita, CAPEX aproximado (ΔImobilizado + D&A),
  dívida líquida/EBITDA, cobertura de juros, ROIC e beta desalavancado (Hamada).
  Persiste `data/processed/<TICKER>_metricas.json`; trilha financeira devolve
  esqueleto não validado (v1.5). Testes em `tests/test_metricas_historicas.py`.
- **`coletor_mercado.py` ampliado:** persiste `preco_minimo_52s` e
  `preco_maximo_52s` (faixa de 52 semanas do Football Field); recoletado para
  DIRR3 e MGLU3.
- **ONDA 1 — 7 módulos Plotly em `src/visualizacao/`** (HTML + PNG via kaleido
  em `outputs/graficos/`, paleta institucional navy):
  - `tema_institucional.py` — paleta/tipografia/salvamento compartilhados; PNG
    falha com aviso (não derruba) em máquinas sem Chrome.
  - `apoio_cenarios.py` — recalcula Target Price sob cenários (ΔWACC, Δg,
    fator/Δ crescimento, Δ margem, fatores de NWC e CAPEX) a partir dos blocos
    persistidos; devolve None quando g' >= WACC' (célula bloqueada). Aproximação
    documentada: ΔNWC e CAPEX escalam com a receita do cenário; D&A fixa.
  - `apoio_heatmap.py` — heatmaps com formatação condicional pelos limiares de
    recomendação (verde COMPRA / amarelo NEUTRO / vermelho VENDA) e caso base
    com borda dourada.
  - `football_field.py` — 7 metodologias (DCF Bear/Base/Bull, Comps EV/EBITDA e
    P/L como placeholders até a v2.0, Múltiplo de Saída ±20%, faixa 52 semanas),
    preço atual em linha vertical vermelha. Parâmetros Bear/Bull e múltiplos
    placeholder em `config/parametros.json` (`football_field`).
  - `waterfall_ev.py` — VP(FCFF) 8 anos + VP(VT) → EV com % de cada bloco e
    aviso quando VP(VT) > 80% do EV.
  - `sensibilidade_wacc_g.py` — grade 7 WACC × 5 g (passos em
    `config/parametros.json` → `sensibilidade`), segunda tabela com % do EV na
    perpetuidade.
  - `sensibilidade_receita_margem.py` — Δcrescimento × Δmargem (pp, 8 anos).
  - `sensibilidade_setor.py` — construção: Margem × intensidade de NWC (proxy
    inverso documentado de VSO, que não é observável no modelo v1.0); varejo:
    Margem × intensidade de CAPEX.
  - `historico_vs_projetado.py` — grade 2×2 (Receita, EBITDA, Margem EBITDA,
    LL), histórico CVM sólido + projeção tracejada conectadas.
  - `dashboard_final.py` — faixa de KPIs de decisão (anotações no papel; o
    go.Indicator não renderizava valores em multilinha) + FCFF anual + ponte
    EV→Equity + histórico vs projetado.
  - Todos os `gerar_*` devolvem `{"html", "png", "figura"}` — o app Streamlit
    reutiliza a figura via `st.plotly_chart` sem regenerar lógica.
- **ONDA 2 — `app.py` + `.streamlit/config.toml` (tema navy institucional):**
  - Sidebar com 6 seções: Overview, Historico, Premissas, Valuation, Analise,
    Excel Preview (esta última é stub declarado até a Etapa 5).
  - Premissas: 8 campos individuais por vetor (number_input em expanders, com
    histórico CVM ao lado como âncora), sliders para DSO/DIO/DPO/beta/Kd/g com
    histórico no rótulo; validação em tempo real bloqueia g >= WACC (st.error +
    botão desabilitado) e alerta margem > máxima histórica + 5pp e g > 5%.
    Slider de g com teto 25% de propósito, para permitir testar o bloqueio.
  - Salvar premissas reexecuta o pipeline oficial completo (DRE → WK → PP&E →
    Dívida → FCFF → WACC → VT → EV → Checklist), injetando Rf e preço atual dos
    JSONs de mercado já coletados para não depender de rede.
  - Valuation: decomposição completa do WACC em tabela, métricas do VT,
    waterfall, football field e checklist com status.
  - `tests/test_app.py` (Streamlit AppTest, sem navegador): Overview renderiza
    Target Price; g=20% mostra BLOQUEADO e desabilita salvar; g=2% não bloqueia;
    Valuation renderiza WACC + checklist. Pula com skipif se data/processed
    estiver ausente.
- **Validação de qualidade:** `pytest tests -q` verde com 63 testes;
  `black --check` e `flake8` limpos; `python -m src.verificar_semana3` OK;
  app validado no navegador (6 seções navegáveis, gráficos embutidos).
- **Decisões de arquitetura tomadas nesta sessão:**
  - O Ano 0 de toda projeção é o último exercício ANUAL da CVM (DFP 31/12),
    nunca um ITR trimestral.
  - Cenários e sensibilidades derivam do resultado persistido do motor
    (`apoio_cenarios.recalcular_cenario`), sem reexecutar o pipeline — o caso
    base continua nascendo exclusivamente do motor.
  - Cores de sensibilidade seguem os mesmos limiares da recomendação do motor
    (COMPRA > +20%, VENDA < −5%) para consistência semântica entre módulos.
  - Parâmetros de cenário/sensibilidade (Bear/Bull, passos de grade, múltiplos
    placeholder) vivem em `config/parametros.json`, não hard-coded.
  - O app não recalcula nada em JavaScript: widgets apenas editam o JSON de
    premissas e disparam o motor Python.
- **Bugs conhecidos / pendências:**
  - MGLU3 alerta S3 (múltiplo de saída implícito 2,59x < 3x) — não bloqueante;
    revisão humana das premissas de perpetuidade da MGLU3 recomendada.
  - Kd histórico da MGLU3 sai alto (~30%+) porque as despesas financeiras da
    CVM incluem itens não-dívida (descontos de recebíveis etc.); o WACC ainda
    fica na faixa de sanidade, mas vale revisão humana na Semana 5.
  - `preview_screenshot` do harness apresentou timeout com os gráficos Plotly;
    validação visual do app foi feita por snapshot/eval + AppTest.
- **PRÓXIMA TAREFA:**
  - SEMANA 5 / Etapa 5: `exportador_excel.py` (7 abas, fórmulas nativas,
    convenção de cores), `exportador_bi.py` (tabelas planas em `outputs/bi/`),
    `main.py` ponta a ponta e aba Excel Preview funcional no app.

### Sessão 07/07/2026 — ROIC/ROIIC projetado como reality check

- `calculador_fcff.py` agora persiste, para cada `ano1..ano8`, `capital_giro_operacional`,
  `capital_investido`, `roic` e `roiic` dentro do bloco `fcff`, mantendo FCFF/FCFE
  como contratos existentes. `ROIIC ano1` fica `n/d`; a partir do ano 2 usa
  `ΔNOPAT_t / ΔIC_(t-1)`.
- `metricas_historicas.py` passou a calcular `capital_investido` e `roiic` históricos,
  além de média e mediana 3a para ROIC/ROIIC. Não há regressão à média automática nem
  regra que force ROIC/ROIIC a subir ou cair; a métrica é apenas diagnóstico.
- `roic_roiic.py` criado em `src/visualizacao/`, gerando HTML+PNG em
  `outputs/graficos/` e incorporado na seção Análise do Streamlit.
- `checklist.py` consome o ROIIC persistido pelo motor para NF2, evitando fórmula
  duplicada no checklist.
- `config/mapeamento_cvm.json` recebeu `intangivel`, `obrigacoes_sociais_trabalhistas`,
  `capital_giro_operacional`, `capital_investido`, `roic` e `roiic`.
- O exportador Excel ainda não existe nesta branch; o contrato da Etapa 5 foi atualizado
  para que a aba Valuation inclua linhas anuais de ROIC/ROIIC e a aba Output incorpore
  o gráfico ROIC/ROIIC.
- Validação: testes direcionados (`test_valuation.py`, `test_checklist.py`,
  `test_metricas_historicas.py`) verdes; `test_app.py` verde; `flake8` direcionado
  verde; `python -m src.verificar_semana3` imprime `SEMANA 3 OK`; gráfico ROIC/ROIIC
  gerado para DIRR3 e MGLU3.

### Sessão 07/07/2026 — Semana 5, Prompts 1 e 2 (exportador Excel + main.py)

- **`src/exportacao/exportador_excel.py` criado (Prompt 1):** openpyxl gerando
  `outputs/excel/<TICKER>_dcf.xlsx` com as 7 abas da seção 5.10 — Capa,
  Premissas (8 valores individuais por vetor em fonte azul + histórico CVM ao
  lado), Modelo Integrado (DRE+BP+DFC, 3 exercícios históricos + 8 projetados
  lado a lado, common-size ao lado), Schedules (WK, PP&E e Dívida em blocos
  verticais com coluna Ano 0), Valuation (FCFF 8 anos com ROIC/ROIIC,
  decomposição completa do WACC, VT de Gordon, bridge EV→Equity→Target,
  Football Field e Waterfall embutidos como PNG), Sensibilidades (3 tabelas
  com formatação condicional verde/âmbar/vermelho pelos limiares do motor e
  caso base com borda dourada) e Output (dashboard de KPIs + checklist
  colorido + PNGs do dashboard executivo e ROIC/ROIIC).
- **Padrão "nível Direcional" implementado:** fórmulas nativas nas células de
  cálculo (Modelo Integrado com ~436 células de fórmula; Schedules ~81;
  Valuation ~80), convenção de cores WSP (azul = input, preto = fórmula,
  verde = link entre abas) e nomes definidos `WACC` e `g_perpetuidade` para
  Data Tables futuras.
- **Mecanismo `escrever_calculo` (decisão de arquitetura):** cada fórmula
  nativa só entra na célula se o valor que ela produziria (recalculado em
  Python com os mesmos operandos) bater com o valor persistido pelo motor;
  caso contrário a célula recebe o VALOR do motor (ex.: salvaguarda do
  ΔNWC do ano 1). O Excel nunca exibe número diferente do pipeline.
- **Layout fixo por constantes `LINHA_*`:** Modelo Integrado e Valuation
  referenciam células da aba Schedules antes de ela ser construída; o
  contrato é travado por constantes e por teste de alinhamento de rótulos.
- **Validação no Excel REAL (COM/PowerShell):** os dois arquivos foram
  abertos no Excel 16.0, recalculados e conferidos célula a célula contra
  `data/processed/<TICKER>_projecao.json` — receita e LL dos 8 anos, FCFF,
  WACC (via nome definido), VT bruto, Target Price, Upside e a linha de
  verificação `Ativo − (Passivo+PL) = 0` nas fórmulas dos 8 anos: TUDO OK.
- **Bug corrigido na formatação condicional:** `PatternFill` de regra
  condicional exige `start_color` E `end_color` (estilo diferencial usa o
  bgColor); sem o end_color a regra existia mas pintava branco. Verificado
  pós-fix via `DisplayFormat.Interior.Color` (DIRR3: 11 verdes/24 âmbar).
- **`main.py` criado (Prompt 2):** CLI com `--ticker`, `--setor`
  (construcao|varejo) e `--usar-premissas-existentes`; executa as 8 etapas
  com timestamp e duração por etapa (coleta → limpeza/validação → métricas →
  premissas → projeção → valuation → gráficos → Excel) e imprime resumo
  final com Target Price, Upside, Recomendação e o checklist completo.
  Detecta o tipo via `_meta.json` e bloqueia trilha financeira na v1.0.
- **Semântica da flag de premissas:** sem premissas no disco, cria do
  template e para com instrução ao analista; com premissas e SEM a flag,
  para pedindo a flag explícita (protege o julgamento humano); com a flag,
  valida os 24 campos anuais individuais + escalares e segue. Os três
  caminhos têm mensagem de erro orientada a ação.
- **Coleta com fallback offline:** cada coletor (CVM, yfinance, BACEN) que
  falhar cai para os dados já persistidos em `data/raw/` com aviso; só
  aborta se não houver dado nenhum.
- **Etapa "limpeza" = validação de contrato:** confere arquivos brutos,
  linhas com `nome_padronizado`/`valor_padronizado` e contas-chave mapeadas
  (decisão v1: a projeção lê os JSONs brutos direto; não há Parquet).
- **Execução ponta a ponta validada COM REDE:** `python main.py --ticker
  DIRR3 --setor construcao --usar-premissas-existentes` (161s, coleta CVM
  real) e idem MGLU3 (`--setor varejo`, 168s), ambos exit 0. DIRR3: Target
  R$ 15,29 vs R$ 13,41 (+14,0%, NEUTRO), WACC 16,60%. MGLU3: Target R$ 6,01
  vs R$ 4,42 (+35,9%, COMPRA), WACC 19,39%. Checklists APROVADOS (alertas
  não-bloqueantes NF4 nos dois; NF2 marginal na MGLU3 com dados recoletados).
- **Testes novos:** `tests/test_exportador_excel.py` (8 testes: 7 abas na
  ordem, alinhamento das constantes de layout, fórmulas nativas, fonte azul
  de input, nomes definidos, formatação condicional, PNGs embutidos,
  checklist na aba Output). Suíte total: 73 testes verdes.
- **Validação de qualidade:** `black --check` limpo, `flake8` limpo,
  `pytest tests -q` com 73 passed; abas Capa/Premissas/Sensibilidades/Output
  exportadas para PDF via Excel COM e inspecionadas visualmente.
- **Bugs conhecidos / pendências:**
  - `exportador_bi.py` e aba Excel Preview do app ainda não existem
    (Prompt 3 da Semana 5).
  - Sensibilidades usam valores calculados (via `apoio_cenarios`) com
    formatação condicional nativa; Data Tables nativas do Excel ficam como
    evolução possível já que WACC e g têm nomes definidos.

### Sessão 02/07/2026 — Fechamento da Semana 2 e início da Semana 3

- **Concluído nesta sessão:**
  - `tests/test_projecao.py` consolidado com teste integrado DRE -> WK -> PP&E -> dívida usando `tmp_path`, sem dados reais e sem rede, validando balanço fechado nos 8 anos, oito taxas individuais diferentes e `LL = PL_t - PL_(t-1)` com payout zero.
  - `src/verificar_semana2.py` criado para rodar o pipeline real de DIRR3 e MGLU3, imprimir Ano 0, premissas anuais, DRE projetada e `diferenca_balanco` por ano.
  - `data/premissas/DIRR3_premissas.json` e `data/premissas/MGLU3_premissas.json` conferidos com vetores anuais diferentes para crescimento, margem EBITDA e CAPEX/Receita.
  - `src/coleta/coletor_mercado.py` criado: coleta yfinance para preço, beta mensal contra `^BVSP`, ações em circulação, market cap e `^TNX`, salvando em `data/raw/mercado/`.
  - `src/coleta/coletor_macro.py` criado: coleta Selic atual via SGS 432 e expectativas Focus anuais de IPCA/Selic via `python-bcb`, salvando em `data/raw/macro/macro_brasil.json`.
  - `src/valuation/calculador_fcff.py` criado: calcula e persiste blocos `fcff` e `fcfe` em `data/processed/<TICKER>_projecao.json`.
  - `tests/test_valuation.py` criado cobrindo FCFF positivo, FCFF negativo permitido, FCFE e construtora RET com alíquota zero no NOPAT.
  - `config/mapeamento_cvm.json` ampliado com campos de FCFF/FCFE, mercado e macro.
- **Critérios de pronto:**
  - Semana 2: `pytest tests -v` verde com 16 testes.
  - Semana 2: `src/verificar_semana2.py` rodou para DIRR3 e MGLU3 e imprimiu `SEMANA 2 OK`.
  - Semana 2: `black --check . --workers 1` e `flake8 .` verdes.
  - Semana 3 parcial: `coletor_mercado.py` rodou para DIRR3 e MGLU3 com rede liberada e gravou `data/raw/mercado/`.
  - Semana 3 parcial: `coletor_macro.py` rodou com rede liberada e gravou `data/raw/macro/macro_brasil.json`.
  - Semana 3 parcial: `calculador_fcff.py` rodou para DIRR3 e imprimiu FCFF diferente ano a ano.
- **Decisões de arquitetura tomadas:**
  - O beta de mercado é calculado manualmente com retornos mensais do ativo contra `^BVSP`, usando até 60 meses; se houver menos meses, o coletor registra aviso e usa o máximo disponível.
  - O `^TNX` é convertido para decimal anual em `rf_usd_tbond10y`.
  - O yfinance usa cache local em `.cache/yfinance` para evitar falha de SQLite fora do workspace.
  - O NOPAT usa 34% para empresas gerais e 0% para construtoras RET, porque o IR/CSLL da DRE já foi calculado por receita e não deve ser aplicado novamente ao EBIT.
  - FCFF negativo é persistido normalmente, sem travar o pipeline.
- **Bugs encontrados e corrigidos:**
  - A `.venv` apontava para um Python 3.11 ausente em `AppData`; foi restaurada com Python 3.11.9 local em `.venv/base/Python311`.
  - O runtime embutido do Codex era Python 3.12 e incompatível com os pacotes compilados da `.venv`; a validação voltou a usar Python 3.11.9.
  - O yfinance falhava com `unable to open database file`; corrigido direcionando o cache para `.cache/yfinance`.
  - O wrapper do Black 26.5.1 travava dentro do sandbox no encerramento dos workers; o comando literal passou fora do sandbox com `--workers 1`.
- **PRÓXIMA TAREFA:**
  - Implementar `src/valuation/calculador_wacc.py`.

---

## 9. Divisão de Trabalho Humano vs. IA

> **Protocolo de decisões autônomas (instrução permanente de Lucas, 12/07/2026):**
> quando a IA precisar de uma escolha que caberia ao humano (erro, ambiguidade,
> conflito, opção de design), ela decide sozinha pela melhor opção, executa e
> registra em **`Humano_revisar.md`** (data, situação, escolha, alternativas,
> justificativa) para revisão humana posterior. Nada registrado lá é definitivo
> até o humano aprovar.

- **Humano (Lucas):** ativa venv, preenche premissas com julgamento real, valida números contra fontes públicas, descreve bugs, commita no GitHub, atualiza este CONTEXT.md, **revisa periodicamente o `Humano_revisar.md`**.
- **Codex:** cria/edita todos os arquivos Python, corrige bugs descritos, roda testes, gera gráficos, exporta Excel.
- **DeepSeek:** reservado apenas para validação de fórmula matemática (caso de borda).
- **Claude Code:** lê `CONTEXT.md` + `ROTEIRO.md`, gera os prompts cirúrgicos que o
  humano cola no Codex, e faz a revisão final de código.

---

## 10. Camada de BI (Power BI) e Backlog Pós-v1.0

**Princípio:** separar *cálculo* (motor Python, fonte única de verdade) de *apresentação*
(Streamlit interativo + Power BI executivo). O Power BI NUNCA recalcula valuation — lê as
tabelas planas de `outputs/bi/` e desenha visuais. Qualquer número exibido nasceu do motor.

**Na v1.0 (decisão ESTRUTURAL, já entra na Semana 5 — ver Etapa 5 do `ROTEIRO.md`):**
- `src/exportacao/exportador_bi.py` grava tabelas planas (long/star-schema) em
  `outputs/bi/<TICKER>/`: `dim_empresa`, `dim_valuation`, `fato_demonstracoes`,
  `fato_fcff`, `fato_sensibilidade_wacc_g`, `fato_sensibilidade_receita_margem`,
  `fato_football_field`, `fato_historico_vs_projetado`. Nomes de coluna seguem
  `mapeamento_cvm.json`.
- Excel "nível Direcional": fórmulas nativas nas células de cálculo (não valores colados)
  + convenção de cor de input (azul = premissa, preto = fórmula, verde = link entre abas).

**Backlog pós-v1.0 (só depois da tag `v1.0`; detalhe na Seção 7 do `ROTEIRO.md`):**
1. **Painel Power BI (`.pbix`)** em `powerbi/`, conectado a `outputs/bi/` (alvo v1.5).
2. **Comparáveis / CCA** (`src/valuation/comparaveis.py`) — múltiplos de peers (alvo v2.0).
3. **Projetado vs. Realizado** (`src/analise/projetado_vs_realizado.py`) — variância/FP&A;
   lente nova sobre DIRR3/MGLU3, NÃO um setor novo (compatível com a regra de ouro) (v2.0).
4. **Nota de research em PDF** (`src/exportacao/exportador_pdf.py`, requer `reportlab`) (v3.0).
5. **Prova visual no README** — screenshots/GIF + case study DIRR3 vs. modelo InFinance.

> Ao gerar prompts para o Codex sobre estes itens, o Claude Code deve confirmar antes que
> a tag `v1.0` já foi criada. Antes disso, o único item de BI permitido é o
> `exportador_bi.py` da Etapa 5.
