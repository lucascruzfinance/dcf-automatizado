# CLAUDE.md — Guia operacional do repositório dcf-automatizado

Sistema de valuation por DCF para ações da B3. Estado atual e próxima tarefa:
`CONTEXT.md` (fonte única de verdade do estado). Especificação v1.0: `docs/ROTEIRO.md`.
Plano vigente — **v2.1: Semana 9.0 CONCLUÍDA** (6 prompts 9.0.0–9.0.5) e
**Semana 10 PLANEJADA** (gráficos vivos no app): `PROMPTS_FABLE.md`. O Excel
final segue o **padrão Direcional** (aba `Modelo` + FCFF/FCFE separadas, cores
de Lucas), não o Smartfit — unit economics ficou para a v3.0. Modelos Excel de
referência (imutáveis) e mapas: `referencias/modelos_excel/`.

## Protocolo de decisões autônomas (instrução permanente de Lucas, 12/07/2026)

Quando encontrar erro, ambiguidade, conflito entre documentos ou uma escolha
que caberia ao humano: **NÃO pare para perguntar.** Escolha sozinho a melhor
opção disponível, execute, e registre a decisão em **`Humano_revisar.md`** com
data, situação, escolha tomada, alternativas consideradas e justificativa
(IDs sequenciais `D-nnn`, mais recente primeiro). O humano revisa o arquivo
periodicamente e pode reverter qualquer decisão. Isso vale para TODA
solicitação, em TODAS as sessões.

## Regras que quebram builds se ignoradas

- Código em português (funções, variáveis, comentários).
- Nomes de coluna só existem se registrados em `config/mapeamento_cvm.json`.
- O motor Python calcula UMA vez; Streamlit/Excel/BI apenas apresentam
  (zero recálculo em JS/DAX).
- Sinais: despesas/saídas negativas; receitas/entradas positivas.
- Vetores de premissas têm 8 valores individuais (`_ano1..8`) — nunca uma
  taxa única replicada.
- ROIC/FCFF/LL negativos são válidos; não travar.
- Campo CVM ausente → log (`logs/`), nunca quebra silenciosa.
- Config em `config/*.json`, nunca hard-code setorial.
- Regressão dourada TRIPLA: DIRR3, MGLU3 e SMFT3 não podem mudar sem explicação.
- Ao fim de cada sessão: atualizar a Seção 8 do `CONTEXT.md` (sessão datada).

## Ambiente e comandos

- Validação SEMPRE com a venv do projeto: `.venv/Scripts/python.exe -m pytest tests -q`,
  `... -m black src tests --check --workers 1` (o `--workers 1` é obrigatório
  nesta máquina), `... -m flake8 src tests`.
- O Python global 3.11.9 também tem as libs (instaladas em 12/07/2026), mas a
  venv é o ambiente oficial.
- Pipeline: `python main.py --ticker DIRR3 --setor construcao
  --usar-premissas-existentes`; lote: `python -m src.coleta.coleta_lote
  --tickers ...`; verificação: `python -m src.verificar_semana3`.
- App: `streamlit run app.py` (testes de UI via `AppTest`, sem navegador).
