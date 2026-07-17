# PROMPTS_FABLE.md — v2.1 · **Semana 9.0 (17/07 → 24/07/2026)** · Automação fiel dos 3 demonstrativos + Excel "Modelo" (padrão Direcional) com FCFF/FCFE

> **Público-alvo deste documento: o Claude Fable 5 (IA de implementação do projeto).**
> O Fable lê os documentos de contexto, escreve/edita o código Python e o front-end,
> roda os testes e atualiza o `CONTEXT.md`. O **humano (Lucas)** é o dono do julgamento
> analítico (premissas reais, validação numérica, commits) e o **Claude Code** é o
> gerador/curador destes prompts e o revisor final.
>
> **Onde paramos:** a Semana 8 fechou até o **Prompt 8.2** (DRE completa 8.1; IFRS-16 +
> capex expansão/manutenção 8.2). A "D&A por safra" do 8.2 foi **revertida a pedido de
> Lucas** (17/07/2026, D-047/D-048): a depreciação volta a ser simples. **Este documento
> foi reescrito do zero** para conter **APENAS a Semana 9.0 (17/07 → 24/07/2026)**. As
> Semanas 10+ NÃO estão aqui — serão planejadas depois.
>
> **Como usar:** os prompts abaixo (9.0.0 → 9.0.5) são **progressivos e sequenciais**.
> Cada um só começa depois que o anterior fechou sua "Definição de Pronto" (DoD). Cada
> prompt é auto-contido: reafirma o contexto, aponta as células do modelo de referência,
> lista arquivos a criar/editar, especifica contratos e critérios objetivos de aceite.
> **Cole um prompt por vez no Claude Fable 5.**
>
> **Calendário:**
> | Semana | Período | Tema | Prompts |
> |---|---|---|---|
> | **9.0** | 17/07 → 24/07/2026 | Enxugar o projeto + automação fiel dos 3 demonstrativos + Excel "Modelo" (≥ Direcional) com FCFF/FCFE | 9.0.0 … 9.0.5 |
>
> Esta Semana 9.0 **absorve e substitui** o que faltava do plano anterior do 8.3 em
> diante (DFC indireto, BP aberto, dívida, WK multi-driver, macro, retornos, front-end
> guiado, Excel novo), **fundido** com as instruções de automação e Excel que Lucas deu
> no chat de 17/07/2026, e **começa cortando a gordura** (Prompt 9.0.0): o projeto tem
> arquivos demais construídos ANTES do núcleo, e o núcleo — um Excel DCF fiel à CVM — é a
> parte mais fraca. A Semana 9.0 conserta isso.

---

## REGRA DE PRECEDÊNCIA (leia primeiro — vale para TODO o documento)

> **As instruções de automação e Excel do chat de 17/07/2026 têm PRECEDÊNCIA sobre
> qualquer coisa dos prompts antigos das Semanas 8 e 9.** Onde houver conflito, o Fable
> segue a instrução atual, avisa sobre o conflito no `CONTEXT.md`/`Humano_revisar.md`, e
> executa. Os pontos onde a instrução atual VENCE o plano antigo:

1. **D&A = % do PP&E** (taxa única sobre o PP&E de abertura), **CAPEX = % da receita
   líquida**. A "D&A por safra de CAPEX com vida derivada" do antigo Prompt 8.2 está
   **CANCELADA** (já revertida — D-047). Vale o modelo simples, como o Direcional faz.
2. **Margens são PRÉ-D&A (nível EBITDA).** A DRE não embute a D&A dentro de CPV/SG&A. Ela
   projeta Lucro Bruto e "EBIT ex-Depreciação" a partir das margens, e **subtrai a D&A
   como linha PRÓPRIA** (vinda do schedule de PP&E) para chegar ao EBIT — exatamente como
   o Direcional (`Modelo` L28-L30). Isso elimina a dupla contagem que quebrou o SMFT3.
3. **Fidelidade absoluta à CVM:** todo valor histórico dos 3 demonstrativos (BP, DRE,
   DFC) persistido e mostrado no Excel **tem que bater com o que a empresa divulgou na
   CVM (DFP/ITR)**. Isso é o item nº 1 de prioridade (Prompt 9.0.1).
4. **Excel final ≥ Direcional**, dentro de uma aba chamada exatamente **`Modelo`**, com
   histórico + projetado dos 3 demonstrativos. **FCFF e FCFE ficam em abas SEPARADAS —
   uma aba `FCFF` e uma aba `FCFE`**, ambas usando a aba `Modelo` como fonte.
5. **Cores no Excel (convenção de Lucas — 17/07/2026):** **histórico = AZUL**,
   **premissa que o usuário escolhe/envia = VERDE**, **resultado de fórmula = PRETO**.
   (Isto DIFERE da convenção WSP/Direcional, onde azul=input e verde=link. Vale a de
   Lucas. Registrar a divergência em `Humano_revisar.md`.)
6. **Receita projetada = crescimento % anual** (vetor de 8 valores). **NÃO** replicar o
   build-up de receita da Direcional (VGV × POC) nem qualquer unit economics — isso é
   v3.0.

> **Protocolo de decisões autônomas (instrução permanente de Lucas, 12/07/2026):**
> diante de erro, ambiguidade, conflito ou escolha que caberia ao humano, o Fable NÃO
> para para perguntar: decide sozinho pela melhor opção, executa e registra em
> **`Humano_revisar.md`** (ID `D-nnn`, data, situação, escolha, alternativas,
> justificativa). O humano revisa e pode reverter.

---

## 0. Contexto: onde estamos e o que a Semana 9.0 persegue

### 0.1 Estado real do repositório — o diagnóstico honesto (medido em 17/07/2026)

> **Encare isto antes de programar.** O projeto construiu MUITA largura (periferia) e
> pouca profundidade no NÚCLEO. O motor de valuation é sólido; a entrega que importa —
> um **Excel DCF fiel à CVM** — é a parte mais fraca. Números reais medidos hoje:

**O que FUNCIONA (o motor — não é "nada"):**
- **Coleta universal:** qualquer ticker da B3 → CD_CVM → DFP/ITR/DVA mapeadas por
  `CD_CONTA` → JSONs em `data/raw/cvm/`.
- **Motor por tipo:** não-financeiras FCFF/WACC; financeiras FCFE/Ke. DRE completa
  (bruta→líquida, CPV/SG&A). Leasing IFRS-16. D&A = **modelo simples** (taxa única sobre
  PP&E de abertura). Balanço fecha por construção. FCFF → WACC (CAPM Brasil real) → VT →
  bridge → Target Price. Cenários Bear/Base/Bull. **Isso está certo e é o alicerce.**

**O que está QUEBRADO ou inchado (o alvo da Semana 9.0):**
- **O Excel — a entrega central — está pela metade.** O `DIRR3_dcf.xlsx` gerado hoje
  tem a aba principal ("Modelo Integrado") com **apenas 40 linhas** (a Direcional de
  referência tem **210**). A DRE do Excel é a **versão ANTIGA** (Receita → margem EBITDA
  → D&A → EBIT) — a DRE completa que o motor calcula **não aparece**. E o balanço:
  **55% do ativo e 59% do passivo do DIRR3 caem em dois baldes "Outros ativos" e "Outros
  passivos"** (R$ 7,2 bi e R$ 7,9 bi) — mais da metade do BP **não bate linha a linha com
  a CVM/RI**. DFC "simplificado". Sem aba de FCFE.
- **Arquivos demais construídos antes do núcleo:** **54 módulos** em `src/`, **30 testes**,
  **9 documentos .md** na raiz. O maior inchaço é `src/visualizacao` com **15 módulos**
  (football field, tornado, waterfall, 3 de sensibilidade, heatmaps, dashboard, comparação,
  roic/roiic…). Comparáveis com yfinance ao vivo, watchlist, exportador de BI, cenários —
  tudo periférico, feito **antes** de fechar o Excel dos 3 demonstrativos.
- **Front-end (`app.py`):** **8 seções** (abas demais). Premissas editáveis hoje só:
  crescimento, **margem EBITDA** (não margem bruta/SG&A/alíquota/WACC), capex/receita.

**Conclusão que guia a Semana 9.0:** cortar a periferia do caminho crítico (Prompt
9.0.0), tornar o histórico 100% fiel à CVM (9.0.1), e construir o Excel `Modelo` de
verdade (9.0.5). O motor não se reescreve — se ajusta (9.0.2) e se apresenta.

### 0.2 O benchmark desta semana: o Excel REAL da Direcional

O arquivo `referencias/modelos_excel/Direcional_DIRR3_referencia.xlsx` (aba `Modelo`,
210×33, + aba `FCFF`) é o **piso de qualidade** do Excel final. **Leia o próprio arquivo
via openpyxl**, não só o `ESTRUTURA_DIRECIONAL.md` (que é um resumo). Estrutura real da
aba `Modelo` (linhas aproximadas — confira no arquivo):

- **Premissas Operacionais** (L2-L14, hard-coded em azul): crescimento, deduções %RB,
  margem bruta %RL, despesas comerciais %RL, G&A %RL, outras %RL, alíquota efetiva,
  equivalência %RL, payout %LL, minoritários %LL, IR/CS %RL.
- **DRE** (L15-L43): Receita Bruta → (−)Deduções → Receita Líquida → (−)CMV →
  **Lucro Bruto** → (−)Desp. Comerciais → (−)G&A → (+/−)Outras → (+)Equivalência →
  **(−)Depreciação [linha própria, = schedule PP&E]** → **EBIT ex-Depreciação** →
  **EBIT** → Margem EBIT → (+/−)Resultado Financeiro → EBT → (−)IR/CS → LL antes SPEs →
  (−)Minoritários → **Lucro Líquido** → Margem Líquida → #Ações → LPA.
- **Balanço Patrimonial** (L47-L122): ATIVO CIRCULANTE (caixa via fluxo; contas a
  receber, estoques, tributos a recuperar via WK; residuais `=F51` constantes) + ATIVO
  NÃO CIRCULANTE (realizável LP; imobilizado via schedule; intangível) + PASSIVO
  CIRCULANTE (empréstimos, fornecedores, **obrigações trab.+trib. via WK**, adiantamento
  de clientes via WK, arrendamento) + PASSIVO NÃO CIRCULANTE + PATRIMÔNIO LÍQUIDO
  (reservas de lucros = anterior + LL − dividendos) → TOTAL → **linha CHECK booleana**
  `IF(ROUND(ativo)=ROUND(passivo+PL),TRUE,FALSE)` (L122).
- **DFC** (L123-L139): LL + D&A − ΔWK = FCO; − CAPEX = FCI; − Dividendos + ΔDívida =
  FCFin; Caixa BoP + Variação = **Caixa EoP** (amarrado ao BP).
- **Capital de Giro** (L142-L180): WK = Ativos − Passivos, cada conta = **dias × driver
  / 365** (contas a receber = dias de RL; estoques = dias de CMV; **impostos a recuperar
  = dias de IR/CS**; fornecedores = dias de CMV; adiantamento clientes = dias de RL;
  **obrigações trab.+trib. = dias de SG&A**), dias = média histórica.
- **Dívida** (L181-L191): BoP + Captação − Amortização = EoP; Custo da Dívida (= CDI da
  Macro + spread); Despesa Financeira = BoP × −custo.
- **PP&E** (L196-L203): BoP + **CAPEX (= capex% × Receita)** − **D&A (= D&A% × PP&E
  BoP)** = EoP; **D&A % do PP&E** e **Capex % da Receita** = médias históricas.
- **Receita Financeira** (L206-L210): taxa × (caixa+aplicações BoP); CDI da Macro.

Aba `FCFF`: `NOPAT = EBIT×(1−T)` + D&A − ΔWK − CAPEX = **FCFF** → VP por ano → EV → −
Dívida Líquida → Equity → /ações → **Target Price** → Upside; build-up de Ke (CAPM
Brasil) e WACC; Data Table de sensibilidade.

### 0.3 O que a Semana 9.0 entrega (essencial → precede tudo)

0. **Enxugar:** tirar a periferia (15 módulos de gráfico, comparáveis/tornado/football
   field/BI/watchlist) do caminho crítico e do app, reduzindo o projeto ao núcleo:
   coleta fiel → motor → Excel dos 3 demonstrativos + FCFF/FCFE (Prompt 9.0.0).
1. **Histórico dos 3 demonstrativos batendo EXATAMENTE com a CVM** — acabar com os baldes
   "outros" que hoje engolem 55%+ do balanço (Prompt 9.0.1).
2. **Motor "padrão Direcional":** DRE com margens pré-D&A, **D&A = %PP&E**, **CAPEX =
   %receita**, alíquota anual, WACC como input direto opcional; **WK expandido** (contas
   a receber, estoques, fornecedores, **obrigações sociais/trabalhistas**, **impostos a
   recuperar**); DFC indireto completo; BP aberto com check (Prompt 9.0.2).
3. **FCFF e FCFE** sobre o novo motor + macro anual (retornos = opcional) (Prompt 9.0.3).
4. **Front-end guiado enxuto** (4 etapas, sem as 8 abas soltas) com as 6 premissas de
   Lucas (Prompt 9.0.4).
5. **Excel "Modelo" ≥ Direcional** (de 40 → ~200 linhas) com histórico=azul /
   premissa=verde / fórmula=preto, fórmulas nativas reproduzindo o motor, **FCFF e FCFE
   em abas separadas** (Prompt 9.0.5).

### 0.4 O que fica DE FORA da Semana 9.0

1. **Unit economics / build-up de receita** (VGV×POC, academias×ticket, coortes): v3.0.
   A receita é crescimento % anual; a função `projetar_receita` fica plugável.
2. **Excel bancário completo:** bancos seguem o caminho atual (aviso no app). O Excel
   "Modelo" desta semana é para **não-financeiras**.
3. **BI/Power BI/PDF/orquestração em lote; colunas trimestrais; conversão de moeda de
   instrumentos:** backlog v2.2 (Apêndice C).
4. **Semana 10+:** não planejar aqui.

---

## Princípios invariantes (valem para TODOS os prompts — releia sempre)

1. **Idioma do código:** funções, variáveis e comentários em **português**.
2. **Fonte única nos nomes:** toda coluna/campo novo registrado em
   `config/mapeamento_cvm.json`. O mesmo nome da coleta à exportação.
3. **Fonte única no cálculo:** o motor Python calcula UMA vez; Streamlit/Excel apenas
   apresentam. Zero recálculo em JS/DAX. No Excel, as fórmulas nativas devem REPRODUZIR
   o valor persistido (mecanismo `escrever_calculo`: se a fórmula não bate com o motor,
   grava o valor do motor + comentário).
4. **Sinais:** despesas/saídas negativas; receitas/entradas positivas.
5. **8 valores individuais** por vetor de premissa (`_ano1..8`). Nunca taxa única
   replicada. (Isso vale para crescimento, margem bruta, SG&A%, alíquota, etc.)
6. **Negativos são válidos** (ROIC/FCFF/LL). Não travar.
7. **Robustez CVM:** campo ausente/renomeado → log em `logs/`, fallback documentado,
   nunca quebra silenciosa. **Ausência de uma conta (ex.: leasing) NÃO é erro** — o
   schedule zera e some das saídas.
8. **Qualidade por etapa:** docstrings, comentário com a fórmula financeira, `black`
   (`--workers 1`) e `flake8` limpos, `pytest` verde ANTES de fechar o prompt. Validação
   SEMPRE com a venv: `.venv/Scripts/python.exe -m pytest tests -q`.
9. **Configuração, não hard-code:** o que varia por setor/empresa vive em
   `config/*.json` ou nas premissas.
10. **Continuidade:** ao final de cada prompt, atualizar a Seção 8 do `CONTEXT.md`
    (sessão datada) e registrar decisões autônomas em `Humano_revisar.md`.
11. **Cores do Excel (convenção de Lucas — PRECEDÊNCIA):** **histórico = azul
    (`FF0000FF`)**, **premissa que o usuário escolhe = verde (`FF008000`)**, **fórmula =
    preto**. Legenda na Capa. (Difere do WSP; é intencional.)
12. **Design institucional do app:** paleta navy (`#0A1628`/`#0F1E33`/`#1B4F8C`), verde
    `#16A34A` = upside / vermelho `#DC2626` = downside, texto sans, números mono.
13. **Regressão dourada EXPLICADA:** DIRR3, MGLU3 e SMFT3 rodam antes/depois de cada
    prompt. Mudança de Target Price é aceitável SOMENTE se quantificada e explicada por
    driver (padrão D-022) no `CONTEXT.md` + `Humano_revisar.md`. Mudança inexplicada =
    bug. (Nesta semana, várias mudanças de Target são ESPERADAS — o motor muda de
    paradigma; cada uma deve ser explicada.)
14. **Compatibilidade de premissas:** todo campo novo de premissa é OPCIONAL. Arquivo
    antigo continua rodando: campo ausente → o gerador deriva default da âncora
    histórica (grava a origem em `origem_premissas`) ou o motor cai no comportamento
    anterior com aviso — nunca KeyError.
15. **Consulte as referências (IMUTÁVEIS):** antes de implementar qualquer mecânica, leia
    o **arquivo Excel real** correspondente (`Direcional_DIRR3_referencia.xlsx` via
    openpyxl) e o mapa em `referencias/modelos_excel/`. Não editar os arquivos de
    `referencias/`.

---
---

# PROMPT 9.0.0 — Enxugamento: reduzir o projeto ao núcleo (coleta → motor → Excel dos 3 demonstrativos)

## Papel e contexto

Você é o **Claude Fable 5**. Antes de construir qualquer coisa nova, **corte a gordura**.
O projeto tem 54 módulos em `src/`, 30 testes e 9 documentos `.md` na raiz; boa parte foi
construída como periferia (gráficos, comparáveis, BI, watchlist) ANTES do núcleo — e o
núcleo (um Excel DCF fiel à CVM) é a parte mais fraca. Leia `CONTEXT.md`, `app.py`, a
árvore de `src/`, e a Seção 0.1 acima. Esta é a **primeira etapa da Semana 9.0**.

## Objetivo

Deixar o repositório com **um caminho crítico claro e curto**: coleta CVM → motor
(3 demonstrativos + FCFF/FCFE) → Excel `Modelo` + app enxuto. Nada é **apagado** sem
ordem do humano; o que sai do núcleo é **congelado** (movido para fora do caminho crítico,
marcado como não-mantido, removido do app e do Excel), de forma reversível.

## Especificação técnica detalhada

### 9.0.0.1 Definir o NÚCLEO (o que fica e é mantido)

- **Coleta:** `coletor_cvm`, `mapeador_contas`, `classificador_empresa`, `resolvedor_ticker`,
  `coletor_macro`, `coletor_mercado`, `limpeza`, `relatorio_qualidade` + o novo
  `auditor_cvm` (9.0.1).
- **Métricas:** `metricas_historicas` (âncoras das premissas), `qualidade_lucro`.
- **Projeção:** `projetor_dre`, `schedule_ppe`, `schedule_wk`, `schedule_divida`,
  `schedule_leasing`, `dfc_indireto` (novo), `gerador_premissas`, `projetor_financeiro`.
- **Valuation:** `calculador_fcff`, `calculador_fcfe`, `calculador_wacc`, `calculador_vt`,
  `calculador_ev`, `checklist`.
- **Exportação:** `exportador_excel` (reescrito no 9.0.5).
- **App:** `app.py` reduzido ao fluxo guiado (9.0.4).

### 9.0.0.2 Congelar a periferia (o que sai do caminho crítico)

- **`src/visualizacao/` (15 módulos):** manter só o mínimo que o Excel/app do núcleo
  usa (se algum). Football field, tornado, waterfall, heatmaps de sensibilidade,
  comparação de empresas, dashboard, roic/roiic PNG, tabela de comparáveis → mover para
  `src/_congelado/visualizacao/` (ou marcar no topo do arquivo: `# CONGELADO v2.1 — fora
  do núcleo; ver Prompt 9.0.0`) e **remover as chamadas** no `app.py` e no
  `exportador_excel`.
- **Comparáveis (`comparaveis.py`, `tabela_comparaveis.py`), watchlist, `motor_cenarios`,
  `exportador_bi.py`, `calculador_retornos` (se não for usado no Excel):** congelar do
  mesmo jeito. Cenários Bear/Base/Bull podem ficar como um bloco simples no motor, mas
  **saem do caminho crítico do Excel**.
- Cada módulo congelado: remover do `import` dos orquestradores (`pipeline.py`, `main.py`,
  `verificar_semana*.py`), mas **manter os testes correspondentes** rodando (ou marcá-los
  `@pytest.mark.skip(reason="congelado 9.0.0")`) para não quebrar a suíte. Registrar a
  lista exata do que foi congelado em `Humano_revisar.md`.

### 9.0.0.3 Enxugar a documentação

- Consolidar os `.md` da raiz: manter `README.md`, `CONTEXT.md`, `CLAUDE.md`,
  `PROMPTS_FABLE.md`, `Humano_revisar.md`. Mover `ROTEIRO.md`, `Roteiro DCF - Copia.md`,
  `CHANGELOG.md`, `CONTRIBUTING.md` para `docs/` (ou marcar como histórico). **Apagar
  `Roteiro DCF - Copia.md`** (é cópia duplicada — confirmar que não é referenciado).

### 9.0.0.4 Pipeline enxuto

- `pipeline.py` e `main.py` passam a ter um caminho principal curto: coleta → motor →
  Excel, com as etapas periféricas removidas ou atrás de flags opcionais desligadas por
  default (`--com-comparaveis`, `--com-graficos`). O fluxo default entrega o Excel.

## Contratos de interface

- Nenhuma mudança de fórmula/valuation (Target Price INALTERADO).
- Nada apagado sem registro; o que sai vira `_congelado/` reversível.

## Definição de Pronto (DoD)

- `git status` mostra a periferia movida/marcada; `pipeline.py`/`main.py`/`app.py`
  importam só o núcleo; o pipeline default roda DIRR3 e gera o Excel **sem** os passos
  periféricos.
- **Regressão dourada:** DIRR3/MGLU3/SMFT3 com Target Price idêntico (nada de cálculo
  mudou).
- `pytest tests -q` verde (testes de módulos congelados marcados skip com motivo);
  `black --workers 1`/`flake8` limpos.
- `Humano_revisar.md` lista exatamente o que foi congelado e onde, para o humano decidir
  depois se apaga de vez.

## O que NÃO fazer

- NÃO apagar módulos definitivamente (só congelar) sem ordem explícita do humano.
- NÃO tocar no motor de cálculo nem no valuation aqui.
- NÃO remover testes — marcá-los skip com motivo, para a suíte seguir verde.

## Ao final

`CONTEXT.md` (sessão datada — Semana 9.0, Prompt 9.0.0) + `Humano_revisar.md` (lista do
congelado). Próxima tarefa: Prompt 9.0.1.

---
---

# PROMPT 9.0.1 — Fidelidade à CVM: BP, DRE e DFC históricos batem EXATAMENTE com DFP/ITR

## Papel e contexto

Você é o **Claude Fable 5**, IA de implementação do **DCF Automatizado**. Antes de
escrever qualquer linha, leia: `CONTEXT.md` (Seção 8), `CLAUDE.md`, os Princípios
Invariantes e a Regra de Precedência acima, `src/coleta/coletor_cvm.py`,
`src/coleta/mapeador_contas.py`, `src/processamento/limpeza.py`,
`config/mapeamento_cvm.json`, e a aba `Modelo` do
`referencias/modelos_excel/Direcional_DIRR3_referencia.xlsx` (linhas do BP L47-L122).
Esta é a **primeira e mais importante etapa da Semana 9.0**.

## Objetivo

Garantir que **todo dado histórico dos três demonstrativos (Balanço Patrimonial, DRE e
DFC) que o sistema persiste e vai mostrar no Excel bate, linha a linha, com o que a
empresa divulgou na CVM (DFP anual / ITR)**. **Estado atual medido (17/07/2026):** no
DIRR3, **55% do ativo e 59% do passivo caem em `outros_ativos`/`outros_passivos`** (R$ 7,2
bi e R$ 7,9 bi jogados em baldes anônimos). Isso torna o balanço do Excel **incomparável
com o RI da empresa** — e é o problema nº 1 a resolver. **Meta desta etapa: residual < 5%
do total do ativo/passivo em cada empresa do lote.** Este prompt NÃO projeta nada novo:
ele **audita e amplia a fidelidade da base histórica** que alimenta tudo depois.

## Especificação técnica detalhada

### 9.0.1.1 Ampliar a cobertura do mapeamento (`config/mapeamento_cvm.json`)

- Mapear as contas do BP que o Direcional abre e que hoje caem em residual, quando
  existirem na DFP (por `CD_CONTA`, com fallback por `DS_CONTA` normalizado):
  **tributos/impostos a recuperar** (1.01.06.x ativo circulante; 1.02.01.x LP),
  **obrigações sociais e trabalhistas** (2.01.01.x), **obrigações fiscais/tributárias**
  (2.01.03.x), **adiantamento de clientes** (quando houver), **provisões** (2.01.04/
  2.02.03), **partes relacionadas**, **dividendos a pagar**, **realizável a longo prazo**
  e **investimentos**. Cada nome novo entra no catálogo `campos` com descrição e sinal.
- Contas que legitimamente não têm mapeamento próprio continuam agregadas, mas o
  **residual passa a ser uma linha EXPLÍCITA e pequena** (`outros_ativos_circulantes`,
  `outros_ativos_nao_circulantes`, `outros_passivos_circulantes`,
  `outros_passivos_nao_circulantes`), não um "buraco" grande. Log de quanto sobrou em
  cada residual.

### 9.0.1.2 Auditor de amarração histórica (`src/coleta/auditor_cvm.py`, novo)

Para um ticker, valida a base histórica JÁ coletada contra a própria CVM (sem rede — usa
os JSONs de `data/raw/cvm/`) e persiste `data/raw/cvm/<TICKER>_auditoria_cvm.json`:

1. **Balanço fecha no histórico:** para cada exercício, `Ativo Total ≈ Passivo Total +
   PL` (tolerância R$ mil / 1e-4 relativa). Se a CVM traz `1` (Ativo) e `2` (Passivo+PL)
   como totais oficiais, conferir contra a SOMA das contas mapeadas + residuais.
2. **Subtotais batem:** Ativo Circulante = Σ contas circulantes; idem não circulante;
   Receita Líquida = Receita Bruta − Deduções (quando a DVA traz a bruta); Lucro Bruto =
   RL − CPV; etc. Cada identidade vira um item OK/ERRO no relatório.
3. **DFC amarra:** Caixa final do DFC ≈ Caixa do BP do mesmo exercício; FCO+FCI+FCF ≈
   variação de caixa.
4. **Cobertura de mapeamento:** % do Ativo/Passivo total que caiu em residual (meta:
   residual < 5% do total; acima disso, aviso apontando as maiores contas não mapeadas
   de `logs/contas_cvm_nao_mapeadas.log`).
5. **Escala e sinais:** confere `ESCALA_MOEDA` (R$ mil) uniforme e a convenção de sinais
   (despesas negativas). Qualquer conta com sinal fora do esperado vira aviso.

O auditor **nunca derruba o pipeline** — reporta OK/AVISO/ERRO e persiste. Um modo
`--estrito` (opcional) faz `raise` no primeiro ERRO para uso em CI.

### 9.0.1.3 Base histórica como fonte única do Excel

- Garantir que a série histórica que o Excel vai mostrar (3-5 exercícios) vem
  **diretamente** dos JSONs da CVM via `montar_series_anuais`, com os nomes padronizados,
  e que cada linha do BP/DRE/DFC do Excel tem correspondência 1:1 com uma conta CVM (ou
  um residual explícito). Sem números "inventados" na coluna histórica.

## Contratos de interface

- `config/mapeamento_cvm.json`: +N campos (contas do BP/obrigações/impostos).
- `data/raw/cvm/<TICKER>_auditoria_cvm.json`: novo bloco de auditoria.
- Nenhuma mudança em projeção/valuation neste prompt (Target Price INALTERADO).

## Definição de Pronto (DoD)

- `python -m src.coleta.auditor_cvm --ticker DIRR3` (e MGLU3, SMFT3, VALE3, WEGE3) →
  balanço histórico fecha em todos os exercícios; **residual < 5% do ativo** (DIRR3 sai
  dos 55%/59% de hoje para < 5% — critério objetivo de aceite); DFC amarra ao caixa do BP.
- Conferência manual pontual: abrir a DFP/ITR de 1 empresa no site da CVM/RI e bater 5-6
  linhas do BP contra o que o sistema persiste (documentar no `CONTEXT.md`).
- **Regressão dourada:** DIRR3/MGLU3/SMFT3 com Target Price **idêntico** ao de antes do
  prompt (este prompt não toca o motor de projeção; se mudar, é bug — investigar).
- `pytest tests -q` verde; `black --workers 1`/`flake8` limpos.

## Testes e validação

- `tests/test_auditor_cvm.py` (novo, fixtures sintéticas): balanço que fecha → OK;
  balanço com furo → ERRO apontando a diferença; residual grande → aviso; DFC que não
  amarra → ERRO.
- `tests/test_mapeador_contas.py` estendido: contas novas (impostos a recuperar,
  obrigações trabalhistas) mapeadas por `CD_CONTA`; conta desconhecida → residual +
  log.

## O que NÃO fazer

- NÃO mudar nenhuma fórmula de projeção/valuation (isso é 9.0.2+).
- NÃO "consertar" um furo da CVM inventando número — se a DFP não fecha, reportar (o
  problema é do dado, e o auditor tem que expor isso).

## Ao final

`CONTEXT.md` (sessão datada — Semana 9.0, Prompt 9.0.1) + `Humano_revisar.md`. Próxima
tarefa: Prompt 9.0.2.

---
---

# PROMPT 9.0.2 — Motor "padrão Direcional": DRE pré-D&A, D&A=%PP&E, CAPEX=%receita, WK expandido, DFC indireto, BP aberto

## Papel e contexto

Você é o **Claude Fable 5**. O Prompt 9.0.1 garantiu a fidelidade do histórico. Leia
`CONTEXT.md`, `src/projecao/projetor_dre.py`, `src/projecao/schedule_ppe.py`,
`src/projecao/schedule_wk.py`, `src/projecao/schedule_divida.py`,
`src/projecao/schedule_leasing.py`, `config/parametros.json`, e a aba `Modelo` do Excel
da Direcional (DRE L15-L43; BP L47-L122; DFC L123-L139; WK L142-L180; Dívida L181-L191;
PP&E L196-L203). Esta é a **etapa mais densa da Semana 9.0** — se precisar, divida em
duas sessões (9.0.2a motor da DRE/PP&E/WK; 9.0.2b DFC indireto + BP aberto), fechando o
DoD completo ao final.

## Objetivo

Reescrever o motor de projeção das não-financeiras para reproduzir a mecânica da aba
`Modelo` da Direcional, com **as instruções atuais de Lucas** (Regra de Precedência):

1. **DRE com margens PRÉ-D&A** e **D&A como linha própria** (fim da dupla contagem).
2. **D&A = % do PP&E de abertura** e **CAPEX = % da receita líquida** (modelo simples).
3. **Alíquota de impostos ANUAL** (vetor de 8 valores).
4. **WK expandido** com as contas que Lucas citou.
5. **DFC indireto completo** + **BP aberto linha a linha** com **check visível**.

### 9.0.2.1 DRE pré-D&A (`projetor_dre.py`) — a mudança de paradigma

Reescrever o **modo completo** para a cascata da Direcional (`Modelo` L17-L39):

```
Receita Bruta            = Receita Líquida / (1 − deduções%)
(−) Deduções             = deduções% × Receita Bruta
(=) Receita Líquida      [projetada por crescimento % anual]
(−) CPV                  = Receita Líquida × (1 − margem_bruta)
(=) Lucro Bruto          = Receita Líquida × margem_bruta
(−) SG&A                 = sgna% × Receita Líquida          [comerciais + G&A]
(+/−) Outras op.         = outras% × Receita Líquida
(+) Equivalência         = equiv% × Receita Líquida
(=) EBIT ex-Depreciação                                     [nível EBITDA]
(−) Depreciação & Amort. = schedule PP&E + direito de uso   [LINHA PRÓPRIA]
(=) EBIT
(+/−) Resultado Financ.  = schedule de dívida (juros + juros arrendamento + rec. fin.)
(=) EBT
(−) IR/CS                = alíquota_ano_t × EBT  (ou RET × Receita Bruta p/ construtora)
(=) LL antes de minoritários
(−) Minoritários         = minoritarios% × LL                [nova linha — ver 9.0.2.6]
(=) Lucro Líquido
Memo: EBITDA = EBIT ex-Depreciação = Lucro Bruto − SG&A + Outras + Equivalência
```

- **`margem_bruta` e `sgna_pct_receita` passam a ser margens de nível EBITDA** (pré-D&A):
  o EBIT ex-Depreciação sai delas, e a D&A é subtraída DEPOIS. **A D&A NÃO está mais
  embutida em CPV/SG&A.** Isso é o oposto do que o antigo 8.1 assumia — está correto e é
  o que a Direcional faz (`Modelo` L28-L30). Atualizar as docstrings deixando isso
  explícito.
- **Alíquota anual:** novo vetor opcional `aliquota_ir_ano1..8` (default: interpolação da
  `aliquota_efetiva` histórica com clamp [15%, 45%]; construtora RET ignora e usa 4%
  sobre a Receita Bruta projetada). O escalar `modo_aliquota` continua aceito
  (retrocompat); se o vetor anual existir, ele vence.
- **Modo legado** (arquivo só com `margem_ebitda`) continua funcionando byte a byte para
  não quebrar bancos/testes antigos; mas o **gerador passa a gerar sempre o conjunto
  completo pré-D&A**, então DIRR3/MGLU3/SMFT3 rodam no modo novo.

### 9.0.2.2 D&A = %PP&E e CAPEX = %receita (`schedule_ppe.py`)

- Manter o modelo simples atual: `CAPEX_t = capex_receita_ano_t × Receita_t`;
  `D&A_t = (1/vida_util) × PP&E_abertura_t` (com `MIN(quota, base)` para não depreciar
  abaixo de zero). `PP&E_t = PP&E_(t-1) + |CAPEX_t| − D&A_t`.
- **Vida útil = default global da config** (`vida_util_ppe_anos`), sobrescrevível por
  premissa `vida_util_ppe_anos` da empresa e por subtipo em `config/setores.json`.
  Persistir a `D&A%_historica` (imob/D&A do Ano 0) como INFORMAÇÃO exibível (a Direcional
  mostra "D&A % do PP&E = média histórica" na L202), mas a taxa USADA é a da config/
  premissa (decisão D-047 — não derivar a vida do histórico).
- **Intangível:** amortização simples opcional (linear sobre o saldo do Ano 0, mesma
  vida) OU constante — seguir o comportamento atual pós-reversão (constante), exibindo a
  linha própria no BP. Documentar a escolha.
- **D&A da DRE = imobilizado + intangível + direito de uso** (o leasing reclassifica sua
  parcela, sem mudar o total — mecânica atual do 8.2 preservada).

### 9.0.2.3 WK expandido (`schedule_wk.py`) — as contas que Lucas pediu

Novo modo `dias_multi_driver` (default para não-construtoras quando houver histórico),
reproduzindo a Direcional (`Modelo` L144-L180). Cada conta = `dias × driver / 365`, com
`dias` default = média histórica implícita (premissa opcional sobrescreve):

| Conta do WK | Driver | Premissa (dias) |
|---|---|---|
| Contas a receber | Receita Líquida | `dias_clientes` |
| Estoques | CPV | `dias_estoques` |
| **Impostos/tributos a recuperar** | IR/CS (ou Receita Líquida se não houver) | `dias_impostos_recuperar` |
| Fornecedores | CPV | `dias_fornecedores` |
| **Obrigações sociais e trabalhistas** | SG&A | `dias_obrigacoes_trabalhistas` |
| (opcional) Adiantamento de clientes | Receita Líquida | `dias_adiantamento_clientes` |

- **NWC = ativos de giro − passivos de giro** = (contas a receber + estoques + impostos a
  recuperar) − (fornecedores + obrigações sociais/trabalhistas + adiantamentos). ΔNWC
  mantém a definição persistida (consumo de caixa = −ΔNWC no FCF).
- Contas ausentes na CVM → dias 0 + aviso (Princípio 7). Os modos `dias` (DSO/DIO/DPO) e
  `percentual_receita` (construtoras ancoradas) **continuam disponíveis**;
  `modo_capital_giro` escolhe (default do subtipo em `config/setores.json`).
- Registrar todos os campos novos no mapeamento.

### 9.0.2.4 Dívida (`schedule_divida.py`) — rolagem + captação automática v2

- Manter a mecânica v2: dívida BoP + captação − amortização = EoP; juros = Kd × saldo de
  abertura (D-015); captação automática para o caixa mínimo
  (`caixa_minimo_pct_receita`); receita financeira sobre o caixa. **SEM revolver formal.**
- **Tabela opcional de instrumentos** nas premissas (`instrumentos_divida`: saldo BRL,
  taxa, indexador textual, ano de vencimento, curva de amortização por ano). Sem a tabela
  → perfil CP/LP agregado atual. Moeda estrangeira: saldo informado já em BRL (conversão
  = backlog).

### 9.0.2.5 DFC indireto completo + BP aberto (`src/projecao/dfc_indireto.py`, novo; balanço)

- **DFC indireto** reconciliando o BP (padrão Direcional `Modelo` L123-L139, ordem):
  `LL + D&A − ΔWK (uma linha por conta do WK) = FCO`; `− CAPEX (imob + intangível) =
  FCI`; `− Dividendos + Δ Empréstimos (captações − amortizações) = FCFin`; `Caixa BoP +
  (FCO+FCI+FCFin) = Caixa EoP`. **Caixa EoP = caixa do BP** (continua a origem do caixa).
- **BP aberto linha a linha:** o bloco `balanco` persiste a abertura completa (caixa,
  aplicações, contas a receber, impostos a recuperar, estoques, outros CP; realizável LP,
  imobilizado, intangível, direito de uso, outros LP; fornecedores, obrigações
  trabalhistas, obrigações fiscais, empréstimos CP/LP, arrendamento CP/LP, adiantamentos,
  outros; PL evoluindo com LL − dividendos), cada residual **constante e explícito**
  (vindo do BP REAL do Ano 0). Campo `verificacao_balanco` por ano (diferença absoluta) —
  o Excel do 9.0.5 exibirá a linha **Check** como a Direcional (L122).
- Manter o `dfc` atual como `dfc_simplificado` até o 9.0.5 migrar os consumidores; depois
  remover.

### 9.0.2.6 Minoritários na DRE + LPA

- Nova linha `participacao_minoritarios` = `minoritarios_pct_ll × LL` (premissa escalar
  default = 0; âncora histórica quando houver). LL final = LL antes de minoritários −
  minoritários. `lpa` = LL / ações fully diluted. (Direcional `Modelo` L13/L38/L43.)

## Contratos de interface

- Blocos: `dre` (pré-D&A, minoritários, LPA, alíquota anual), `ppe` (D&A%PP&E),
  `wk` (multi-driver com contas novas), `divida` (instrumentos opcionais), `dfc` (indireto
  novo) + `dfc_simplificado` (legado temporário), `balanco` (aberto com check). Todos os
  nomes no mapeamento.
- **FCFF não muda de DEFINIÇÃO** (`NOPAT + D&A − ΔWK − CAPEX`), mas os componentes mudam
  de valor (nova DRE) — a regressão dourada será re-explicada.

## Definição de Pronto (DoD)

- DIRR3, MGLU3, SMFT3, VALE3, WEGE3 rodam ponta a ponta: DRE pré-D&A coerente (EBITDA =
  EBIT + D&A; margem bruta bate); DFC indireto fecha (variação de caixa = Δ caixa do BP,
  dif < 1e-6); **balanço fecha nos 8 anos** (check TRUE); WK com as contas novas.
- **Regressão dourada EXPLICADA por driver** (padrão D-022): o Target de DIRR3/MGLU3/
  SMFT3 muda (paradigma pré-D&A + D&A%PP&E + WK expandido) — quantificar cada driver.
  **Importante:** com margens pré-D&A, o SMFT3 NÃO deve mais colapsar (o descasamento
  D&A×margens some) — se colapsar, é bug.
- `pytest tests -q` verde; `black`/`flake8` limpos; `python -m src.verificar_semana3` OK.

## Testes e validação

- `tests/test_projetor_dre.py`: cascata pré-D&A (EBIT ex-D&A das margens; EBIT = ex-D&A −
  D&A; EBITDA = EBIT + D&A); alíquota anual vence o escalar; minoritários e LPA; modo
  legado intocado.
- `tests/test_schedule_wk.py`: modo multi-driver com as 5+ contas; drivers corretos
  (impostos a recuperar por IR/CS; obrigações trab. por SG&A); modos antigos preservados.
- `tests/test_dfc_indireto.py` (novo): cada bloco reconcilia; caixa EoP = caixa BP.
- `tests/test_balanco_aberto.py` (novo): abertura soma ao total; check ≈ 0.

## O que NÃO fazer

- NÃO reintroduzir D&A por safra nem embutir D&A nas margens (Regra de Precedência 1-2).
- NÃO mexer no front-end/Excel (Prompts 9.0.4/9.0.5). NÃO tocar em bancos.
- NÃO remover o `dfc_simplificado` ainda (consumidores migram no 9.0.5).

## Ao final

`CONTEXT.md` + `Humano_revisar.md` (registrar o re-baseline do golden triplo). Próxima
tarefa: Prompt 9.0.3.

---
---

# PROMPT 9.0.3 — FCFF + FCFE sobre o novo motor, macro anual e painel de Retornos

## Papel e contexto

Você é o **Claude Fable 5**. O motor "padrão Direcional" está pronto (9.0.2). Leia
`CONTEXT.md`, `src/valuation/calculador_fcff.py`, `src/valuation/calculador_fcfe.py`,
`src/valuation/calculador_ev.py`, `src/coleta/coletor_macro.py`, e a aba `FCFF` do Excel
da Direcional. Esta é a **terceira etapa da Semana 9.0**.

## Objetivo

Fechar a camada de valuation sobre o novo motor: **FCFF e FCFE** ambos gerados para
não-financeiras (o Excel do 9.0.5 mostra os dois "ao final do modelo"), um **bloco macro
anual** que alimenta CDI/inflação, e o **painel de Retornos** (TIR/MOIC/múltiplos).

### 9.0.3.1 FCFF e FCFE para não-financeiras (`calculador_fcff.py` / novo `fcfe_naofinanceira`)

- **FCFF** (já existe): `NOPAT + D&A − ΔWK − CAPEX`, agora sobre a DRE pré-D&A. Confirmar
  ROIC/ROIIC por ano.
- **FCFE para não-financeiras** (novo): `FCFE_t = FCFF_t − (juros_dívida_t +
  juros_arrendamento_t) × (1 − alíquota_t) + Δdívida_líquida_t` (captações − amortizações,
  incluindo a captação automática v2), equivalente a `LL + D&A − ΔWK − CAPEX + Δdívida`.
  Descontar ao **Ke** (CAPM Brasil, já existe) → Equity Value direto; conferir contra o
  Equity do bridge FCFF/WACC (devem ser próximos; divergência = aviso, não erro).
  Persistir bloco `fcfe` (paralelo ao `fcff`) para o Excel mostrar os dois.

### 9.0.3.2 Macro anual (`coletor_macro.py`)

- Além de Selic/IPCA/Focus: **CDI** (SGS 4389; fallback Selic−0,1pp), **IGP-M**, **câmbio
  BRL/USD**. Bloco `macro_anual` (ano1..8) persistido: IPCA/Selic/CDI/PIB esperados
  (Focus onde cobre; convergência linear para metas de `config/parametros.json` além do
  horizonte). O motor LÊ o CDI daqui (receita financeira e custo da dívida = CDI + spread,
  como a Direcional `Modelo` L190). Sem rede → usa o persistido.

### 9.0.3.3 Painel de Retornos (`src/valuation/calculador_retornos.py`, novo)

- **Múltiplos implícitos por ano** (preço atual e target): EV/EBITDA, EV/Receita, P/L.
- **TIR do acionista** (fluxo: −preço no ano 0; +dividendos/ação nos anos 1..N; +preço-
  alvo no ano N, default N=5) e **MOIC**. Grade Bear/Base/Bull (bloco `cenarios`).
- Persistir bloco `retornos`. Financeiras: P/L e P/VP (sem EV/EBITDA).

## Definição de Pronto (DoD)

- Blocos `fcfe` (não-financeira), `macro_anual` e `retornos` persistidos para DIRR3,
  MGLU3, SMFT3; FCFE ≈ Equity do bridge FCFF (divergência explicada); TIR > 0 quando
  target > preço.
- Regressão dourada: Target Price (bridge FCFF) **inalterado** vs 9.0.2 (nada aqui muda o
  FCFF; se o CDI vier do macro e antes era fallback, explicar a diferença na receita
  financeira).
- `pytest` verde; `black`/`flake8` limpos.

## Testes e validação

- `tests/test_calculador_fcfe.py` estendido: FCFE não-financeira de fixture fechada;
  reconciliação FCFE vs bridge FCFF.
- `tests/test_coletor_macro.py`: novas séries + convergência do `macro_anual`.
- `tests/test_calculador_retornos.py` (novo): TIR/MOIC de fluxo conhecido; múltiplos
  implícitos com denominadores do motor.

## O que NÃO fazer

- NÃO indexar custos ao IPCA automaticamente (premissas nominais). NÃO implementar cap
  table/diluição. NÃO redesenhar o app (é o 9.0.4).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. Próxima tarefa: Prompt 9.0.4.

---
---

# PROMPT 9.0.4 — Front-end guiado: escolher → premissas (as 6) → resultados ao vivo → exportar

## Papel e contexto

Você é o **Claude Fable 5**. O motor e o valuation estão prontos. Leia `CONTEXT.md`,
`app.py` inteiro, `tests/test_app.py`, e a lista de premissas de Lucas (abaixo). Esta é a
**quarta etapa da Semana 9.0**. Requisito direto de Lucas (17/07/2026): na página
inicial, buscar a empresa pelo ticker e em seguida digitar as premissas; ao mudar as
premissas, a projeção dos 3 demonstrativos, o DCF, FCFF e FCFE mudam corretamente.

## Objetivo

Reorganizar o app em um **fluxo guiado de 4 etapas** (sem perder capacidade existente):

```
① Escolher empresa   ② Premissas   ③ Resultados & ajustes ao vivo   ④ Exportar
```

### 9.0.4.1 Etapa ② — as 6 premissas de Lucas (o formulário essencial)

O editor de premissas das não-financeiras passa a expor, em grupos colapsáveis com a
âncora histórica ao lado (fonte verde = "você escolhe", coerente com a cor do Excel):

1. **Crescimento da Receita Líquida** — vetor ×8 (já existe).
2. **Margem Bruta** — vetor ×8 (nível EBITDA, pré-D&A). **Substitui o slider de Margem
   EBITDA** no fluxo das não-financeiras (o `margem_ebitda` vira derivado, só leitura).
3. **SG&A % da Receita Líquida** — vetor ×8.
4. **Alíquota de impostos** — vetor ×8 (construtora RET: campo travado com aviso "RET 4%
   sobre Receita Bruta").
5. **WACC** — **input direto opcional** (`wacc_manual`): se preenchido, o motor usa esse
   WACC; se vazio, usa o build-up CAPM atual (beta/ERP/CRP/Kd). Mostrar o WACC
   resultante ao lado.
6. **Outros** — capex%receita ×8, dias do WK (as contas novas), Kd, caixa mínimo, payout,
   g, minoritários%, vidas úteis, leasing (quando houver), instrumentos de dívida
   (tabela opcional).

- **Validação em tempo real** (regras atuais + novas): `g ≥ WACC` bloqueia; deduções
  0-40%; alíquota 0-45%; margem bruta coerente; curvas de amortização somando ≤ 100%.
- `Salvar e calcular` roda o motor oficial (`rodar_motor_valuation`) e remove a flag
  `premissas_automaticas`. **"Restaurar automáticas"** regenera do gerador (com
  confirmação).

### 9.0.4.2 Etapa ③ — Resultados & ajustes ao vivo

- Sub-abas (as 8 seções atuais + uma nova): Overview, Histórico, Valuation, Comparáveis,
  Retornos (9.0.3), Análise (tornado + sensibilidade viva), Comparar, e **Modelo** (NOVA:
  DRE/BP/DFC projetados + FCFF/FCFE em tabelas navegáveis, com a linha de verificação do
  balanço). Mudar premissa e salvar re-renderiza com os números novos.

### 9.0.4.3 Etapa ④ — Exportar

- Preview do Excel por aba + botão de download; status/data do arquivo; "Regerar Excel".
  (O conteúdo novo do Excel é do 9.0.5; aqui a etapa já funciona com o exportador.)

## Definição de Pronto (DoD)

- Fluxo completo no navegador com SMFT3: escolher → editar **margem bruta / SG&A /
  alíquota / WACC** → salvar → ver os 3 demonstrativos, FCFF e FCFE mudarem → baixar.
- Nenhuma funcionalidade perdida (cenários, comparar, watchlist, busca).
- `tests/test_app.py` verde (novos + antigos adaptados); `pytest` geral verde;
  `black`/`flake8` limpos.

## O que NÃO fazer

- NÃO recalcular valuation em JS (Princípio 3). NÃO expor o slider de Margem EBITDA como
  se ele afetasse a projeção no modo novo (ele é derivado). NÃO mexer no exportador
  (9.0.5).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. Próxima tarefa: Prompt 9.0.5.

---
---

# PROMPT 9.0.5 — Excel "Modelo" (≥ Direcional): histórico azul / premissa verde / fórmula preto + FCFF + FCFE

## Papel e contexto

Você é o **Claude Fable 5**. O motor persiste os 3 demonstrativos abertos + FCFF + FCFE,
e o app guia até "Exportar". Leia `CONTEXT.md`, `src/exportacao/exportador_excel.py`
(mecanismos `escrever_calculo`, `escrever_numero`, constantes `LINHA_*`, convenção de
cores), `tests/test_exportador_excel.py`, e — **obrigatório** — a aba `Modelo` e a aba
`FCFF` do `referencias/modelos_excel/Direcional_DIRR3_referencia.xlsx` via openpyxl. Esta
é a **etapa final da Semana 9.0 e o entregável mais visível**.

## Objetivo

Reescrever o exportador **do zero**. O Excel de hoje é o principal fracasso do projeto:
a aba "Modelo Integrado" tem **40 linhas** com a DRE ANTIGA (margem EBITDA) e o balanço
com 55%+ em "outros" — inutilizável. O novo Excel gera, para QUALQUER não-financeira, um
arquivo **no mínimo igual ao da Direcional** (aba `Modelo` de ~200 linhas), cuja peça
central é a aba **`Modelo`** (nome exato) com os 3 demonstrativos abertos, históricos +
projetados, e **FCFF e FCFE em abas SEPARADAS** (uma aba `FCFF` e uma aba `FCFE`), ambas
usando a aba `Modelo` como fonte. **Exceção ao Direcional:** a receita é projetada por
**crescimento % anual** (sem o build-up VGV×POC nem as abas de unit economics).

## Layout das abas (ordem fixa)

| # | Aba | Conteúdo | Referência |
|---|---|---|---|
| 1 | `Capa` | Título, empresa, ticker, data-base, data de geração, **legenda de cores** (Histórico=azul / Premissa=verde / Fórmula=preto), decisão (Target/Upside/Recomendação), disclaimer quando `premissas_automaticas` | — |
| 2 | `Premissas` | As 6 premissas de Lucas (vetores ×8 + escalares), **em verde** (input do usuário), âncora histórica ao lado, comentário de célula em cada uma | conv. de Lucas |
| 3 | **`Modelo`** | **DRE + BP aberto + DFC indireto + WK multi-driver + Dívida + PP&E**, histórico (azul) + 8 projetados (fórmulas pretas), **linha Check do balanço** (`IF(ROUND(ativo)=ROUND(passivo+PL),"Ok",dif)`), caixa BoP/EoP amarrado | Direcional `Modelo` |
| 4 | **`FCFF`** | Aba PRÓPRIA: `NOPAT = EBIT×(1−T)` + D&A − ΔWK − CAPEX → **FCFF** → VP por ano → EV → − Dívida Líquida → Equity → **Target (FCFF)** → Upside; build-up do **WACC** (Ke CAPM Brasil + Kd); múltiplos implícitos + TIR/MOIC (bloco `retornos`) | Direcional `FCFF` |
| 5 | **`FCFE`** | Aba PRÓPRIA: `LL + D&A − ΔWK − CAPEX + Δdívida líquida` → **FCFE** → VP ao **Ke** por ano → Equity Value direto → **Target (FCFE)** → Upside; build-up do Ke; nota de reconciliação FCFE × Equity do bridge FCFF | Damodaran FCFE |
| 6 | `Macro` | Bloco `macro_anual` + séries coletadas (histórico e projeção, fonte/data) | Direcional `Projeções Macro` |
| 7 | `Sensibilidades` | Tabelas de sensibilidade + grade Bear/Base/Bull | atual + `cenarios` |
| 8 | `Avisos` | Score de qualidade, checklist do motor (colorido), auditoria CVM (9.0.1), contas não mapeadas, fallbacks, flag de premissas automáticas | atual + auditor |

> **FCFF e FCFE ficam em abas SEPARADAS — uma aba para cada** (`FCFF` e `FCFE`), ambas
> referenciando a aba `Modelo` como fonte. O núcleo essencial (precedência) é: **`Modelo`
> (3 demonstrativos, ≥ Direcional) + `FCFF` + `FCFE` + `Premissas`**. As demais abas são
> suporte; se o tempo apertar, priorize o núcleo com qualidade total.

## Especificação técnica detalhada

### 9.0.5.1 A aba `Modelo` (espinha dorsal)

- Reproduzir a estrutura da Direcional `Modelo`: DRE (bruta→líquida→lucro bruto→SG&A→
  EBIT ex-D&A→**D&A linha própria**→EBIT→EBT→IR→minoritários→LL→LPA), BP aberto com
  subtotais (Ativo Circulante/Não Circulante/Total; Passivo Circulante/Não Circulante;
  PL), **linha Check** booleana, DFC indireto (FCO/FCI/FCFin, caixa BoP/EoP), blocos de
  WK (cada conta = dias × driver), Dívida (BoP/captação/amortização/EoP, custo da dívida =
  CDI+spread da aba Macro), PP&E (BoP/CAPEX/D&A/EoP, com "D&A % PP&E" e "Capex % Receita").
- **Colunas:** todos os exercícios históricos disponíveis na CVM (tipicamente 4-7) +
  `Ano 1..8` projetados.
- **Cores (Princípio 11 / convenção de Lucas):**
  - **AZUL** — toda célula de dado **histórico** (vinda da CVM).
  - **VERDE** — toda célula de **premissa** que o usuário escolhe (as linhas de premissa
    no topo dos blocos e na aba `Premissas`; no `Modelo`, as referências às premissas).
  - **PRETO** — todo **resultado de fórmula** nativa do Excel.
- **Fórmulas nativas reproduzindo o motor** (mecanismo `escrever_calculo`): cada célula
  projetada é uma fórmula que referencia as premissas e as linhas do próprio `Modelo`
  (ex.: `Lucro Bruto = Receita Líquida × Margem Bruta`; `D&A = −D&A% × PP&E BoP`;
  `EBIT = EBIT ex-D&A + D&A`). Se a fórmula não reproduzir o valor do motor (salvaguardas),
  grava o valor do motor + comentário. **Consistência horizontal:** a mesma fórmula
  estrutural em todas as colunas de projeção de uma linha.

### 9.0.5.2 As abas `FCFF` e `FCFE` (SEPARADAS — uma para cada)

- **Aba `FCFF`** referenciando o `Modelo` (como a Direcional): `NOPAT = Modelo!EBIT×(1−T)`;
  +D&A; −ΔWK; −CAPEX; VP por ano; EV; −Dívida Líquida; Equity; **Target (FCFF)**; Upside.
  Inclui o build-up do **WACC** (Ke CAPM Brasil + Kd + pesos D/E + alíquota). Se o usuário
  informou `wacc_manual`, exibir e usar esse valor (célula verde); senão, o build-up
  (fórmulas pretas). Múltiplos implícitos + TIR/MOIC (bloco `retornos`) entram aqui.
- **Aba `FCFE`** referenciando o `Modelo`: `LL + D&A − ΔWK − CAPEX + Δdívida líquida`
  (captações − amortizações); VP por ano ao **Ke**; Equity Value direto; **Target
  (FCFE)**; Upside. Inclui o build-up do **Ke** e uma **nota de reconciliação** FCFE ×
  Equity do bridge FCFF (devem ser próximos; divergência anotada, não é erro).
- As duas abas puxam os fluxos dos blocos persistidos `fcff` e `fcfe` (9.0.3) e conferem
  contra eles (mecanismo `escrever_calculo`). Nenhum número nasce no Excel.

### 9.0.5.3 Fidelidade e verificação

- Toda coluna histórica do `Modelo` **bate com a CVM** (o auditor do 9.0.1 é a garantia).
- Abrir o `.xlsx` gerado e **recalcular** não muda nenhum valor exibido (fórmulas
  reproduzem o motor); a linha **Check** mostra "Ok" nos 8 anos; zero erros de fórmula
  (`#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`).
- Blocos condicionais: empresa sem leasing → bloco Leasing omitido; sem instrumentos → só
  o agregado da dívida.
- Manter `exportar_excel(ticker)` e o Excel Preview do app funcionando (leitor genérico).
  Migrar consumidores do `dfc_simplificado` para o `dfc` indireto e remover o legado.

## Definição de Pronto (DoD)

- Excel gerado para DIRR3, MGLU3, SMFT3, VALE3, WEGE3 com as abas acima; abre no Excel
  real sem reparo; recalcular não muda valores; **linha Check = "Ok" nos 8 anos**; as
  colunas históricas do `Modelo` conferem com a CVM (auditor 9.0.1).
- **Modelo vivo:** alterar uma premissa NO EXCEL (ex.: margem bruta ano 3, célula verde)
  propaga pelas fórmulas até o **Target da aba `FCFF` E o Target da aba `FCFE`** (as duas
  abas separadas recalculam a partir do `Modelo`; teste manual documentado).
- Cores corretas: histórico azul, premissa verde, fórmula preto (auditoria programática).
- `tests/test_exportador_excel.py` reescrito e verde; `pytest` geral verde;
  `black`/`flake8` limpos.

## Testes e validação

- Testes por aba: presença/ordem; nomes exatos `Modelo`, `FCFF` e `FCFE` (abas
  separadas); legenda de cores na Capa; colunas históricas = CVM; linha Check com fórmula
  booleana; abas `FCFF` e `FCFE` batendo com os blocos `fcff`/`fcfe`; blocos condicionais
  somem quando não aplicáveis (fixture sem
  leasing); cores por tipo de célula (amostra: um histórico azul, uma premissa verde, uma
  fórmula preta).
- Smoke de recálculo: abrir via COM/LibreOffice, recalcular, zero erros de fórmula.

## O que NÃO fazer

- NÃO colar valores onde uma fórmula é possível. NÃO replicar o build-up de receita nem
  as abas de unit economics da Direcional (receita = crescimento %). NÃO criar Excel
  bancário (backlog). NÃO usar a convenção WSP de cores — usar a de Lucas (histórico azul
  / premissa verde / fórmula preto).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. **Fecha a Semana 9.0.** A próxima semana será
planejada depois (não está neste documento).

---
---

## Apêndice A — Fluxo de trabalho dos 3 atores

> **Humano (Lucas):** julgamento (premissas reais, validação numérica contra
> RI/Status Invest), descrição de bugs, commits/tags, revisão do `Humano_revisar.md`. →
> **Claude Code:** cura/gera estes prompts e revisa. → **Claude Fable 5:** implementa,
> testa, atualiza `CONTEXT.md`. → **Humano** fecha.

## Apêndice B — Ordem obrigatória e critério de avanço

Não abra o prompt N+1 antes de o DoD do prompt N estar verde **e** a regressão dourada
explicada (Princípio 13). Cada prompt deixa o repositório consistente e testável. Se uma
sessão terminar no meio de um prompt, registre o ponto exato no `CONTEXT.md` e retome do
mesmo prompt.

## Apêndice C — Backlog explícito (NÃO fazer na Semana 9.0)

| Item | Alvo |
|---|---|
| Unit economics setorial / build-up de receita (VGV×POC, academias×ticket, coortes) — receita fica como função plugável | **v3.0** |
| Excel bancário completo (FCFE/capital regulatório para financeiras) | v2.2 |
| `exportador_bi.py` completo + Power BI (`.pbix`) + nota PDF + orquestração em lote + Projetado vs. Realizado | v2.2 |
| Colunas trimestrais 1Q–4Q do ano corrente + LTM | v2.2 |
| Conversão automática de moeda de instrumentos de dívida | v2.2 |
| Target-leverage (dívida-alvo = alavancagem × EBITDA) | v2.2 |
| Indexação automática de custos a IPCA/IGP-M | v2.2 |
| Auditoria dupla profunda do Excel recalculado célula a célula (antiga Semana 10.1) | Semana 10 |
| Universalização B3 (lote ≥ 12 empresas, casos de borda, premissa→efeito) | Semana 10 |

## Apêndice D — O que o HUMANO precisa fazer na Semana 9.0 (checklist do Lucas)

1. **Colar um prompt por vez** (9.0.0 → 9.0.5, começando pelo enxugamento) no Fable e conferir o DoD antes do próximo.
2. **Commitar** ao final de cada prompt (mensagem sugerida: `claude semana 9.0.N`).
3. **Revisar `Humano_revisar.md`** ao fim da semana (decisões D-047+ e as novas).
4. **Conferir a fidelidade à CVM** (Prompt 9.0.1) em 1-2 empresas que você conheça,
   comparando o `Modelo` histórico do Excel com a DFP/ITR no site da CVM ou no RI.
5. **Premissas reais** de DIRR3/MGLU3/SMFT3 quando quiser que o Target seja tese (o
   pipeline gera automáticas; a comparação de números só faz sentido com as suas).
6. Se discordar de qualquer decisão (cores, WK, FCFE, retornos), reverter via
   `Humano_revisar.md` — nada é definitivo até você aprovar.
