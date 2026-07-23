# Humano_revisar.md — decisões que dependem de VOCÊ

> **Protocolo (instrução permanente de Lucas, 12/07/2026):** quando a IA encontra
> um erro, uma ambiguidade ou um conflito entre documentos, ela **decide sozinha
> pela melhor opção, executa e registra**. Nada aqui é definitivo até você
> aprovar — se discordar, peça a reversão.

**Este arquivo lista SÓ o que exige uma escolha sua sobre o app atual.**
Decisões já executadas, estabilizadas e sem pergunta pendente (D-001…D-079,
1.520 linhas) foram arquivadas em
[`docs/historico_decisoes.md`](docs/historico_decisoes.md) — consulta histórica,
não precisa ler.

Status: `⏳ aberta` | `✅ aprovada` | `🔁 revertida`.
Última verificação ponta a ponta: **22/07/2026** — 204 testes verdes, 12 tickers
no app sem exceção, 10 Excels recalculados fórmula a fórmula (0 divergência).

---

## ⏳ A-1 — Os alvos automáticos estão irreais em 9 de 12 tickers (ex-D-024 / D-073)

Estado hoje (11 dos 12 tickers **nunca tiveram premissa revisada por você** —
flag `premissas_automaticas: true`):

| ticker | target | preço | upside |     | ticker | target | preço | upside |
|--------|-------:|------:|-------:|-----|--------|-------:|------:|-------:|
| DIRR3  |  20,88 | 12,05 |   +73% |     | VALE3  |  41,32 | 74,18 |   −44% |
| BBAS3  |  40,77 | 20,58 |   +98% |     | RENT3  |  20,65 | 41,10 |   −50% |
| ITUB4  |  54,33 | 44,30 |   +23% |     | WEGE3  |   9,44 | 46,51 |   −80% |
| ABEV3  |  11,87 | 15,63 |   −24% |     | MGLU3  |   0,77 |  5,05 |   −85% |
| PETR4  |   1,35 | 40,90 |   −97% |     | SMFT3  |  −3,93 | 21,20 |  −119% |
| TOTS3  |  −1,70 | 29,19 |  −106% |     | RADL3  |  −2,18 | 18,77 |  −112% |

**Por que:** a premissa de partida é gerada por âncora histórica (CAGR 3a, margem
3a, capex 3a) com fade conservador. Não é uma tese — é um ponto de partida. PETR4
−97%, TOTS3 e RADL3 negativos são consequência disso somada ao Kd derivado (A-2).

**A decisão é sua:**
- **(a) manter** — a etapa ② existe exatamente para você escrever a tese ticker a
  ticker; o app já avisa em amarelo enquanto a premissa for automática. **(recomendada)**
- (b) calibrar o gerador para partir mais perto do preço de mercado — inverte a
  lógica do DCF (o preço deixa de ser conclusão e vira input).
- (c) esconder o target enquanto a premissa for automática — esconde também o
  diagnóstico.

---

## ⏳ A-2 — Kd derivado do histórico sai absurdo em nomes alavancados (ex-D-063 / D-065 / D-066)

O `calculador_wacc` deriva o custo da dívida dividindo despesa financeira pelo
saldo médio de dívida. Nos casos em que a empresa tem pouca dívida bruta e muita
despesa financeira, o resultado explode:

| ticker | Kd derivado | WACC resultante |
|--------|------------:|----------------:|
| ABEV3  |    **168%** |           10,3% |
| WEGE3  |     **48%** |            9,9% |
| MGLU3  |     **46%** |           21,8% |
| RADL3  |     **44%** |           20,2% |
| SMFT3  |      19,9%  |           15,6% |

É a **maior distorção numérica em aberto** no motor. É também o que produz a
divergência FCFE × bridge FCFF (MGLU3 +935%, ABEV3 +64%, WEGE3 +51%) que o app
mostra na sub-aba Modelo.

**A decisão é sua:**
- **(a) clampar o Kd derivado** numa faixa de sanidade (ex.: `[CDI; CDI + 8pp]`),
  igual ao que já é feito com o beta em `[0,5; 1,8]`. **(recomendada)**
- (b) preferir SEMPRE o Kd da premissa (o slider da etapa ② ⑥) e usar o derivado
  só como referência exibida.
- (c) deixar como está — o número é "fiel ao histórico", só que economicamente
  sem sentido para essas empresas.

Enquanto não decidir: dá para contornar caso a caso na etapa ② → grupo ⑥ →
slider "Kd — custo da dívida", ou informando o WACC direto no grupo ⑤.

---

## ⏳ A-3 — Excel não cobre bancos (ex-D-034 / D-068)

ITUB4 e BBAS3 rodam o pipeline, o valuation FCFE/Ke e as 5 sub-abas da etapa ③
normalmente. Mas a etapa ④ Exportar mostra só um aviso: o exportador de 8 abas é
da trilha **não-financeira**. Um modelo bancário (margem financeira, provisão,
Basileia, capital regulatório) é um Excel diferente, não uma adaptação.

**A decisão é sua:** construir o Excel bancário (é uma semana inteira de
trabalho) ou aceitar que banco vive só no app. Hoje está como backlog v2.2.

---

## ⏳ A-4 — O que fazer com os módulos de gráfico (ex-D-053 / D-078)

15 módulos foram congelados no enxugamento da Semana 9 e 14 já foram
descongelados e re-testados com dados reais (football field, tornado, waterfall,
ROIC/ROIIC, sensibilidades, comparáveis, cenários). **Eles funcionam, mas ainda
não aparecem no app** — religá-los é a Semana 10, já planejada em
`PROMPTS_FABLE.md`.

Sobra um caso: **`src/exportacao/exportador_bi.py`** continua congelado (export de
tabelas planas para Power BI). **A decisão é sua:** apagar de vez ou manter
congelado esperando o `.pbix`?

---

## ⏳ A-5 — TIR usa preço de saída truncado em zero (ex-D-067)

Na sub-aba Retornos, quando o target é negativo (SMFT3, RADL3, TOTS3 hoje) o
preço de saída é truncado em **zero** — responsabilidade limitada: o acionista
não paga para sair. A TIR sai ≈ −100% em vez de um número impossível.

**A decisão é sua:** manter o truncamento (recomendado, é economicamente
correto) ou mostrar "n/d" e omitir o cenário quando o target for negativo.

---

## ⏳ A-6 — Principal do leasing fica fora do DFC (ex-D-042)

Os **juros** de arrendamento IFRS-16 entram no resultado financeiro e afetam
LL/FCFE. A **amortização do principal** não é lançada como saída de financiamento
no DFC projetado — o balanço fecha (residual ~1e-9) porque o passivo de
arrendamento é projetado constante.

**Efeito prático:** FCFF e EBITDA não mudam; o FCFE de empresas com leasing
pesado (RENT3, SMFT3, RADL3) fica ligeiramente otimista.

**A decisão é sua:** implementar o schedule de amortização do arrendamento
(exige desmembrar a conta CVM 1.02.03, ripple amplo) ou aceitar a simplificação.

---

## ⏳ A-7 — Unit economics adiado para a v3.0 (ex-D-027)

Seu mentor disse que o valuation "tem que ser feito por unit economics". O
projeto adotou **toda** a mecânica do modelo dele (DRE bruta→líquida, IFRS-16,
DFC indireto, BP aberto, TIR/MOIC) mas com premissas percentuais, porque o
build-up por unit economics exige método específico por setor. A função
`projetar_receita` já é plugável para receber esse build-up sem reescrever a DRE.

**A decisão é sua:** confirmar que fica para a v3.0, ou antecipar.

---

## ⏳ A-8 — O motor usa o número ORIGINAL, não o reapresentado (achado de 22/07/2026)

Cada exercício aparece **duas vezes** na base da CVM: como `ORDEM_EXERC =
ÚLTIMO` na DFP do próprio ano, e como `PENÚLTIMO` na DFP do ano seguinte (a
coluna comparativa). O motor filtra `ÚLTIMO` — ou seja, **o número como foi
divulgado na época**, não como a empresa o reapresentou depois.

Medido em 5 tickers: das 891 linhas anuais que existem nas duas versões, **47
(5,3%) divergem**. Exemplos reais:

| ticker | conta | exercício | ÚLTIMO (original) | PENÚLTIMO (reapresentado) |
|---|---|---|---:|---:|
| VALE3 | 3.01 receita | 2020 | 208.528.759 | 206.098.000 |
| VALE3 | 3.02 CPV | 2020 | −98.567.494 | −90.948.000 |
| ABEV3 | 3.06.01 rec. financeiras | 2023 | 2.670.300 | 2.494.161 |
| WEGE3 | 3.06.01 rec. financeiras | 2022 | 1.105.994 | 1.197.270 |

**A decisão é sua:**
- **(a) manter `ÚLTIMO`** — é reprodutível e é o número que o mercado viu na
  época. **(recomendada)**
- (b) preferir a versão mais recente de cada exercício (pega reapresentação e
  reclassificação, mas o histórico muda retroativamente a cada DFP nova).

---

## Convenções já travadas (não precisam de decisão — só para você saber)

- **Cores do Excel:** histórico = AZUL, premissa = VERDE, fórmula = PRETO (as
  suas, não as do modelo WSP). Verificado: 266 azuis / 109 verdes / 942 pretos no
  DIRR3.
- **Excel = 8 abas:** Capa, Premissas, Modelo, FCFF, FCFE, Macro, Sensibilidades,
  Avisos — padrão Direcional, com fórmulas vivas.
- **Horizonte 8 anos**, sempre 8 valores individuais por premissa (nunca uma taxa
  replicada).
- **Margem de partida é BRUTA pré-D&A**; a margem EBITDA virou derivada
  (bruta − SG&A), somente leitura.
- **WACC manual vence o build-up CAPM** quando preenchido; a decomposição CAPM
  continua visível.
- **Construtoras no RET:** alíquota travada em 4% sobre a receita bruta.
- **O motor Python calcula uma vez**; app e Excel só apresentam.
- Auditor da CVM acusa `dfc_amarra` em RENT3/PETR4/ABEV3 (caixa do DFC ≠ caixa do
  BP em 0,1–5%, escopo da própria companhia) e `balanco_fecha` em bancos
  (falso-positivo: banco não tem split AC/ANC). São **avisos**, não erros.
