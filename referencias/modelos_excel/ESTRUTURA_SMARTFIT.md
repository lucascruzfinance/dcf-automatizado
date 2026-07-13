# ESTRUTURA_SMARTFIT.md — Mapa do modelo "Smartfit Model — PEP 2025.2 — Grupo 4"

> Arquivo: `referencias/modelos_excel/Smartfit_SMFT3_referencia.xlsx`
> Origem: mentor Heitor Crespo (InFinance), recebido em 13/07/2026. Autores:
> Carlos dos Anjos, Eduardo Lima, Heitor Crespo, Lisa Mandetta, Yago Santos;
> mentor do grupo: João Jaca. Contexto: PEP (programa de private equity) —
> avaliação da Smart Fit (SMFT3) como um deal de PE, não como DCF de mercado.
> Este mapa foi extraído programaticamente (openpyxl) em 13/07/2026 e traz
> números de linha reais do xlsx para consulta dirigida.

## Visão geral das 8 abas

| Aba | Dimensão | Fórmulas | Conteúdo |
|---|---|---|---|
| `Capa` | 59×23 | 0 | Título, autores, mentor e **legenda de cores** |
| `To do list` | 25×5 | 0 | Controle de pendências do modelo (tarefa/dono/data/check) + "Considerações" (limitações conhecidas) |
| `Model ` (com espaço!) | 188×23 | 1.236 | **3-statements integrado**: Overview de mercado, P&L, Balanço, Fluxo de Caixa indireto |
| `Build-Up` | 1194×21 | 2.467 | **Motor de projeção**: macro, receita por região/coorte, custos por natureza, WK, PP&E+safras de D&A, IFRS-16, dívida por instrumento, revolver, equity |
| `Unit Economics` | 65×11 | 130 | P&L, capex e fluxo POR ACADEMIA (payback, TIR 5a) |
| `D@G` | 65×39 | 525 | "Deal at a Glance": entry/exit valuation por múltiplos, sources & uses, cap table |
| `AVP` | 37×20 | 103 | Retornos do fundo: TEV por múltiplo de saída 6–10x → equity → **XIRR/MOIC/K-gain** |
| `Macro` | 51×35 | 89 | Séries macro 2004→projeções (fonte Itaú): PIB, IPCA, IGP-M, Selic, CDI, TJLP, câmbio BRL/USD e MXN, fiscal |

Colunas de período do `Model `/`Build-Up`: histórico anual 2022–2024 (G:I),
trimestres do ano corrente 1Q25–4Q25 (J:M), projeção anual 2025–2032 (N:U) —
**8 anos projetados**, datas via `EOMONTH(ant,12)`, cabeçalho de projeção com
fundo laranja `FFC000`.

## Convenção visual (aba Capa, L29–L32)

- **Input** — fonte azul `FF0000FF` (dado histórico digitado).
- **Premissas** — fonte azul + fundo amarelo-claro `FFFFFFCC` (célula que o
  usuário calibra; ex.: `Model !N24`, `Model !N65`, `Build-Up` F1062).
- **Fórmula** — fonte preta.
- Links entre abas — fonte **verde** (`FF008000`/`FF00CC00`).

## Aba `Model ` — linha a linha (o contrato do 3-statements)

### Overview (L12–L17)
Share Price, Mkt Cap, 52w high/low, % of week high, Shares Outstanding
(fórmulas array de provedor de dados — no nosso caso, virão do coletor).

### P&L (L19–L81)
- L21 `Gross Revenue` = Net Revenue − Deductions (derivada de baixo p/ cima).
- L23 `(-) Deductions` projetada como **% da receita bruta** (L24, premissa =
  média histórica `AVERAGE(G24:I24)` congelada e arrastada).
- L25 `(=) Net Revenue` ← `Build-Up!L21` (o build-up manda; o P&L apresenta).
- L28–L34 abertura da receita por segmento (Smart Fit Brasil/México/LatAm,
  Bio Ritmo & O2, Franchises, Digital) ← linhas do Build-Up (fonte verde).
- L36 `(-) Costs` ← `Build-Up!L204` (COGS por natureza agregado).
- L39 `Gross Profit` = Net Revenue + Costs; L40 margem.
- L42 `(-) SG&A` ← `Build-Up!L242`; histórico aberto em Vendas/G&A/Aluguéis
  (L44–46).
- L48 `(+/-) Other revenue (expenses)`; L50 `(+/-) Equivalência Patrimonial`
  (históricos input; projeção não modelada — zero).
- L52 `(=) EBIT` = Gross Profit + SG&A.
- L55 `Financial Result` = Interest Income + Financial expenses, com a
  despesa aberta em **L58 Juros de Arrendamento Mercantil** ←
  `Build-Up!L1047` (IFRS-16) e **L59 Others** ← `Build-Up!L413` (juros da
  dívida bancária + revolver).
- L61 `(=) EBT`; L64 `(-) Income Taxes` = **alíquota efetiva % EBT** (L65,
  premissa = efetiva do último ano histórico, arrastada) — NÃO 34% marginal.
- L67 `(=) Net Income`; L68 margem; L69 YoY.
- L72 `Depreciação e amortização` (memo, fora do EBIT) somando **L73
  Depreciação de Direito de Uso** ← `Build-Up!L374`, **L75 Depreciação de
  Imobilizado** ← `Build-Up!L341`, L77 Amortização de Intangível, L78 Outros.
- L80 `EBITDA` = EBIT − D&A (D&A negativa ⇒ soma de volta); L81 margem.
  ⚠️ No modelo, custos/SG&A já contêm D&A embutida (a abertura por natureza do
  Build-Up tem linha D&A dentro de COGS e SG&A); o EBITDA reconstrói somando-a.

### Balance Sheet (L83–L127)
- Ativo circulante: Caixa (L87 ← L186, resultado do fluxo), Investimentos
  financeiros, **Clientes** ← WK, Outros ← WK.
- Ativo não circulante: **Impostos a recuperar** ← WK, Ativos por imposto
  diferido/Depósitos judiciais/Investimentos/Outros **constantes** (`=I94`,
  `=I95`…), **Imobilizado** ← Build-Up L325, **Lease (direito de uso)** ←
  Build-Up L365, Intangível.
- L102 `Revolver` (linha própria no ativo — não usada; o revolver entra como
  dívida).
- Passivo circulante: **Empréstimos** ← Build-Up L408, **Passivos de
  arrendamentos** ← Build-Up L1042, **Fornecedores** ← WK, Receita
  diferida/Impostos a recolher/Contas a pagar constantes, **Salários** ← WK.
- Passivo não circulante: Empréstimos LP ← L410, Lease LP ← L1044, restantes
  constantes.
- Shareholders' Equity: Capital social/Reservas/OCI/Minoritários constantes;
  **Reserva de Lucro** = ano anterior + Net Income + Dividendos
  (`=I122+N67+'Build-Up'!L1084`).
- **L127 `Check` = `IF(G85=G104,"Ok",G85-G104)`** — verificação visível de
  Ativo = Passivo + PL em TODAS as colunas.

### Cash Flow (L129–L186) — DFC INDIRETO COMPLETO
Reconcilia CADA linha do BP (padrão a replicar):
- L131 EBITDA pós IFRS-16.
- L132 bloco `Aluguel`: variação do lease asset, variação do lease liability,
  juros de arrendamento, depreciação de direito de uso.
- L138 bloco `Impostos`: impostos da DRE + **impostos diferidos**
  (−Δ ativo diferido).
- L142 bloco `(+/-) WK`: Δ Clientes, Δ Impostos a recuperar, Δ Fornecedores,
  Δ Salários, Δ Contas a pagar.
- L149 bloco `Others Operational`: Δ outros ativos, Δ depósitos judiciais,
  Δ receita diferida, Δ impostos a recolher, Δ outros passivos.
- L156 `(=) OCF` + L157 **% EBITDA** (indicador de conversão de caixa).
- L159 bloco `Capex`: Δ imobilizado, Δ intangível, − depreciações (recompõe o
  capex bruto a partir das variações líquidas).
- L166 `OCF post-CAPEX & M&As` + % EBITDA.
- L169 Resultado financeiro (juros da dívida); L171 `(+/-) Empréstimos`
  (variação da dívida); L173 bloco `Dividendos` (derivado da variação das
  reservas − LL); L179 bloco `Outros` (OCI, capital social).
- L183 `Variação do caixa`; L185/186 **Caixa BoP/EoP** (fecha no BP L87).

## Aba `Build-Up` — os schedules (linhas-chave)

- **L10–L17 Macroeconomic indicators**: GDP, IPCA, IGP-M, Selic, CDI, BRL/USD
  por coluna-ano (ancoram custos indexados e juros) ← aba Macro.
- **L19–L69 Revenue Build-up**: receita líquida por região = Σ segmentos;
  para cada segmento: receita own-gym = `Revenue per client × # of clients`.
- **L71–L112 # of gyms / Net openings**: academias próprias/franquias por
  país; aberturas líquidas por ano (PREMISSA de expansão).
- **L115–L161 Store share / maturidade / coorte**: mix por maturidade
  (Year 1/Year 2/Mature), **Maturity Curve (0,60/0,85/1,00)** e receita por
  coorte via `SUMPRODUCT` — com linhas `Check` de fechamento (L139, L145,
  L156). É o CORAÇÃO do unit economics de receita (v3.0 do projeto).
- **L164–L199 # of clients / clients per gym**: clientes por academia por
  região; Digital como % do total.
- **L202–L238 Costs Build-up (COGS por natureza)**: Pessoal e encargos, D&A,
  Despesa de consumo, Serviços de apoio operacional, **Gastos com abertura de
  novas unidades (custo × loja nova)**, Aluguéis variáveis/condomínio,
  Manutenções, Outros — cada um com `% of revenue` e `% of Total COGS`;
  "Outros" cresce por inflação (`=K236*(1+IPCA)`).
- **L240–L290 SG&A Build-Up (por natureza)**: Pessoal, D&A, Consumo,
  Serviços, Gastos por loja aberta, Aluguéis variáveis (indexado a IGP-M),
  Manutenções, **Mídia e comerciais**, **Taxa de administração de cartões**,
  **Stock options**, Outros (inflação).
- **L292–L318 Working Capital Build-Up** — dias sobre DRIVERS DISTINTOS:
  - `Clientes` = dias de **Receita Bruta** (L303)
  - `Fornecedores` = dias de **COGS** (L306)
  - `Impostos a Recuperar` = dias de **Deduções** (L309)
  - `Salários` = dias de **SG&A** (L312)
  - `Other ST Assets/Liabilities` = dias de **Receita Bruta** (L315/L318)
- **L320–L337 PP&E + Capex**: rollforward BoP→EoP; capex TOTAL % receita;
  split **Capex para expansão (80%) vs manutenção**; `CapEx / Academia`.
- **L339–L357 D&A do imobilizado POR SAFRA (vintage)**: vida útil derivada do
  histórico (`# of Years of D&A = PP&E/D&A ≈ 8,8 anos` ⇒ `tx = 1/vida`);
  estoque existente deprecia linearmente; **cada ano de capex novo vira uma
  camada** com fórmula:
  `=-IF(ano=safra, (capex/vida)/2, IF(ano>safra, MIN(capex/vida, saldo_restante), 0))`
  — **meia-depreciação no ano da safra** e **para quando totalmente
  depreciada** (MIN com o saldo).
- **L359–L393 IFRS-16 Lease Asset**: BoP − D&A direito de uso + Additions
  (% receita, L370) − Write-off = EoP; depreciação do direito de uso TAMBÉM
  por safra (L384–L393), vida ≈ 5,6 anos derivada do histórico.
- **L395–L418 Debt (agregado)**: BoP + New Fundraising − Amortization = EoP;
  **Target Debt = alavancagem bruta constante × EBITDA**
  (`L406 = Gross Debt/EBITDA do ano-base × EBITDA projetado`) com
  `New Fundraising = MAX(target − BoP − amort, 0)`; split CP/LP por proporção
  histórica; `Financial Expenses`/taxa implícita; Net debt e Net debt/EBITDA.
- **L420–L1030 Dívida POR INSTRUMENTO** (~45 instrumentos): cada bloco tem
  Saldo, Curva de Amortização (input por ano), Vencimento, Juros (% spread),
  Moeda e Kd — debêntures (7ª–12ª emissões e séries), notas comerciais,
  capital de giro, e empréstimos em MXN (Latamgym México 1–8), COP (Sporty
  City Colombia 1–24), PEN (SmartFit Peru 1–7), CLP (Chile 1–5), USD/PAB
  (Sporty Panama 1–4), PYG (Paraguai 1–4) — com `Valor Inicial em BRL`
  convertido pelo câmbio da aba Macro.
- **L1034–L1049 Lease Liability**: BoP − Amortização + **Net New Leases** =
  EoP; split CP/LP; `Interest Provision` (juros de arrendamento) com taxa
  implícita ≈ 10,3% comparada ao CDI.
- **L1051–L1072 Revolver** (mecânica de fechamento de caixa SEM plug):
  `Cash EoP pre-Revolver = Cash BoP + OCF pós-capex + dividendos + Δ dívida
  existente + resultado financeiro − amortização do revolver`;
  `Minimum Cash = 2% da receita` (premissa F1062);
  `Cash Need = mínimo + pre-revolver` ⇒
  `New Debt = -MIN(Cash Need, 0)` (saca só o necessário);
  `Financial Expenses do revolver = (CDI + spread) × BoP`.
- **L1074–L1078 Interest Income**: receita financeira = CDI × caixa BoP
  (esqueleto).
- **L1080–L1090 Equity schedule**: BoP + Net Income − Dividends + Capital
  Increase = EoP; `Dividend Payout % of Net Income` (histórico ≈ 15%).
- **L1092–L1120 Financial ratios** (parcial): margens, ROIC (NOPAT/IC com
  WK + PP&E + intangível), ROE, cobertura, alavancagem.

## Aba `Unit Economics` — P&L por academia

Premissas: Growth Capex LTM, Maintenance Capex LTM, New Units (L10–L15).
P&L por loja: `Revenue/Store` com **% Mature (0,60 no ano 1)**; custos e SG&A
herdam os % of revenue do `Model `; D&A por loja; EBIT; Taxes 34%; NOPAT;
**Opening Capex = Growth Capex / novas lojas** e Maintenance Capex por loja;
fluxo da loja (EBITDA − taxes − capex de abertura) → **fluxo acumulado →
Payback** e IRR 5 anos. *(Adoção adiada para a v3.0 — exige curva de
maturação e drivers POR SETOR.)*

## Abas `D@G` e `AVP` — mecânica de PE (adaptar, não copiar)

- `D@G`: Entry (EV/Revenue, EV/EBITDA, P/E pre/post-money em 2027) e Exit
  (mesmos múltiplos em 2031); EV − Net Debt = Equity; + Money-In = Post
  Money; Cap table Founders×PEP; Sources & Uses (Money-Out/In, DD costs);
  tabela de conversão de caixa à direita (K43–K60: EBITDA → capex →
  empréstimos → dividendos → % conversão).
- `AVP`: grade de múltiplo de saída 6–10× EBITDA → TEV → Equity → valor da
  participação → fluxos anuais do fundo → **XIRR (TIR), MOIC e K-Gain** por
  coluna de múltiplo.
- **Tradução para equity listado (semana 9):** painel de "Retornos do
  acionista" — múltiplos implícitos no preço-alvo por ano (EV/EBITDA,
  EV/Receita, P/L), TIR implícita de comprar ao preço atual e realizar o
  target no ano N (com dividendos), MOIC do período projetado. Cap
  table/sources & uses NÃO se aplicam (não há deal).

## Aba `Macro` — premissas macroeconômicas

Séries anuais 2004→projeção (fonte: Itaú): PIB mundial/EUA/Euro/China; CPI
EUA; PIB Brasil nominal (R$ e US$) e real; desemprego; IPCA, INPC, IGP-M,
IPA-M; **Selic fim/média, CDI fim/acumulado, TJLP, TLP**; fiscal (primário,
nominal, dívida líquida/bruta % PIB); **câmbio BRL/USD dez/média**; setor
externo; inflação LatAm; **MXN/BRL e CPI México** (conversão das operações
mexicanas). O Build-Up referencia estas séries nas linhas macro L10–L17.

## O que o projeto JÁ TEM e o Smartfit NÃO tem

WACC/Ke e valor terminal de Gordon (o Smartfit avalia por múltiplo de
entrada/saída, sem desconto a valor presente de FCFF), FCFF explícito,
comparáveis com peers reais, checklist automático de consistência, cenários
Bear/Base/Bull persistidos, football field, sensibilidades WACC×g,
front-end, coleta automática CVM/yfinance/BACEN. **A v2.1 une os dois
mundos**: a mecânica operacional do Smartfit + a camada de valuation DCF do
projeto.
