# Humano_revisar.md — Decisões da IA aguardando revisão humana

> **Protocolo (instrução permanente de Lucas, 12/07/2026):** sempre que a IA
> (Claude Fable 5) encontrar um erro, ambiguidade, conflito entre documentos
> ou uma escolha que caberia ao humano, ela **decide sozinha pela melhor
> opção disponível, executa, e registra aqui**: data, situação, escolha
> tomada, alternativas consideradas e justificativa. O humano revisita este
> arquivo periodicamente: se discordar de uma decisão, pede a mudança e a IA
> reverte/ajusta. **Nenhuma entrada aqui é definitiva até o humano aprovar.**
> Esta instrução vale para TODAS as solicitações futuras e está replicada no
> `README.md`, `ROTEIRO.md`, `CONTEXT.md`, `PROMPTS_FABLE.md` e `CLAUDE.md`.

**Como ler:** status `⏳ aguardando revisão` | `✅ aprovada` | `🔁 revertida`.
Entradas mais recentes primeiro. IDs sequenciais `D-nnn` para referência.

---

## 19/07/2026 — Prompt 9.0.3 (FCFE não-financeira + macro anual + painel de Retornos)

> Sessão do **Claude Fable 5**. Fecha a camada de valuation sobre o motor 9.0.2:
> FCFE de não-financeiras descontado ao Ke (checagem do bridge), bloco
> `macro_anual` (Focus + convergência) alimentando o CDI do motor, e o painel
> de Retornos (múltiplos implícitos, TIR/MOIC, grade bear/base/bull).

### D-068 ⏳ — Validação em lote (12 tickers): achados e correção do erro do Excel p/ financeiras

- **Situação:** Lucas pediu validação ponta a ponta da Semana 9 (dados
  automáticos, ≥5 anos de histórico, Excel correto) para vários tickers.
  Lote executado: DIRR3, MGLU3, SMFT3, VALE3, WEGE3, RENT3, RADL3 (reuso de
  cache) + **PETR4, ABEV3, TOTS3 coletados DO ZERO** (42–53s cada, automação
  completa) + ITUB4, BBAS3 (financeiras). Resultado: **12/12 pipelines OK**;
  **10/10 Excel de não-financeiras OK** na auditoria estrutural (7 abas na
  ordem, 8 inputs azuis, ~540 fórmulas/arquivo TODAS com referências válidas,
  formatos milhar/percentual, 278 faixas navy, formatação condicional, nomes
  WACC/g, checklist na aba Output, zero células de erro). Histórico coletado:
  **7 exercícios anuais (2019–2025)** em todos — acima dos 5 pedidos.
- **Correção aplicada:** o Excel para financeiras falhava com mensagem
  enganosa ("bloco fcff ausente… rode a Semana 3"). `montar_contexto` agora
  detecta `tipo=financeira` ANTES e explica: o Excel de 7 abas cobre só
  não-financeiras (D-034); o valuation FCFE/Ke do banco fica no app/JSON;
  Excel bancário é backlog v2.2.
- **Achados SEM correção (expor, não travar):** (1) auditor CVM acusa
  `dfc_amarra` em RENT3/PETR4/ABEV3 (caixa do DFC divulgado ≠ caixa do BP em
  0,1–5% — escopo de "caixa e equivalentes" da própria companhia; o auditor
  existe para expor isso); (2) auditor acusa `balanco_fecha` em ITUB4/BBAS3 —
  falso-positivo estrutural: bancos não têm split AC/ANC (auditor foi
  desenhado p/ não-financeiras; trilha financeira valida na v1.5); (3) o
  Modelo Integrado mostra **3 anos históricos por contrato** da seção 5.10
  (`ANOS_HISTORICOS_MODELO=3`) embora a base tenha 7 — a coluna histórica
  ampliada (5 anos, padrão Direcional) é entrega EXPLÍCITA do Excel 9.0.5;
  não alterei o layout v1 (vetado pelo 9.0.3: "não mexer no Excel").
  TOTS3: setor CVM "Comunicação e Informática" sem regra → subtipo `outros`
  com FCFF/WACC (default seguro funcionou). Targets de premissa automática
  (PETR4 1,35; RADL3 −2,18; TOTS3 −1,70) são padrão D-024: REVISAR, não bug.

### D-065 ⏳ — Motor lê o CDI anual do macro; golden −0,04% a −8,5% explicado; Kd do WACC INTOCADO

- **Situação:** a taxa de aplicação do caixa era a Selic spot constante (14,25%
  nos 8 anos). O 9.0.3 manda o motor ler o CDI do `macro_anual` (Direcional
  `Modelo` L190), e o DoD manda explicar a diferença na receita financeira.
- **Escolha:** cascata nova `premissa > CDI anual do macro_anual > Selic spot >
  fallback config`. O CDI anual converge 13,9% (2026) → 8,9% (2033) — metas de
  longo prazo NOVAS em `config/parametros.json` bloco `macro` (IPCA 3% = meta
  BC; Selic 9% ≈ juro neutro nominal arredondado pelas medianas longas do
  Focus; PIB 2%; CDI = Selic − 0,1pp). Medianas do Focus convertem SEMPRE /100
  (`focus_para_decimal`) — a heurística legada erraria PIB < 1%. Coleta nova
  PRESERVA campos persistidos quando a rede falha (merge campo a campo).
- **Golden (rf/preço persistidos, FCFF byte-IDÊNTICO nos 5):** DIRR3 21,2560 →
  **20,8806** (−1,77%); MGLU3 0,8430 → **0,7713** (−8,52%); SMFT3 −3,8481 →
  **−3,9300**; VALE3 −0,08%; WEGE3 −0,04%. Canal ÚNICO: receita financeira
  acumulada cai ~25% (ex.: DIRR3 1,45 → 1,10 bi) → LL/PL menores → PL médio
  −2% → WACC +0,06 a +0,13pp → target. A queda é amplificada onde o equity é
  resíduo de bridge grande (MGLU3, padrão D-048/D-060).
- **Kd:** premissa opcional NOVA `spread_divida_sobre_cdi` (Kd_t = CDI_t +
  spread, por ano); sem ela, o `custo_divida_kd` escalar segue byte-igual.
  **O Kd do WACC NÃO foi tocado** apesar da pendência D-063 (kd derivado 46%
  MGLU3): o DoD do 9.0.3 exige target inalterado. A pendência CONTINUA aberta
  — ver D-066 (a divergência FCFE vs bridge da MGLU3 é o sintoma quantificado).

### D-066 ⏳ — VT do FCFE com ΔDívida normalizada; divergências vs bridge explicadas por ticker

- **Escolha:** perpetuar a amortização do ano 8 levaria a dívida a ficar
  negativa para sempre; a base do VT do FCFE usa `FCFE_8 − ΔDívida_8 + g ×
  Dívida_8` (estrutura estável na perpetuidade, Damodaran). Fallbacks: payout
  sustentável `LL8 × (1 − g/ROE8)` → sem base viável persiste equity None +
  aviso (nunca quebra — é checagem secundária; o bridge FCFF segue primário).
  Decomposição por ano persistida: `FCFE = FCFF − juros após IR + rec. fin.
  após IR + ΔDívida + resíduo` (resíduo = RET/EBT≤0/alíquota anual +
  minoritários; zero no caso marginal puro).
- **Divergências (premissas atuais, AVISO > 15%):** DIRR3 **−50%** (RET sem
  escudo fiscal + desalavancagem pesada: FCFE 1-8 ≪ FCFF; estrutura Ke único
  vs WACC com pesos contábeis); MGLU3 **+935%** — SINTOMA da D-063: o WACC usa
  kd_historico 46% (equity residual ~0,6 bi), o FCFE paga os juros REAIS da
  premissa e desconta ao Ke (equity 6,2 bi); SMFT3 **−102%** (bridge negativo,
  premissa automática D-024); VALE3 −37%; WEGE3 +51%. Interpretação: a
  divergência é diagnóstico útil, não erro — quando Lucas revisar o Kd (D-063)
  as pontas devem se aproximar.

### D-067 ⏳ — Retornos: saída = target truncado em zero; grade = ±20% na saída; proxies da financeira

- **Escolha:** TIR do acionista com fluxo `−preço; +dividendos/ação (payout do
  DFC); +preço de saída no ano 5` e saída = target do bridge **truncada em
  zero** quando negativa (responsabilidade limitada — o acionista não paga
  para sair; flag `preco_saida_truncado_em_zero` persistida). TIR por bissecção
  robusta (sem mudança de sinal → None + nota, nunca explode). Grade
  bear/base/bull = **±20% no preço de saída** (`retornos.variacao_target_bear_
  bull`): o motor de cenários completo está CONGELADO desde o 9.0.0 — a grade é
  sensibilidade de saída, não re-run do valuation (alternativa descartada:
  descongelar `motor_cenarios.py`, vetado pelo enxugamento).
- **Financeiras:** P/L e P/VP (sem EV/EBITDA); VPA via `capital_regulatorio`
  (que parte do PL contábil do Ano 0 — proxy documentado) e dividendos = FCFE
  truncado em zero (capacidade de distribuição; não há DFC na trilha bancária).
- **Múltiplos com denominador ≤ 0 → None** ("n.m."), LL/EBITDA negativos
  continuam válidos no motor. Resultado atual: DIRR3 TIR base **+14,7%**/MOIC
  1,93x (target > preço ✓ DoD); MGLU3 −10,2%; SMFT3 −60,5% (saída truncada);
  VALE3 −8,4%; WEGE3 −24,1% — coerentes com os upsides.

---

## 18/07/2026 — Prompt 9.0.2 (Motor "padrão Direcional"): DRE pré-D&A, WK expandido, DFC indireto, BP aberto

> Sessão do **Claude Fable 5**. A etapa mais densa da Semana 9.0: o modo completo
> da DRE muda de paradigma (margens PRÉ-D&A, D&A linha própria), o WK ganha o modo
> multi-driver com as contas de Lucas, a dívida aceita instrumentos opcionais, e
> nascem o DFC indireto (`dfc_indireto.py`) e o BP aberto com check visível.
> Golden triplo RE-BASELINE explicado em D-060.

### D-059 ⏳ — Paradigma PRÉ-D&A + calibração do gerador (margem bruta += D&A%RL)

- **Situação:** o 8.1 assumia D&A embutida em CPV/SG&A (padrão Smartfit) — o que
  causou o colapso do SMFT3 (D-048). A Regra de Precedência do 9.0 manda margens
  de NÍVEL EBITDA (pré-D&A) com D&A como linha própria (padrão Direcional).
- **Escolha:** `projetar_linhas_dre_completa` reescrita: EBIT ex-Depreciação =
  Lucro Bruto + SG&A + Outras + Equivalência (nível EBITDA); EBIT = ex-D&A −
  D&A (schedule PP&E); EBITDA = ex-D&A (invariante). Cauda EBT → IR (RET sobre
  RB projetada > vetor `aliquota_ir_ano1..8` NOVO > efetiva > marginal) →
  minoritários → LL → LPA, recalculada nos schedules por UMA função
  (`recalcular_cauda_dre_completa`, fonte única). **Gerador calibrado:** a margem
  bruta histórica da CVM é PÓS-D&A; a âncora pré-D&A soma a D&A%RL inteira à
  margem bruta — identidade exata: EBIT ex-D&A ano 1 = EBITDA histórico.
  Aproximação consciente: D&A toda no CPV (padrão industrial); se o humano
  preferir split CPV×SG&A, é premissa a ajustar.
- **Modo legado byte a byte:** DIRR3/MGLU3 legados deram targets IDÊNTICOS ao
  baseline pós-9.0.1 antes da regeneração de premissas (prova executada).

### D-060 ⏳ — RE-BASELINE do golden triplo (padrão D-022; premissas regeneradas)

- **Baseline pós-9.0.1 → pós-9.0.2:** DIRR3 16,9687 → **21,2560** (+25,3%);
  MGLU3 2,6542 → **0,8430** (−68,2%); SMFT3 0,6361 → **−3,8481**.
- **Drivers por ticker:**
  - **DIRR3 (+25,3%):** driver dominante = premissas REGENERADAS (manuais de
    teste: crescimento 1%/margem 10% → automáticas ancoradas: CAGR clamp 15%,
    margem bruta pré-D&A da CVM, capex histórico) + modo legado → completo
    pré-D&A (RET sobre a Receita Bruta projetada). WK segue ancorado
    (construtora, sem mudança).
  - **MGLU3 (−68%):** modo legado → completo pré-D&A + WK dias → multi-driver
    (tributos a recuperar de 2,05 bi entram no giro) sobre um equity que é
    RESÍDUO pequeno de bridge de ~12 bi (alavancagem do bridge, padrão D-048).
    Premissas: as de TESTE manuais restauradas do git e COMPLEMENTADAS para o
    modo novo (margem bruta 28% − SG&A 20% = margem EBITDA 8% original) — as
    automáticas davam WACC 24-27% (ver D-063) e target negativo no gate E6.
  - **SMFT3 (−3,85, REVISAR):** premissas automáticas 100% regeneradas: capex
    de EXPANSÃO histórico −30%→−4% + Kd derivado ~19,9% + bridge real de 13,75
    bi (dívida 7,48 + leasing 6,27, conferido linha a linha SEM dupla
    contagem). **O colapso estrutural do D-048 SUMIU:** EBITDA ancorado no
    histórico real (46,6% da RL), FCFF cresce 0,23 → 1,53 bi, margem bruta
    bate por identidade. **Prova de sensibilidade:** capex de analista
    (−15%→−4%) → target **+3,11**. É o padrão D-024 (premissa automática não é
    tese; o analista revisa), não um bug do paradigma.
- **Premissas do lote regeneradas (reversível):** DIRR3/VALE3/WEGE3/SMFT3 =
  automáticas novas (pré-D&A completo + `modo_capital_giro: dias_multi_driver` +
  vetor de alíquota anual + minoritários); MGLU3 = teste manual complementada. Os
  arquivos antigos de DIRR3/MGLU3 estão no git (`git diff data/premissas/`).

### D-061 ⏳ — WK multi-driver: salvaguardas de driver e agregação

- **Escolha:** dias implícitos = saldo_ano0/driver_ano0×365 (premissa `dias_*`
  sobrescreve). **Salvaguarda:** dias > 365 pelo driver nominal → recai para a
  receita líquida (na MGLU3 o driver IR dava **2.307 dias** de tributos a
  recuperar — varejo acumula ICMS/PIS/COFINS ligados à receita, não ao IR).
  Adiantamento de clientes somado CP+LP (construtoras reportam a maior parte no
  LP); obrigações sociais/trabalhistas com driver SG&A (fallback RL quando o
  SG&A do Ano 0 não existe). Contas ausentes → dias 0 + aviso (Princípio 7).
- **Modos antigos preservados:** `dias` (arquivos v2 com DSO/DIO/DPO seguem
  byte a byte) e `percentual_receita` (construtoras) intactos; o gerador grava
  `dias_multi_driver` para não-construtoras.

### D-062 ⏳ — BP aberto: arrendamento como linha própria CONSTANTE; residuais menores

- **Escolha:** o balanço projetado ganha as linhas do WK expandido (tributos a
  recuperar, obrigações trabalhistas, adiantamentos — projetadas no modo
  multi-driver; zero nos demais) e **`passivo_arrendamento` como linha própria
  CONSTANTE no valor do Ano 0** (o rollforward do leasing segue informativo no
  bloco `leasing`; integrar os fluxos de caixa do arrendamento ao DFC/BP é
  backlog — mantê-lo constante preserva o fechamento por construção). Residuais
  `outros_ativos`/`outros_passivos` agora EXCLUEM essas contas. Campo novo
  `verificacao_balanco` = |Ativo − Passivo − PL| por ano (check da Direcional
  L122). Com `instrumentos_divida`, a diferença entre a soma dos instrumentos e
  a dívida do BP fica explícita em `outros_passivos` (aviso quando > 1%).
- **DFC indireto (`dfc_indireto.py`):** abre o ΔWK linha a linha (contribuição
  ao caixa = −Δsaldo assinado, unifica ativos e passivos); `dfc` vira SUPERSET
  (campos legados intactos + linhas novas) e `dfc_simplificado` preserva o
  contrato v2 até o Excel do 9.0.5 migrar. Amarração verificada: Σ variações =
  −ΔNWC e caixa EoP = caixa do BP (dif < 1e-6 nos 5 tickers).

### D-063 ⏳ — Beta de partida clampado [0,5; 1,8]; Kd derivado ALTO fica para revisão

- **Situação:** o gerador clampava crescimento/margens/capex mas NÃO o beta; o
  beta desalavancado histórico da MGLU3 (ação em colapso) saiu **2,27** → WACC
  27,4% e target −9,98 (com o bug dos dias, −2,44 depois do fix D-061).
- **Escolha:** clamp `LIMITES_BETA = (0.5, 1.8)` SÓ na premissa automática de
  partida (o analista sobrescreve). **Pendência anotada para o humano/9.0.3:**
  o `kd_historico` DERIVADO pelo calculador de WACC sai 46% (MGLU3) e 19,9%
  (SMFT3) — distorce o WACC de nomes alavancados; o motor de valuation não foi
  tocado neste prompt (vetado pelo escopo). Recomendo revisar a derivação (ou
  preferir o Kd de premissa) no 9.0.3.

### D-064 ⏳ — Minoritários: LL final único na cadeia (minoria como distribuída)

- **Escolha:** `participacao_minoritarios = −pct × LL antes` (divide lucro E
  prejuízo); o LL FINAL alimenta PL/FCO/dividendos — equivale a tratar a parcela
  dos minoritários como distribuída (payout 100% da minoria). Alternativa
  (equity consolidado retendo a minoria) exigiria abrir o PL em controladores ×
  minoritários no balanço — backlog. Default 0 (nada muda sem a premissa);
  âncora histórica = |3.11.02|/|3.11| do Ano 0, clamp [0, 50%].

---

## 17/07/2026 — Prompt 9.0.1 (Fidelidade à CVM): mapeamento expandido + auditor

> Sessão do **Claude Fable 5**. Executado o Prompt 9.0.1: BP/DRE/DFC históricos
> batendo com a DFP/ITR da CVM. Novo `src/coleta/auditor_cvm.py` (5 checagens +
> remapeamento offline), `config/mapeamento_cvm.json` +25 entradas, e
> `montar_series_anuais` ampliada (BP aberto + DFC + Receita Bruta). Motor e
> valuation INTOCADOS; golden triplo idêntico (ver D-056 sobre o baseline).

### D-055 ⏳ — Diagnóstico do "55% residual" e como foi fechado (meta < 5% ATINGIDA)

- **Situação:** o plano dizia "55% do ativo / 59% do passivo do DIRR3 em baldes
  outros". Medição real: o mapeamento bruto estava COMPLETO (0 contas não
  mapeadas); o buraco era (a) a camada de extração (`montar_series_anuais` só
  nomeava ~10 contas do BP) e (b) os baldes gigantes `1.02.01` (realizável LP =
  50% do ativo da DIRR3: contas a receber LP + estoques/terrenos LP) e `2.02.02`
  (outras obrigações LP = 50% do passivo: credores por imóveis 5,1 bi + cessão +
  adiantamentos), que ficavam anônimos.
- **Escolha:** (1) mapear por CD_CONTA as sub-contas PADRÃO de nível 4
  (1.02.01.01–.10, 2.01.05.01/.02, 2.02.02.01/.02 — códigos estáveis 2019–2025,
  verificado); (2) mapear por NOME as sub-contas recorrentes de nível 5
  (adiantamento de clientes, dividendos/JCP a pagar, credores por imóveis —
  cobrindo o typo "imóvies" da DFP da Direcional —, passivo de cessão, depósitos
  judiciais, tributos a recuperar/recolher, contas a pagar, receitas diferidas,
  participação nos lucros, derivativos, provisão para garantias); (3) os 4
  residuais explícitos do prompt (`outros_ativos_circulantes` já existia;
  `outros_ativos_nao_circulantes`, `outros_passivos_circulantes`,
  `outros_passivos_nao_circulantes` = códigos 1.02.01.10, 2.01.05.02,
  2.02.02.02). **Residual medido (último exercício): DIRR3 0,01%/0,11% (era
  55%/59%); MGLU3 1,53%/3,58%; SMFT3 1,14%/0,03%; VALE3 2,61%/0,66%; WEGE3
  2,40%/4,49% — todos < 5%.** Única exceção histórica: VALE3 2023 ativo 6,03%
  (AVISO no laudo, "Outros" da própria Vale).
- **Alternativas:** abrir por nome TODAS as sub-contas específicas de empresa
  (ex.: "Parceiros e outros depósitos" da MGLU3, 3,6% — deixada como residual
  explícito: criar campo por empresa não escala e o residual já é pequeno).

### D-056 ⏳ — Remapeamento OFFLINE + prova de neutralidade do golden (novo baseline DIRR3)

- **Situação:** expandir o mapeamento deixa defasados os `nome_padronizado`
  persistidos na coleta original. Recoletar com rede seria lento e não
  determinístico.
- **Escolha:** `remapear_empresa` no auditor (`--remapear`): reaplica a cascata
  ATUAL aos JSONs brutos já persistidos (sem rede) e atualiza o Parquet limpo.
  **Prova de neutralidade:** MGLU3 2,6542154782645526 e SMFT3 0,6360724149230469
  BYTE-IDÊNTICOS antes/depois do remap (diff 0.0). Os consumidores do motor leem
  a linha CONSOLIDADA (código mais curto), cujos nomes não mudaram; os residuais
  do balanço são aritméticos (total − nomeadas), não somas por nome.
- **DIRR3 16,9029 → 16,9687 NÃO é o remap:** é o `rf_usd` vivo (4,541%)
  refrescado pelo `main.py` do DoD do 9.0.0 (padrão D-011: o JSON de mercado é
  atualizado na coleta). Novo baseline do golden triplo registrado:
  **DIRR3 16,968729990248534 | MGLU3 2,6542154782645526 | SMFT3
  0,6360724149230469** (verificado idêntico em reexecução dupla).

### D-057 ⏳ — Identidade da DRE que fecha invertendo UM sinal vira AVISO explicado

- **Situação:** a DFP 2022 da VALE divulga o CPV POSITIVO (+124,2 bi; todos os
  outros anos divulgam negativo). A identidade `lucro_bruto = 3.01 + 3.02` dava
  ERRO, mas `3.01 − 3.02` fecha exato — o furo é de CONVENÇÃO DE SINAL do
  arquivo divulgado, não de aritmética.
- **Escolha:** quando a identidade só fecha invertendo o sinal de UMA parcela, o
  auditor reporta AVISO com a conta apontada ("sinal divulgado fora da convenção
  CVM") em vez de ERRO. Nenhum número é inventado (o que NÃO fazer do prompt); o
  problema do dado fica exposto e o laudo da VALE3 fecha com 0 ERRO.
- **Alternativas:** manter ERRO (pune a empresa por quirk de arquivamento da
  CVM e polui o gate de CI); normalizar o sinal silenciosamente (vetado).

### D-058 ⏳ — Desambiguação AC×LP posicional; aproximações de nome registradas

- **Situação:** sub-contas de nível 5 com o MESMO nome nos dois lados do BP
  ("Tributos a Recuperar" no AC e no realizável LP) não são distinguíveis por
  DS_CONTA no fallback por nome.
- **Escolha:** reutilizar o nome existente (ex.: `tributos_a_recuperar`) — as
  séries por nome pegam a linha consolidada (código mais curto, AC), e a
  decomposição do auditor (`bp_aberto`) atribui POSICIONALMENTE pela árvore de
  códigos, então cada seção fica correta. Aproximações conscientes: "provisão
  para garantias" → `provisoes_cp` (WEGE3 reporta no circulante; se alguma
  empresa reportar em LP, a linha aparece na seção certa da decomposição mas com
  nome de CP); "participação nos lucros" → `obrigacoes_sociais_trabalhistas`
  (natureza trabalhista).
- **Reversível:** se o humano preferir campos distintos (`tributos_a_recuperar_lp`
  etc.), basta trocar o nome no fallback e re-rodar `--remapear`.

---

## 17/07/2026 — Prompt 9.0.0 (Enxugamento): congelar a periferia, reduzir ao núcleo

> Sessão do **Claude Fable 5**. Executado o Prompt 9.0.0 do `PROMPTS_FABLE.md`:
> cortar a gordura ANTES de construir o Excel-núcleo. Nada apagado (exceto a
> cópia duplicada de doc); a periferia foi CONGELADA de forma reversível. Motor
> e valuation intocados. Regressão dourada neutra (ver nota abaixo).

### D-053 ⏳ — Lista EXATA do que foi congelado (para o humano decidir apagar depois)

- **Congelados** (banner `# CONGELADO v2.1 (Prompt 9.0.0 ...)` no topo do arquivo;
  removidos dos `import` de `app.py`/`main.py`/`src/pipeline.py`; **arquivos NÃO
  movidos nem apagados** — só marcados e desligados do caminho crítico):
  - `src/visualizacao/football_field.py`
  - `src/visualizacao/tornado.py`
  - `src/visualizacao/waterfall_ev.py`
  - `src/visualizacao/dashboard_final.py`
  - `src/visualizacao/roic_roiic.py`
  - `src/visualizacao/historico_vs_projetado.py`
  - `src/visualizacao/comparacao_empresas.py`
  - `src/visualizacao/tabela_comparaveis.py`
  - `src/visualizacao/sensibilidade_wacc_g.py`
  - `src/visualizacao/sensibilidade_receita_margem.py`
  - `src/visualizacao/sensibilidade_setor.py`
  - `src/visualizacao/apoio_heatmap.py`
  - `src/valuation/comparaveis.py`
  - `src/valuation/motor_cenarios.py`
  - `src/exportacao/exportador_bi.py`
- **Testes pulados** (com `pytest.mark.skip(reason="congelado 9.0.0 — ... (D-053)")`,
  NÃO removidos): `tests/test_football_field.py`, `tests/test_roic_roiic.py`,
  `tests/test_comparaveis.py`, `tests/test_motor_cenarios.py` (módulo inteiro); e
  3 testes de `tests/test_app.py` (Comparáveis, Comparar/watchlist e seletor de
  cenários do Overview — seções que saíram do app enxuto).
- **Para reverter qualquer item:** remover o banner do módulo, restaurar o
  `import` no orquestrador e tirar o `skip` do teste. **A DECIDIR pelo humano:**
  se prefere apagar de vez algum desses (o 9.0.0 só congela).
- **Alternativas:** mover para `src/_congelado/` (a spec permitia) — preferi
  marcar-no-lugar porque os charts importam entre si e de `tema_institucional`/
  `apoio_cenarios`; mover exigiria reescrever imports internos de código
  não-mantido (mais risco, mesmo efeito de "fora do caminho crítico").

### D-052 ⏳ — `apoio_cenarios` e `tema_institucional` RETIDOS; `exportador_excel` intocado no 9.0.0

- **Situação/conflito:** o Prompt 9.0.0.2 manda "remover as chamadas no
  `exportador_excel`", mas o `exportador_excel.py` (NÚCLEO) **importa**
  `src.visualizacao.apoio_cenarios` (tabelas de sensibilidade) e
  `src.visualizacao.tema_institucional` (cores/formatação) e **insere PNGs** dos
  charts. Congelar esses dois helpers OU reescrever o exportador agora quebraria
  o Excel-núcleo e contrariaria "NÃO tocar no motor/Excel" + "Excel reescrito no
  9.0.5" + "Target Price INALTERADO".
- **Escolha:** manter `tema_institucional.py` e `apoio_cenarios.py` como SUPORTE
  RETIDO (banner `# RETIDO no nucleo`), não congelados, usados só pelo
  `exportador_excel` legado até a reescrita do 9.0.5. `exportador_excel.py` fica
  **intocado** (Excel idêntico; `_inserir_png` já degrada com aviso quando o PNG
  não existe, então sem gráficos o Excel gera igual). Para o `app.py` NÃO
  depender de `src/visualizacao/`, criei `src/apresentacao/formatacao.py` (núcleo)
  com as funções de formatação BR + cores; `app.py` e `main.py` passaram a usar
  esse módulo / leitura inline (zero import de `src/visualizacao/`).
- **Desvio registrado:** é uma leitura conservadora do 9.0.0.2 (remover as
  chamadas do exportador fica para o 9.0.5, que reescreve o Excel). Se o humano
  preferir, dá para já cortar PNG+sensibilidade do exportador agora.
- **Alternativas:** congelar os dois helpers e mutilar o exportador agora
  (quebra a golden do Excel e o test_exportador_excel); mover os helpers para o
  núcleo e reescrever os imports dos 12 charts congelados (churn em código
  não-mantido).

### D-054 ⏳ — Consolidação da documentação da raiz

- **Escolha:** `git mv` de `ROTEIRO.md`, `CHANGELOG.md`, `CONTRIBUTING.md` para
  `docs/`; **apagado** `Roteiro DCF - Copia.md` (cópia duplicada — confirmado por
  `grep` que só o próprio plano e este arquivo a citavam, nenhuma referência
  funcional). Raiz agora com 5 `.md`: `README.md`, `CONTEXT.md`, `CLAUDE.md`,
  `PROMPTS_FABLE.md`, `Humano_revisar.md`. Referências a `ROTEIRO.md` atualizadas
  em `README.md` (link + árvore) e `CLAUDE.md` (→ `docs/ROTEIRO.md`); os links
  internos entre os docs movidos continuam válidos (relativos, mesma pasta).
- **Alternativas:** manter na raiz "marcados como histórico" (não reduz o
  inchaço que Lucas apontou).

### Nota (sem decisão) — Golden estava DEFASADA; enxugamento é neutro

- Os JSONs em `data/processed/` (ignorados pelo git) estavam no estado **8.2/
  D-045** (DIRR3 16,8618; MGLU3 7,5128; SMFT3 18,6259) — **nunca regenerados após
  a simplificação da D&A (D-047/D-048)**. Re-rodar o motor (sem tocar em nada do
  motor) os atualizou para o estado ATUAL do código, **D-048**, determinístico em
  2 execuções: **DIRR3 16,90289543726421; MGLU3 2,65421547826455; SMFT3
  0,63607241492305** (idêntico aos números já registrados na D-048). Ou seja: a
  diferença é a defasagem dos dados persistidos, **não** o enxugamento — `git
  diff` confirma que nenhum arquivo de motor/valuation foi tocado.

---

## 17/07/2026 — Reescrita do PROMPTS_FABLE.md para a Semana 9.0 (automação + Excel)

> Sessão do **Claude Fable 5**. Lucas pediu para reescrever o `PROMPTS_FABLE.md`
> inteiro contendo APENAS a Semana 9.0 (17→24/07), fundindo o que faltava do plano
> (8.3 em diante até o fim da semana 9) com as instruções de automação/Excel que ele
> deu no chat, dando PRECEDÊNCIA às instruções atuais. Depois, ao constatar que o
> projeto tem "arquivos demais" e o Excel-núcleo está fraco, pediu para o plano
> corrigir isso (D-051).

### D-051 ⏳ — Semana 9.0 começa por ENXUGAR o projeto (Prompt 9.0.0)

- **Situação (medida em 17/07/2026):** o projeto tem 54 módulos em `src/` (15 só em
  `visualizacao`), 30 testes e 9 `.md` na raiz. O Excel gerado hoje tem a aba principal
  com **40 linhas** (Direcional = 210), DRE ANTIGA (margem EBITDA) e **55% do ativo /
  59% do passivo do DIRR3 em baldes "outros"**. Ou seja: muita periferia construída
  antes do núcleo, e o núcleo (Excel DCF fiel à CVM) é a parte mais fraca. Lucas
  reconheceu isso ("arquivos demais", "o Excel não tem ainda").
- **Escolha:** o `PROMPTS_FABLE.md` ganhou um **Prompt 9.0.0 (Enxugamento)** como
  primeira etapa da Semana 9.0: **congelar** (não apagar) a periferia — os 15 módulos de
  visualização, comparáveis, watchlist, BI, retornos, cenários — para fora do caminho
  crítico e do app/Excel, reduzindo o projeto ao núcleo (coleta → motor → Excel dos 3
  demonstrativos + FCFF/FCFE). Docs consolidadas; `Roteiro DCF - Copia.md` a apagar
  (cópia). A Seção 0.1 do plano foi reescrita com o diagnóstico honesto e os números
  reais. Metas objetivas cravadas: residual < 5% (era 55%); Excel de 40 → ~200 linhas.
- **Alternativas:** apagar a periferia de vez (mais radical; deixei como decisão do
  humano — 9.0.0 só congela, reversível); seguir sem enxugar (mantém o inchaço que Lucas
  reclamou). **A DECIDIR pelo humano:** se prefere apagar de vez o que o 9.0.0 congelar.

### D-049 ⏳ — Plano da Semana 9.0: automação fiel à CVM + Excel "Modelo" ≥ Direcional

### D-049 ⏳ — Plano da Semana 9.0: automação fiel à CVM + Excel "Modelo" ≥ Direcional

- **Situação:** o plano antigo (8.3/9.1/9.2/9.3/10.x) seguia o "Padrão Smartfit" (D&A
  por safra, D&A embutida nas margens, Excel de 9 abas, cores WSP). O pedido atual de
  Lucas muda o alvo para o **modelo da Direcional** (verificado no xlsx real): D&A =
  %PP&E, CAPEX = %receita, margens PRÉ-D&A (D&A como linha própria), aba única
  `Modelo` com os 3 demonstrativos, FCFF + FCFE, e a prioridade nº 1 é o histórico
  bater EXATAMENTE com a CVM/DFP/ITR.
- **Escolha:** `PROMPTS_FABLE.md` reescrito do zero com 5 prompts (9.0.1 fidelidade
  CVM; 9.0.2 motor pré-D&A + D&A%PP&E + WK expandido + DFC indireto + BP aberto;
  9.0.3 FCFF+FCFE+macro+retornos; 9.0.4 front-end das 6 premissas; 9.0.5 Excel
  `Modelo` ≥ Direcional). Uma "Regra de Precedência" no topo diz que a instrução
  atual vence o plano antigo em 6 pontos (D&A simples; margens pré-D&A; fidelidade
  CVM; Excel ≥ Direcional; cores; receita = crescimento %). Semanas 10+ ficaram FORA
  (Lucas pediu só a 9.0); a auditoria dupla e a universalização viraram Apêndice C.
- **Alternativas:** manter o plano Smartfit (contraria o pedido e reintroduz o
  descasamento D&A×margens que quebrou o SMFT3); planejar até a semana 10 (Lucas pediu
  explicitamente só a 9.0).

### D-050 ⏳ — Convenção de cores do Excel: histórico=AZUL, premissa=VERDE, fórmula=PRETO

- **Situação:** Lucas especificou no chat: histórico em azul, premissas (que o usuário
  escolhe) em verde, resultados de fórmula em preto. O Excel REAL da Direcional usa a
  convenção WSP oposta em parte: **azul = input/premissa**, **verde = link para outra
  aba**, preto = fórmula (verificado célula a célula: margem bruta G6 = azul; link
  histórico F19 = verde).
- **Escolha:** seguir a convenção de LUCAS no novo Excel (histórico azul, premissa
  verde, fórmula preto), por precedência da instrução atual. Registrado por divergir do
  benchmark que o próprio plano manda "no mínimo igualar". O Princípio 11 do
  `PROMPTS_FABLE.md` foi atualizado para essa convenção.
- **Alternativas:** usar a convenção WSP/Direcional (azul=input, verde=link) — é o
  padrão de mercado e o que o arquivo de referência faz, mas contraria o pedido
  explícito. Se Lucas preferir o padrão de mercado, é só reverter esta decisão.

---

## 17/07/2026 — Simplificação da D&A (pedido de Lucas: reverter D&A por safra)

> Sessão do **Claude Fable 5**. Pedido explícito de Lucas no meio do Prompt 8.2:
> *"Não precisa fazer o D&A por safra, faça simplificado, conforme estava antes,
> apenas fazendo CAPEX por % da receita e D&A por % do PP&E."* A modelagem de
> arrendamento IFRS-16 (juros de arrendamento separados, D&A do direito de uso
> por reclassificação, bridge com passivo somado) é MANTIDA; só a mecânica de
> depreciação do imobilizado volta ao modelo simples.

### D-047 ⏳ — D&A do imobilizado volta ao modelo SIMPLES (reverte D-041)

- **Situação:** o Prompt 8.2.3 tinha trocado a D&A por uma matriz de safras de
  CAPEX com vida útil DERIVADA do histórico (D-041). Lucas pediu para reverter à
  mecânica simples "como estava antes" (v2/8.1).
- **Escolha:** `schedule_ppe.py` volta a: (1) **CAPEX = % da receita** (premissa
  `capex_receita_anoN`, inalterada); (2) **D&A = taxa única** `1/vida_util_ppe_anos`
  (config = 10 anos) sobre o **PP&E de abertura**, com `MIN(quota, base)` para não
  depreciar abaixo de zero (helper `calcular_depreciacao_amortizacao` que já
  existia). Removidos: vida derivada, clamp [3,30], matriz de safras,
  meia-depreciação e o bloco `ppe_safras` da config (virou `capex_split`). O
  **intangível NÃO amortiza mais** (`da_intangivel = 0`; saldo do Ano 0 constante,
  mas mantido como **linha própria do balanço** — a estrutura de D-043 permanece e
  o balanço continua fechando por construção). **Mantido do 8.2:** split
  informativo capex expansão×manutenção (agora com default por subtipo em
  `setores.json` → global 80%) e a D&A histórica do Ano 0 persistida em `ano0.ppe`
  (insumo do prazo médio do leasing).
- **Alternativas:** manter as safras (contraria o pedido explícito); dobrar o
  intangível de volta para dentro de `outros_ativos` como na v2 (funciona, mas
  esconde a linha — manter explícita é mais auditável e o balanço fecha igual).

### D-048 ⏳ — Golden re-baseline da simplificação (mudanças EXPLICADAS de Target)

- **Números (preço de mercado congelado, mesmo rf da golden):**
  DIRR3 16,8618 → **16,9029** (+0,24%); MGLU3 7,5128 → **2,6542** (−64,7%);
  SMFT3 18,6259 → **0,6361** (−96,6%). Balanço fecha nos 3 (dif < 6e-9). VALE3
  (109,85) e WEGE3 (12,87) rodam sem quebrar; `verificar_semana3` → SEMANA 3 OK.
- **Driver único:** a D&A simples (config vida=10) é MENOR que a D&A por safra com
  vida derivada (DIRR3 3,22; MGLU3 3,98; SMFT3 7,22 anos), então:
  - **Modo legado (DIRR3, MGLU3):** menos D&A → menos tax shield `D&A×t` no FCFF.
  - **Modo completo (SMFT3):** menos D&A add-back no FCFF (a D&A embutida em
    CPV/SG&A vem das margens históricas, mas o add-back agora é menor).
- **Por que a queda é grande em MGLU3/SMFT3 e não em DIRR3:** o equity é um
  RESÍDUO pequeno após um bridge grande (dívida + leasing IFRS-16 somado, D-044).
  MGLU3 (dívida 8,5 mi + leasing 3,6 mi) e SMFT3 (dívida 13,8 mi + leasing 6,3 mi)
  têm bridge da ordem do próprio EV → uma redução moderada de EV vira uma queda
  grande no equity/target (alavancagem do bridge). DIRR3 tem leasing imaterial e
  dívida pequena → efeito quase nulo (+0,24%).
- **AÇÃO RECOMENDADA AO HUMANO — SMFT3 R$ 0,64 é um artefato, não tese:** SMFT3 é
  o pior caso para o modelo simples (leasing gigante, modo completo, **premissas
  automáticas** `premissas_automaticas: true`). No modo completo a D&A embutida nas
  margens (real, ~1,76 mi/ano) é MAIOR que o add-back simples (config vida 10),
  subestimando o FCFF; com o bridge quase igual ao EV, o equity vira um sliver. Foi
  exatamente esse descasamento que a D&A por safra corrigia (D-046). Se o Target de
  SMFT3 importar como tese, ou (a) revisar as premissas na aba Premissas (crescimento/
  margens/`prazo_medio_leasing_anos`), ou (b) reconsiderar reativar a D&A por safra
  SÓ para o modo completo. Padrão D-024 (premissas automáticas produzem extremos; a
  triangulação expõe; o analista revisa).

## 14/07/2026 — Prompt 8.2 (IFRS-16, D&A por safra, capex expansão×manutenção)

> Sessão do **Claude Code**: modelagem do arrendamento (IFRS-16) como cidadão de
> primeira classe, D&A do imobilizado POR SAFRA de CAPEX com vida derivada do
> histórico, amortização do intangível e split de capex expansão×manutenção.
> Novo módulo `src/projecao/schedule_leasing.py`; `schedule_ppe.py` reescrito;
> `schedule_divida.py` e o bridge ajustados. Golden re-baseline EXPLICADO (D-045).
> **NOTA (17/07/2026):** a parte de D&A por safra (D-041) foi REVERTIDA a pedido
> de Lucas — ver D-047/D-048 na seção de 17/07 acima. O leasing IFRS-16 (D-042/
> D-044) e a linha própria do intangível (D-043) permanecem; D-045/D-046 são
> substituídos pelo novo golden re-baseline em D-048.

### D-041 🔁 REVERTIDA em 17/07/2026 (ver D-047) — D&A do imobilizado POR SAFRA com vida útil DERIVADA do histórico

- **Situação:** a v2/8.1 depreciava o imobilizado por uma taxa única global
  (`1/vida_util_ppe_anos`, config = 10 anos), subestimando a D&A de empresas
  com ativos de vida mais curta.
- **Escolha:** `schedule_ppe.py` passa a depreciar POR SAFRA (Smartfit L339):
  vida útil = `imobilizado_ano0 / |D&A_historica_ano0|` (do DFC), clamp [3,30];
  o estoque existente deprecia linear até zerar (`MIN(quota, saldo)`), cada safra
  de capex faz **meia-depreciação no ano da safra** e `MIN(quota, saldo)` depois.
  Fallback: `vida_util_ppe_anos` da config. Amortização do intangível linear
  sobre o saldo do Ano 0 (mesma vida). Split capex expansão (default 80%,
  `config/parametros.json`) × manutenção — informativo, não muda o capex total.
- **Alternativas:** manter a taxa única (subestima D&A e ignora a vida real);
  exigir a vida como premissa obrigatória (quebra a automação).

### D-042 ⏳ — D&A do direito de uso por RECLASSIFICAÇÃO proporcional (fallback 8.2.1)

- **Situação:** na CVM o ativo de direito de uso (1.02.03.02) vem AGREGADO dentro
  do imobilizado (1.02.03). Depreciar o direito de uso separadamente E manter o
  imobilizado cheio DUPLICARIA a D&A.
- **Escolha:** o `schedule_leasing.py` obtém `da_direito_uso` por reclassificação
  proporcional da D&A do imobilizado (`proporção = direito_uso / imobilizado`) —
  o fallback documentado do próprio Prompt 8.2.1. A D&A TOTAL não muda (só se abre
  em imobilizado × direito de uso), logo **EBIT/EBITDA e FCFF não mudam com a
  reclassificação**; apenas os **juros de arrendamento** (abaixo do EBIT) entram
  no resultado financeiro e afetam LL/FCFE/caixa. Empresa com passivo de
  arrendamento < 1% do ativo → bloco inteiro zera (sem erro).
- **Alternativas:** subtrair o direito de uso do imobilizado e depreciar cada um
  por safra (correto, mas exige desmembrar 1.02.03 na coleta/limpeza — ripple
  amplo, fica para o backlog); ignorar leasing na D&A (perde a abertura).

### D-043 ⏳ — Intangível vira linha própria (amortiza) para o balanço fechar

- **Situação:** ao amortizar o intangível (novo em 8.2), o FCO devolvia a
  amortização mas o balanço mantinha o intangível CONSTANTE dentro de
  `outros_ativos` → o balanço deixava de fechar (diferença = amortização
  acumulada; ex.: DIRR3 platô em 33.063 = intangível do Ano 0).
- **Escolha:** o intangível passa a ser uma LINHA PRÓPRIA do balanço projetado
  (declina pela amortização) e sai do residual `outros_ativos`. Com isso o
  balanço volta a fechar por construção (dif ~0 nos 8 anos, verificado). O
  DFC/BP aberto completo continua sendo do Prompt 8.3.
- **Alternativas:** não amortizar intangível (contraria a D&A aberta do 8.2);
  reconstruir o DFC/BP completo agora (é o Prompt 8.3).

### D-044 ⏳ — Passivo de arrendamento SOMADO das sub-contas (fonte única do bridge)

- **Situação:** `selecionar_ultimo_exercicio` devolve UMA linha (código mais
  curto). O passivo de arrendamento vive em várias sub-contas (2.01.05.x CP +
  2.02.02.x LP); a linha mais curta às vezes é zero → MGLU3/SMFT3 liam passivo
  de arrendamento = 0 (subestimava a dívida líquida no bridge).
- **Escolha:** novo helper `somar_ultimo_exercicio` soma TODAS as sub-contas do
  mesmo exercício; usado no schedule de leasing E no `carregar_ano0_divida_balanco`
  (bridge) — fonte única, sem dupla contagem. O bridge passa a subtrair o passivo
  de arrendamento REAL (MGLU3 ~3,58 mi; SMFT3 ~6,27 mi; DIRR3 ~89 mil).
- **Alternativas:** manter a leitura de uma sub-conta (subestima o net debt).

### D-045 ⏳ — Regressão dourada da Semana 8.2 (mudanças EXPLICADAS de Target)

- **Números (preço de mercado congelado, mesmo rf da golden):**
  DIRR3 17,0418 → 16,8541 (−1,10%); MGLU3 8,1040 → 7,5200 (−7,21%);
  SMFT3 12,3617 → 18,6259 (+50,67%). Balanço fecha nos 3 (dif ~0).
- **Drivers, por ordem de materialidade:**
  1. **D&A por safra com vida derivada** (D-041): a vida derivada (DIRR3 3,22;
     MGLU3 3,98; SMFT3 7,22) é MENOR que a config (10) → D&A maior → mais tax
     shield no FCFF (modo legado) ou mais D&A somada no FCFF (modo completo).
  2. **Bridge com passivo de arrendamento somado** (D-044): reduz o equity
     (MGLU3 −3,58 mi; SMFT3 −6,27 mi; DIRR3 −0,09 mi) → puxa o Target para baixo.
  3. **Amortização do intangível** (D-043): novo componente de D&A (tax shield).
  4. Juros de arrendamento (D-042): afetam LL/FCFE/caixa, NÃO o FCFF/Target.
- **DIRR3 −1,1%** (leasing imaterial, imob pequeno): efeito líquido pequeno.
  **MGLU3 −7,2%**: bridge do leasing domina. **SMFT3 +50,7%** ver D-046.

### D-046 ⏳ — SMFT3 +50%: correção da D&A subestimada (modo completo) + premissas auto

- **Situação:** SMFT3 salta 12,36 → 18,63 (+50,67%). É um caso de estresse
  (leasing gigante, muita D&A, MODO COMPLETO, premissas AUTOMÁTICAS).
- **Diagnóstico (não é bug):** no modo completo o EBIT sai das margens (D&A
  embutida em CPV/SG&A) e o FCFF SOMA a D&A memo de volta. A 8.1 usava vida 10
  (config) → D&A do estoque = 12,7 mi/10 = 1,27 mi, ABAIXO da D&A histórica real
  (1,76 mi). A 8.2 deriva a vida (7,22 = imob/D&A histórica) → a D&A do estoque
  REPRODUZ a histórica (1,76 mi) + safras de capex novo → FCFF maior. Ou seja, a
  8.1 SUBESTIMAVA a D&A e a 8.2 corrige para a taxa real. O salto é a correção,
  amplificada pela alavancagem FCFF→EV e por premissas de partida agressivas.
- **Ação recomendada ao humano:** SMFT3 continua com `premissas_automaticas`
  (REVISAR); o Target não é tese. Revisar crescimento/margens e, se quiser um
  D&A menos "bull", informar `prazo_medio_leasing_anos`/margens na aba Premissas.
- **Alternativas:** travar a vida na config (esconde a D&A real); só tax shield
  no modo completo (contraria o desenho 8.1 de D&A como add-back).

---

## 14/07/2026 — Prompt 8.1 (DRE completa) + descope do revolver formal

> Sessão do **Claude Code** a pedido de Lucas: (1) retirar do `PROMPTS_FABLE.md`
> (e demais locais do plano) a NECESSIDADE de um revolver formal no DCF; (2)
> implementar o Prompt 8.1 — DRE completa bruta→líquida com CPV/SG&A separados,
> imposto efetivo e D&A aberta. Código de motor tocado (projetor_dre, schedule_ppe,
> schedule_divida, gerador_premissas) + configs + testes. Golden DIRR3/MGLU3
> preservada byte a byte.

### D-036 ⏳ — Revolver formal FORA DE ESCOPO (supera a parte de revolver da D-032/D-027)

- **Situação:** a D-032 (13/07) tinha decidido FORMALIZAR um revolver (juros
  próprios + amortização automática, bloco `revolver` separado, spread em config)
  como evolução da captação automática v2. Lucas pediu em 14/07 para **retirar essa
  necessidade** do `PROMPTS_FABLE.md`, do README e de qualquer outro local que
  dissesse que "haverá revolver no DCF".
- **Escolha:** o projeto **NÃO implementa revolver formal**. A **captação automática
  para caixa mínimo** que a v2 já tem (`caixa_minimo_pct_receita`, D-015) permanece
  como o mecanismo de fechamento de caixa SEM plug — a captação entra na dívida
  estrutural e paga juros por Kd em t+1. Editado no `PROMPTS_FABLE.md`: tabela de gap
  (linha 10), Prompt 8.3 (título, contexto, objetivo, 8.3.2, DFC, BP, contratos, DoD,
  testes) e todas as referências cruzadas em 8.1/8.2/9.1/9.2/9.3/10.1/10.2. Onde o
  Smartfit usa "Revolver", o plano passa a usar a captação automática v2.
- **Referências IMUTÁVEIS não alteradas (Princípio 14):** `referencias/README.md` e
  `referencias/modelos_excel/ESTRUTURA_SMARTFIT.md` descrevem FATUALMENTE o modelo do
  mentor (que TEM um revolver) — não são "o nosso DCF", então a descrição foi mantida
  intacta. O `CONTEXT.md` (log histórico da sessão 13/07) idem; o descope fica
  registrado na sessão nova de 14/07.
- **Alternativas:** manter a D-032 (contraria o pedido explícito); apagar toda menção
  a revolver, inclusive dos mapas de referência (falsificaria a descrição do modelo do
  mentor — vetado pela imutabilidade das referências).

### D-037 ⏳ — DRE completa: detecção de modo por premissa definidora (retrocompat)

- **Situação:** trocar "receita líquida × margem EBITDA" pela DRE completa não pode
  quebrar a golden de DIRR3/MGLU3 nem os arquivos de premissas v2.
- **Escolha:** o `projetor_dre` roda no **modo completo** SOMENTE quando o arquivo de
  premissas traz as duas premissas definidoras — `margem_bruta_ano1` E
  `sgna_pct_receita_ano1`. Sem elas, roda no **modo legado** byte a byte (path atual
  intocado). O modo é persistido em `modo_dre` no JSON de projeção e propagado aos
  schedules. **Verificado:** DIRR3 17.041750319793266 e MGLU3 8.104037755921702
  IDÊNTICOS (diff 0.0) com premissas v2 e mercado congelado; a DRE ano1 é byte a byte.
- **Cadeia no modo completo:** a D&A já está embutida em CPV/SG&A (como no Smartfit
  L68-69) ⇒ o EBIT sai direto das margens; o `schedule_ppe` no modo completo apenas
  preenche `da_imobilizado` e faz `EBITDA = EBIT + D&A` (não recalcula EBT/IR/LL); o
  `schedule_divida` recompõe EBT com o resultado financeiro e o IR pelo modo da DRE
  completa.
- **Alternativas:** migração forçada (quebra golden e premissas antigas); duplicar o
  projetor (dobra manutenção).

### D-038 ⏳ — SG&A separa Outras e Equivalência (evita dupla contagem)

- **Situação:** o Prompt 8.1.1 descreve `sgna_pct` como "3.04 comerciais + G&A +
  outras, excluindo equivalência", mas o quadro da DRE (8.1.2) tem linhas SEPARADAS
  para SG&A, Outras receitas/despesas e Equivalência. Somar "outras" dentro de SG&A E
  ter uma linha `outras_despesas_pct_receita` contaria "outras" duas vezes no EBIT.
- **Escolha:** no motor e no gerador, `sgna` = apenas comerciais + G&A (3.04.01 +
  3.04.02); `outras_despesas_pct_receita` = 3.04.03/04/05 (impairment + outras rec/desp
  operacionais, com sinal); `equivalencia_pct_receita` = 3.04.06. Assim
  `EBIT = LucroBruto + SG&A + Outras + Equivalência` reconstrói o EBIT sem dupla
  contagem. Registrado por divergir da leitura literal do texto do prompt.

### D-039 ⏳ — Defaults setoriais da DRE completa em bloco único no setores.json

- **Situação:** o Prompt 8.1.4 pede defaults setoriais de `margem_bruta`/`sgna` para o
  gerador. Adicionar 2 chaves em cada um dos 16 `premissas_default` geraria um diff
  ruidoso (o `json.dump` reflow quebraria arrays `peers`/`vetor_sensibilidade`).
- **Escolha:** um bloco novo `defaults_dre_completa` (subtipo → {margem_bruta,
  sgna_pct_receita}) em `config/setores.json` — uma edição contígua, sem tocar nos
  blocos existentes. O gerador usa a média histórica quando disponível e cai nesses
  defaults. Clamps/defaults globais (aliquota efetiva [15%,45%], marginal 34%, modo)
  em `config/parametros.json` (`dre_completa`).

### D-040 ⏳ — SMFT3 classificada como "outros"; alíquota default marginal

- **Situação:** o setor CVM da Smart Fit é "Brinquedos e Lazer", que não tem regra em
  `mapa_setor_cvm` → subtipo `outros` (FCFF/WACC, default seguro). O gerador default
  usa `modo_aliquota = "marginal"` (34%), não a efetiva histórica.
- **Escolha:** manter `outros` (nenhum subtipo existente descreve academia melhor que
  o balde genérico; mapear errado seria pior) e `marginal` como default conservador
  (padrão de `parametros.json`; o analista liga `efetiva_historica` se quiser — o
  `aliquota_efetiva` histórico já é gravado na premissa). **Resultado SMFT3 (premissas
  automáticas, REVISAR):** Target R$ 12,36 · VENDA · score 95 · modo_dre completo ·
  balanço fecha (dif 0,0) · DRE bruta→líquida→CPV→SG&A→EBIT→EBITDA→EBT→LL coerente.

---

## 13/07/2026 — Planejamento da v2.1 "Padrão Smartfit" (novo Excel de referência do mentor)

> Sessão do **Claude Code**: análise do modelo Smartfit enviado pelo mentor,
> comparação com o da Direcional e com o código atual, reorganização dos
> arquivos de referência e reescrita completa do `PROMPTS_FABLE.md` para as
> semanas 8–10. Nenhum código de motor/app/exportador foi tocado — só
> planejamento e documentação. As decisões abaixo (D-027 a D-035) orientam o
> Fable 5 nas semanas 8–10 e podem ser revertidas pelo humano.

### D-027 ⏳ — Adotar a MECÂNICA do Smartfit, adiar o UNIT ECONOMICS para a v3.0

- **Situação:** o mentor disse "é assim que tem que ser feito — através de unit
  economics", mas o Lucas decidiu (mensagem de 13/07) começar por premissas
  básicas (crescimento %, margens %, capex %) porque unit economics exige um
  método específico por setor que ele ainda precisa aprender e receber mais
  exemplos.
- **Escolha:** as semanas 8–10 adotam TODO o resto da mecânica do Smartfit
  (DRE completa bruta→líquida, IFRS-16, D&A por safra, revolver, DFC indireto,
  BP aberto, retornos TIR/MOIC, Excel de 9 abas) usando premissas básicas; o
  build-up por unit economics fica para a v3.0. No Prompt 8.1 a projeção de
  receita é extraída para uma função plugável (`projetar_receita`) para que a
  v3.0 encaixe o build-up setorial sem reescrever a DRE.
- **Alternativas:** (a) implementar unit economics já (bloqueia — falta método
  setorial e exemplos); (b) ignorar o Smartfit e manter a v2.0 (perde o
  benchmark novo). Registrado como o caminho pragmático que preserva o alvo.

### D-028 ⏳ — Numeração por SEMANAS de calendário, não por "ondas"

- **Situação:** o humano pediu que daqui para frente o planejamento use
  semanas datadas (8 = 12–19/07, 9 = 19–26/07, 10 = 26/07–02/08) e que o
  `PROMPTS_FABLE.md` seja reescrito do zero até a semana 10 (02/08).
- **Escolha:** `PROMPTS_FABLE.md` reescrito com 8 prompts (8.1–8.3, 9.1–9.3,
  10.1–10.2) mapeados às 3 semanas; a nomenclatura "v2.0 Universalização /
  Ondas 1–5" foi encerrada e substituída por "v2.1 Padrão Smartfit". O
  histórico das Ondas 1–4 (concluídas) permanece no `CONTEXT.md`.
- **Alternativas:** manter "Ondas" (contraria o pedido); recomeçar a contagem
  de semanas em 1 (perde a continuidade com as semanas 1–7 já existentes no
  histórico do projeto).

### D-029 ⏳ — Excels de referência movidos para `referencias/modelos_excel/`

- **Situação:** o Smartfit estava solto na raiz do repo; o da Direcional vivia
  em `tests/fixtures/`. O humano pediu um lugar canônico que sirva de
  referência para o Claude Code / Codex, sem ficar solto.
- **Escolha:** criado `referencias/` (com `README.md`) e
  `referencias/modelos_excel/` contendo os DOIS xlsx + um `ESTRUTURA_*.md`
  para cada (mapa por aba/linha extraído com openpyxl) + o mentor/legenda. O
  Smartfit foi renomeado para `Smartfit_SMFT3_referencia.xlsx` (padrão do da
  Direcional). Movimentação via `git mv` (preserva histórico). Referências em
  `CONTEXT.md`, `README.md` e `CLAUDE.md` atualizadas.
- **Verificação:** nenhum teste depende do arquivo da Direcional (os testes
  usam fixtures sintéticas); `grep` confirmou que só docs citavam
  `tests/fixtures/...xlsx`. Sem quebra de teste esperada pela mudança.
- **Alternativas:** deixar em `tests/fixtures/` (mistura material de
  referência com fixtures de teste); duplicar (arquivos xlsx grandes no git).

### D-030 ⏳ — Ticker de referência do Smartfit: `SMFT3`

- **Situação:** o modelo do mentor avalia a Smart Fit; o pipeline identifica
  empresas por ticker B3. A Smart Fit negocia como **SMFT3**.
- **Escolha:** usar `SMFT3` como o ticker da empresa de referência da v2.1 (o
  arquivo de referência e os DoDs das semanas 8–10 citam SMFT3). O Fable deve
  confirmar na primeira coleta que o resolvedor de ticker encontra SMFT3 na
  CVM (Smart Fit Escola de Ginástica e Dança S.A.); se o código CVM divergir,
  registrar e ajustar.
- **Risco a checar pelo humano/Fable:** SMFT3 fez IPO em 2021 — deve ter ≥ 3
  exercícios anuais na CVM (2022–2024), suficiente para as âncoras. Confirmar
  no Prompt 8.1.

### D-031 ⏳ — DRE completa é OPCIONAL/retrocompatível (modo legado preservado)

- **Situação:** trocar "receita líquida × margem EBITDA" por uma DRE completa
  (bruta→líquida, CPV, SG&A separados) poderia quebrar a regressão dourada de
  DIRR3/MGLU3 e os arquivos de premissas v2 já existentes.
- **Escolha:** o Prompt 8.1 mantém DOIS modos: **legado** (arquivo v2 só com
  `margem_ebitda_ano1..8` → caminho atual byte a byte) e **completo** (campos
  novos presentes → DRE Smartfit). O `gerador_premissas.py` passa a gerar
  sempre o conjunto completo; a regressão dourada roda no modo legado. Todo
  campo novo de premissa é opcional (Princípio 13 novo).
- **Alternativas:** migração forçada (quebra golden e premissas antigas);
  duplicar o projetor (dobra manutenção).

### D-032 🔁 REVERTIDA (ver D-036) — Dívida por instrumento é OPCIONAL; target-leverage vira backlog

- **Situação:** o Smartfit modela ~45 instrumentos de dívida em várias moedas
  e uma dívida-alvo = alavancagem × EBITDA. Reproduzir isso como obrigatório
  seria inviável para "qualquer empresa da B3" automaticamente.
- **Escolha:** no Prompt 8.3, a tabela de instrumentos é OPCIONAL nas
  premissas (o analista copia das notas explicativas, já em BRL); sem ela, o
  perfil CP/LP agregado da v2 continua. A dívida-alvo por alavancagem e a
  conversão automática de moeda vão para o backlog (Apêndice C). O REVOLVER,
  esse sim, é formalizado (juros próprios + amortização) porque generaliza a
  captação automática que a v2 já tem.
- **Alternativas:** exigir instrumentos (não escala); ignorar o revolver
  (perde o fechamento de caixa sem plug que é a espinha do modelo).

### D-033 ⏳ — Traduzir D@G/AVP (deal de PE) para "Retornos do acionista"

- **Situação:** as abas D@G e AVP do Smartfit são de private equity (cap
  table, money-in/out, sources & uses, diluição, TIR do fundo) — não se
  aplicam a equity listado.
- **Escolha:** o Prompt 9.1 cria um painel de **Retornos do acionista**:
  múltiplos implícitos por ano (no preço atual e no target) + TIR/MOIC de
  comprar ao preço atual e realizar o target no ano N (com dividendos). A
  mecânica de deal (cap table/sources&uses/diluição) é descartada.
- **Alternativas:** copiar D@G/AVP literalmente (produz números sem sentido
  para ação listada); omitir retornos (perde uma camada que o mentor valoriza).

### D-034 ⏳ — Excel novo: 9 abas para NÃO-financeiras; bancário fica no backlog

- **Situação:** o exportador atual tem 7 abas (FCFF). O Smartfit sugere mais
  abas (Capa+legenda, controle, Macro, Build-Up, Model 3-statements, DCF &
  Retornos). Bancos usam FCFE e não têm dívida operacional/leasing como
  não-financeiras.
- **Escolha:** o Prompt 9.3 reescreve o Excel para 9 abas cobrindo QUALQUER
  não-financeira; bancos mantêm o caminho atual (Excel FCFF bloqueado com
  aviso no app) e o Excel bancário vai para o backlog v2.2. O
  `dfc_simplificado` legado é removido no 9.3 (consumidores migram para o DFC
  indireto).
- **Alternativas:** Excel único para os dois tipos (complexo e arriscado
  agora); manter 7 abas (não alcança o padrão Smartfit).

### D-035 ⏳ — Semana 10 é AUDITORIA dupla (Excel recalculado + app no navegador)

- **Situação:** o humano pediu explicitamente 4 provas: (2) código sem erro
  com dados automatizados; (3) front-end correspondendo; (4) Excel gerado
  correto em valores/fórmulas/referências/premissas/comentários/cores; (5)
  funcionar para qualquer empresa e premissa→efeito.
- **Escolha:** o Prompt 10.1 cria um `verificar_excel.py` que ABRE o Excel,
  RECALCULA de verdade (Excel COM/LibreOffice) e confere célula a célula
  contra os JSONs, mais auditoria de cores/comentários/consistência de fórmula
  e paridade estrutural com o Smartfit; o 10.2 amplia o lote B3 (≥12 empresas,
  casos de borda) e adiciona `test_premissa_efeito.py` (edita 1 premissa →
  verifica a cadeia até o Excel). É o custo de garantir "zero erro".
- **Alternativas:** confiar nos testes unitários (não pega erro de fórmula no
  Excel real); validação só manual (não repetível).

**Observação sem decisão nova:** os itens do "To do list" e "Considerações" do
próprio modelo do mentor (D&A de leasing/imob "muito alta", "checar revolver",
"net debt muito alto", "EBITDA desproporcional") são limitações CONHECIDAS do
modelo dele — não do nosso código. Foram usados apenas para entender a
mecânica; não são tarefas do projeto.

---

## 13/07/2026 — Validação completa das Ondas 3–4 (suíte + auditoria + figuras + app no navegador)

### D-025 ⏳ — Painel de decisão passa a mostrar a taxa e o g do CENÁRIO ativo

- **Situação:** na validação visual do app, o Overview com cenário Bear/Bull
  ativo mostrava Target/upside/recomendação do cenário, mas WACC (ou Ke) e g
  do caso BASE — mesmo com o bloco `cenarios` persistindo `taxa_desconto` e
  `g` próprios por cenário (ex.: DIRR3 Bull = 13,90%/1,5% vs base
  14,97%/1,0%). Os cinco KPIs da mesma linha contavam histórias mistas.
- **Escolha:** `painel_decisao` (app.py) usa `taxa_desconto`/`g` do cenário
  ativo quando presentes, com fallback no caso base. Validado no navegador:
  Bull mostra 13,90%/1,50%. A figura "Dashboard Executivo" logo abaixo
  permanece SEMPRE no caso base — ela é a arte persistida do motor e está
  rotulada como tal ("fonte unica: motor de calculo").
- **Alternativas consideradas:** manter tudo no base com os deltas apenas no
  caption (estado anterior — KPI inconsistente com o Target exibido);
  regenerar a figura executiva por cenário (recálculo/arte no front-end,
  contra o contrato "o app apenas apresenta o persistido").

### D-026 ⏳ — Escape de `$` no metric da faixa de múltiplos (bug visual real)

- **Situação:** o metric "Faixa por multiplos (Q1-Q3)" concatena DUAS moedas
  na mesma string ("R$ 10,72 - R$ 19,65"). O `st.metric` renderiza o valor
  como markdown, e um PAR de `$` vira delimitador de math inline: a tela
  mostrava "R 10,72 - R 19,65" com o trecho central em fonte de código
  (confirmado no DOM: `<code class="language-math">`). Único ponto do app
  com duas moedas numa string (auditado por grep).
- **Escolha:** escapar `$` → `\$` apenas nesse metric, com comentário no
  código explicando a restrição. Validado no navegador: "R$ 10,72 - R$
  19,65" literal, zero elementos math.
- **Alternativas consideradas:** mudar `formatar_moeda_brl` globalmente
  (vazaria `\$` literal em Plotly/Excel, que não passam por markdown);
  trocar o formato da faixa para evitar o segundo `R$` (perde o padrão
  visual das demais moedas do app).

**Observações sem decisão nova (não são erros novos):** (1) preço atual
divergente entre seções — 13,01 no painel (ev_equity, mercado congelado de
08/07) vs 13,28 nos comparáveis (coletado em 12/07) — é a consequência já
registrada em D-011/D-022; a Onda 5 (orquestração/automação de dados)
sincroniza as datas de mercado. (2) A validação rodou o pipeline completo de
RENT3 pelo próprio app (21,1s, score 96, VENDA −46,6% por premissas
automáticas conservadoras — padrão já registrado em D-024); os artefatos de
dados de RENT3 ficaram no working tree.

---

## 12/07/2026 — Onda 2 (Prompt 2, executada ANTES das Ondas 3–4 por ordem do humano)

### D-014 ⏳ — Correção do sinal do CAPEX no PP&E (bug real da v1)

- **Situação:** na v1, `schedule_ppe` somava o CAPEX ASSINADO (negativo) ao
  imobilizado — o ativo ENCOLHIA a cada investimento e o caixa-plug absorvia
  a inconsistência em silêncio. Com o caixa vindo do DFC (v2), o balanço
  passou a vazar exatamente 2×|capex| por ano.
- **Escolha:** PP&E_t = PP&E_(t-1) + |CAPEX_t| − D&A_t (ativo cresce pela
  magnitude; o capex segue persistido assinado por convenção de caixa).
- **Impacto na regressão dourada:** D&A projetada agora cresce com o ativo
  → EBIT menor, mas FCFF maior (tax shield da D&A) → Target Price sobe
  (DIRR3 15,25→17,04; MGLU3 5,97→8,10 — ver D-022).

### D-015 ⏳ — Convenção de saldo inicial para juros e receita financeira

- **Situação:** juros dependem da dívida, que depende da captação, que
  depende do caixa, que depende dos juros (circularidade clássica).
- **Escolha:** juros = Kd × dívida de ABERTURA; receita financeira = taxa ×
  (caixa inicial + aplicações); captação entra no FIM do ano (não paga juros
  no próprio ano). Sem iteração, sem circularidade, documentado no módulo.
- **Alternativas:** iterar 2–3 passadas (converge, mas o Excel espelho vira
  referência circular); saldo médio com captação (circular).

### D-016 ⏳ — Balanço ancorado no BP real: residuais constantes + verificação

- **Situação:** o caixa deixou de ser plug; o fechamento precisa nascer da
  contabilidade, não de um resíduo forçado.
- **Escolha:** `outros_ativos`/`outros_passivos` = residuais do BP REAL do
  Ano 0 (intangível, RLP, provisões etc.), constantes na projeção; caixa =
  resultado do DFC; `Ativo = Passivo + PL` vira VERIFICAÇÃO (alerta + NF1,
  nunca raise silencioso). Com residuais constantes o fechamento é exato
  por construção — desvio indica premissa/dado quebrado.
- **Alternativas:** projetar cada linha residual (escopo de modelo completo
  por setor, sem dado que sustente); manter plug (esconde erros — vetado
  pela spec).

### D-017 ⏳ — Trilha bancária: calibração pela margem líquida + clamp de alíquota

- **Situação:** a alíquota efetiva histórica de banco na DFP é ruidosa (JCP
  e participações estatutárias distorcem 3.06/3.05 — BBAS3 media 74,5%!), e
  linhas intermediárias (equivalência, participações) não são projetadas.
  Com as âncoras cruas, o Target do BBAS3 saía R$ −10,50.
- **Escolha:** (a) alíquota bancária clampada em [20%, 50%], senão padrão
  45% da config; (b) razão de despesas operacionais CALIBRADA para
  reproduzir a margem líquida média histórica: desp = ML/(1−t) − margem_RB.
  O desvio das linhas não projetadas é absorvido na linha de despesas, e o
  ano 1 projetado reproduz a lucratividade REAL do banco.
- **Resultado:** BBAS3 Target R$ 40,77 (+98% — premissa de partida
  agressiva, ordem de grandeza correta); ITUB4 R$ 54,33 (+22,6%).

### D-018 ⏳ — Capital regulatório retido nunca é liberado

- **Situação:** FCFE = LL − ΔCapital exige política para o excesso de
  capital do Ano 0 (PL real > mínimo regulatório).
- **Escolha:** capital_0 = max(PL real, mínimo); capital_t = max(mínimo_t,
  capital_(t-1)) — o banco não devolve capital já constituído de uma vez
  (evita FCFE ano-1 inflado por "liberação" irrealista) nem deixa o índice
  cair. RWA por proxy: fator_rwa × ativos, com ativos crescendo com as
  receitas (a DFP não expõe RWA real).
- **Alternativas:** liberar excesso no ano 1 (agressivo); payout fixo sobre
  LL (ignora exigência de capital).

### D-019 ⏳ — Cenários: delta de taxa aplicado ao bloco persistido

- **Situação:** WACC/Ke nascem de beta/Kd/estrutura — não são premissas
  diretas; o cenário pede "WACC +1pp".
- **Escolha:** o motor_cenarios roda o pipeline com premissas ajustadas
  (crescimento×fator, margem+Δ, g+Δ) e aplica o Δ de taxa AO BLOCO
  persistido antes de VT/EV; preço e Rf vêm do JSON de mercado (congelados,
  reproduzíveis — nada de preço vivo em cenário). Premissas do analista são
  restauradas SEMPRE (backup + finally) e o disco termina no caso base.

### D-020 ⏳ — VT financeiro: payout sustentável e compatibilidade do checklist

- **Situação:** FCFE_8 pode ser ≤ 0 (crescimento consumindo capital); e o
  checklist universal (U1/U4) lê a taxa do campo `wacc`.
- **Escolha:** base do VT = FCFE_8; se ≤ 0, usa LL_8 × (1 − g/ROE_8)
  (payout sustentável de Damodaran) com aviso e `base_vt` explicitando; o
  `valor_terminal` financeiro persiste o Ke TAMBÉM sob a chave `wacc` com
  `taxa_desconto_rotulo` explicando (compat sem duplicar o checklist).

### D-021 ⏳ — Convenção de desconto e alíquota do NOPAT

- **Escolha:** mid-year e período-stub implementados como config global
  (`desconto`), DEFAULT DESLIGADO (golden preservada); aplicados no motor
  (VT/EV/FCFE) mas NÃO nas derivações rápidas do `apoio_cenarios` (heatmaps
  continuam fim-de-período — divergência só existe se o humano ligar a
  convenção). NOPAT segue alíquota MARGINAL 34% (efetiva fica nas métricas
  como âncora; motivo documentado no código).

### D-022 ⏳ — Regressão dourada da Onda 2 (mudanças EXPLICADAS de Target Price)

- **Números (preço de mercado congelado de 08/07):** DIRR3 R$ 15,25 → 17,04
  (+11,7%); MGLU3 R$ 5,97 → 8,10 (+35,7%); balanço fecha (dif < 1e-6) e
  checklists aprovados nos dois.
- **Drivers, na ordem de materialidade:** (1) correção do PP&E (D-014):
  D&A cresce com o ativo → tax shield maior no FCFF; (2) dívida amortizando
  → dívida média menor → WACC DIRR3 16,63%→~14,9% (e bridge subtrai dívida
  do Ano 0 real incluindo leasing); (3) bridge completo com minoritários,
  coligadas e leasing reais (antes zerados); (4) RET da DIRR3 agora sobre
  Receita Bruta real (razão RB/RL da DVA) — imposto maior que o proxy;
  (5) payout real e receita financeira sobre caixa mudam FCFE/caixa (não o
  FCFF). MGLU3 é mais sensível por alavancagem operacional + leasing alto.
- **Validação numérica final é do humano** (comparar com RI/consenso).

## 12/07/2026 — Sessão "Ondas 3 e 4" (Prompts 3 e 4 do PROMPTS_FABLE.md)

### D-001 ⏳ — Pular a Onda 2 e executar as Ondas 3 e 4

- **Situação:** o humano pediu explicitamente os Prompts 3 e 4, mas o
  `PROMPTS_FABLE.md` define as ondas como progressivas e sequenciais ("não
  pule etapas") e os Prompts 3–4 citam dependências da Onda 2 (motor de
  cenários Bear/Base/Bull de primeira classe, trilha FCFE/Ke validada para
  bancos).
- **Escolha:** executar 3 e 4 agora, adaptando os pontos dependentes da
  Onda 2 (ver D-002, D-003, D-004) e registrando cada adaptação.
- **Alternativas:** (a) executar a Onda 2 primeiro — contraria o pedido
  explícito; (b) recusar parcialmente — pior das opções, não entrega nada.
- **Justificativa:** a "Regra de precedência" do próprio `PROMPTS_FABLE.md`
  diz que o pedido explícito do humano vence, desde que a IA avise sobre o
  conflito — este registro é o aviso. A Onda 2 fica pendente e recomendada
  como próximo passo.

### D-002 ⏳ — Football Field sem o motor de cenários da Onda 2

- **Situação:** o Prompt 3 pede DCF Bear/Base/Bull "agora do motor de
  cenários da Onda 2", que não existe.
- **Escolha:** manter as barras DCF Bear/Base/Bull derivadas de
  `apoio_cenarios.recalcular_cenario` (aproximação v1 documentada) e trocar
  apenas os comps placeholders por comps reais — o objetivo central da onda.
- **Alternativas:** implementar `motor_cenarios.py` completo agora (escopo
  da Onda 2 inteira); remover as barras de cenário.
- **Justificativa:** o placeholder eliminado era o dos comps; os cenários
  v1 já são calculados a partir do resultado do motor (fonte única).

### D-003 ⏳ — ITUB4 no DoD da Onda 3 sem trilha FCFE validada

- **Situação:** o DoD pede Football Field para ITUB4, mas banco não tem
  valuation DCF antes da Onda 2 (não há `ev_equity` para ITUB4).
- **Escolha:** tornar as barras do Football Field **opcionais por
  disponibilidade de dados**: para ITUB4 renderizam comps reais (P/VP, P/L),
  faixa de 52 semanas e preço atual, SEM as barras DCF; o app explica que a
  trilha FCFE chega na Onda 2.
- **Alternativas:** falhar para ITUB4 (quebra o DoD); inventar um DCF
  bancário rápido (violaria a regra de não fazer valuation errado por tipo).
- **Justificativa:** entrega o máximo de valor real sem produzir um Target
  Price sem sentido para banco — exatamente o erro que a v2.0 quer evitar.

### D-004 ⏳ — Premissas automáticas de partida para tickers novos

- **Situação:** o DoD da Onda 4 exige que buscar um ticker novo (ex.:
  WEGE3, RADL3) rode o pipeline completo e renderize tudo; mas a filosofia
  do projeto diz que premissas são o trabalho intelectual do humano, e o
  `main.py` v1 PARA quando não há premissas revisadas.
- **Escolha:** criar `gerador_premissas.py`: premissas de partida geradas
  por âncoras históricas (CAGR, margem média, CAPEX médio, DSO/DIO/DPO) +
  defaults do subtipo (`config/setores.json`), com 8 valores individuais em
  interpolação linear (nunca taxa única replicada), marcadas com
  `premissas_automaticas: true` e alerta visível no app até o analista
  salvar premissas revisadas (o salvamento remove a flag).
- **Alternativas:** parar e pedir premissas (quebra o DoD e a UX);
  premissas nulas (pipeline falha); copiar as premissas de outra empresa
  (contaminação entre teses).
- **Justificativa:** preserva a filosofia (o humano continua dono da tese;
  o app deixa explícito que são premissas de PARTIDA) e destrava o fluxo
  universal exigido pela onda.

### D-005 ⏳ — `st.data_editor` no lugar de `streamlit-aggrid`

- **Situação:** o Prompt 4 pede tabelas editáveis "via streamlit-aggrid".
- **Escolha:** usar `st.data_editor` (nativo do Streamlit) para os vetores
  de premissas editáveis.
- **Alternativas:** `streamlit-aggrid` (continua instalado e disponível).
- **Justificativa:** o AgGrid é um componente customizado que não é
  testável via `AppTest` (o DoD exige testes verdes de app), tem tema
  próprio difícil de alinhar à paleta navy e quebra com atualizações do
  Streamlit; o `data_editor` é nativo, testável, respeita o tema e mantém a
  regra "editar célula → recalcular o motor Python". Troco por AgGrid se o
  humano preferir.

### D-006 ⏳ — Fonte dos múltiplos dos comparáveis

- **Situação:** o Prompt 3 permite "yfinance e/ou CVM" para os múltiplos.
- **Escolha:** múltiplos dos PEERS via yfinance (`trailingPE`,
  `priceToBook`, `enterpriseToEbitda`, `enterpriseToRevenue`; EV/EBIT
  calculado só quando o EBIT do peer está disponível na demonstração do
  yfinance); denominadores da EMPRESA-ALVO via CVM (Ano 0 oficial do
  pipeline). Peer sem dado → log e exclusão; múltiplo ≤ 0 → descartado com
  aviso; mediana exige ≥ 2 peers válidos (aviso de amostra pequena com < 3).
  A empresa-alvo é EXCLUÍDA da mediana do próprio peer group (padrão de
  mercado; evita viés circular) mas aparece na tabela destacada.
- **Alternativas:** calcular múltiplos dos peers pela CVM (exigiria coletar
  DFP de todos os peers — minutos por empresa e sem preço intradiário);
  incluir a própria empresa na mediana.
- **Justificativa:** yfinance dá múltiplos de mercado atuais em segundos e
  a CVM continua sendo a fonte dos fundamentos da empresa avaliada.

### D-007 ⏳ — Cenários no app antes da Onda 2

- **Situação:** o Prompt 4 pede "alternar Bear/Base/Bull recarrega todo o
  dashboard", mas cenários completos e persistidos são da Onda 2.
- **Escolha:** seletor de cenário no app aplicado aos KPIs de decisão,
  sensibilidades e Football Field via `apoio_cenarios` (derivação do caso
  base); o restante do dashboard continua no caso base até a Onda 2.
- **Alternativas:** reexecutar o pipeline inteiro por cenário a cada clique
  (custo alto e mistura premissas); esconder o seletor.

## 12/07/2026 — Auditoria da Onda 1 (Prompt 1, executado em 11–12/07)

### D-008 ⏳ — Ordem da cascata de mapeamento: nome ANTES de prefixo

- **Situação:** o Prompt 1 especificou a cascata como código → prefixo →
  nome → log; a implementação usa código → **nome** → **prefixo** → log.
- **Escolha:** manter nome antes de prefixo.
- **Justificativa:** agregados do DFC (6.01 = FCO) absorveriam por prefixo
  linhas de ajuste como "Depreciação e Amortização", que precisam do match
  por nome. A inversão está documentada no módulo e no mapeamento
  (`cascata.observacao`), com teste cobrindo o caso.

### D-009 ⏳ — Parquet limpo adotado só no Ano 0 do projetor (schedules no JSON bruto)

- **Situação:** o Prompt 1 diz "a partir da v2, a projeção lê Parquet
  limpo"; hoje o `projetor_dre` lê o Ano 0 do Parquet, mas os schedules
  WK/PP&E/Dívida ainda leem os JSONs brutos (fallback documentado).
- **Escolha:** migração parcial na Onda 1, completando na Onda 2 (que
  reescreve os schedules de qualquer forma).
- **Justificativa:** trocar a fonte de dados dos schedules sem reescrevê-los
  dobraria o risco de regressão da Onda 1; a regressão dourada exigia
  estabilidade. Registrado no CONTEXT como pendência.

### D-010 ⏳ — Arquivos de dados rastreados no git contra o .gitignore

- **Situação:** `data/raw/cvm/DIRR3_bp.json`, `DIRR3_dre.json` e
  `DIRR3_meta.json` foram commitados antes do `.gitignore` de dados e
  continuam rastreados — a recoleta os marca como modificados.
- **Escolha:** NÃO mexer no índice git (a divisão de trabalho do projeto
  diz que commits são do humano). Recomendação registrada: rodar
  `git rm --cached data/raw/cvm/DIRR3_bp.json data/raw/cvm/DIRR3_dre.json
  data/raw/cvm/DIRR3_meta.json` no próximo commit para o repositório seguir
  a própria convenção.
- **Alternativas:** executar o `git rm --cached` eu mesma (mexe no que vai
  para o GitHub sem aval humano).

### D-011 ⏳ — Preço ao vivo do yfinance no `calculador_ev`

- **Situação:** `obter_preco_atual` prioriza yfinance AO VIVO sobre o JSON
  de mercado persistido; o upside muda entre execuções (em 12/07 a MGLU3
  saiu de COMPRA para NEUTRO só porque a ação subiu de R$ 4,36 para 5,22).
- **Escolha:** manter o comportamento v1 (preço vivo) e registrar — preço
  atual de mercado é, por definição, vivo; o Target Price não é afetado.
- **Alternativas:** congelar no preço do JSON coletado (reprodutível, porém
  desatualizado); gravar a data/fonte do preço no resultado (feito: o
  `ev_equity` persiste o preço usado).
- **Impacto documentado:** comparações de upside entre execuções precisam
  considerar a data do preço.

### D-012 ⏳ — CONTEXT.md v1 desatualizado sobre a aba Excel Preview

- **Situação:** o CONTEXT dizia que a aba Excel Preview era "stub
  declarado", mas o `app.py` atual (commit "claude 6.2 parte 1", 11/07) já
  renderiza as 7 abas via `montar_preview_por_aba` + botão de download com
  testes verdes.
- **Escolha:** tratar o item 4.5 do Prompt 4 como JÁ ENTREGUE (só refinar),
  e corrigir a descrição no CONTEXT.
- **Justificativa:** evitar retrabalho; os testes
  `test_excel_preview_renderiza_7_abas` e `test_excel_preview_download_...`
  já cobrem o comportamento.

### D-023 ⏳ — Onda 4: escolhas do front-end multi-empresa

- **Situação:** o Prompt 4 deixa graus de liberdade na implementação do app.
- **Escolhas tomadas:** (a) sensibilidade "ao vivo" usa a derivação rápida
  do caso base (`apoio_cenarios`) — instantânea e sem recálculo em JS; o
  recálculo OFICIAL continua no botão Salvar (motor completo); (b) o
  seletor de cenários do Overview lê o bloco `cenarios` persistido (pipeline
  completo por cenário — o "recarrega todo o dashboard" da spec aplica-se
  aos KPIs de decisão; gráficos pesados seguem no caso base até a Onda 5);
  (c) watchlist em `data/watchlist.json` com snapshot de target/recomendação
  e timestamp (sem preço vivo); (d) Excel Preview bloqueado para financeiras
  com aviso (o exportador de 7 abas é FCFF; modelo bancário na Onda 5);
  (e) cache do app por mtime dos JSONs (recoleta só em ação explícita).
- **Alternativas:** recalcular o motor a cada movimento de slider (2s+ por
  interação); cenário recarregando todos os gráficos (recusa por latência).

### D-024 ⏳ — Premissas automáticas produzem casos extremos (para revisão)

- **Situação:** com premissas de PARTIDA automáticas, alguns resultados
  saem extremos: BBAS3 +98% (COMPRA), WEGE3 R$ 13,08 e RADL3 R$ 1,08
  (VENDA) contra preços de mercado muito acima.
- **Escolha:** manter os resultados persistidos COM a flag
  `premissas_automaticas` e o aviso permanente no app; a triangulação
  denuncia o descolamento ("DCF abaixo/acima da faixa dos múltiplos").
  Nenhum resultado automático é tese de investimento.
- **Alternativas:** calibrar premissas para convergir ao preço de mercado
  (inverte o propósito do DCF — vetado); esconder o valuation até revisão
  humana (esconde também o diagnóstico).
- **Ação recomendada ao humano:** revisar premissas de BBAS3, WEGE3 e RADL3
  na seção Premissas do app e salvar (remove a flag e assume a autoria).

### D-013 ⏳ — Classificação de "Emp. Adm. Part. - X" pelo segmento X

- **Situação:** a CVM registra operadoras consolidadas (ex.: WEG) como
  "Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças"; a regra de holding
  capturava tudo e WEGE3 virava `holding`.
- **Escolha:** look-through configurável (`prefixo_holding_cvm` em
  `config/setores.json`): classifica pelo segmento após o prefixo; holding
  só sem segmento reconhecível (ITSA4 "Sem Setor Principal"). Efeito
  colateral aceito: BRAP4 ("Emp. Adm. Part. - Extração Mineral") classifica
  como `mineracao` mesmo sendo holding pura da Vale — peers de mineração são
  mais úteis para ela do que um balde genérico de holdings.
- **Alternativas:** manter tudo como holding (esconde o negócio real);
  lista manual de exceções por ticker (não escala).
