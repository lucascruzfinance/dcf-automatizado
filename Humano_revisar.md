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
