# referencias/ — Modelos de referência do projeto

> **Local canônico dos materiais de referência externos** (modelos Excel de
> benchmark, futuros exemplos de unit economics, etc.). Nada aqui é gerado
> pelo pipeline: são artefatos trazidos pelo humano que definem o **padrão de
> qualidade** que o código precisa alcançar. Toda IA (Claude Code, Claude
> Fable 5, Codex) deve consultar este diretório ANTES de mexer no motor de
> projeção ou no exportador Excel.

## Conteúdo

| Arquivo | O que é | Papel no projeto |
|---|---|---|
| `modelos_excel/Direcional_DIRR3_referencia.xlsx` | Modelo DCF da Direcional (DIRR3) do trainee InFinance | **Benchmark da v2.1** — a aba `Modelo` do exportador (8 abas na v2.1) é inspirada na aba Modelo deste arquivo (3 demonstrativos abertos + FCFF) |
| `modelos_excel/ESTRUTURA_DIRECIONAL.md` | Mapa estrutural do modelo acima (abas, linhas, mecânicas) | Consulta rápida sem abrir o xlsx |
| `modelos_excel/Smartfit_SMFT3_referencia.xlsx` | "Smartfit Model — PEP 2025.2 — Grupo 4" (nome original), enviado pelo mentor Heitor Crespo (InFinance) em 13/07/2026 | Referência conceitual; a v2.1 adotou o **padrão Direcional** e **adiou o unit economics do Smartfit para a v3.0** (receita = crescimento % anual, não VGV×POC) |
| `modelos_excel/ESTRUTURA_SMARTFIT.md` | Mapa estrutural completo do modelo acima | Consulta das mecânicas do Smartfit (IFRS-16, WK multi-driver, dívida por instrumento) que inspiraram partes do motor |

## Como consultar os modelos

1. **Primeiro leia o `ESTRUTURA_*.md`** correspondente — ele mapeia cada aba,
   as linhas-chave e as mecânicas financeiras (com números de linha do xlsx).
2. Só abra o `.xlsx` via `openpyxl` quando precisar de uma fórmula exata ou
   formatação específica. Duas passadas: `load_workbook(caminho)` para
   fórmulas e `load_workbook(caminho, data_only=True)` para valores cacheados.
   Nunca salvar por cima dos arquivos de referência.
3. Convenção de cores — atenção à DIFERENÇA (D-071):
   - **Modelos de REFERÊNCIA** (Direcional/Smartfit) usam a convenção WSP/InFinance:
     azul = input/premissa, preto = fórmula, verde = link entre abas.
   - **O EXPORTADOR DO PROJETO usa a convenção de LUCAS** (NÃO a WSP):
     **histórico da CVM = AZUL**, **premissa que o usuário escolhe = VERDE**,
     **fórmula = PRETO**. Registrado em `Humano_revisar.md` (D-071).

## O que cada modelo ensina (resumo executivo)

- **Direcional (v1.0):** DCF clássico FCFF/WACC de construtora — DRE com
  premissas percentuais no topo, BP completo linha a linha, WK por "dias de"
  com drivers distintos por conta, FCFF→VP→EV→Target, aba de múltiplos e
  build-up de receita por empreendimento (units imobiliárias).
- **Smartfit (v2.1):** modelo operacional integrado estilo Private Equity —
  build-up de receita por unit economics (academias × clientes × ticket, com
  curva de maturação por coorte), custos por natureza, IFRS-16 completo
  (lease asset + lease liability + juros de arrendamento), dívida instrumento
  a instrumento em várias moedas, revolver automático com caixa mínimo,
  depreciação por safra de CAPEX, DFC indireto reconciliando o BP inteiro,
  aba Macro (fonte Itaú), aba de controle ("To do list") e análise de
  retornos (múltiplos de entrada/saída, TIR/MOIC).
- **Nota do mentor (13/07/2026):** "Modelo tá mais bull, mas é assim que tem
  que ser feito — através de unit economics." A adoção do build-up por unit
  economics setorial ficou para a **v3.0** (exige exemplos por setor e
  aprendizado do humano); as semanas 8–10 adotam todo o restante da mecânica.

## Regras

- Estes arquivos são **imutáveis** (só o humano adiciona/substitui).
- Novos materiais de referência entram AQUI (subpasta por tema) e ganham
  linha na tabela acima + um `ESTRUTURA_*.md` se forem modelos Excel.
- Os testes NUNCA devem depender destes arquivos para rodar (fixtures de
  teste são sintéticas em `tests/`); eles servem a validação estrutural
  manual/assistida e à consulta das IAs.
