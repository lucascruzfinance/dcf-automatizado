# ROTEIRO.md — Especificação de Desenvolvimento para o Codex

> **Público-alvo deste documento: o Codex (IA de desenvolvimento).**
> Este é o plano técnico sequenciado do projeto DCF Automatizado, da fundação até a
> v1.0 (prazo 06/08/2026). Leia este arquivo junto com o `CONTEXT.md` no início de
> cada sessão. O `CONTEXT.md` diz o ESTADO ATUAL e a PRÓXIMA TAREFA; este `ROTEIRO.md`
> diz o PLANO COMPLETO e os CONTRATOS entre módulos.
>
> Regra de precedência: se este roteiro conflitar com um pedido pontual do usuário na
> sessão, o pedido do usuário vence, mas avise sobre o conflito antes de executar.

---

## 0. Princípios Invariantes (valem para TODAS as etapas)

Estes princípios não mudam entre semanas. Violá-los é um bug, mesmo que o código rode.

1. **Escopo v1.0 fixo:** apenas DIRR3 (construção civil) e MGLU3 (varejo). Ambas
   não-financeiras. A trilha financeira (FCFE/Ke) é construída como arquitetura, mas
   NÃO é validada na v1.0. Não gaste esforço tentando fazer bancos funcionarem agora.
2. **Idioma do código:** nomes de função, variável e comentário em português.
3. **Fonte única de verdade nos nomes de coluna:** toda coluna de DataFrame usa o
   nome padronizado definido em `config/mapeamento_cvm.json`. A mesma grandeza tem o
   MESMO nome em coleta, projeção, valuation e exportação. Inconsistência de nome
   entre módulos é o bug mais caro do projeto.
4. **Sinais:** despesas e saídas de caixa negativas; receitas e entradas positivas.
5. **8 valores individuais:** crescimento de receita, margem EBITDA e CAPEX/Receita
   têm 8 campos separados por ano (`..._ano1` a `..._ano8`). NUNCA replicar uma taxa
   única pelos 8 anos.
6. **Negativos são válidos:** ROIC, FCFF e LL podem ser negativos. Não travar.
7. **Robustez de dados externos:** todo acesso a campo da CVM/API trata campo
   ausente ou renomeado sem quebrar silenciosamente. Campo não mapeado vai para log.
8. **Qualidade por etapa:** toda função com docstring; todo cálculo financeiro com
   comentário da fórmula; `black` e `flake8` limpos antes de considerar algo pronto.
9. **Continuidade:** ao final de cada tarefa, atualizar a seção "Estado Atual" do
   `CONTEXT.md` com o que foi feito, decisões tomadas e a próxima tarefa.
10. **Comunicação entre módulos:** os módulos se comunicam por arquivos intermediários
    — dados brutos em `data/raw/`, dados limpos em Parquet em `data/processed/`,
    premissas em JSON em `data/premissas/`, saídas em `outputs/`. Um módulo não chama
    o outro diretamente por import quando a comunicação natural é por arquivo; isso
    mantém o pipeline inspecionável em cada estágio.

---

## 1. Arquitetura de Referência

Pipeline de 5 módulos sequenciais. Cada módulo depende do output do anterior.

```
Módulo 1 — Coleta          src/coleta/           -> data/raw/, data/processed/
Módulo 2 — Métricas Hist.  src/metricas/         -> âncora para premissas
Módulo 3 — Premissas       app.py / interface/   -> data/premissas/<TICKER>.json
Módulo 4 — Motor Cálculo   src/projecao/,        -> DRE/BP/DFC proj., FCFF, WACC,
                           src/valuation/           VT, EV, Target Price
Módulo 5 — Dashboard/Out   src/visualizacao/,    -> gráficos, Excel 7 abas,
                           src/exportacao/, app.py  front-end Streamlit
```

**Ordem de cálculo obrigatória dentro do Módulo 4 (não-financeiras):**
`projetor_dre -> schedule_wk -> schedule_ppe -> schedule_divida -> calculador_fcff ->
calculador_wacc -> calculador_vt -> calculador_ev -> checklist`.
A ordem existe porque cada passo consome o output do anterior (ex.: a D&A vem do
schedule de PP&E de volta para a DRE; o resultado financeiro vem do schedule de
dívida de volta para a DRE; o FCFF consome componentes de todos os schedules).

---

## 2. Fórmulas Canônicas (fonte: Damodaran, McKinsey, Assaf Neto)

```
NOPAT  = EBIT × (1 − t)
FCFF   = NOPAT + D&A − ΔNWC − CAPEX
FCFE   = LL + D&A − ΔNWC − CAPEX + ΔDívida Líquida
Ke_USD = Rf + Beta_realavancado × (ERP_EUA + CRP_Brasil)
Ke_BRL = [(1 + Ke_USD) × (1 + IPCA)] / (1 + CPI_EUA) − 1
Kd     = Despesas Financeiras / Dívida Bruta Média (3 anos)
WACC   = (E/V) × Ke_BRL + (D/V) × Kd × (1 − t)
TV     = FCFF₈ × (1 + g) / (WACC − g)      [não-financeira]
TV     = FCFE₈ × (1 + g) / (Ke − g)        [financeira]
VP(TV) = TV / (1 + WACC)^8
EV     = Σ VP(FCFF_t) + VP(TV)
Equity = EV − Dívida Bruta (CP+LP+Leasing IFRS16) + Caixa + Aplicações
         − Minoritários + Coligadas + Ativos Não Operacionais
Target Price = Equity Value / Ações Fully Diluted
Upside = (Target Price / Preço Atual) − 1
Beta desalavancado (Hamada): βu = βL / [1 + (1 − t) × (D/E)]
ROIC   = NOPAT / Capital Investido médio
IC     = NWC + Imobilizado líquido + Goodwill + Outros ativos operacionais
```

**Tributação:** empresas gerais → IR/CSLL de 34% sobre o EBT. Construtoras no RET →
4% sobre a Receita Bruta.

**FCFF₈ negativo:** usar o NOPAT normalizado do último ano como base do Valor Terminal
em vez do FCFF negativo, com comentário explicando o ajuste.

**Recomendação:** COMPRA se Upside > 20%; NEUTRO se entre −5% e +20%; VENDA se < −5%.

---

## 3. Contratos de Interface entre Módulos

Estes são os "aceites" que cada módulo deve respeitar para não quebrar o próximo.

- **Coleta -> resto do pipeline:** produz `data/raw/cvm/<TICKER>_meta.json` (com
  `tipo` = "nao_financeira"|"financeira" e setor) e os dados brutos mapeados. Todo
  módulo posterior lê o `_meta.json` para decidir a trilha.
- **Limpeza -> Métricas/Projeção:** produz DataFrames limpos em Parquet em
  `data/processed/`, com sinais normalizados, colunas com nomes padronizados, e uma
  flag booleana marcando itens não-recorrentes (sem removê-los).
- **Premissas -> Motor:** produz `data/premissas/<TICKER>_premissas.json` seguindo
  exatamente o schema do template. O motor lê os 8 campos individuais de crescimento,
  margem e CAPEX; se algum dos 8 estiver ausente, é erro (não preencher com repetição).
- **Motor -> Dashboard/Excel:** produz um objeto/estrutura de resultado do valuation
  contendo, no mínimo: DRE/BP/DFC projetados (8 anos), FCFF por ano, WACC com
  decomposição, VT, VP(VT), % do EV na perpetuidade, EV, Equity, Target Price,
  Upside, Recomendação, e o resultado do checklist. Visualização e exportação
  consomem essa mesma estrutura — não recalculam nada por conta própria.

---

## 4. Etapas Sequenciadas (Definição de Pronto por etapa)

### ETAPA 0 — Fundação + Coleta inicial

**Arquivos:** estrutura de pastas; `config/setores.json`; `config/mapeamento_cvm.json`;
`config/parametros.json`; `data/premissas/template_naofinanceiras.json` e
`template_financeiras.json` (com 8 campos individuais); mover Excel para
`tests/fixtures/`; `src/coleta/coletor_cvm.py`.
(NÃO recriar README, CONTEXT, CONTRIBUTING, CHANGELOG, requirements.txt, .env.example,
.gitignore, LICENSE — já existem commitados.)

**coletor_cvm.py deve:** descobrir CD_CVM pelo ticker; coletar DFP e ITR (7 anos) de
DRE/BP/DFC; mapear contas via `mapeamento_cvm.json`; logar campos não mapeados sem
quebrar; detectar tipo financeira/não-financeira; salvar `_meta.json`; tratar todos
os erros de API; ao rodar direto, executar para DIRR3 e MGLU3 e imprimir resumo
comparativo com Receita Líquida e LL dos últimos 3 anos.

**Pronto quando:** estrutura de pastas existe; `mapeamento_cvm.json` cobre as contas
principais; templates têm `crescimento_receita_ano1..8`; coletor gera meta + dados
para DIRR3 e MGLU3; ambas detectadas como não-financeiras. (Validação numérica
contra fontes públicas é feita pelo humano.)

### ETAPA 1 — Coleta completa + Métricas históricas

**Arquivos:** `src/coleta/coletor_mercado.py`; `src/coleta/coletor_macro.py`;
`src/processamento/limpeza.py`; `src/metricas/metricas_historicas.py`.

- **coletor_mercado.py:** yfinance — preço atual + histórico 5 anos, ações fully
  diluted, beta rolling 60 meses (mensal), market cap, dividend yield, T-Bond 10Y via
  `^TNX`. Tratar tickers `.SA` não reconhecidos.
- **coletor_macro.py:** python-bcb — Selic atual + Focus 1 e 2 anos, IPCA atual +
  Focus, CDI, TJLP. Salvar em `data/raw/macro/`.
- **limpeza.py:** normaliza sinais, separa dívida financeira de NIBCLs
  (não-financeiras), flag de não-recorrentes sem remover, salva Parquet em
  `data/processed/`.
- **metricas_historicas.py:** DUAS trilhas via `_meta.json`. Trilha não-financeira
  (validada): crescimento YoY, CAGR 3/5/7, margens bruta/EBIT/EBITDA/líquida, ROIC
  com DuPont, ROIIC rolling 3 anos, DSO/DIO/DPO/CCC, FCO/EBITDA, FCO/LL, Dívida
  Líquida/EBITDA, cobertura de juros, beta desalavancado (Hamada), alíquota efetiva.
  Trilha financeira (esqueleto, não validada): ROE, ROA, NIM, eficiência, NPL,
  coverage, Basileia.

**Pronto quando:** mercado e macro coletam para DIRR3/MGLU3 com valores plausíveis;
Parquet gerado em `data/processed/`; métricas não-financeiras calculadas sem travar
em anos de prejuízo.

### ETAPA 2 — Projeção das demonstrações (etapa mais crítica)

**Arquivos:** `src/projecao/projetor_dre.py`; `schedule_wk.py`; `schedule_ppe.py`;
`schedule_divida.py`; `tests/test_projecao.py`.

- **projetor_dre.py:** projeta DRE 8 anos lendo obrigatoriamente os 8 campos de
  crescimento e aplicando cada taxa ao seu ano (sem repetir). Margem EBITDA individual
  por ano. EBIT = EBITDA − D&A (D&A vem do schedule de PP&E). IR sobre EBT (geral) ou
  sobre Receita Bruta a 4% (construtora RET). Permite LL negativo.
- **schedule_wk.py:** NWC via DSO/DIO/DPO; ΔNWC como consumo de caixa quando positiva.
- **schedule_ppe.py:** PP&E_t = PP&E_{t−1} + CAPEX_t − D&A_t; CAPEX = % individual do
  ano × Receita do ano; ativo para de depreciar em zero; devolve D&A para a DRE.
- **schedule_divida.py:** juros = Kd × saldo médio; atualiza resultado financeiro da
  DRE; verifica fechamento do balanço nos 8 anos, imprimindo cada verificação.
- **test_projecao.py:** pytest validando Ativo = Passivo + PL em cada um dos 8 anos.

**Pronto quando:** `pytest tests/test_projecao.py` verde; balanço fecha nos 8 anos
para DIRR3 e MGLU3; a DRE projetada de DIRR3 mostra taxa de crescimento DIFERENTE em
cada ano (prova das 8 taxas individuais).

### ETAPA 3 — Valuation completo

**Arquivos:** `src/valuation/calculador_fcff.py`; `calculador_wacc.py`;
`calculador_vt.py`; `calculador_ev.py`; `checklist.py`; `tests/test_valuation.py`.

- **calculador_fcff.py:** FCFF pelos 8 anos (mantém negativo sem travar); calcula
  FCFE também.
- **calculador_wacc.py:** Rf via `^TNX`; Ke_USD -> Ke_BRL; Kd histórico; WACC com
  decomposição completa exibida. Para financeiras: apenas Ke, usando peers do setor
  bancário para beta.
- **calculador_vt.py:** TV pelo Gordon; bloqueia se g >= taxa de desconto; alerta se
  g > 5% BRL; verifica reinvestimento 0-100%; trata FCFF₈ negativo com NOPAT
  normalizado; calcula VP(TV), % do EV na perpetuidade, múltiplo de saída implícito.
- **calculador_ev.py:** bridge EV -> Equity -> Target Price -> Upside -> Recomendação
  (não-financeiras); para financeiras, Equity direto sem bridge.
- **checklist.py:** verificações universais + por tipo (ver seção 5). + test_valuation.py.

**Pronto quando:** terminal imprime Target Price, Upside e checklist para DIRR3 e
MGLU3; `pytest tests/test_valuation.py` verde; sistema bloqueia g >= WACC; Target
Price de DIRR3 na mesma ordem de magnitude do Excel de referência (validação humana).

### ETAPA 4 — Visualizações + Front-end institucional

**Arquivos de visualização:** `src/visualizacao/football_field.py`; `waterfall_ev.py`;
`sensibilidade_wacc_g.py`; `sensibilidade_receita_margem.py`; `sensibilidade_setor.py`;
`historico_vs_projetado.py`; `dashboard_final.py`. Todos Plotly, salvando HTML + PNG
em `outputs/graficos/`.

**Front-end:** `app.py` (Streamlit) + `.streamlit/config.toml` (tema institucional).

**Design institucional obrigatório** (aplicar em gráficos e no app):
- Paleta: fundo navy `#0A1628`, superfície `#0F1E33`, azul âncora `#1B4F8C`, acento
  sóbrio; verde `#16A34A` = upside, vermelho `#DC2626` = downside (uso semântico
  estrito, nunca decorativo).
- Tipografia: texto em sans (Inter/IBM Plex Sans); números em fonte monoespaçada
  (IBM Plex Mono) para alinhamento das casas decimais.
- Densidade com hierarquia: decisão (Target Price, Recomendação) em destaque; suporte
  agrupado e secundário. Sem elemento puramente decorativo.

**Front-end — sidebar de 6 seções:** Overview, Histórico, Premissas, Valuation,
Análise, Excel Preview. A seção Premissas usa `number_input` + `slider`, exibe o
histórico ao lado de cada campo (lendo `metricas_historicas.py`), e valida em tempo
real (bloqueia g >= WACC; alerta margem > 5pp acima da máxima histórica).

**Football Field — 7 metodologias:** DCF Bear (crescimento −20%, margem −2pp, WACC
+1pp, g −0,5pp), DCF Base, DCF Bull (espelho do Bear), Comps EV/EBITDA, Comps P/L,
Múltiplo de Saída, 52-week Range; preço atual em linha vertical vermelha.

**Sensibilidade WACC × g:** 6×6, WACC de base −1,5pp a +1,5pp (passo 0,5pp), g de base
−1pp a +1pp (passo 0,5pp); formatação condicional verde/amarelo/vermelho; caso base
com borda destacada; segunda tabela com % do EV na perpetuidade por combinação.

**Pronto quando:** 7 HTMLs abrem com qualidade profissional para DIRR3 e MGLU3;
`streamlit run app.py` sobe; sidebar navega nas 6 seções; ajustar premissa reflete no
resultado.

### ETAPA 5 — Excel 7 abas + integração ponta a ponta

**Arquivos:** `src/exportacao/exportador_excel.py`; `main.py`; aba Excel Preview no
`app.py`.

- **exportador_excel.py (openpyxl):** 7 abas — (1) Capa; (2) Premissas com os 8
  valores individuais + histórico ao lado; (3) Modelo Integrado (DRE+BP+DFC, 3 anos
  históricos + 8 projetados lado a lado, common-size ao lado); (4) Schedules (WK, PP&E,
  Dívida em blocos verticais); (5) Valuation (FCFF 8 anos, decomposição WACC, bridge,
  Football Field e Waterfall embutidos como PNG); (6) Sensibilidades (3 tabelas,
  formatação condicional, caso base destacado); (7) Output (dashboard + checklist).
  Cabeçalhos navy, números com separador de milhar e 2 casas, percentuais com 1 casa.
- **main.py:** aceita `--ticker` e `--setor`; detecta tipo via `_meta.json`; executa o
  pipeline na ordem correta com timestamps; flag `--usar-premissas-existentes`; resumo
  final com Target Price, Upside, Recomendação, checklist.

**Pronto quando:** `python main.py --ticker DIRR3 --setor construcao
--usar-premissas-existentes` roda ponta a ponta sem erro e gera o Excel com 7 abas,
gráficos embutidos e formatação; idem para MGLU3; Excel Preview funciona no app.

### ETAPA FINAL — Revisão e tag v1.0

Revisão geral: docstrings faltantes, nomes genéricos, cálculos sem comentário,
inconsistências de nome de coluna entre módulos, pontos que quebram se a CVM mudar um
campo. Rodar o pipeline completo para DIRR3 e MGLU3 corrigindo bugs; `pytest` verde em
tudo; confirmar Excels em `outputs/excel/` e gráficos em `outputs/graficos/`.

**Pronto quando:** `pytest` verde geral; os 2 Excels gerados; `streamlit run app.py`
funcional; repositório com tag `v1.0`.

---

## 5. Checklist de Consistência (implementar em `checklist.py`)

**Universais (todas as empresas):** g < taxa de desconto; g ≤ 5% BRL; taxa de
reinvestimento entre 0% e 100%; VP(VT) < 85% do EV; ações fully diluted usadas no
Target Price.

**Não-financeiras:** balanço fecha nos 8 anos; ROIIC implícito < 50% nos 2 últimos
anos; CAPEX ≥ D&A na perpetuidade; FCO/EBITDA histórico > 0,7x; Dívida Líquida/EBITDA
< 4x em todos os anos.

**Financeiras (v1.5):** Índice de Basileia projetado > 10,5%; Coverage Ratio > 100%;
ROE projetado > Ke.

Cada verificação retorna status (aprovado/alerta) e uma mensagem legível. O checklist
nunca interrompe o pipeline por um alerta — apenas sinaliza.

---

## 6. O Que NÃO Fazer

- Não expandir o escopo além de DIRR3 + MGLU3 na v1.0.
- Não reimplementar cálculo em JavaScript. O Python (motor) é a fonte única de verdade;
  o Streamlit apenas o consome.
- Não recriar/sobrescrever os arquivos de documentação e config da raiz que já existem.
- Não replicar uma taxa única pelos 8 anos em nenhuma hipótese.
- Não commitar `.env`, `data/`, `outputs/`, `.venv/`.
- Não hard-codar valores que deveriam ser premissas (JSON) ou parâmetros (config).
- Não introduzir um nome de coluna novo sem registrá-lo no `mapeamento_cvm.json`.
