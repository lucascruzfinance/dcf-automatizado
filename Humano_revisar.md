# Humano_revisar.md — Decisões da IA aguardando revisão humana

> **Protocolo (instrução permanente de Lucas, 12/07/2026):** sempre que a IA
> (Claude Fable 5) encontrar um erro, ambiguidade, conflito entre documentos
> ou uma escolha que caberia ao humano, ela **decide sozinha pela melhor
> opção disponível, executa, e registra aqui**: data, situação, escolha
> tomada, alternativas consideradas e justificativa. O humano revisita este
> arquivo periodicamente: se discordar de uma decisão, pede a mudança e a IA
> reverte/ajusta. **Nenhuma entrada aqui é definitiva até o humano aprovar.**
> Esta instrução vale para TODAS as solicitações futuras e está replicada no
> `README.md`, `ROTEIRO.md`, `CONTEXT.md`, `PROMPTS_FABLE.md` e `CLAUDE.md`.

**Como ler:** status `⏳ aguardando revisão` | `✅ aprovada` | `🔁 revertida`.
Entradas mais recentes primeiro. IDs sequenciais `D-nnn` para referência.

---

## 13/07/2026 — Planejamento da v2.1 "Padrão Smartfit" (novo Excel de referência do mentor)

> Sessão do **Claude Code**: análise do modelo Smartfit enviado pelo mentor,
> comparação com o da Direcional e com o código atual, reorganização dos
> arquivos de referência e reescrita completa do `PROMPTS_FABLE.md` para as
> semanas 8–10. Nenhum código de motor/app/exportador foi tocado — só
> planejamento e documentação. As decisões abaixo (D-027 a D-035) orientam o
> Fable 5 nas semanas 8–10 e podem ser revertidas pelo humano.

### D-027 ⏳ — Adotar a MECÂNICA do Smartfit, adiar o UNIT ECONOMICS para a v3.0

- **Situação:** o mentor disse "é assim que tem que ser feito — através de unit
  economics", mas o Lucas decidiu (mensagem de 13/07) começar por premissas
  básicas (crescimento %, margens %, capex %) porque unit economics exige um
  método específico por setor que ele ainda precisa aprender e receber mais
  exemplos.
- **Escolha:** as semanas 8–10 adotam TODO o resto da mecânica do Smartfit
  (DRE completa bruta→líquida, IFRS-16, D&A por safra, revolver, DFC indireto,
  BP aberto, retornos TIR/MOIC, Excel de 9 abas) usando premissas básicas; o
  build-up por unit economics fica para a v3.0. No Prompt 8.1 a projeção de
  receita é extraída para uma função plugável (`projetar_receita`) para que a
  v3.0 encaixe o build-up setorial sem reescrever a DRE.
- **Alternativas:** (a) implementar unit economics já (bloqueia — falta método
  setorial e exemplos); (b) ignorar o Smartfit e manter a v2.0 (perde o
  benchmark novo). Registrado como o caminho pragmático que preserva o alvo.

### D-028 ⏳ — Numeração por SEMANAS de calendário, não por "ondas"

- **Situação:** o humano pediu que daqui para frente o planejamento use
  semanas datadas (8 = 12–19/07, 9 = 19–26/07, 10 = 26/07–02/08) e que o
  `PROMPTS_FABLE.md` seja reescrito do zero até a semana 10 (02/08).
- **Escolha:** `PROMPTS_FABLE.md` reescrito com 8 prompts (8.1–8.3, 9.1–9.3,
  10.1–10.2) mapeados às 3 semanas; a nomenclatura "v2.0 Universalização /
  Ondas 1–5" foi encerrada e substituída por "v2.1 Padrão Smartfit". O
  histórico das Ondas 1–4 (concluídas) permanece no `CONTEXT.md`.
- **Alternativas:** manter "Ondas" (contraria o pedido); recomeçar a contagem
  de semanas em 1 (perde a continuidade com as semanas 1–7 já existentes no
  histórico do projeto).

### D-029 ⏳ — Excels de referência movidos para `referencias/modelos_excel/`

- **Situação:** o Smartfit estava solto na raiz do repo; o da Direcional vivia
  em `tests/fixtures/`. O humano pediu um lugar canônico que sirva de
  referência para o Claude Code / Codex, sem ficar solto.
- **Escolha:** criado `referencias/` (com `README.md`) e
  `referencias/modelos_excel/` contendo os DOIS xlsx + um `ESTRUTURA_*.md`
  para cada (mapa por aba/linha extraído com openpyxl) + o mentor/legenda. O
  Smartfit foi renomeado para `Smartfit_SMFT3_referencia.xlsx` (padrão do da
  Direcional). Movimentação via `git mv` (preserva histórico). Referências em
  `CONTEXT.md`, `README.md` e `CLAUDE.md` atualizadas.
- **Verificação:** nenhum teste depende do arquivo da Direcional (os testes
  usam fixtures sintéticas); `grep` confirmou que só docs citavam
  `tests/fixtures/...xlsx`. Sem quebra de teste esperada pela mudança.
- **Alternativas:** deixar em `tests/fixtures/` (mistura material de
  referência com fixtures de teste); duplicar (arquivos xlsx grandes no git).

### D-030 ⏳ — Ticker de referência do Smartfit: `SMFT3`

- **Situação:** o modelo do mentor avalia a Smart Fit; o pipeline identifica
  empresas por ticker B3. A Smart Fit negocia como **SMFT3**.
- **Escolha:** usar `SMFT3` como o ticker da empresa de referência da v2.1 (o
  arquivo de referência e os DoDs das semanas 8–10 citam SMFT3). O Fable deve
  confirmar na primeira coleta que o resolvedor de ticker encontra SMFT3 na
  CVM (Smart Fit Escola de Ginástica e Dança S.A.); se o código CVM divergir,
  registrar e ajustar.
- **Risco a checar pelo humano/Fable:** SMFT3 fez IPO em 2021 — deve ter ≥ 3
  exercícios anuais na CVM (2022–2024), suficiente para as âncoras. Confirmar
  no Prompt 8.1.

### D-031 ⏳ — DRE completa é OPCIONAL/retrocompatível (modo legado preservado)

- **Situação:** trocar "receita líquida × margem EBITDA" por uma DRE completa
  (bruta→líquida, CPV, SG&A separados) poderia quebrar a regressão dourada de
  DIRR3/MGLU3 e os arquivos de premissas v2 já existentes.
- **Escolha:** o Prompt 8.1 mantém DOIS modos: **legado** (arquivo v2 só com
  `margem_ebitda_ano1..8` → caminho atual byte a byte) e **completo** (campos
  novos presentes → DRE Smartfit). O `gerador_premissas.py` passa a gerar
  sempre o conjunto completo; a regressão dourada roda no modo legado. Todo
  campo novo de premissa é opcional (Princípio 13 novo).
- **Alternativas:** migração forçada (quebra golden e premissas antigas);
  duplicar o projetor (dobra manutenção).

### D-032 ⏳ — Dívida por instrumento é OPCIONAL; target-leverage vira backlog

- **Situação:** o Smartfit modela ~45 instrumentos de dívida em várias moedas
  e uma dívida-alvo = alavancagem × EBITDA. Reproduzir isso como obrigatório
  seria inviável para "qualquer empresa da B3" automaticamente.
- **Escolha:** no Prompt 8.3, a tabela de instrumentos é OPCIONAL nas
  premissas (o analista copia das notas explicativas, já em BRL); sem ela, o
  perfil CP/LP agregado da v2 continua. A dívida-alvo por alavancagem e a
  conversão automática de moeda vão para o backlog (Apêndice C). O REVOLVER,
  esse sim, é formalizado (juros próprios + amortização) porque generaliza a
  captação automática que a v2 já tem.
- **Alternativas:** exigir instrumentos (não escala); ignorar o revolver
  (perde o fechamento de caixa sem plug que é a espinha do modelo).

### D-033 ⏳ — Traduzir D@G/AVP (deal de PE) para "Retornos do acionista"

- **Situação:** as abas D@G e AVP do Smartfit são de private equity (cap
  table, money-in/out, sources & uses, diluição, TIR do fundo) — não se
  aplicam a equity listado.
- **Escolha:** o Prompt 9.1 cria um painel de **Retornos do acionista**:
  múltiplos implícitos por ano (no preço atual e no target) + TIR/MOIC de
  comprar ao preço atual e realizar o target no ano N (com dividendos). A
  mecânica de deal (cap table/sources&uses/diluição) é descartada.
- **Alternativas:** copiar D@G/AVP literalmente (produz números sem sentido
  para ação listada); omitir retornos (perde uma camada que o mentor valoriza).

### D-034 ⏳ — Excel novo: 9 abas para NÃO-financeiras; bancário fica no backlog

- **Situação:** o exportador atual tem 7 abas (FCFF). O Smartfit sugere mais
  abas (Capa+legenda, controle, Macro, Build-Up, Model 3-statements, DCF &
  Retornos). Bancos usam FCFE e não têm dívida operacional/leasing como
  não-financeiras.
- **Escolha:** o Prompt 9.3 reescreve o Excel para 9 abas cobrindo QUALQUER
  não-financeira; bancos mantêm o caminho atual (Excel FCFF bloqueado com
  aviso no app) e o Excel bancário vai para o backlog v2.2. O
  `dfc_simplificado` legado é removido no 9.3 (consumidores migram para o DFC
  indireto).
- **Alternativas:** Excel único para os dois tipos (complexo e arriscado
  agora); manter 7 abas (não alcança o padrão Smartfit).

### D-035 ⏳ — Semana 10 é AUDITORIA dupla (Excel recalculado + app no navegador)

- **Situação:** o humano pediu explicitamente 4 provas: (2) código sem erro
  com dados automatizados; (3) front-end correspondendo; (4) Excel gerado
  correto em valores/fórmulas/referências/premissas/comentários/cores; (5)
  funcionar para qualquer empresa e premissa→efeito.
- **Escolha:** o Prompt 10.1 cria um `verificar_excel.py` que ABRE o Excel,
  RECALCULA de verdade (Excel COM/LibreOffice) e confere célula a célula
  contra os JSONs, mais auditoria de cores/comentários/consistência de fórmula
  e paridade estrutural com o Smartfit; o 10.2 amplia o lote B3 (≥12 empresas,
  casos de borda) e adiciona `test_premissa_efeito.py` (edita 1 premissa →
  verifica a cadeia até o Excel). É o custo de garantir "zero erro".
- **Alternativas:** confiar nos testes unitários (não pega erro de fórmula no
  Excel real); validação só manual (não repetível).

**Observação sem decisão nova:** os itens do "To do list" e "Considerações" do
próprio modelo do mentor (D&A de leasing/imob "muito alta", "checar revolver",
"net debt muito alto", "EBITDA desproporcional") são limitações CONHECIDAS do
modelo dele — não do nosso código. Foram usados apenas para entender a
mecânica; não são tarefas do projeto.

---

## 13/07/2026 — Validação completa das Ondas 3–4 (suíte + auditoria + figuras + app no navegador)

### D-025 ⏳ — Painel de decisão passa a mostrar a taxa e o g do CENÁRIO ativo

- **Situação:** na validação visual do app, o Overview com cenário Bear/Bull
  ativo mostrava Target/upside/recomendação do cenário, mas WACC (ou Ke) e g
  do caso BASE — mesmo com o bloco `cenarios` persistindo `taxa_desconto` e
  `g` próprios por cenário (ex.: DIRR3 Bull = 13,90%/1,5% vs base
  14,97%/1,0%). Os cinco KPIs da mesma linha contavam histórias mistas.
- **Escolha:** `painel_decisao` (app.py) usa `taxa_desconto`/`g` do cenário
  ativo quando presentes, com fallback no caso base. Validado no navegador:
  Bull mostra 13,90%/1,50%. A figura "Dashboard Executivo" logo abaixo
  permanece SEMPRE no caso base — ela é a arte persistida do motor e está
  rotulada como tal ("fonte unica: motor de calculo").
- **Alternativas consideradas:** manter tudo no base com os deltas apenas no
  caption (estado anterior — KPI inconsistente com o Target exibido);
  regenerar a figura executiva por cenário (recálculo/arte no front-end,
  contra o contrato "o app apenas apresenta o persistido").

### D-026 ⏳ — Escape de `$` no metric da faixa de múltiplos (bug visual real)

- **Situação:** o metric "Faixa por multiplos (Q1-Q3)" concatena DUAS moedas
  na mesma string ("R$ 10,72 - R$ 19,65"). O `st.metric` renderiza o valor
  como markdown, e um PAR de `$` vira delimitador de math inline: a tela
  mostrava "R 10,72 - R 19,65" com o trecho central em fonte de código
  (confirmado no DOM: `<code class="language-math">`). Único ponto do app
  com duas moedas numa string (auditado por grep).
- **Escolha:** escapar `$` → `\$` apenas nesse metric, com comentário no
  código explicando a restrição. Validado no navegador: "R$ 10,72 - R$
  19,65" literal, zero elementos math.
- **Alternativas consideradas:** mudar `formatar_moeda_brl` globalmente
  (vazaria `\$` literal em Plotly/Excel, que não passam por markdown);
  trocar o formato da faixa para evitar o segundo `R$` (perde o padrão
  visual das demais moedas do app).

**Observações sem decisão nova (não são erros novos):** (1) preço atual
divergente entre seções — 13,01 no painel (ev_equity, mercado congelado de
08/07) vs 13,28 nos comparáveis (coletado em 12/07) — é a consequência já
registrada em D-011/D-022; a Onda 5 (orquestração/automação de dados)
sincroniza as datas de mercado. (2) A validação rodou o pipeline completo de
RENT3 pelo próprio app (21,1s, score 96, VENDA −46,6% por premissas
automáticas conservadoras — padrão já registrado em D-024); os artefatos de
dados de RENT3 ficaram no working tree.

---

## 12/07/2026 — Onda 2 (Prompt 2, executada ANTES das Ondas 3–4 por ordem do humano)

### D-014 ⏳ — Correção do sinal do CAPEX no PP&E (bug real da v1)

- **Situação:** na v1, `schedule_ppe` somava o CAPEX ASSINADO (negativo) ao
  imobilizado — o ativo ENCOLHIA a cada investimento e o caixa-plug absorvia
  a inconsistência em silêncio. Com o caixa vindo do DFC (v2), o balanço
  passou a vazar exatamente 2×|capex| por ano.
- **Escolha:** PP&E_t = PP&E_(t-1) + |CAPEX_t| − D&A_t (ativo cresce pela
  magnitude; o capex segue persistido assinado por convenção de caixa).
- **Impacto na regressão dourada:** D&A projetada agora cresce com o ativo
  → EBIT menor, mas FCFF maior (tax shield da D&A) → Target Price sobe
  (DIRR3 15,25→17,04; MGLU3 5,97→8,10 — ver D-022).

### D-015 ⏳ — Convenção de saldo inicial para juros e receita financeira

- **Situação:** juros dependem da dívida, que depende da captação, que
  depende do caixa, que depende dos juros (circularidade clássica).
- **Escolha:** juros = Kd × dívida de ABERTURA; receita financeira = taxa ×
  (caixa inicial + aplicações); captação entra no FIM do ano (não paga juros
  no próprio ano). Sem iteração, sem circularidade, documentado no módulo.
- **Alternativas:** iterar 2–3 passadas (converge, mas o Excel espelho vira
  referência circular); saldo médio com captação (circular).

### D-016 ⏳ — Balanço ancorado no BP real: residuais constantes + verificação

- **Situação:** o caixa deixou de ser plug; o fechamento precisa nascer da
  contabilidade, não de um resíduo forçado.
- **Escolha:** `outros_ativos`/`outros_passivos` = residuais do BP REAL do
  Ano 0 (intangível, RLP, provisões etc.), constantes na projeção; caixa =
  resultado do DFC; `Ativo = Passivo + PL` vira VERIFICAÇÃO (alerta + NF1,
  nunca raise silencioso). Com residuais constantes o fechamento é exato
  por construção — desvio indica premissa/dado quebrado.
- **Alternativas:** projetar cada linha residual (escopo de modelo completo
  por setor, sem dado que sustente); manter plug (esconde erros — vetado
  pela spec).

### D-017 ⏳ — Trilha bancária: calibração pela margem líquida + clamp de alíquota

- **Situação:** a alíquota efetiva histórica de banco na DFP é ruidosa (JCP
  e participações estatutárias distorcem 3.06/3.05 — BBAS3 media 74,5%!), e
  linhas intermediárias (equivalência, participações) não são projetadas.
  Com as âncoras cruas, o Target do BBAS3 saía R$ −10,50.
- **Escolha:** (a) alíquota bancária clampada em [20%, 50%], senão padrão
  45% da config; (b) razão de despesas operacionais CALIBRADA para
  reproduzir a margem líquida média histórica: desp = ML/(1−t) − margem_RB.
  O desvio das linhas não projetadas é absorvido na linha de despesas, e o
  ano 1 projetado reproduz a lucratividade REAL do banco.
- **Resultado:** BBAS3 Target R$ 40,77 (+98% — premissa de partida
  agressiva, ordem de grandeza correta); ITUB4 R$ 54,33 (+22,6%).

### D-018 ⏳ — Capital regulatório retido nunca é liberado

- **Situação:** FCFE = LL − ΔCapital exige política para o excesso de
  capital do Ano 0 (PL real > mínimo regulatório).
- **Escolha:** capital_0 = max(PL real, mínimo); capital_t = max(mínimo_t,
  capital_(t-1)) — o banco não devolve capital já constituído de uma vez
  (evita FCFE ano-1 inflado por "liberação" irrealista) nem deixa o índice
  cair. RWA por proxy: fator_rwa × ativos, com ativos crescendo com as
  receitas (a DFP não expõe RWA real).
- **Alternativas:** liberar excesso no ano 1 (agressivo); payout fixo sobre
  LL (ignora exigência de capital).

### D-019 ⏳ — Cenários: delta de taxa aplicado ao bloco persistido

- **Situação:** WACC/Ke nascem de beta/Kd/estrutura — não são premissas
  diretas; o cenário pede "WACC +1pp".
- **Escolha:** o motor_cenarios roda o pipeline com premissas ajustadas
  (crescimento×fator, margem+Δ, g+Δ) e aplica o Δ de taxa AO BLOCO
  persistido antes de VT/EV; preço e Rf vêm do JSON de mercado (congelados,
  reproduzíveis — nada de preço vivo em cenário). Premissas do analista são
  restauradas SEMPRE (backup + finally) e o disco termina no caso base.

### D-020 ⏳ — VT financeiro: payout sustentável e compatibilidade do checklist

- **Situação:** FCFE_8 pode ser ≤ 0 (crescimento consumindo capital); e o
  checklist universal (U1/U4) lê a taxa do campo `wacc`.
- **Escolha:** base do VT = FCFE_8; se ≤ 0, usa LL_8 × (1 − g/ROE_8)
  (payout sustentável de Damodaran) com aviso e `base_vt` explicitando; o
  `valor_terminal` financeiro persiste o Ke TAMBÉM sob a chave `wacc` com
  `taxa_desconto_rotulo` explicando (compat sem duplicar o checklist).

### D-021 ⏳ — Convenção de desconto e alíquota do NOPAT

- **Escolha:** mid-year e período-stub implementados como config global
  (`desconto`), DEFAULT DESLIGADO (golden preservada); aplicados no motor
  (VT/EV/FCFE) mas NÃO nas derivações rápidas do `apoio_cenarios` (heatmaps
  continuam fim-de-período — divergência só existe se o humano ligar a
  convenção). NOPAT segue alíquota MARGINAL 34% (efetiva fica nas métricas
  como âncora; motivo documentado no código).

### D-022 ⏳ — Regressão dourada da Onda 2 (mudanças EXPLICADAS de Target Price)

- **Números (preço de mercado congelado de 08/07):** DIRR3 R$ 15,25 → 17,04
  (+11,7%); MGLU3 R$ 5,97 → 8,10 (+35,7%); balanço fecha (dif < 1e-6) e
  checklists aprovados nos dois.
- **Drivers, na ordem de materialidade:** (1) correção do PP&E (D-014):
  D&A cresce com o ativo → tax shield maior no FCFF; (2) dívida amortizando
  → dívida média menor → WACC DIRR3 16,63%→~14,9% (e bridge subtrai dívida
  do Ano 0 real incluindo leasing); (3) bridge completo com minoritários,
  coligadas e leasing reais (antes zerados); (4) RET da DIRR3 agora sobre
  Receita Bruta real (razão RB/RL da DVA) — imposto maior que o proxy;
  (5) payout real e receita financeira sobre caixa mudam FCFE/caixa (não o
  FCFF). MGLU3 é mais sensível por alavancagem operacional + leasing alto.
- **Validação numérica final é do humano** (comparar com RI/consenso).

## 12/07/2026 — Sessão "Ondas 3 e 4" (Prompts 3 e 4 do PROMPTS_FABLE.md)

### D-001 ⏳ — Pular a Onda 2 e executar as Ondas 3 e 4

- **Situação:** o humano pediu explicitamente os Prompts 3 e 4, mas o
  `PROMPTS_FABLE.md` define as ondas como progressivas e sequenciais ("não
  pule etapas") e os Prompts 3–4 citam dependências da Onda 2 (motor de
  cenários Bear/Base/Bull de primeira classe, trilha FCFE/Ke validada para
  bancos).
- **Escolha:** executar 3 e 4 agora, adaptando os pontos dependentes da
  Onda 2 (ver D-002, D-003, D-004) e registrando cada adaptação.
- **Alternativas:** (a) executar a Onda 2 primeiro — contraria o pedido
  explícito; (b) recusar parcialmente — pior das opções, não entrega nada.
- **Justificativa:** a "Regra de precedência" do próprio `PROMPTS_FABLE.md`
  diz que o pedido explícito do humano vence, desde que a IA avise sobre o
  conflito — este registro é o aviso. A Onda 2 fica pendente e recomendada
  como próximo passo.

### D-002 ⏳ — Football Field sem o motor de cenários da Onda 2

- **Situação:** o Prompt 3 pede DCF Bear/Base/Bull "agora do motor de
  cenários da Onda 2", que não existe.
- **Escolha:** manter as barras DCF Bear/Base/Bull derivadas de
  `apoio_cenarios.recalcular_cenario` (aproximação v1 documentada) e trocar
  apenas os comps placeholders por comps reais — o objetivo central da onda.
- **Alternativas:** implementar `motor_cenarios.py` completo agora (escopo
  da Onda 2 inteira); remover as barras de cenário.
- **Justificativa:** o placeholder eliminado era o dos comps; os cenários
  v1 já são calculados a partir do resultado do motor (fonte única).

### D-003 ⏳ — ITUB4 no DoD da Onda 3 sem trilha FCFE validada

- **Situação:** o DoD pede Football Field para ITUB4, mas banco não tem
  valuation DCF antes da Onda 2 (não há `ev_equity` para ITUB4).
- **Escolha:** tornar as barras do Football Field **opcionais por
  disponibilidade de dados**: para ITUB4 renderizam comps reais (P/VP, P/L),
  faixa de 52 semanas e preço atual, SEM as barras DCF; o app explica que a
  trilha FCFE chega na Onda 2.
- **Alternativas:** falhar para ITUB4 (quebra o DoD); inventar um DCF
  bancário rápido (violaria a regra de não fazer valuation errado por tipo).
- **Justificativa:** entrega o máximo de valor real sem produzir um Target
  Price sem sentido para banco — exatamente o erro que a v2.0 quer evitar.

### D-004 ⏳ — Premissas automáticas de partida para tickers novos

- **Situação:** o DoD da Onda 4 exige que buscar um ticker novo (ex.:
  WEGE3, RADL3) rode o pipeline completo e renderize tudo; mas a filosofia
  do projeto diz que premissas são o trabalho intelectual do humano, e o
  `main.py` v1 PARA quando não há premissas revisadas.
- **Escolha:** criar `gerador_premissas.py`: premissas de partida geradas
  por âncoras históricas (CAGR, margem média, CAPEX médio, DSO/DIO/DPO) +
  defaults do subtipo (`config/setores.json`), com 8 valores individuais em
  interpolação linear (nunca taxa única replicada), marcadas com
  `premissas_automaticas: true` e alerta visível no app até o analista
  salvar premissas revisadas (o salvamento remove a flag).
- **Alternativas:** parar e pedir premissas (quebra o DoD e a UX);
  premissas nulas (pipeline falha); copiar as premissas de outra empresa
  (contaminação entre teses).
- **Justificativa:** preserva a filosofia (o humano continua dono da tese;
  o app deixa explícito que são premissas de PARTIDA) e destrava o fluxo
  universal exigido pela onda.

### D-005 ⏳ — `st.data_editor` no lugar de `streamlit-aggrid`

- **Situação:** o Prompt 4 pede tabelas editáveis "via streamlit-aggrid".
- **Escolha:** usar `st.data_editor` (nativo do Streamlit) para os vetores
  de premissas editáveis.
- **Alternativas:** `streamlit-aggrid` (continua instalado e disponível).
- **Justificativa:** o AgGrid é um componente customizado que não é
  testável via `AppTest` (o DoD exige testes verdes de app), tem tema
  próprio difícil de alinhar à paleta navy e quebra com atualizações do
  Streamlit; o `data_editor` é nativo, testável, respeita o tema e mantém a
  regra "editar célula → recalcular o motor Python". Troco por AgGrid se o
  humano preferir.

### D-006 ⏳ — Fonte dos múltiplos dos comparáveis

- **Situação:** o Prompt 3 permite "yfinance e/ou CVM" para os múltiplos.
- **Escolha:** múltiplos dos PEERS via yfinance (`trailingPE`,
  `priceToBook`, `enterpriseToEbitda`, `enterpriseToRevenue`; EV/EBIT
  calculado só quando o EBIT do peer está disponível na demonstração do
  yfinance); denominadores da EMPRESA-ALVO via CVM (Ano 0 oficial do
  pipeline). Peer sem dado → log e exclusão; múltiplo ≤ 0 → descartado com
  aviso; mediana exige ≥ 2 peers válidos (aviso de amostra pequena com < 3).
  A empresa-alvo é EXCLUÍDA da mediana do próprio peer group (padrão de
  mercado; evita viés circular) mas aparece na tabela destacada.
- **Alternativas:** calcular múltiplos dos peers pela CVM (exigiria coletar
  DFP de todos os peers — minutos por empresa e sem preço intradiário);
  incluir a própria empresa na mediana.
- **Justificativa:** yfinance dá múltiplos de mercado atuais em segundos e
  a CVM continua sendo a fonte dos fundamentos da empresa avaliada.

### D-007 ⏳ — Cenários no app antes da Onda 2

- **Situação:** o Prompt 4 pede "alternar Bear/Base/Bull recarrega todo o
  dashboard", mas cenários completos e persistidos são da Onda 2.
- **Escolha:** seletor de cenário no app aplicado aos KPIs de decisão,
  sensibilidades e Football Field via `apoio_cenarios` (derivação do caso
  base); o restante do dashboard continua no caso base até a Onda 2.
- **Alternativas:** reexecutar o pipeline inteiro por cenário a cada clique
  (custo alto e mistura premissas); esconder o seletor.

## 12/07/2026 — Auditoria da Onda 1 (Prompt 1, executado em 11–12/07)

### D-008 ⏳ — Ordem da cascata de mapeamento: nome ANTES de prefixo

- **Situação:** o Prompt 1 especificou a cascata como código → prefixo →
  nome → log; a implementação usa código → **nome** → **prefixo** → log.
- **Escolha:** manter nome antes de prefixo.
- **Justificativa:** agregados do DFC (6.01 = FCO) absorveriam por prefixo
  linhas de ajuste como "Depreciação e Amortização", que precisam do match
  por nome. A inversão está documentada no módulo e no mapeamento
  (`cascata.observacao`), com teste cobrindo o caso.

### D-009 ⏳ — Parquet limpo adotado só no Ano 0 do projetor (schedules no JSON bruto)

- **Situação:** o Prompt 1 diz "a partir da v2, a projeção lê Parquet
  limpo"; hoje o `projetor_dre` lê o Ano 0 do Parquet, mas os schedules
  WK/PP&E/Dívida ainda leem os JSONs brutos (fallback documentado).
- **Escolha:** migração parcial na Onda 1, completando na Onda 2 (que
  reescreve os schedules de qualquer forma).
- **Justificativa:** trocar a fonte de dados dos schedules sem reescrevê-los
  dobraria o risco de regressão da Onda 1; a regressão dourada exigia
  estabilidade. Registrado no CONTEXT como pendência.

### D-010 ⏳ — Arquivos de dados rastreados no git contra o .gitignore

- **Situação:** `data/raw/cvm/DIRR3_bp.json`, `DIRR3_dre.json` e
  `DIRR3_meta.json` foram commitados antes do `.gitignore` de dados e
  continuam rastreados — a recoleta os marca como modificados.
- **Escolha:** NÃO mexer no índice git (a divisão de trabalho do projeto
  diz que commits são do humano). Recomendação registrada: rodar
  `git rm --cached data/raw/cvm/DIRR3_bp.json data/raw/cvm/DIRR3_dre.json
  data/raw/cvm/DIRR3_meta.json` no próximo commit para o repositório seguir
  a própria convenção.
- **Alternativas:** executar o `git rm --cached` eu mesma (mexe no que vai
  para o GitHub sem aval humano).

### D-011 ⏳ — Preço ao vivo do yfinance no `calculador_ev`

- **Situação:** `obter_preco_atual` prioriza yfinance AO VIVO sobre o JSON
  de mercado persistido; o upside muda entre execuções (em 12/07 a MGLU3
  saiu de COMPRA para NEUTRO só porque a ação subiu de R$ 4,36 para 5,22).
- **Escolha:** manter o comportamento v1 (preço vivo) e registrar — preço
  atual de mercado é, por definição, vivo; o Target Price não é afetado.
- **Alternativas:** congelar no preço do JSON coletado (reprodutível, porém
  desatualizado); gravar a data/fonte do preço no resultado (feito: o
  `ev_equity` persiste o preço usado).
- **Impacto documentado:** comparações de upside entre execuções precisam
  considerar a data do preço.

### D-012 ⏳ — CONTEXT.md v1 desatualizado sobre a aba Excel Preview

- **Situação:** o CONTEXT dizia que a aba Excel Preview era "stub
  declarado", mas o `app.py` atual (commit "claude 6.2 parte 1", 11/07) já
  renderiza as 7 abas via `montar_preview_por_aba` + botão de download com
  testes verdes.
- **Escolha:** tratar o item 4.5 do Prompt 4 como JÁ ENTREGUE (só refinar),
  e corrigir a descrição no CONTEXT.
- **Justificativa:** evitar retrabalho; os testes
  `test_excel_preview_renderiza_7_abas` e `test_excel_preview_download_...`
  já cobrem o comportamento.

### D-023 ⏳ — Onda 4: escolhas do front-end multi-empresa

- **Situação:** o Prompt 4 deixa graus de liberdade na implementação do app.
- **Escolhas tomadas:** (a) sensibilidade "ao vivo" usa a derivação rápida
  do caso base (`apoio_cenarios`) — instantânea e sem recálculo em JS; o
  recálculo OFICIAL continua no botão Salvar (motor completo); (b) o
  seletor de cenários do Overview lê o bloco `cenarios` persistido (pipeline
  completo por cenário — o "recarrega todo o dashboard" da spec aplica-se
  aos KPIs de decisão; gráficos pesados seguem no caso base até a Onda 5);
  (c) watchlist em `data/watchlist.json` com snapshot de target/recomendação
  e timestamp (sem preço vivo); (d) Excel Preview bloqueado para financeiras
  com aviso (o exportador de 7 abas é FCFF; modelo bancário na Onda 5);
  (e) cache do app por mtime dos JSONs (recoleta só em ação explícita).
- **Alternativas:** recalcular o motor a cada movimento de slider (2s+ por
  interação); cenário recarregando todos os gráficos (recusa por latência).

### D-024 ⏳ — Premissas automáticas produzem casos extremos (para revisão)

- **Situação:** com premissas de PARTIDA automáticas, alguns resultados
  saem extremos: BBAS3 +98% (COMPRA), WEGE3 R$ 13,08 e RADL3 R$ 1,08
  (VENDA) contra preços de mercado muito acima.
- **Escolha:** manter os resultados persistidos COM a flag
  `premissas_automaticas` e o aviso permanente no app; a triangulação
  denuncia o descolamento ("DCF abaixo/acima da faixa dos múltiplos").
  Nenhum resultado automático é tese de investimento.
- **Alternativas:** calibrar premissas para convergir ao preço de mercado
  (inverte o propósito do DCF — vetado); esconder o valuation até revisão
  humana (esconde também o diagnóstico).
- **Ação recomendada ao humano:** revisar premissas de BBAS3, WEGE3 e RADL3
  na seção Premissas do app e salvar (remove a flag e assume a autoria).

### D-013 ⏳ — Classificação de "Emp. Adm. Part. - X" pelo segmento X

- **Situação:** a CVM registra operadoras consolidadas (ex.: WEG) como
  "Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças"; a regra de holding
  capturava tudo e WEGE3 virava `holding`.
- **Escolha:** look-through configurável (`prefixo_holding_cvm` em
  `config/setores.json`): classifica pelo segmento após o prefixo; holding
  só sem segmento reconhecível (ITSA4 "Sem Setor Principal"). Efeito
  colateral aceito: BRAP4 ("Emp. Adm. Part. - Extração Mineral") classifica
  como `mineracao` mesmo sendo holding pura da Vale — peers de mineração são
  mais úteis para ela do que um balde genérico de holdings.
- **Alternativas:** manter tudo como holding (esconde o negócio real);
  lista manual de exceções por ticker (não escala).
