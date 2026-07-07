# Changelog

Todas as mudanças relevantes deste projeto são documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Não lançado]

### Em desenvolvimento
- Semana 0 (01/07–06/07): fundação do repositório e coletor da CVM.

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
