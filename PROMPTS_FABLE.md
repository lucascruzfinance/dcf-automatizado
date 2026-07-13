# PROMPTS_FABLE.md — v2.1 "Padrão Smartfit" · Semanas 8–10 · 8 prompts progressivos para o Claude Fable 5

> **Público-alvo deste documento: o Claude Fable 5 (IA de implementação do projeto).**
> O Fable lê os documentos de contexto, escreve/edita o código Python e o front-end,
> roda os testes e atualiza o `CONTEXT.md`. O **humano (Lucas)** é o dono do julgamento
> analítico (premissas reais, validação numérica, commits) e o **Claude Code** é o
> gerador/curador destes prompts e o revisor final.
>
> **Como usar:** os 8 prompts abaixo são **progressivos e sequenciais**, organizados em
> 3 semanas de calendário. Cada prompt só começa depois que o anterior fechou a sua
> "Definição de Pronto". Cada prompt é auto-contido: reafirma o contexto, aponta as
> seções do modelo de referência, lista arquivos a criar/editar, especifica contratos
> e critérios objetivos de aceite. **Cole um prompt por vez no Claude Fable 5.**
>
> **Calendário (convenção de semanas fixada pelo humano em 13/07/2026):**
> | Semana | Período | Tema | Prompts |
> |---|---|---|---|
> | **8** | 12/07 → 19/07/2026 | Motor "Padrão Smartfit" (por dentro) | 8.1, 8.2, 8.3 |
> | **9** | 19/07 → 26/07/2026 | Apresentação: front-end guiado + Excel novo | 9.1, 9.2, 9.3 |
> | **10** | 26/07 → 02/08/2026 | Auditoria profunda + universalização B3 + fechamento | 10.1, 10.2 |
>
> **Regra de precedência:** se um prompt conflitar com `ROTEIRO.md`/`CONTEXT.md`, o
> pedido explícito do humano na sessão vence, mas o Fable avisa sobre o conflito antes
> de executar.
>
> **Protocolo de decisões autônomas (instrução permanente de Lucas, 12/07/2026):**
> diante de erro, ambiguidade, conflito ou escolha que caberia ao humano, o Fable NÃO
> para para perguntar: decide sozinho pela melhor opção, executa e registra em
> **`Humano_revisar.md`** (ID `D-nnn`, data, situação, escolha, alternativas,
> justificativa). O humano revisa e pode reverter qualquer decisão.

---

## 0. Contexto: onde estamos e o que esta fase persegue

### 0.1 Estado real do repositório (após as sessões de 12–13/07/2026)

A v2.0 "Universalização" fechou as **Ondas 1–4** (validadas em 13/07/2026, suíte com
135 testes verdes):

- **Coleta universal** (Onda 1): qualquer ticker da B3 → CD_CVM → DFP/ITR/DVA mapeadas
  por `CD_CONTA` → Parquet limpo + relatório de qualidade com score. 8 empresas no lote.
- **Motor universal por tipo** (Onda 2): não-financeiras FCFF/WACC com dívida
  amortizando, captação automática para caixa mínimo, receita financeira, payout real,
  caixa via DFC, bridge completo (minoritários/coligadas/IFRS-16), RET sobre receita
  bruta real; financeiras FCFE/Ke validadas (ITUB4/BBAS3); qualidade do lucro; cenários
  Bear/Base/Bull persistidos; mid-year/stub via config (default desligado).
- **Comparáveis reais** (Onda 3): peers por subtipo, múltiplos yfinance, triangulação.
- **Front-end multi-empresa** (Onda 4): 8 seções, pipeline por busca de ticker,
  premissas editáveis com validação, sensibilidade viva, comparação, watchlist.

A antiga "Onda 5" (Excel dinâmico por tipo, BI completo, Power BI, PDF, orquestração)
**não foi executada** e foi **redistribuída**: o que interessa ao novo padrão entra
nas semanas 8–10 abaixo; o restante virou backlog v2.2 (Apêndice C).

### 0.2 O novo benchmark: o modelo Smartfit do mentor

Em 13/07/2026 o mentor (Heitor Crespo, InFinance) enviou o **"Smartfit Model — PEP
2025.2 — Grupo 4"**, um modelo operacional 3-statements MAIS COMPLETO que o da
Direcional. Recado dele: *"Modelo tá mais bull, mas é assim que tem que ser feito —
através de unit economics."*

- Arquivo canônico: `referencias/modelos_excel/Smartfit_SMFT3_referencia.xlsx`
- **Mapa estrutural (LEIA ANTES DE QUALQUER PROMPT):**
  `referencias/modelos_excel/ESTRUTURA_SMARTFIT.md` — cada prompt cita as seções/linhas
  relevantes desse mapa. O modelo da Direcional e seu mapa estão na mesma pasta.

### 0.3 O que o Smartfit ensina e o projeto ainda NÃO tem (o gap desta fase)

| # | Mecânica do Smartfit | Estado no projeto hoje | Prompt |
|---|---|---|---|
| 1 | Receita **bruta** + deduções (% RB) na DRE projetada | Começa na líquida; RET usa razão RB/RL fixa | 8.1 |
| 2 | **CPV e SG&A projetados separadamente** (margem bruta + SG&A % receita) | Só margem EBITDA direta | 8.1 |
| 3 | Imposto por **alíquota efetiva % EBT** (opção) | Só marginal 34% / RET | 8.1 |
| 4 | **D&A aberta**: direito de uso × imobilizado × intangível | D&A única do PP&E | 8.1/8.2 |
| 5 | **IFRS-16 completo**: lease asset + lease liability + juros de arrendamento | Leasing só no bridge | 8.2 |
| 6 | **D&A por safra de CAPEX** (meia no 1º ano, para no saldo, vida derivada do histórico) | Taxa única `1/vida_util` global | 8.2 |
| 7 | Capex **expansão × manutenção** | Capex único % receita | 8.2 |
| 8 | **WK multi-driver**: clientes=dias de RB; fornecedores=dias de CPV; impostos=dias de deduções; salários=dias de SG&A | DSO/DIO/DPO ou % receita | 8.3 |
| 9 | **Dívida por instrumento** (saldo, taxa, moeda, curva, vencimento) | Perfil CP/LP agregado | 8.3 |
| 10 | **Revolver formal** (caixa mínimo % receita, juros CDI+spread, amortização automática) | Captação p/ caixa mínimo sem juros próprios/amortização | 8.3 |
| 11 | **DFC indireto COMPLETO** reconciliando cada linha do BP (blocos IFRS-16, impostos diferidos, WK, outros operacionais, capex, dividendos, OCI) + caixa BoP/EoP + FCO % EBITDA | DFC simplificado | 8.3 |
| 12 | **BP aberto linha a linha** (diferidos, depósitos judiciais, receita diferida…) com linha `Check` visível | BP mínimo com residuais agregados | 8.3 |
| 13 | **Aba Macro** (PIB, IPCA, IGP-M, Selic, CDI, câmbio; histórico + projeção) alimentando o modelo | Selic/IPCA/Focus coletados, sem bloco anual nem aba | 9.1 |
| 14 | **Retornos** (múltiplos implícitos de entrada/saída, TIR/MOIC — abas D@G/AVP) | Múltiplo de saída no checklist | 9.1 |
| 15 | Excel com **Capa+legenda, aba de controle ("To do list"), comentários, fundo de premissa, checks visíveis** | 7 abas nível Direcional | 9.3 |
| 16 | Front-end: fluxo do usuário **escolher → premissas → ajustar/ver → exportar** | 8 seções soltas | 9.2 |

### 0.4 O que fica DE FORA desta fase (decisão do humano em 13/07/2026)

1. **Unit economics setorial** (build-up por academias×clientes×ticket, coortes, curva
   de maturação — o "recado do mentor"): **v3.0**. Exige exemplos de outros setores e
   aprendizado do humano. As semanas 8–10 usam **premissas básicas** (crescimento %,
   margens %, capex %), mas a arquitetura deve **deixar o encaixe pronto** (a receita
   projetada vira função plugável — ver Prompt 8.1).
2. **Mecânica de deal de PE** (cap table, money-in/out, sources & uses, diluição):
   não se aplica a equity listado. A tradução útil (múltiplos implícitos + TIR/MOIC do
   acionista) entra no Prompt 9.1.
3. **Colunas trimestrais do ano corrente (1Q–4Q)**: backlog v2.2 (o pipeline usa o
   exercício anual como Ano 0; mid-year/stub já existe via config).
4. **BI/Power BI/PDF/orquestração em lote** (antiga Onda 5): backlog v2.2 (Apêndice C).
5. **Excel bancário completo**: bancos continuam com o caminho atual (aviso no app);
   o Excel novo desta fase é para NÃO-financeiras. Backlog v2.2.

---

## Princípios invariantes (valem para TODOS os prompts — releia sempre)

1. **Idioma do código:** funções, variáveis e comentários em **português**.
2. **Fonte única nos nomes:** toda coluna/campo novo registrado em
   `config/mapeamento_cvm.json`. O mesmo nome da coleta à exportação.
3. **Fonte única no cálculo:** o motor Python calcula UMA vez; Streamlit/Excel/BI
   apenas apresentam. Zero recálculo em JS/DAX. (No Excel, as fórmulas nativas devem
   REPRODUZIR o valor persistido — mecanismo `escrever_calculo` existente.)
4. **Sinais:** despesas/saídas negativas; receitas/entradas positivas.
5. **8 valores individuais** por vetor de premissa (`_ano1..8`). Nunca taxa única.
6. **Negativos são válidos** (ROIC/FCFF/LL). Não travar.
7. **Robustez CVM:** campo ausente/renomeado → log em `logs/`, fallback documentado,
   nunca quebra silenciosa. **Ausência de uma conta (ex.: leasing) NÃO é erro** — o
   schedule correspondente zera e some das saídas.
8. **Qualidade por etapa:** docstrings, comentário com fórmula financeira, `black`
   (`--workers 1`) e `flake8` limpos, pytest verde ANTES de fechar o prompt.
   Validação SEMPRE com a venv: `.venv/Scripts/python.exe -m pytest tests -q`.
9. **Configuração, não hard-code:** o que varia por setor/empresa vive em
   `config/*.json` ou nas premissas.
10. **Continuidade:** ao final de cada prompt, atualizar a Seção 8 do `CONTEXT.md`
    (sessão datada: o que foi feito, decisões, bugs, próxima tarefa) e registrar
    decisões autônomas em `Humano_revisar.md`.
11. **Design institucional:** paleta navy (`#0A1628`/`#0F1E33`/`#1B4F8C`), verde
    `#16A34A` = upside / vermelho `#DC2626` = downside (semântica estrita), texto sans,
    números mono. No Excel: convenção WSP + Smartfit — **azul = input, azul com fundo
    amarelo-claro `FFFFCC` = premissa do analista, preto = fórmula, verde = link entre
    abas** (legenda na Capa).
12. **Regressão dourada EXPLICADA:** DIRR3 e MGLU3 (e, a partir do Prompt 10.1, SMFT3)
    rodam antes/depois de cada prompt. Mudança de Target Price é aceitável SOMENTE se
    quantificada e explicada por driver (padrão D-022) no `CONTEXT.md` +
    `Humano_revisar.md`. Mudança inexplicada = bug.
13. **Compatibilidade de premissas (nova, crítica nesta fase):** todo campo novo de
    premissa é OPCIONAL. Arquivo de premissas antigo continua rodando: campo ausente →
    o gerador deriva default da âncora histórica (e grava a derivação em
    `origem_premissas`) ou o motor cai no comportamento v2 com aviso — nunca KeyError.
14. **Consulte as referências:** antes de implementar qualquer mecânica desta fase,
    leia a seção correspondente de
    `referencias/modelos_excel/ESTRUTURA_SMARTFIT.md` (e o xlsx via openpyxl quando
    precisar da fórmula exata). Os arquivos de `referencias/` são IMUTÁVEIS.

---
---

# PROMPT 8.1 — DRE completa: receita bruta→líquida, CPV+SG&A separados, imposto efetivo, D&A aberta (Semana 8 · 12–19/07)

## Papel e contexto

Você é o **Claude Fable 5**, IA de implementação do projeto **DCF Automatizado**.
Antes de escrever qualquer linha, leia integralmente: `CONTEXT.md` (Seção 8),
`CLAUDE.md`, os Princípios Invariantes deste arquivo,
`referencias/modelos_excel/ESTRUTURA_SMARTFIT.md` (seções "Aba Model — P&L" e
"Costs/SG&A Build-up"), `src/projecao/projetor_dre.py`,
`src/projecao/gerador_premissas.py`, `data/premissas/template_naofinanceiras.json`,
`config/mapeamento_cvm.json` e `config/setores.json`. Esta é a **primeira etapa da
v2.1 "Padrão Smartfit"** — Semana 8.

## Objetivo

A DRE projetada deixa de ser "receita líquida × margem EBITDA" e passa a ser uma
**demonstração completa no padrão do modelo Smartfit** (`Model !L19–L81`):

```
Receita Bruta
(−) Deduções                       [% da receita bruta, vetor 8 anos]
(=) Receita Líquida                [motor de crescimento continua aqui]
(−) CPV                            [via margem bruta, vetor 8 anos]
(=) Lucro Bruto
(−) SG&A                           [% da receita líquida, vetor 8 anos]
(+/−) Outras receitas/despesas     [% receita, escalar]
(+/−) Equivalência patrimonial     [% receita, escalar]
(=) EBIT
(+/−) Resultado financeiro         [continua vindo do schedule de dívida]
(=) EBT
(−) IR/CSLL                        [modo marginal (atual) OU efetivo % EBT]
(=) Lucro Líquido
Memo: D&A = direito de uso + imobilizado + intangível   [preparação p/ 8.2]
(=) EBITDA                         [derivado: EBIT + D&A]
```

## Referência no modelo Smartfit

- P&L: `Model ` L21–L81 (deduções L23–L24; segmentos L28–L34 — NÃO replicar agora,
  ver "encaixe v3.0" abaixo; imposto % EBT L64–L65; D&A aberta L72–L78; EBITDA L80).
- Custos por natureza: `Build-Up` L202–L290 (adotar apenas a SEPARAÇÃO CPV × SG&A
  nesta etapa; a quebra por natureza fica registrada como enriquecimento opcional).

## Especificação técnica detalhada

### 8.1.1 Premissas novas (todas opcionais — Princípio 13)

Estender `data/premissas/template_naofinanceiras.json`, o `gerador_premissas.py` e a
validação do `main.py`/app com os vetores (8 valores individuais cada):

- `deducoes_pct_receita_bruta_ano1..8` — default: média histórica de
  `1 − RL/RB` via DVA (razão que a Onda 2 já calcula para o RET); sem DVA → 0 com aviso.
- `margem_bruta_ano1..8` — default: média/tendência histórica (âncora das métricas).
- `sgna_pct_receita_ano1..8` — default: média histórica de SG&A/receita líquida
  (3.04 da CVM: comerciais + G&A + outras, EXCLUINDO equivalência).
- `outras_despesas_pct_receita` e `equivalencia_pct_receita` (escalares) — default:
  média histórica 3 anos (pode ser 0 quando não houver linha).
- `modo_aliquota`: `"marginal"` (default — comportamento atual 34%/RET) ou
  `"efetiva_historica"` (média % EBT dos anos com EBT>0, clamp [15%, 45%]) — padrão
  Smartfit `Model !N65`. Construtoras RET ignoram o modo (RET continua sobre RB).
- **Retrocompatibilidade:** `margem_ebitda_ano1..8` continua aceito. Se o arquivo de
  premissas tiver SÓ margem EBITDA (arquivos v2), o motor roda no **modo legado**
  (caminho atual intocado) e loga aviso. Se tiver os campos novos, roda no **modo
  completo** e PERSISTE também a margem EBITDA derivada (compat com consumidores).
  O `gerador_premissas.py` passa a gerar SEMPRE o conjunto completo.

### 8.1.2 Projetor de DRE (`src/projecao/projetor_dre.py`)

- Projeta as linhas novas na ordem do quadro acima, cada uma com nome padronizado
  REGISTRADO em `config/mapeamento_cvm.json` (`receita_bruta_projetada`, `deducoes`,
  `cpv_projetado`, `lucro_bruto`, `sgna`, `outras_receitas_despesas`,
  `equivalencia_patrimonial`, `aliquota_efetiva_usada`, `da_direito_uso`,
  `da_imobilizado`, `da_intangivel` — conferir/estender o catálogo `campos`).
- Receita bruta projetada = receita líquida projetada / (1 − deduções%). O RET da
  construção passa a usar ESTA receita bruta ano a ano (remove a razão fixa RB/RL).
- D&A: nesta etapa, `da_imobilizado` continua vindo do schedule PP&E;
  `da_direito_uso` e `da_intangivel` nascem zeradas (o 8.2 as preenche). O EBITDA
  persiste como EBIT + D&A total.
- O schedule de WK passa a receber o CPV projetado REAL (remove o proxy
  `cpv_ano0/receita_ano0` documentado na v1) quando o modo completo está ativo.

### 8.1.3 Encaixe para o unit economics (v3.0) — só a INTERFACE

- Extrair a projeção de receita para uma função única
  `projetar_receita(premissas, historico) -> serie_8_anos` no projetor. Hoje ela
  implementa apenas "crescimento % sobre o ano anterior". A v3.0 plugará aqui o
  build-up setorial (academias×ticket, VGV×POC etc.) SEM tocar no resto da DRE.
  Documentar isso na docstring. NÃO implementar nenhum build-up agora.

### 8.1.4 Config e mapeamento

- `config/parametros.json`: bloco `dre_completa` com os clamps/defaults citados.
- `config/setores.json`: defaults setoriais de `margem_bruta`/`sgna_pct_receita`
  para o gerador (subtipos existentes; valores plausíveis e documentados).

## Contratos de interface

- `data/processed/<TICKER>_projecao.json` → bloco `dre` ganha as linhas novas com
  nomes do mapeamento; blocos existentes (`fcff`, `wk`, `ppe`, `divida`, `balanco`,
  `dfc`) permanecem válidos.
- Consumidores (visualização/Excel/app) NÃO quebram com o bloco estendido (checar
  leitores que iteram chaves).

## Definição de Pronto (DoD)

- `python -m src.verificar_semana3` → `SEMANA 3 OK` (modo legado intocado).
- SMFT3 coletada e rodando ponta a ponta no modo completo com premissas geradas
  automaticamente (`python -m src.pipeline` ou busca no app) — Target Price existe e
  o bloco `dre` mostra bruta→líquida→CPV→SG&A→EBIT→EBT→LL com EBITDA derivado.
- DIRR3 no modo completo: RET calculado sobre a receita bruta PROJETADA ano a ano;
  diferença vs modo legado quantificada e explicada.
- **Regressão dourada:** DIRR3/MGLU3 com premissas v2 atuais (modo legado) produzem
  EXATAMENTE o mesmo Target Price de antes do prompt.
- `pytest tests -q` verde; `black --workers 1`/`flake8` limpos.

## Testes e validação

- `tests/test_projetor_dre.py` estendido: modo completo (bruta→líquida, CPV por
  margem bruta, SG&A, imposto efetivo com clamp), modo legado (arquivo v2 → mesmo
  resultado de antes), EBITDA derivado = EBIT + D&A.
- `tests/test_gerador_premissas.py`: gera conjunto completo com defaults históricos;
  interpolação com 8 valores individuais; arquivo sem DVA → deduções 0 + aviso.
- Teste de contrato: premissas v2 sem campos novos → sem KeyError, aviso logado.

## O que NÃO fazer

- NÃO implementar IFRS-16, safras de D&A, revolver ou DFC completo (Prompts 8.2/8.3).
- NÃO quebrar bancos (trilha FCFE não usa este projetor — não tocar).
- NÃO replicar a abertura por segmento/coorte do Smartfit (v3.0).
- NÃO mudar o front-end nem o Excel ainda (Semana 9) — apenas garantir que não quebram.

## Ao final

Atualizar `CONTEXT.md` (sessão datada, Semana 8 — Prompt 8.1) e `Humano_revisar.md`
com as decisões tomadas. Próxima tarefa: Prompt 8.2.

---
---

# PROMPT 8.2 — IFRS-16 completo, D&A por safra de CAPEX e capex expansão×manutenção (Semana 8 · 12–19/07)

## Papel e contexto

Você é o **Claude Fable 5**. O Prompt 8.1 fechou (DRE completa com D&A aberta em três
componentes, dois deles ainda zerados). Leia `CONTEXT.md` atualizado,
`ESTRUTURA_SMARTFIT.md` (seções "IFRS-16 Lease Asset", "Lease Liability", "D&A do
imobilizado POR SAFRA", "PP&E + Capex"), `src/projecao/schedule_ppe.py`,
`src/projecao/schedule_divida.py` (blocos de leasing do bridge) e
`config/parametros.json`. Esta é a **segunda etapa da Semana 8**.

## Objetivo

Modelar arrendamentos (IFRS-16) como cidadão de primeira classe e tornar a
depreciação economicamente realista, como no Smartfit:

1. **Lease Asset** (direito de uso): BoP − depreciação + adições − baixas = EoP.
2. **Lease Liability**: BoP − amortização + novos contratos = EoP, split CP/LP,
   **juros de arrendamento** separados dos juros de dívida na DRE.
3. **D&A por safra**: cada ano de capex vira uma camada de depreciação com
   **meia-depreciação no ano da safra** e **parada no saldo remanescente**
   (`MIN(quota, saldo)`); vida útil DERIVADA do histórico da empresa.
4. **Capex expansão × manutenção** como % do capex total.

## Referência no modelo Smartfit

- Lease Asset: `Build-Up` L359–L393 (adições % receita L370; D&A por safra L384–393).
- Lease Liability: `Build-Up` L1034–L1049 (amortização, net new leases, CP/LP, juros
  com taxa implícita vs CDI).
- D&A por safra do imobilizado: `Build-Up` L339–L357 (vida derivada
  `PP&E/D&A ≈ nº de anos`; fórmula com `IF(ano=safra, quota/2, MIN(quota, saldo))`).
- Capex: `Build-Up` L320–L337 (split expansão 80% × manutenção; capex/academia é
  unit economics — NÃO adotar).
- Efeitos na DRE/DFC: `Model ` L58 (juros de arrendamento), L72–L78 (D&A aberta),
  L132–L136 (bloco Aluguel do DFC — será consumido no 8.3).

## Especificação técnica detalhada

### 8.2.1 Dados de partida (coleta/mapeamento — best-effort com fallback)

- Mapear em `config/mapeamento_cvm.json` (quando existirem na DFP): ativo de direito
  de uso (sublinha do imobilizado 1.02.03.x quando aberta), passivo de arrendamento
  CP/LP (já mapeado para o bridge — reutilizar), amortização de direito de uso e juros
  de arrendamento (linhas do DFC MI quando presentes).
- **Fallbacks documentados** (Princípio 7): sem direito de uso no BP → estimar
  `direito_uso_ano0 = passivo_arrendamento_ano0`; sem juros de arrendamento →
  `taxa_implicita = premissa (default: CDI + spread do bloco config)`; sem D&A de
  direito de uso separada → split da D&A histórica proporcional aos saldos
  (direito de uso vs imobilizado). Cada fallback loga aviso e fica gravado no bloco
  persistido (`origem_dados`).
- **Empresa sem arrendamento relevante** (ex.: passivo < 1% do ativo): schedule
  inteiro zera, DRE mantém `da_direito_uso = 0`, juros de arrendamento = 0, e o
  Excel/app omitem o bloco — SEM erro.

### 8.2.2 Novo módulo `src/projecao/schedule_leasing.py`

- Premissas novas (opcionais, geradas com âncora histórica):
  `adicoes_leasing_pct_receita_ano1..8` (default: média histórica de
  adições/receita; proxy: Δdireito_uso + amortização), `taxa_arrendamento`
  (escalar; default: taxa implícita histórica com clamp [CDI−2pp, CDI+8pp]),
  `prazo_medio_leasing_anos` (default: derivado `direito_uso/D&A_direito_uso`,
  clamp [2, 15]).
- Rollforward do ativo e do passivo ano a ano; depreciação do direito de uso POR
  SAFRA (mesma mecânica do 8.2.3); amortização do passivo consistente com o prazo
  médio; juros = taxa × passivo de ABERTURA (convenção D-015, sem circularidade).
- Persiste bloco `leasing` em `data/processed/<TICKER>_projecao.json` (nomes no
  mapeamento) e devolve à DRE: `da_direito_uso` e `juros_arrendamento` (linha própria
  no resultado financeiro, separada dos juros de dívida).
- **Bridge:** o `calculador_ev` já subtrai o passivo de arrendamento do Ano 0 — passa
  a subtrair o MESMO saldo que o schedule usa (fonte única; sem dupla contagem).

### 8.2.3 D&A por safra no `schedule_ppe.py`

- Vida útil derivada: `vida_util = PP&E_bruto_ou_liquido_ano0 / D&A_imobilizado_ano0`
  com clamp [3, 30] anos; fallback: `config/parametros.json → vida_util_ppe_anos`
  (comportamento atual). Persistir a vida usada e a origem.
- Estoque EXISTENTE do Ano 0 deprecia linear pela vida derivada ATÉ ZERAR (não
  para sempre — usar `MIN(quota, saldo_existente)` como o Smartfit L343–L346).
- Cada safra de capex `t` deprecia: ano `t` = `(capex_t/vida)/2` (meia-depreciação);
  anos seguintes = `MIN(capex_t/vida, saldo_da_safra)`; total do ano = existente +
  Σ safras. Persistir a matriz de safras no bloco `ppe` (para o Excel do 9.2
  reproduzir com fórmulas).
- `da_imobilizado` da DRE (8.1) passa a vir daqui; intangível: manter amortização
  simples (linear sobre saldo do Ano 0, vida derivada com fallback) em
  `da_intangivel` — Smartfit trata intangível junto do PP&E; aqui fica explícito.
- Premissas novas: `capex_expansao_pct_ano1..8` (default: 80% — âncora Smartfit
  L332 — sobrescrevível por setor em `config/setores.json`); a D&A de MANUTENÇÃO ≥
  substituição na perpetuidade continua garantida pelo checklist NF3 existente.

## Contratos de interface

- Blocos novos/estendidos: `leasing` (novo), `ppe` (safras + vida derivada +
  expansão/manutenção), `dre` (`da_direito_uso`, `da_intangivel`,
  `juros_arrendamento` preenchidos).
- O FCFF NÃO muda de definição (D&A total volta no NOPAT; capex total sai) — mas os
  COMPONENTES agora são auditáveis.

## Definição de Pronto (DoD)

- SMFT3 (leasing gigante — caso de estresse ideal) roda ponta a ponta: bloco
  `leasing` persistido, juros de arrendamento separados na DRE, D&A aberta em 3
  componentes somando o total, balanço fechando.
- MGLU3 (leasing alto) e DIRR3 (leasing pequeno) rodam; VALE3/WEGE3 (lote da Onda 1)
  não quebram; empresa sem leasing zera o bloco sem erro (testar com fixture).
- **Regressão dourada EXPLICADA:** Target de DIRR3/MGLU3 muda (D&A por safra + juros
  de arrendamento) — quantificar por driver (padrão D-022) em `CONTEXT.md` +
  `Humano_revisar.md`.
- `pytest` verde; `black`/`flake8` limpos.

## Testes e validação

- `tests/test_schedule_leasing.py` (novo, fixtures sintéticas): rollforward fecha;
  meia-depreciação da safra 1; juros por saldo de abertura; empresa sem leasing →
  bloco zerado; fallbacks (sem direito de uso no BP) logam aviso.
- `tests/test_schedule_ppe.py` estendido: matriz de safras (soma das camadas = D&A
  total), safra para de depreciar no saldo, vida derivada com clamp, split
  expansão/manutenção, fallback para vida da config.
- `tests/test_projetor_dre.py`: D&A total = soma dos 3 componentes; resultado
  financeiro = juros dívida + juros arrendamento + receita financeira.

## O que NÃO fazer

- NÃO mexer no revolver/DFC/BP completo (Prompt 8.3). NÃO tocar em bancos.
- NÃO adotar capex/academia nem qualquer driver por unidade (v3.0).
- NÃO alterar a convenção de sinais persistida (capex assinado; D&A positiva no
  schedule, negativa na DRE — seguir o que os módulos atuais documentam).

## Ao final

`CONTEXT.md` (sessão datada) + `Humano_revisar.md`. Próxima tarefa: Prompt 8.3.

---
---

# PROMPT 8.3 — Dívida por instrumento (opcional), revolver formal, DFC indireto completo e BP aberto (Semana 8 · 12–19/07)

## Papel e contexto

Você é o **Claude Fable 5**. Os Prompts 8.1–8.2 fecharam (DRE completa; IFRS-16;
safras). Leia `CONTEXT.md`, `ESTRUTURA_SMARTFIT.md` (seções "Debt", "Dívida POR
INSTRUMENTO", "Revolver", "Equity schedule", "Balance Sheet", "Cash Flow"),
`src/projecao/schedule_divida.py`, `src/projecao/schedule_wk.py` e
`src/valuation/checklist.py`. Esta é a **terceira etapa da Semana 8** — a mais densa;
se precisar, divida em duas sessões (8.3a dívida+revolver / 8.3b DFC+BP), fechando o
DoD completo ao final.

## Objetivo

Fechar o motor no padrão Smartfit: dívida modelável por instrumento, revolver que
fecha o caixa SEM plug, um DFC indireto que reconcilia TODAS as linhas do balanço, e
um BP projetado aberto com verificação visível. Inclui o WK multi-driver.

## Referência no modelo Smartfit

- Dívida agregada + target: `Build-Up` L395–L418. Instrumentos: L420–L1030 (estrutura
  por bloco: saldo, curva de amortização, vencimento, juros, moeda, Kd).
- Revolver: `Build-Up` L1051–L1072 (caixa mínimo 2% da receita; saque =
  `-MIN(cash need, 0)`; juros CDI+spread sobre saldo de abertura).
- Equity schedule: `Build-Up` L1080–L1090. Receita financeira: L1074–L1078.
- DFC indireto: `Model ` L129–L186 (blocos e ordem descritos no mapa estrutural).
- BP aberto + Check: `Model ` L83–L127.
- WK multi-driver: `Build-Up` L292–L318.

## Especificação técnica detalhada

### 8.3.1 WK multi-driver (`schedule_wk.py` — modo novo `dias_multi_driver`)

- Premissas novas (vetores opcionais; default = dias implícitos do Ano 0):
  `dias_clientes` (sobre receita BRUTA), `dias_fornecedores` (sobre CPV),
  `dias_impostos_recuperar` (sobre deduções), `dias_salarios` (sobre SG&A),
  `dias_outros_ativos_cp` e `dias_outros_passivos_cp` (sobre receita bruta).
- Contas correspondentes mapeadas do BP real (impostos a recuperar, salários/
  obrigações sociais, outros CP) — registrar códigos no mapeamento; conta ausente →
  dias 0 + aviso.
- Os modos v1/v2 (`dias` DSO/DIO/DPO e `percentual_receita` p/ construtoras)
  CONTINUAM disponíveis; `modo_capital_giro` escolhe (default do subtipo em
  `config/setores.json`; construtoras seguem ancoradas como hoje).
- NWC e ΔNWC continuam com a mesma definição persistida (compat com FCFF).

### 8.3.2 Dívida por instrumento (OPCIONAL) + revolver formal (`schedule_divida.py`)

- **Tabela opcional de instrumentos** nas premissas:
  ```json
  "instrumentos_divida": [
    {"nome": "Debênture 7a — 1a série", "saldo_brl": 366.1, "taxa_anual": 0.145,
     "indexador": "CDI+1,5%", "ano_vencimento": 2029,
     "curva_amortizacao": [0, 0, 0.33, 0.33, 0.34, 0, 0, 0]}
  ]
  ```
  (curva = fração do saldo amortizada em cada `ano1..8`; sem curva → bullet no
  vencimento; `indexador` é texto documental — a taxa efetiva usada é `taxa_anual`).
  O analista copia das notas explicativas. **Sem a tabela → perfil CP/LP agregado
  atual (v2), sem mudança.** Moeda estrangeira: o analista informa o saldo JÁ em BRL
  (conversão automática de moeda = backlog; documentar no template).
- Agregação: juros por instrumento = taxa × saldo de ABERTURA (D-015); amortizações
  somadas ao fluxo de financiamento; captações novas continuam pela regra v2.
- **Revolver formal** (evolução da captação automática v2): saque =
  `max(0, caixa_minimo − caixa_pre_revolver)`; **amortização automática** quando o
  caixa excede o mínimo E há saldo de revolver; juros próprios =
  `(CDI_coletado + spread_revolver) × saldo de abertura` (spread em
  `config/parametros.json`, default 2,5pp); saldo persistido em bloco `revolver`
  separado da dívida estrutural. `caixa_minimo_pct_receita` continua premissa.
- Receita financeira: alinhar a taxa default ao **CDI coletado** (9.1 amplia o
  coletor; até lá, Selic ≈ CDI com aviso) — mantém a cascata premissa > coletado >
  fallback.

### 8.3.3 DFC indireto completo (novo módulo `src/projecao/dfc_indireto.py`)

Persistir bloco `dfc` NOVO (mantendo o antigo como `dfc_simplificado` até a Semana 9
para não quebrar consumidores), com a estrutura do `Model ` L129–L186:

```
EBITDA
  bloco IFRS-16/Aluguel: Δ lease asset, Δ lease liability, juros arrendamento,
                          depreciação direito de uso
  bloco Impostos: impostos da DRE + Δ impostos diferidos (constantes ⇒ Δ=0, linha explícita)
  bloco Δ WK: uma linha POR CONTA do WK multi-driver
  bloco Outros operacionais: Δ de cada residual do BP (explicitados, Δ=0 quando constantes)
(=) FCO   [+ % do EBITDA — indicador de conversão]
  bloco Capex: imobilizado, intangível (assinados)
(=) FCO pós-capex [+ % do EBITDA]
  Resultado financeiro caixa (juros dívida + revolver + receita financeira)
  Δ Empréstimos (captações − amortizações, por instrumento quando houver)
  Δ Revolver (saques − amortizações)
  Dividendos pagos
  Outros (OCI/capital social — Δ=0 explícito)
(=) Variação de caixa → Caixa BoP → Caixa EoP
```

- **Caixa EoP do DFC = caixa do BP** (continua sendo a origem do caixa, como na v2) e
  a linha de verificação `Ativo − (Passivo+PL)` continua ≈ 0 por construção; qualquer
  desvio > tolerância vira alerta NF1 (nunca raise). FCO/EBITDA alimenta o indicador
  que `qualidade_lucro.py` hoje calcula só no histórico (unificar a definição).

### 8.3.4 BP projetado ABERTO (`schedule_divida.py`/módulo do balanço)

- O bloco `balanco` persiste a abertura completa: caixa, aplicações, clientes,
  impostos a recuperar, outros CP, direito de uso, imobilizado, intangível,
  diferidos/judiciais/outros LP (constantes explícitos, um campo cada — vindos do BP
  REAL do Ano 0 como na D-016), fornecedores, salários, impostos a recolher, receita
  diferida, outros CP passivos, empréstimos CP/LP, revolver, arrendamento CP/LP,
  outros LP, PL (capital social + reservas + lucros acumulados evoluindo com
  LL − dividendos + OCI constante, minoritários).
- Campo `verificacao_balanco` por ano (diferença absoluta) — o Excel do 9.2 exibirá
  a linha `Check` como no Smartfit L127.

## Contratos de interface

- Blocos: `divida` (instrumentos opcionais + agregado), `revolver` (novo), `dfc`
  (novo indireto) + `dfc_simplificado` (legado temporário), `balanco` (aberto),
  `wk` (multi-driver). Todos os nomes no mapeamento.
- `calculador_fcff`/`calculador_ev`/`checklist` continuam lendo os campos que já
  leem (FCFF não muda de definição; bridge usa dívida total incl. revolver).

## Definição de Pronto (DoD)

- SMFT3, DIRR3, MGLU3, VALE3, WEGE3, RADL3, RENT3 rodam ponta a ponta com: DFC
  indireto fechando (variação de caixa = Δ caixa do BP; dif < 1e-6), balanço aberto
  verificado nos 8 anos, revolver sacando/amortizando quando aplicável.
- Caso de estresse: premissas que forçam caixa negativo → revolver saca, paga juros,
  amortiza quando sobra — teste sintético cobrindo o ciclo completo.
- Instrumentos de dívida: DIRR3 com tabela de 2 instrumentos fictícios nas premissas
  de TESTE produz juros/amortizações por instrumento (não usar como tese).
- **Regressão dourada EXPLICADA** (padrão D-022) para DIRR3/MGLU3.
- `pytest` verde; `black`/`flake8` limpos; `python -m src.verificar_semana3` OK.

## Testes e validação

- `tests/test_schedule_divida.py` estendido: instrumento com curva, bullet no
  vencimento, sem tabela → v2 idêntico; revolver saque/juros/amortização.
- `tests/test_dfc_indireto.py` (novo): cada bloco reconcilia com o BP; FCO % EBITDA;
  caixa EoP = caixa BP; empresa sem leasing → bloco IFRS-16 zerado.
- `tests/test_schedule_wk.py` estendido: modo multi-driver com drivers distintos;
  modos v1/v2 preservados byte a byte.
- `tests/test_balanco_aberto.py` (novo): abertura soma ao total; verificação ≈ 0;
  residuais constantes.

## O que NÃO fazer

- NÃO converter moeda de instrumentos (analista informa BRL). NÃO modelar
  target-leverage automático (a captação continua pela regra de caixa mínimo v2 —
  o `Target Debt = alavancagem × EBITDA` do Smartfit fica como opção de backlog,
  registrada em `Humano_revisar.md`).
- NÃO tocar no front-end/Excel (Semana 9). NÃO tocar em bancos.
- NÃO remover o `dfc_simplificado` ainda (consumidores migram no 9.2).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. Fecha a Semana 8. Próxima tarefa: Prompt 9.1.

---
---

# PROMPT 9.1 — Macro anual, painel de Retornos (TIR/MOIC/múltiplos implícitos) e blocos persistidos para o front (Semana 9 · 19–26/07)

## Papel e contexto

Você é o **Claude Fable 5**. A Semana 8 fechou o motor "Padrão Smartfit". Leia
`CONTEXT.md`, `ESTRUTURA_SMARTFIT.md` (seções "Aba Macro", "D@G e AVP — adaptar, não
copiar"), `src/coleta/coletor_macro.py`, `src/valuation/calculador_ev.py` e
`src/valuation/motor_cenarios.py`. Esta é a **primeira etapa da Semana 9**.

## Objetivo

1. **Bloco macro anual de primeira classe**: séries históricas + projeção por ano
   (`ano1..8`) persistidas e disponíveis para o motor, o app e a futura aba Macro do
   Excel — no espírito da aba `Macro` do Smartfit (fonte Itaú), mas com fontes
   públicas automatizadas (BACEN/Focus/yfinance).
2. **Painel de Retornos do acionista** — a tradução para equity listado das abas
   `D@G`/`AVP`: múltiplos implícitos e TIR/MOIC do investimento até o preço-alvo.

## Especificação técnica detalhada

### 9.1.1 Coletor macro ampliado (`coletor_macro.py`)

- Além de Selic/IPCA/Focus atuais: **CDI** (SGS 4389 anualizado; fallback Selic−0,1pp
  com aviso), **IGP-M** (SGS 189 acumulado 12m), **câmbio BRL/USD** (SGS 1 ou
  yfinance `BRL=X`), **PIB real** (expectativa Focus anual). Persistir em
  `data/raw/macro/macro_brasil.json` com data de coleta e fonte por série.
- **Bloco `macro_anual` persistido na projeção**: para `ano1..8`, IPCA/Selic/CDI/PIB
  esperados — Focus para os anos que ele cobre; além do horizonte, convergência
  linear para as metas de longo prazo em `config/parametros.json` (documentar).
- O motor passa a LER daqui o CDI (receita financeira, revolver — cascata
  premissa > coletado > fallback do 8.3 fica completa). NENHUMA outra fórmula muda.

### 9.1.2 Painel de Retornos (`src/valuation/calculador_retornos.py`, novo)

Consome os blocos persistidos (`ev_equity`, `fcff`, `dre`, `divida`, `cenarios`) e
persiste bloco `retornos`:

- **Múltiplos implícitos por ano projetado** (padrão D@G L13–L28): no preço ATUAL e
  no TARGET — EV/EBITDA, EV/Receita, P/L para `ano0..8` (EV do target = equity alvo +
  dívida líquida corrente; denominadores projetados do motor). Inclui o múltiplo de
  saída implícito na perpetuidade (já existe no checklist — unificar a fonte).
- **TIR do acionista** (padrão AVP L29–L35): fluxo = −preço_atual no ano 0;
  +dividendos/ação projetados (payout × LL / ações) nos anos 1..N; +preço-alvo
  realizado no ano N (default N=5, configurável). TIR via `numpy_financial.irr` ou
  bisseção própria documentada (sem dependência nova se possível). **MOIC** =
  (Σ dividendos + preço de saída) / preço de entrada. Grade de sensibilidade: TIR
  para saída no target do cenário Bear/Base/Bull (bloco `cenarios`).
- Financeiras: mesma mecânica com P/L e P/VP implícitos (denominadores da trilha
  FCFE); sem EV/EBITDA (documentar).

### 9.1.3 Exposição no app (mínima nesta etapa)

- Nova seção "Retornos" (ou sub-aba da Valuation atual) exibindo o bloco: tabela de
  múltiplos implícitos + KPIs TIR/MOIC + grade Bear/Base/Bull. **Sem redesenho do
  app** — o fluxo guiado é escopo do Prompt 9.2; aqui entra só a seção nova no
  layout atual.

## Definição de Pronto (DoD)

- `macro_anual` persistido para as 8+ empresas do lote; CDI/IGP-M/câmbio no JSON
  macro com fontes e datas.
- Bloco `retornos` persistido para SMFT3, DIRR3, MGLU3, ITUB4 (financeira) — TIR/MOIC
  coerentes (teste de sanidade: preço-alvo > preço atual ⇒ TIR > 0).
- Seção Retornos renderiza no app para as 4 empresas; `tests/test_app.py` cobre.
- Regressão dourada: Target Price INALTERADO (nada aqui muda o valuation; CDI só
  muda receita financeira/revolver se antes usava fallback — se mudar, explicar).
- `pytest` verde; `black`/`flake8` limpos.

## Testes e validação

- `tests/test_coletor_macro.py`: novas séries com fallbacks (sem rede → usa
  persistido); convergência do `macro_anual` além do Focus.
- `tests/test_calculador_retornos.py`: TIR de fluxo conhecido (fixture fechada na
  mão); MOIC; múltiplos implícitos com denominadores do motor; financeira sem
  EV/EBITDA.

## O que NÃO fazer

- NÃO indexar custos ao IPCA automaticamente (premissas continuam nominais — a
  indexação é decisão do analista; registrar como opção futura).
- NÃO implementar cap table/diluição/sources & uses (não se aplica).
- NÃO redesenhar o app (Prompt 9.2).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. Próxima tarefa: Prompt 9.2.

---
---

# PROMPT 9.2 — Front-end em fluxo guiado: Escolher → Premissas → Resultados ao vivo → Exportar (Semana 9 · 19–26/07)

## Papel e contexto

Você é o **Claude Fable 5** — e aqui o requisito veio DIRETO do humano (13/07/2026):
*"ao inicializar o programa, existam abas para: escolher a empresa, inserir todas as
premissas necessárias, após finalizar, uma aba em que seja possível mudar as
premissas e ver as mudanças, e ao final baixar o Excel sem nenhum erro."*
Leia `CONTEXT.md`, `app.py` inteiro, `tests/test_app.py`, os Princípios 3 e 11, e o
bloco de premissas novas dos Prompts 8.1–8.3. Esta é a **segunda etapa da Semana 9**.

## Objetivo

Reorganizar o app em um **fluxo guiado de 4 etapas** (stepper na sidebar), SEM perder
nenhuma capacidade existente (as 8 seções atuais viram sub-abas da etapa 3):

```
① Escolher empresa   ② Premissas   ③ Resultados & ajustes   ④ Exportar
```

## Especificação técnica detalhada

### 9.2.1 Etapa ① — Escolher empresa

- Busca por ticker (dispara pipeline com `st.status`, como hoje) + cards das
  empresas já analisadas (ticker, nome, data-base, score de qualidade, recomendação,
  flag de premissas automáticas) + atalhos DIRR3/MGLU3/SMFT3.
- Selecionar empresa → estado global + avança para ②. Empresa sem dados → mensagem
  clara com score/avisos (comportamento atual preservado).

### 9.2.2 Etapa ② — Premissas (o formulário COMPLETO)

- **Grupos colapsáveis, cada um com a âncora histórica ao lado** (padrão atual):
  1. Receita (crescimento ×8; deduções % RB ×8)
  2. Rentabilidade (margem bruta ×8; SG&A % receita ×8; outras/equivalência)
  3. Capital de giro (modo + vetores do modo escolhido, incl. multi-driver)
  4. Capex & D&A (capex % receita ×8; expansão %; vidas úteis derivadas EXIBIDAS
     como informação, com override opcional)
  5. IFRS-16 (adições % receita ×8; taxa; prazo — só se a empresa tem leasing)
  6. Dívida & Revolver (Kd; caixa mínimo; spread; tabela OPCIONAL de instrumentos
     via `st.data_editor` com adicionar/remover linha)
  7. Dividendos & Impostos (payout; modo de alíquota)
  8. Custo de capital & Perpetuidade (beta, ERP, CRP, g, estrutura-alvo)
  9. Macro (somente leitura: bloco `macro_anual` com fonte/data)
- Validação em tempo real (regras atuais + novas: margem bruta ≥ SG&A+margem EBITDA
  implícita coerente; deduções 0–40%; caixa mínimo 0–10%; curvas de amortização
  somando ≤ 100%). `Salvar e calcular` roda o motor oficial e remove a flag
  `premissas_automaticas` (fluxo atual).
- **"Restaurar automáticas"**: regenera premissas do gerador (confirmação antes).

### 9.2.3 Etapa ③ — Resultados & ajustes ao vivo

- Sub-abas: **Overview** (capa viva + seletor de cenário), **Histórico**,
  **Valuation** (WACC/VT/bridge/waterfall/football field/checklist), **Comparáveis**,
  **Retornos** (bloco 9.1), **Análise** (tornado + sensibilidade viva + heatmaps),
  **Comparar** (multi-empresa + watchlist), **Modelo** (NOVA: DRE/BP/DFC projetados
  em tabelas navegáveis — o 3-statements na tela, com a linha de verificação).
- **Painel lateral "ajuste rápido"** persistente na etapa ③: sliders Δ (crescimento,
  margem, WACC, g) da sensibilidade viva atual + botão "Aplicar às premissas"
  (transforma o ajuste em premissa oficial e re-roda o motor). Mantém a regra: ao
  vivo = derivação rápida; oficial = motor.
- Toda mudança salva invalida caches e re-renderiza com os números novos (padrão
  mtime atual).

### 9.2.4 Etapa ④ — Exportar

- Preview do Excel por aba (leitor openpyxl atual) + botão de download; status/data
  do arquivo; botão "Regerar Excel". (O CONTEÚDO novo do Excel chega no 9.3 — aqui a
  etapa já existe funcionando com o exportador atual.)
- Exportação BI (`exportador_bi.py` parcial existente) listada com status.
- Financeiras: aviso padrão (Excel bancário = backlog) — comportamento atual.

### 9.2.5 Qualidade

- `AppTest` cobrindo: navegação ①→②→③→④; salvar premissa recalcula; validação
  bloqueia g≥WACC; tabela de instrumentos aceita linha nova; seção Modelo renderiza
  o check do balanço; download presente. Manter os 9 testes atuais passando
  (adaptar aos novos caminhos).

## Definição de Pronto (DoD)

- Fluxo completo no navegador com SMFT3: escolher → revisar premissas → salvar →
  ver resultados → ajustar margem e ver o Target mudar → baixar o Excel.
- Nenhuma funcionalidade da Onda 4 perdida (cenários, comparar, watchlist, busca).
- `tests/test_app.py` verde (novos + antigos adaptados); `pytest` geral verde;
  `black`/`flake8` limpos.

## O que NÃO fazer

- NÃO recalcular valuation em JS (Princípio 3). NÃO remover seções — reorganizar.
- NÃO mexer no exportador Excel (Prompt 9.3).
- NÃO estilizar contra a paleta navy (Princípio 11).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. Próxima tarefa: Prompt 9.3.

---
---

# PROMPT 9.3 — Excel "Padrão Smartfit": 9 abas, fórmulas nativas, cores, comentários e checks (Semana 9 · 19–26/07)

## Papel e contexto

Você é o **Claude Fable 5**. O motor persiste todos os blocos novos (Semana 8) e o
app guia o usuário até "Exportar" (9.2). Leia `CONTEXT.md`,
`ESTRUTURA_SMARTFIT.md` INTEIRO, `ESTRUTURA_DIRECIONAL.md`,
`src/exportacao/exportador_excel.py` (mecanismos `escrever_calculo`, constantes
`LINHA_*`, convenção de cores) e `tests/test_exportador_excel.py`. Esta é a
**terceira etapa da Semana 9** — o entregável mais visível da v2.1.

## Objetivo

Reescrever o exportador para gerar, para QUALQUER não-financeira, um Excel no padrão
do modelo do mentor: build-up auditável, 3-statements integrado com check visível,
DCF com retornos, e a camada de METAINFORMAÇÃO que o Smartfit ensina (legenda,
aba de controle, comentários, fundo de premissa).

## Layout das 9 abas (ordem fixa)

| # | Aba | Conteúdo | Referência |
|---|---|---|---|
| 1 | `Capa` | Título, empresa, ticker, data-base, data de geração, versão do modelo, **legenda de cores** (Input/Premissa/Fórmula/Link), disclaimer quando `premissas_automaticas` | Smartfit `Capa` L29–32 |
| 2 | `Avisos` | Aba de CONTROLE estilo "To do list": score de qualidade + avisos da coleta, checklist do motor (status colorido), contas não mapeadas, fallbacks usados (leasing estimado etc.), flag de premissas automáticas, "Considerações ao analista" | Smartfit `To do list` |
| 3 | `Macro` | Bloco `macro_anual` + séries coletadas (histórico e projeção, fonte e data por série) | Smartfit `Macro` |
| 4 | `Premissas` | TODOS os vetores ×8 e escalares (grupos do 9.2.2), fonte azul + fundo `FFFFCC`, âncora histórica ao lado, **comentário de célula em cada premissa** (origem/âncora/última edição) | conv. WSP+Smartfit |
| 5 | `Build-Up` | Blocos verticais: Receita (bruta→líquida), CPV/SG&A, WK multi-driver (dias × driver), PP&E + **matriz de safras de D&A**, Leasing (asset+liability), Dívida (agregado + instrumentos quando houver), Revolver, Equity schedule | Smartfit `Build-Up` |
| 6 | `Model` | P&L completa + BP ABERTO + DFC INDIRETO, 3 exercícios históricos + 8 projetados, **linha `Check` do balanço** (`IF(=,"Ok",dif)`) e caixa BoP/EoP amarrado | Smartfit `Model ` |
| 7 | `DCF & Retornos` | FCFF 8 anos (ROIC/ROIIC), decomposição do WACC, VT, bridge EV→Equity→Target→Upside, **múltiplos implícitos por ano + TIR/MOIC** (bloco `retornos`), Football Field/Waterfall PNG | Direcional `FCFF` + Smartfit `D@G`/`AVP` |
| 8 | `Sensibilidades` | 3 tabelas atuais com formatação condicional + grade de cenários Bear/Base/Bull (premissas e resultados por cenário) | atual + `cenarios` |
| 9 | `Output` | Dashboard de KPIs, checklist colorido, PNGs institucionais | atual |

## Especificação técnica detalhada

- **Fórmulas nativas em TODAS as células de cálculo** (mecanismo `escrever_calculo`:
  a fórmula só entra se reproduz o valor do motor; senão, valor + comentário
  explicando — regra existente). Consistência horizontal: a MESMA fórmula estrutural
  em todas as colunas de projeção de uma linha (auditável no 10.1).
- Referências entre abas na direção `Premissas → Build-Up → Model → DCF` (fonte
  verde nos links, como o Smartfit). Nomes definidos: manter `WACC`/`g_perpetuidade`
  e adicionar `receita_liquida_ano1..8` se necessário para Data Tables.
- **Formatos numéricos:** R$ mil `#,##0;(#,##0);-`, % `0,0%`, múltiplos `0,0x`,
  anos como texto. Larguras, freeze panes (cabeçalho + rótulos), agrupamento
  (outline) dos blocos do Build-Up.
- **Comentários de célula** (novo padrão): toda premissa (origem/âncora), toda
  fórmula-chave (fórmula financeira em português — FCFF, VT, bridge, revolver,
  safras), todo fallback (ex.: "direito de uso estimado = passivo de arrendamento").
- **Blocos condicionais:** empresa sem leasing → bloco Leasing omitido (sem linhas
  vazias); sem instrumentos → só o agregado; sem revolver acionado → bloco com
  saldos zero mas fórmulas vivas.
- **Compatibilidade:** manter função/CLI atuais (`exportar_excel(ticker)`), o Excel
  Preview do app lê as abas novas automaticamente (leitor é genérico); atualizar as
  constantes `LINHA_*` e os testes de alinhamento.
- Financeiras: manter o caminho atual (Excel FCFF bloqueado com aviso) — inalterado.
- Remover o consumo do `dfc_simplificado` (migrar para o `dfc` indireto) em TODOS os
  consumidores (Excel, app, gráficos) e então apagar o bloco legado do motor.

## Definição de Pronto (DoD)

- Excel gerado para SMFT3, DIRR3, MGLU3, VALE3, WEGE3, RENT3 com as 9 abas; abre no
  Excel real sem reparo; recalcular (Ctrl+Alt+F9) não muda nenhum valor exibido
  (fórmulas reproduzem o motor) e a linha Check mostra "Ok" nos 8 anos.
- Célula de premissa alterada NO EXCEL (ex.: margem bruta ano 3) propaga pelas
  fórmulas até o Target Price (teste manual documentado — é o critério "modelo vivo"
  do padrão InFinance).
- `tests/test_exportador_excel.py` reescrito e verde; `pytest` geral verde;
  `black`/`flake8` limpos.

## Testes e validação

- Testes por aba: presença/ordem; legenda na Capa; avisos espelham
  qualidade/checklist; premissas com fonte azul+fundo e comentário; matriz de safras
  soma a D&A; check do balanço com fórmula; múltiplos implícitos batem com o bloco
  `retornos`; formatação condicional das sensibilidades; blocos condicionais somem
  quando não aplicáveis (fixture sem leasing).
- Smoke de recálculo já aqui (o 10.1 aprofunda): abrir via COM/LibreOffice,
  recalcular, zero erros de fórmula (`#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`).

## O que NÃO fazer

- NÃO colar valores onde uma fórmula é possível. NÃO usar funções pós-2007 sem
  necessidade (compatibilidade de recálculo). NÃO criar Excel bancário (backlog).
- NÃO quebrar o preview do app (etapa ④ do 9.2 deve continuar funcionando).

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. Fecha a Semana 9. Próxima tarefa: Prompt 10.1.

---
---

# PROMPT 10.1 — Auditoria dupla: Excel recalculado célula a célula + app no navegador + paridade estrutural com o modelo do mentor (Semana 10 · 26/07–02/08)

## Papel e contexto

Você é o **Claude Fable 5**. Tudo está construído; esta etapa é **verificação
profunda** — os itens 2, 3 e 4 do pedido do humano de 13/07/2026 ("testar se o código
funciona sem nenhum erro; se o front corresponde; se o Excel gerado está correto em
valores, fórmulas, referências, premissas, comentários, cores"). Leia `CONTEXT.md`,
`ESTRUTURA_SMARTFIT.md` e os DoDs da Semana 9. Esta é a **primeira etapa da
Semana 10**.

## Objetivo

Provar, com evidência programática e visual, que motor → app → Excel contam a MESMA
história, sem nenhum erro, para as empresas do conjunto de teste — e que o Excel
gerado tem paridade estrutural com o modelo do mentor.

## Especificação técnica detalhada

### 10.1.1 Auditor automatizado do Excel (`src/verificar_excel.py`, novo)

Para um ticker, executa e imprime relatório (e persiste
`outputs/excel/<TICKER>_auditoria.json`):

1. **Recálculo real**: abre o `.xlsx` via Excel COM (PowerShell/pywin32; fallback
   LibreOffice headless), força recálculo completo, salva cópia temporária —
   **zero células de erro** (`#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`).
2. **Célula a célula vs motor**: TODAS as linhas-chave × 8 anos contra os JSONs
   persistidos (tolerância 1e-6 relativa): receita bruta/líquida, CPV, SG&A, EBIT,
   EBITDA, LL, D&A (3 componentes), NWC/ΔNWC, capex, saldos de leasing, dívida,
   revolver, caixa BoP/EoP, FCO e % EBITDA, FCFF, WACC, VT, EV, equity, Target,
   upside, TIR/MOIC, múltiplos implícitos.
3. **Consistência de fórmula por linha**: nas colunas de projeção, a fórmula da
   coluna N difere da N+1 apenas pelas referências de coluna (detector de "célula
   editada no meio da linha" — o erro silencioso mais comum de modelos).
4. **Auditoria visual programática**: inputs/premissas em azul (premissas com fundo
   `FFFFCC`), fórmulas pretas, links verdes; comentários presentes em 100% das
   premissas; legenda na Capa; linha Check = "Ok" nos 8 anos; formatos numéricos
   (amostra); freeze panes.
5. **Paridade estrutural com o Smartfit** (checklist fixo em
   `config/paridade_smartfit.json`): blocos obrigatórios presentes por aba (ex.:
   Build-Up tem WK multi-driver + safras + leasing + revolver; Model tem DFC
   indireto com blocos nomeados; DCF tem TIR/MOIC) — comparação de ESTRUTURA, nunca
   de números (as premissas diferem por definição).

### 10.1.2 Validação do app no navegador (manual assistida, roteiro fixo)

Roteiro documentado em `docs/roteiro_validacao_app.md` (novo) e executado nesta
sessão via navegador real (padrão da validação de 13/07/2026):

- Fluxo ①→④ com SMFT3 e DIRR3: escolher, revisar premissa (âncora visível), salvar,
  ver Target mudar, ajustar ao vivo, comparar cenários, baixar Excel e ABRIR o
  arquivo baixado (auditor 10.1.1 nele).
- Conferência numérica DOM vs JSONs por seção (padrão Frente 4 da sessão
  13/07/2026); screenshots das etapas para o README.
- `tests/test_app.py` completo verde ao final.

### 10.1.3 Correções

Todo desvio achado é corrigido NA FONTE (motor/exportador/app) e o auditor re-roda
até zerar. Bugs achados/corrigidos documentados um a um (padrão D-025/D-026).

## Definição de Pronto (DoD)

- `python -m src.verificar_excel --ticker SMFT3` (e DIRR3, MGLU3, VALE3, WEGE3,
  RENT3) → `AUDITORIA OK` nas 5 dimensões.
- Roteiro do navegador executado com evidências; zero divergência DOM×JSON.
- `pytest` geral verde; `black`/`flake8` limpos.

## O que NÃO fazer

- NÃO "consertar" divergência ajustando o Excel na mão — a fonte é o motor.
- NÃO afrouxar tolerâncias para passar. NÃO pular o recálculo real.

## Ao final

`CONTEXT.md` + `Humano_revisar.md`. Próxima tarefa: Prompt 10.2.

---
---

# PROMPT 10.2 — Universalização B3 (lote ampliado, casos de borda, premissa→efeito) e fechamento da v2.1 (Semana 10 · 26/07–02/08)

## Papel e contexto

Você é o **Claude Fable 5**. Tudo funciona e está auditado para o conjunto-núcleo.
Esta etapa fecha o item 5 do pedido do humano ("funciona para toda e qualquer
empresa da B3; as áreas de premissas mudam e o programa altera tudo corretamente") e
a v2.1. Leia `CONTEXT.md` e os DoDs anteriores. Esta é a **última etapa da fase**.

## Especificação técnica detalhada

### 10.2.1 Lote B3 ampliado (≥ 12 empresas, ≥ 8 setores)

- `python -m src.coleta.coleta_lote --tickers DIRR3 MGLU3 SMFT3 VALE3 WEGE3 RADL3
  RENT3 PETR4 SUZB3 EQTL3 ABEV3 ITUB4 BBAS3` (ajustar se algum falhar por motivo
  externo — registrar) e, para as NÃO-financeiras, pipeline completo + Excel +
  auditor 10.1.1 em série. Falha em uma empresa não derruba o lote; relatório final
  consolidado (ticker, tipo, score, Target, checklist, auditoria).
- **Casos de borda obrigatórios** (fixtures sintéticas quando não houver empresa
  real no lote): sem leasing, sem dívida, prejuízo no Ano 0, sem DVA (deduções 0),
  receita bruta ausente, PP&E ~0 (asset-light), FCFF₈ negativo (regra do NOPAT
  normalizado existente). Cada um roda sem exceção e o Excel correspondente omite
  os blocos não aplicáveis.

### 10.2.2 Testes premissa→efeito (`tests/test_premissa_efeito.py`, novo)

Suíte que edita UMA premissa por vez (em `tmp_path`, motor re-rodado) e verifica a
cadeia inteira JSON→Excel:

- `margem_bruta_ano3` +2pp → lucro bruto/EBITDA/FCFF do ano 3 sobem; Target sobe;
  célula correspondente do Excel muda.
- `caixa_minimo_pct_receita` ↑ → revolver saca mais; juros sobem; check fecha.
- `dias_clientes` ↑ → NWC sobe, FCFF ano 1 cai.
- `payout` ↑ → dividendos no DFC e equity schedule mudam; FCFF INALTERADO.
- `adicoes_leasing_pct` ↑ → D&A direito de uso e juros de arrendamento sobem.
- Instrumento de dívida adicionado → juros por instrumento aparecem; bullet amortiza
  no ano certo.
- g ≥ WACC → bloqueio (validação existente).

### 10.2.3 Fechamento da v2.1

- **Regressão dourada final**: DIRR3, MGLU3 e SMFT3 com premissas revisadas viram o
  **novo golden triplo** (persistir os valores de referência em
  `tests/golden_v2_1.json` + teste que compara com tolerância e mensagem
  orientando a atualização consciente).
- Documentação: `README.md` (novas capacidades + screenshots do fluxo e do Excel),
  `CHANGELOG.md` (v2.1), `CONTEXT.md` (marco: v2.1 concluída), este arquivo
  (marcar prompts como executados).
- **Resumo executivo para o mentor** em `docs/resumo_v2_1_mentor.md`: o que foi
  adotado do modelo Smartfit (tabela do gap fechado), o que ficou para a v3.0 (unit
  economics — e o que o Lucas precisa aprender/receber para destravá-la), 3
  screenshots (fluxo, Model, DCF & Retornos).
- Sugerir a tag `v2.1` (criação/commit é do humano).

## Definição de Pronto (DoD)

- Lote processado com relatório consolidado; ≥ 10 não-financeiras com Excel
  auditado OK; bancos seguem pela trilha FCFE sem regressão.
- `tests/test_premissa_efeito.py` verde com ≥ 7 casos; suíte geral verde;
  `black`/`flake8` limpos; `python -m src.verificar_semana3` OK.
- Golden triplo persistido; docs e resumo do mentor escritos.

## O que NÃO fazer

- NÃO iniciar unit economics, BI/PDF/Power BI, Excel bancário ou colunas
  trimestrais (backlog — Apêndice C). NÃO criar a tag (humano).

## Ao final

`CONTEXT.md` marca a **v2.1 "Padrão Smartfit" como CONCLUÍDA** + `Humano_revisar.md`
+ lista objetiva do que o humano deve revisar/decidir para a v3.0.

---
---

## Apêndice A — Fluxo de trabalho dos 3 atores (permanece)

> **Humano (Lucas):** julgamento (premissas reais, validação numérica contra
> RI/Status Invest), descrição de bugs, commits/tags, revisão periódica do
> `Humano_revisar.md`. → **Claude Code:** cura/gera estes prompts e revisa. →
> **Claude Fable 5:** implementa, testa, atualiza `CONTEXT.md`. → **Humano** fecha.

## Apêndice B — Ordem obrigatória e critério de avanço

Não abra o prompt N+1 antes de o DoD do prompt N estar verde **e** a regressão
dourada explicada (Princípio 12). Cada prompt deixa o repositório consistente e
testável. Se uma sessão terminar no meio de um prompt, registre o ponto exato no
`CONTEXT.md` e retome do mesmo prompt.

## Apêndice C — Backlog explícito (NÃO fazer nas semanas 8–10)

| Item | Origem | Alvo |
|---|---|---|
| Unit economics setorial (build-up por unidade, coortes, curva de maturação; receita = função plugável já preparada no 8.1.3) | Recado do mentor + abas `Build-Up`/`Unit Economics` do Smartfit | **v3.0** — depende de exemplos por setor e estudo do humano |
| Excel bancário (FCFE/capital regulatório) | Antiga Onda 5 | v2.2 |
| `exportador_bi.py` completo + Power BI (`.pbix`) + nota PDF + orquestração em lote (`main.py --lote`) + Projetado vs. Realizado | Antiga Onda 5 | v2.2 |
| Colunas trimestrais 1Q–4Q do ano corrente + LTM | Smartfit `Model ` J:M | v2.2 |
| Conversão automática de moeda de instrumentos de dívida | Smartfit `Build-Up` L544+ | v2.2 |
| Target-leverage (dívida-alvo = alavancagem × EBITDA) | Smartfit `Build-Up` L406 | v2.2 (registrado no 8.3) |
| Indexação automática de custos a IPCA/IGP-M | Smartfit custos "Outros" | v2.2 (registrado no 9.1) |
| Minoritários destacados na DRE (% LL) | Direcional `Modelo` L13 | v2.2 |

## Apêndice D — O que o HUMANO precisa fazer nesta fase (checklist do Lucas)

1. **Colar um prompt por vez** no Fable e conferir o DoD antes do próximo.
2. **Commitar** ao final de cada prompt (mensagem sugerida: `claude semana N.M`).
3. **Revisar `Humano_revisar.md`** ao fim de cada semana (decisões D-027+).
4. **Premissas reais de SMFT3** quando quiser comparar o resultado com o modelo do
   mentor (o pipeline gera automáticas; a comparação de NÚMEROS só faz sentido com
   premissas suas — a paridade ESTRUTURAL o 10.1 valida sozinho).
5. Para a **v3.0 (unit economics)**: pedir ao mentor 1–2 modelos de OUTROS setores
   feitos "do jeito certo" (ex.: varejo e utilities) e estudar como cada setor
   constrói o build-up; sem isso a v3.0 não abre.
6. Se discordar do painel de Retornos (TIR/MOIC) ou de qualquer adaptação, reverter
   via `Humano_revisar.md` — nada é definitivo até você aprovar.
