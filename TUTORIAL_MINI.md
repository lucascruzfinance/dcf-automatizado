# TUTORIAL_MINI.md — passo a passo direto

> Versão completa e comentada: [`TUTORIAL.md`](TUTORIAL.md).

---

## 1. Iniciar

PowerShell na pasta do projeto:

```bash
.venv/Scripts/python.exe -m streamlit run app.py
```

Abre em `http://localhost:8501`. Parar: `Ctrl+C`.

---

## 2. Etapa ① Empresa

1. Sidebar → **Etapa** → `① Empresa`.
2. Digite o ticker no campo (ex.: `WEGE3`).
3. Clique **Analisar**.
4. Espere ~1 min (ticker novo) ou ~8s (já analisado).

Ticker já analisado: use o dropdown **Empresa** na sidebar.

---

## 3. Etapa ② Premissas

Sidebar → **Etapa** → `② Premissas`.

**Grupo ①②③ — tabela editável, 4 linhas × 8 anos.** Clique na célula, digite, `Enter`:

| Linha | Formato |
|---|---|
| Crescimento da receita líquida | `0.12` = 12% |
| Margem bruta (pré-D&A) | `0.37` = 37% |
| SG&A % da receita líquida | `0.15` = 15% |
| CAPEX / Receita | `-0.04` (negativo) |

**Grupo ④ — Alíquota:** tabela ×8, `0.34` = 34%. Construtora no RET: bloqueado.

**Grupo ⑤ — WACC:** marque a caixa → digite `0.135` = 13,5%.

**Grupo ⑥ — Outros:** sliders de DSO, DIO, DPO, payout, minoritários, beta, Kd, caixa mínimo, g.

Clique **Salvar premissas e recalcular valuation**. Espere ~8s.

> Botão desabilitado = `g ≥ WACC`, alíquota fora de 0–45% ou margem fora de 0–100%. Corrija no grupo ⑥ ou ①.

---

## 4. Etapa ③ Resultados

Sidebar → **Etapa** → `③ Resultados`. Cinco sub-abas:

| Sub-aba | Olhe |
|---|---|
| Overview | Target, upside, recomendação, score |
| Histórico | Métricas CVM ano a ano |
| Valuation | WACC, bridge, checklist |
| Modelo | DRE, Balanço, DFC, FCFF, FCFE |
| Retornos | TIR, MOIC, múltiplos |

---

## 5. Etapa ④ Exportar

1. Sidebar → **Etapa** → `④ Exportar`.
2. Clique **Regerar Excel**.
3. Clique **Baixar TICKER_dcf.xlsx**.

Arquivo também em `outputs/excel/TICKER_dcf.xlsx`.

Cores: 🔵 azul = CVM · 🟢 verde = sua premissa · ⚫ preto = fórmula.

Banco (ITUB4, BBAS3): sem Excel.

---

## 6. Comandos

| Ação | Comando |
|---|---|
| Abrir o app | `.venv/Scripts/python.exe -m streamlit run app.py` |
| Analisar vários tickers | `.venv/Scripts/python.exe -m src.pipeline PETR4 VALE3 WEGE3` |
| Rodar os testes | `.venv/Scripts/python.exe -m pytest tests -q` |
| Checar formatação | `.venv/Scripts/python.exe -m black src tests --check --workers 1` |

Logs: `logs/`.
