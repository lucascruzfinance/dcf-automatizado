# ESTRUTURA_DIRECIONAL.md — Mapa do modelo "Direcional (DIRR3)" do trainee InFinance

> Arquivo: `referencias/modelos_excel/Direcional_DIRR3_referencia.xlsx`
> Benchmark de qualidade da **v1.0** (o exportador Excel de 7 abas atual foi
> validado contra ele). Mapa extraído programaticamente em 13/07/2026.
> Movido de `tests/fixtures/` para cá em 13/07/2026 (nenhum teste depende do
> arquivo; a menção antiga em CONTEXT/README foi atualizada).

## Visão geral das 13 abas

| Aba | Dimensão | Conteúdo |
|---|---|---|
| `Modelo` | 210×33 | DRE + BP completo + DFC simplificado + WK por dias + schedules de dívida/depreciação |
| `FCFF` | 41×13 | NOPAT → FCFF → VP; WACC build-up (Ke CAPM Brasil + Kd); EV → Equity → Target Price |
| `Multiplos` | 40×37 | Múltiplos de mercado e comparação |
| `Buildup da Receita` | 60×49 | Receita por safra de empreendimentos (VGV lançado × % vendido × POC) — unit economics imobiliário |
| `Inputs - BP` / `Inputs - DRE` / `Inputs - Operacionais` | — | Dados históricos colados (equivalente ao nosso `data/raw/cvm/`) |
| `Projeções Macro` | 13×10 | Mini-tabela macro (IPCA, Selic, INCC…) |
| `Unit Direcional/Riva/INCC/Parcelamento/Cury` | 114×41 cada | Unit economics POR PROJETO imobiliário (5 abas) |

## Mecânicas notáveis (aba `Modelo`)

- **Premissas percentuais no topo** (L3–L14, fonte azul): crescimento VGV,
  deduções % receita bruta, margem bruta, despesas comerciais/G&A/outras %
  receita líquida, alíquota RET % receita bruta, equivalência % receita,
  **payout % LL**, **minoritários % LL consolidado**.
- **BP completo linha a linha** (L49–L122) com contas projetadas (caixa via
  fluxo, contas a receber/estoques/impostos/fornecedores/adiantamentos/
  credores por imóveis via dias de WK, imobilizado via schedule, reservas de
  lucro via LL − dividendos) e residuais **constantes** (`=F51`);
  **check booleano** `IF(ROUND(ativo)=ROUND(passivo+PL),TRUE,FALSE)` (L122).
- **DFC simplificado** (L125–L139): LL + D&A − ΔWK − CAPEX − dividendos +
  Δdívida → caixa BoP/EoP (menos completo que o do Smartfit).
- **WK por dias multi-driver** (L144–L180): Contas a Receber = dias de
  RECEITA LÍQUIDA; Estoques = dias de CMV; Impostos a recuperar = dias de
  IR/CS; Fornecedores/Credores por imóveis = dias de CMV; Adiantamento de
  clientes = dias de receita; Obrigações trab.+trib. = dias de SG&A.
- Schedules de dívida (L182–L196: rolagem com captações/amortizações) e
  depreciação (L198–L210).

## Aba `FCFF` (a camada de valuation que o Smartfit não tem)

`NOPAT = EBIT × (1−T)` → + D&A − ΔWK − CAPEX = FCFF → VP por ano
(`FCFF/(1+WACC)^t`) → PV explícito + PV perpetuidade = EV → − dívida líquida
= Equity → /ações = **Target Price** vs preço atual = Upside. WACC build-up:
Ke = Rf(T-bond 10Y) + β×ERP + CRP + risco de desvalorização (inflação
BR−EUA); Kd; pesos D/E; tax rate.

## Papel atual

O exportador `src/exportacao/exportador_excel.py` (7 abas) nasceu deste
modelo. A v2.1 "Padrão Smartfit" ESTENDE esse padrão com as mecânicas do
Smartfit (ver `ESTRUTURA_SMARTFIT.md`); a Direcional continua sendo a
referência da trilha FCFF/WACC e do unit economics imobiliário (futuro v3.0).
