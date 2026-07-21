# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado] — v2.1 "Padrão Direcional" — Semana 9.0 (CONCLUÍDA, 17→20/07/2026)

Motor e apresentação reescritos ao padrão da Direcional; a auditoria multi-agente (5
agentes) deu PASS em dados, Excel, front-end, DCF e sensibilidades. Suíte **192 passed /
12 skipped**.

### Adicionado / Alterado (prompts 9.0.0 → 9.0.5)
- **9.0.0 Enxugamento:** projeto reduzido ao núcleo; 15 módulos de gráficos/BI congelados
  (`# CONGELADO v2.1`, D-053) — voltam na Semana 10.
- **9.0.1 Fidelidade à CVM:** BP/DRE/DFC batendo com a DFP/ITR (residual < 5%); novo
  `auditor_cvm.py` (5 checagens).
- **9.0.2 Motor "padrão Direcional":** DRE **pré-D&A** (margem bruta + SG&A; margem EBITDA
  derivada; D&A linha própria), WK **multi-driver**, DFC **indireto**, BP **aberto** com
  linha Check, alíquota anual, minoritários + LPA.
- **9.0.3 FCFE + macro + retornos:** FCFE não-financeira ao Ke, bloco `macro_anual`
  (CDI/IGP-M/câmbio), painel de retornos (TIR/MOIC/múltiplos).
- **9.0.4 Front-end guiado:** app de 4 etapas (① Empresa → ② Premissas → ③ Resultados →
  ④ Exportar), 6 premissas, WACC manual, sub-abas Modelo/Retornos.
- **9.0.5 Excel "Modelo":** exportador reescrito em **8 abas** (Capa, Premissas, Modelo,
  FCFF, FCFE, Macro, Sensibilidades, Avisos) com fórmulas nativas VIVAS que reproduzem o
  motor, linha Check booleana e **cores de Lucas** (histórico azul / premissa verde /
  fórmula preto). `dfc_simplificado` removido.

### Planejado — Semana 10
- Descongelar `src/visualizacao/` e religar os gráficos no app (Football Field
  automatizado, tornado, waterfall, ROIC/ROIIC, sensibilidade viva, comparáveis,
  bear/base/bull); resolver os achados menores da revisão.

---

## [Não lançado] — v2.0 "Universalização" (Ondas 1–4 CONCLUÍDAS em 13/07/2026)

### Entregue (ver `PROMPTS_FABLE.md`, IA: Claude Fable 5)
- **Onda 1 — Coleta universal:** mapeamento CVM por `CD_CONTA`, resolvedor de ticker,
  classificador de tipo/subtipo setorial, `limpeza.py` real com Parquet, relatório de
  qualidade de dados e coleta em lote. Meta: qualquer empresa da B3 entra no pipeline.
- **Onda 2 — Motor completo por tipo:** trilha financeira (FCFE/Ke) validada para bancos,
  bridge EV→Equity completo, dívida amortizando, dividendos e receita financeira reais,
  cenários Bear/Base/Bull, qualidade de lucro.
- **Onda 3 — Comparáveis/CCA:** peers automáticos, múltiplos, triangulação, Football Field
  com comps reais (fim dos placeholders).
- **Onda 4 — Front-end multi-empresa:** seletor universal de ticker, sensibilidades vivas,
  tabelas editáveis, comparação entre empresas, aba Excel Preview funcional.
- **Onda 5 — Exportações e automação:** Excel dinâmico por tipo, `exportador_bi.py`, Power BI
  (`.pbix`), nota em PDF, Projetado vs. Realizado, orquestração/automação de dados em lote.

---

## [1.0.0] - 2026-07-11 — v1.0 concluída

Pipeline de DCF ponta a ponta validado para **DIRR3** (referência) e **MGLU3** (prova de
universalidade), ambas não-financeiras.

### Adicionado
- Coleta CVM/yfinance/BACEN; métricas históricas (trilha não-financeira).
- Projeção de DRE (8 taxas individuais) + schedules WK/PP&E/Dívida; balanço fecha nos 8 anos.
- Valuation FCFF/WACC, VT (Gordon), bridge EV→Equity→Target Price, ROIC/ROIIC, checklist.
- 7+ gráficos Plotly institucionais; front-end Streamlit (6 seções, tema navy).
- Exportador Excel com 7 abas, fórmulas nativas e convenção de cor WSP.
- `main.py` ponta a ponta; ~73 testes verdes; `black`/`flake8` limpos.

### Dívida técnica herdada (endereçada na v2.0)
- `exportador_bi.py` e aba Excel Preview do app ainda inexistentes.
- Comps do Football Field são placeholders; trilha financeira não validada contra banco real.
- Motor v1 simplifica: dívida constante, payout 0%, caixa como plug, aplicações constantes.

---

## Cronograma de Entregas Planejadas (v1.0 — prazo 06/08/2026)

> Este bloco documenta o plano. Conforme cada semana é concluída, mover os itens
> para uma seção de versão datada acima (ex.: `## [0.1.0] - 2026-07-06`).

### Semana 0 — 01/07 a 06/07 | Fundação + Coleta inicial
- Estrutura de pastas dos 5 módulos.
- `CONTEXT.md`, `.gitignore`, `.env.example`, `requirements.txt`.
- `config/setores.json`, `config/mapeamento_cvm.json`, `config/parametros.json`.
- Templates de premissas (não-financeiras e financeiras) com 8 campos individuais.
- `src/coleta/coletor_cvm.py` universal, validado para DIRR3 e MGLU3.

### Semana 1 — 07/07 a 13/07 | Coleta completa + Métricas históricas
- `src/coleta/coletor_mercado.py` (yfinance).
- `src/coleta/coletor_macro.py` (python-bcb).
- `src/processamento/limpeza.py` (normalização + Parquet).
- `src/metricas/metricas_historicas.py` (trilha não-financeira validada).

### Semana 2 — 14/07 a 20/07 | Projeção das demonstrações
- `src/projecao/projetor_dre.py` (8 taxas individuais).
- `src/projecao/schedule_wk.py`, `schedule_ppe.py`, `schedule_divida.py`.
- `tests/test_projecao.py` (balanço fecha nos 8 anos).

### Semana 3 — 21/07 a 27/07 | Valuation completo
- `src/valuation/calculador_fcff.py`, `calculador_wacc.py`, `calculador_vt.py`, `calculador_ev.py`.
- `src/valuation/checklist.py` + `tests/test_valuation.py`.
- Target Price de DIRR3 validado contra o Excel do trainee.

### Semana 4 — 28/07 a 03/08 | Visualizações + Front-end institucional
- `src/visualizacao/` completo (Football Field, Waterfall, sensibilidades, dashboard).
- `app.py` (Streamlit) com 6 seções + `.streamlit/config.toml` (tema institucional).

### Semana 5 — 04/08 a 05/08 | Excel 7 abas + integração + camada de BI
- `src/exportacao/exportador_excel.py` (7 abas formatadas, com fórmulas nativas do
  Excel nas abas de modelo/valuation e convenção de cor de input — azul = premissa,
  preto = fórmula, verde = link entre abas).
- `src/exportacao/exportador_bi.py` (tabelas planas star-schema em `outputs/bi/<TICKER>/`
  para o Power BI consumir — mesma estrutura de resultado do motor, sem recálculo).
- `main.py` (pipeline ponta a ponta; gera Excel, gráficos e tabelas de BI).
- Aba Excel Preview no front-end.

### 06/08 | Revisão final e tag v1.0
- Revisão geral de código, documentação e testes.
- `git tag v1.0`.

---

## Backlog Pós-v1.0 (NÃO implementar sem fechar a v1.0)

> Detalhamento técnico na Seção 7 do `ROTEIRO.md`. São peças NOVAS (não apenas
> acabamento de peças já planejadas) e só entram depois da tag `v1.0`.

- **Painel Power BI (`.pbix`)** conectado a `outputs/bi/` — dashboard executivo sobre
  as tabelas planas que a v1.0 já gera. (Alvo: v1.5.)
- **Comparáveis / CCA** (`src/valuation/comparaveis.py`) — peers, EV/EBITDA, P/L, P/VP,
  preço implícito por múltiplos; triangula o DCF. (Alvo: v2.0.)
- **Projetado vs. Realizado** (`src/analise/projetado_vs_realizado.py`) — análise de
  variância (FP&A) do projetado contra o realizado da CVM. (Alvo: v2.0.)
- **Nota de research em PDF (1 página)** (`src/exportacao/exportador_pdf.py`). (Alvo: v3.0.)
- **README com screenshots/GIF do dashboard e case study DIRR3 vs. modelo InFinance.**
