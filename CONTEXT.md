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
- **Benchmark de qualidade:** o modelo Excel da Direcional (DIRR3) do trainee InFinance, em `tests/fixtures/Direcional_DIRR3_referencia.xlsx`.

---

## 2. Escopo da v1.0 (NÃO EXPANDIR SEM AUTORIZAÇÃO EXPLÍCITA)

A v1.0 é **deliberadamente enxuta**. O objetivo é profundidade, não amplitude.

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

- **Data da última atualização:** 03/07/2026
- **Versão alvo:** v1.0 (prazo: 06/08/2026)
- **Fase atual:** SEMANA 3 — Valuation completo: FCFF, WACC, VT, EV e checklist
- **O que está PRONTO e VALIDADO:**
  - Estrutura inicial de pastas e pacotes Python criada.
  - Arquivos de configuração criados: `config/setores.json`, `config/mapeamento_cvm.json` e `config/parametros.json`.
  - Templates de premissas criados em `data/premissas/` com campos individuais por ano.
  - `src/coleta/coletor_cvm.py` implementado para descobrir CD_CVM via dados da CVM, coletar DFP/ITR, mapear contas, registrar contas não mapeadas e persistir JSONs em `data/raw/cvm/`.
  - Coletor CVM validado localmente para DIRR3 e MGLU3: gera `_meta.json`, DRE, BP e DFC em JSON para as duas empresas.
  - DIRR3 e MGLU3 foram detectadas como `nao_financeira`.
  - Ambiente Python 3.11.9 com `.venv` criado; `pip check`, `black`, `flake8` e `pytest` executados com sucesso.
  - Excel de referência da Direcional movido para `tests/fixtures/Direcional_DIRR3_referencia.xlsx`.
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
  - Validação atual: `pytest tests\ -v` verde com 45 testes; `flake8 .` verde; `black --check src\valuation\checklist.py tests\test_checklist.py --workers 1` verde.
- **O que está EM PROGRESSO:**
  - Validação humana dos números coletados para DIRR3 e MGLU3.
  - Validação ponta a ponta da Semana 3 para DIRR3 e MGLU3 com Target Price, Upside e checklist impressos.
- **PRÓXIMA TAREFA:**
  - Fechar a validação operacional da Semana 3 para DIRR3 e MGLU3 e, depois, iniciar a Etapa 4 de visualizações.
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
- **Bugs conhecidos / pendências:**
  - A validação numérica de Receita Líquida e Lucro Líquido contra RI/Status Invest ainda depende de conferência humana.
  - O RET deveria incidir sobre Receita Bruta, mas o coletor atual só traz Receita Líquida (CVM 3.01); a DRE projetada usa Receita Líquida como proxy até existir uma linha confiável de Receita Bruta.

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

- **Humano (Lucas):** ativa venv, preenche premissas com julgamento real, valida números contra fontes públicas, descreve bugs, commita no GitHub, atualiza este CONTEXT.md.
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
