# TUTORIAL — como usar o DCF Automatizado

> Escrito em 22/07/2026 contra o estado real do repositório (app de 4 etapas,
> Excel de 8 abas). Cada passo abaixo foi executado de verdade antes de virar
> texto.
>
> ⚡ **Só quer os cliques e comandos, sem explicação?**
> [`TUTORIAL_MINI.md`](TUTORIAL_MINI.md).

---

## 0. Antes de tudo: o que o programa faz

Você digita um ticker da B3. O programa baixa sozinho os dados da CVM (7
exercícios), o preço no yfinance e o macro (Focus/SGS do Bacen), classifica a
empresa (financeira × não-financeira, setor), **gera premissas de partida** a
partir do histórico e roda o DCF completo — DRE, balanço, DFC, FCFF, FCFE, WACC,
valor terminal, bridge até o target price.

O que ele **não** faz é a sua tese. As premissas automáticas são um ponto de
partida conservador. O trabalho na etapa ② é seu.

---

## 1. Ligar o app

Abra o PowerShell na pasta do projeto e rode:

```bash
.venv/Scripts/python.exe -m streamlit run app.py
```

O Streamlit abre o navegador em `http://localhost:8501` (se a porta estiver
ocupada ele usa a próxima). Para parar: `Ctrl+C` no terminal.

Se aparecer erro de import, o ambiente errado está ativo — o oficial é a `.venv`
do projeto, sempre chamada pelo caminho completo como acima.

---

## 2. A tela que abre

À **esquerda (sidebar)** ficam sempre visíveis:

| Controle | O que faz |
|---|---|
| **Empresa** | dropdown com tudo que já foi analisado — troca de empresa sem recarregar |
| **Etapa** | os 4 rádios: ① Empresa · ② Premissas · ③ Resultados · ④ Exportar |
| **Recalcular motor (premissas atuais)** | roda só o motor com o que já está salvo (~8s) |
| **Recoletar tudo e reanalisar** | baixa CVM/preço/macro de novo e **regenera as premissas automáticas** — cuidado, descarta as suas |

À **direita** aparece a etapa selecionada. O título da página é sempre
`TICKER — etapa`.

> Se a sidebar não aparecer no primeiro carregamento, dê F5 — é timing de
> renderização do Streamlit, não erro do app.

---

## 3. Etapa ① Empresa — escolher ou analisar

Três caminhos:

1. **Ticker novo:** digite no campo (`SUZB3`, `KLBN11`, `WEGE3`…) e clique
   **Analisar**. Um painel de progresso mostra as etapas: Coleta CVM → Limpeza
   Parquet → Relatório de qualidade → Coleta de mercado → Macro → Métricas →
   Premissas automáticas → Motor. **Leva 45–65 segundos** numa empresa nova
   (é download da CVM). Depois cai sozinho na etapa ③.
2. **Botões de referência:** DIRR3, MGLU3, SMFT3 carregam na hora.
3. **Empresas já analisadas:** dropdown, carregamento instantâneo (usa cache).

Quando a empresa já tem valuation, aparece embaixo o **painel de decisão**:
Target Price · Preço atual · upside · Recomendação · WACC · g.

> **Não precisa informar setor.** A classificação vem do registro CVM. O
> `main.py` da linha de comando ainda pede `--setor` e só aceita DIRR3/MGLU3 —
> é a CLI legada da v1. Pela linha de comando universal use
> `.venv/Scripts/python.exe -m src.pipeline SUZB3`.

---

## 4. Etapa ② Premissas — onde você trabalha

O topo mostra as **âncoras históricas** para você calibrar: CAGR de receita 3
anos, margem bruta 3 anos, CAPEX/receita 3 anos. Se as premissas ainda forem
automáticas, aparece um aviso amarelo.

São 6 grupos colapsáveis:

### ① ② ③ — Crescimento, Margem bruta e SG&A *(aberto por padrão)*

Uma **tabela editável** com 4 linhas × 8 colunas (Ano 1 … Ano 8). Clique na
célula, digite, `Enter`:

| Linha | O que é | Formato |
|---|---|---|
| Crescimento da receita líquida | crescimento de cada ano | decimal (`0.12` = 12%) |
| Margem bruta (nível EBITDA, **pré-D&A**) | receita − custos, **antes** da depreciação | decimal |
| SG&A % da receita líquida | despesas comerciais/administrativas | decimal |
| CAPEX / Receita (**negativo = saída**) | investimento | decimal negativo (`-0.04`) |

Logo abaixo, a **Margem EBITDA derivada** (margem bruta − SG&A) aparece só para
leitura — ela deixou de ser input.

> A margem é **pré-D&A** de propósito: a depreciação é subtraída depois pelo
> schedule de PP&E, que é quem sabe o capex de cada ano.

### ④ Alíquota de impostos

Mesma tabela editável (8 anos). **Construtora no RET** (caso da DIRR3): o grupo
mostra um aviso e não deixa editar — a alíquota fica travada em 4% sobre a
receita bruta, aplicada pelo motor.

### ⑤ WACC (input direto opcional)

Marque **"Informar o WACC manualmente"** e digite o decimal (`0.135` = 13,5%).
Isso **sobrepõe** o build-up CAPM — o motor usa o seu número no VT e no EV. A
decomposição CAPM continua calculada e visível na sub-aba Valuation, para você
comparar. Desmarcando, volta ao build-up.

### ⑥ Outros

Sliders, dois blocos:

- **Esquerda:** DSO, DIO, DPO (dias de capital de giro), payout de dividendos,
  participação de minoritários (% do LL).
- **Direita:** beta desalavancado, **Kd (custo da dívida)**, caixa mínimo (% da
  receita), **g** (crescimento na perpetuidade).

> O slider de **Kd** é o contorno prático para o problema aberto do Kd derivado
> (veja `Humano_revisar.md`, item A-2): em ABEV3/WEGE3/MGLU3/RADL3 o Kd que o
> motor deriva do histórico sai entre 44% e 168%. Ajuste aqui.

### Salvar

**"Salvar premissas e recalcular valuation"** grava o JSON, roda o motor e
recarrega a tela (~8s). A partir daí a flag `premissas_automaticas` some — você
assumiu a autoria e o aviso amarelo desaparece.

O botão fica **desabilitado** se a validação em tempo real reprovar:
`g ≥ WACC`, alíquota fora de 0–45%, margem bruta fora de 0–100%.

**"Restaurar automáticas"** pede confirmação e depois descarta tudo o que você
escreveu, regenerando as premissas do zero.

---

## 5. Etapa ③ Resultados — 5 sub-abas

| Sub-aba | O que tem |
|---|---|
| **Overview** | painel de decisão + linha de identidade (razão social, tipo/subtipo, método, score de dados /100, checklist APROVADO/REPROVADO, % do EV que vem da perpetuidade) + espinha do valuation (Soma VP(FCFF), VP(VT), EV, Equity) |
| **Histórico** | métricas ano a ano da CVM (crescimento, margens, alíquota efetiva, NWC/receita, capex/receita, ROIC, ROIIC, DSO/DIO/DPO/CCC, dívida líquida/EBITDA, cobertura de juros) + as 4 âncoras agregadas |
| **Valuation** | decomposição do WACC (rf, beta, Hamada, ERP, CRP, Ke USD → Ke BRL, Kd, pesos) + valor terminal e bridge EV → Equity → Target + **checklist de consistência** item a item |
| **Modelo** | DRE pré-D&A, Balanço **com linha de verificação**, DFC indireto, e FCFF × FCFE lado a lado com a divergência entre as duas pontas |
| **Retornos** | TIR e MOIC do acionista em grade bear/base/bull + múltiplos implícitos por ano (EV/EBITDA, EV/Receita, P/L) |

Mudou premissa? Salve na ② e volte aqui — as tabelas re-renderizam com os
números novos.

**Empresa financeira** (ITUB4, BBAS3): as 5 sub-abas aparecem, mas com a trilha
FCFE/Ke — decomposição do Ke, métricas bancárias, capital regulatório.

---

## 6. Etapa ④ Exportar — o Excel

A tela traz:

- **Regerar Excel** — reconstrói o `.xlsx` a partir do pipeline persistido.
- **Baixar TICKER_dcf.xlsx** — botão azul de download, com data/hora e tamanho.
- **Preview das 8 abas** em sub-abas na própria tela, antes de baixar.

O arquivo também fica em `outputs/excel/TICKER_dcf.xlsx`.

### As 8 abas

| Aba | Conteúdo |
|---|---|
| **Capa** | identidade, target, upside, recomendação, resumo do valuation |
| **Premissas** | as 6 premissas ×8 anos, em VERDE (é o que você edita) |
| **Modelo** | DRE + Balanço + DFC, **6 anos históricos (2020–2025) + 8 projetados**, painéis congelados na coluna H |
| **FCFF** | EBIT→NOPAT→FCFF, VP, ROIC/ROIIC, bridge EV→Equity→Target, build-up do WACC, TIR/MOIC |
| **FCFE** | trilha do acionista, descontada ao Ke |
| **Macro** | IPCA, Selic, CDI, câmbio — projetados por ano |
| **Sensibilidades** | matrizes WACC × g e receita × margem |
| **Avisos** | score de dados, checklist do motor item a item, auditoria CVM, e a **procedência de cada política** (origem do WACC, do Kd, do payout, modo da DRE…) |

### A convenção de cores (a sua, não a do WSP)

| Cor | Significa |
|---|---|
| 🔵 **AZUL** | dado histórico vindo da CVM — não mexa |
| 🟢 **VERDE** | premissa sua — é aqui que você escreve |
| ⚫ **PRETO** | fórmula viva do Excel — recalcula sozinha |

**As fórmulas são de verdade.** Mude uma célula verde no Excel e a planilha
inteira recalcula até o target — porque `TARGET PRICE` é
`=B25*B27/B26`, não um número colado. Foi conferido: recalculando as ~740
fórmulas de cada arquivo à mão, o resultado bate com o motor Python com 12 casas
decimais.

**Bancos não têm Excel.** ITUB4 e BBAS3 mostram um aviso nesta etapa — o
exportador cobre a trilha não-financeira. O valuation do banco vive no app.

---

## 7. Receitas rápidas

**Analisar uma carteira inteira de uma vez** (sem abrir o app):

```bash
.venv/Scripts/python.exe -m src.pipeline PETR4 VALE3 ITUB4 WEGE3 SUZB3
```

**Rodar a bateria de testes:**

```bash
.venv/Scripts/python.exe -m pytest tests -q
```

**Verificar formatação antes de commitar:**

```bash
.venv/Scripts/python.exe -m black src tests --check --workers 1
```

**Se algo der errado:** os logs ficam em `logs/`. O app nunca quebra por campo
ausente da CVM — ele registra e segue.

---

## 8. O fluxo que eu recomendo

1. Etapa ① → digite o ticker → **Analisar** → espere ~1 min.
2. Etapa ③ → sub-aba **Histórico** → olhe crescimento, margens e capex reais dos
   últimos anos. **Esta é a base da sua tese.**
3. Etapa ② → escreva as 8 colunas de crescimento e margem que você acredita;
   ajuste Kd e g; **Salvar**.
4. Etapa ③ → sub-aba **Valuation** → confira o checklist. Item em ALERTA não é
   erro: é o modelo te avisando (ex.: "FCO/EBITDA abaixo de 0,7x").
5. Etapa ③ → sub-aba **Modelo** → confira que o balanço fecha (linha de
   verificação ≈ 0).
6. Etapa ④ → **Regerar Excel** → **Baixar**.
