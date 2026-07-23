# 📊 DCF Automatizado — Sistema de Valuation para Ações da B3

> **Projeto de Ciências da Computação aplicado ao Mercado Financeiro**
> Automação completa do processo de valuation por Fluxo de Caixa Descontado com coleta de dados via APIs públicas, motor de cálculo financeiro integrado, interface de premissas guiada por dados históricos, front-end institucional interativo e exportação em Excel de nível profissional — com arquitetura projetada para escalar a qualquer ação listada na B3.

---

> **🤖 Protocolo de decisões da IA (instrução permanente, 12/07/2026):** quando a IA de
> implementação (Claude Fable 5) encontra um erro, ambiguidade ou escolha que caberia ao
> humano, ela decide sozinha pela melhor opção disponível, executa, e registra a decisão em
> **[`Humano_revisar.md`](Humano_revisar.md)** — data, situação, escolha tomada, alternativas
> e justificativa. O humano revisita o arquivo e aprova ou pede reversão. Nenhuma decisão
> registrada lá é definitiva até a revisão humana. Desde 22/07/2026 esse arquivo guarda só
> as decisões **em aberto**; o histórico executado está em
> [`docs/historico_decisoes.md`](docs/historico_decisoes.md).
>
> 📘 **Como usar o app:** [`docs/TUTORIAL.md`](docs/TUTORIAL.md).

---

## 🧭 Índice

1. [Sobre o Projeto](#sobre-o-projeto)
2. [Escopo da Versão 1.0](#escopo-da-versão-10)
3. [Por Que Construir Isso](#por-que-construir-isso)
4. [O Problema que Este Projeto Resolve](#o-problema-que-este-projeto-resolve)
5. [Arquitetura do Sistema](#arquitetura-do-sistema)
6. [Por Que Cada Decisão Foi Tomada Dessa Forma](#por-que-cada-decisão-foi-tomada-dessa-forma)
7. [Stack Tecnológico](#stack-tecnológico)
8. [Front-end Institucional](#front-end-institucional)
9. [Estrutura do Repositório](#estrutura-do-repositório)
10. [Módulos do Sistema](#módulos-do-sistema)
11. [O Que o Analista Faz vs. O Que o Sistema Faz](#o-que-o-analista-faz-vs-o-que-o-sistema-faz)
12. [Outputs Gerados](#outputs-gerados)
13. [Instalação e Execução](#instalação-e-execução)
14. [Roadmap](#roadmap)
15. [Referências Teóricas e Bibliográficas](#referências-teóricas-e-bibliográficas)
16. [Autor](#autor)

---

## Sobre o Projeto

Este projeto constrói um **sistema automatizado de valuation por DCF (Discounted Cash Flow)** com arquitetura projetada para analisar empresas de capital aberto listadas na B3. A partir do ticker da empresa, o sistema identifica se ela é uma empresa operacional ou uma instituição financeira, coleta dados históricos de múltiplas fontes públicas, calcula métricas financeiras, apresenta esse histórico ao analista como âncora intelectual, solicita as premissas que exigem julgamento humano — incluindo taxas de crescimento de receita individuais para cada um dos 8 anos de projeção — executa toda a cadeia de cálculo do valuation pelo método correto para cada tipo de empresa, e entrega um front-end institucional interativo com Football Field, tabelas de sensibilidade, análise de criação de valor e exportação profissional em Excel.

O benchmark de qualidade mínima é o modelo Excel desenvolvido para a **Direcional Engenharia (DIRR3)** durante o programa trainee do InFinance/Insper em 2026 — um modelo integrado com DRE, Balanço Patrimonial e DFC projetados, schedules completos de Working Capital, PP&E e Dívida, modelos unitários de empreendimento, Football Field e tabelas de sensibilidade. O objetivo deste sistema é replicar e superar esse nível de análise de forma programática, escalável e auditável.

---

## Escopo da Versão 1.0

Este projeto adota uma filosofia deliberada de **profundidade antes de amplitude**. A versão 1.0 não tenta cobrir todos os setores da B3 de uma vez — essa ambição, sob prazo real, produz cinco análises rasas em vez de uma excelente. Em vez disso, a v1.0 entrega:

- **DIRR3 (Direcional Engenharia) — implementação de referência.** O caso canônico, validado célula a célula contra o modelo Excel do trainee. É o benchmark de que o motor produz um valuation defensável ponta a ponta.
- **MGLU3 (Magazine Luiza) — prova de universalidade.** Um segundo setor não-financeiro (varejo) que demonstra que a arquitetura não está acoplada a uma única empresa. Reaproveita mais de 90% do motor sem alteração de código.

A **arquitetura de duas trilhas** (não-financeira via FCFF/WACC e financeira via FCFE/Ke) é construída e documentada na v1.0, mas a trilha financeira só é validada contra dados reais na v1.5. Isso mantém o sistema honesto: o que está no repositório como "funciona" foi de fato testado contra uma fonte pública, não apenas escrito.

O detalhamento semana a semana da construção está no arquivo [`docs/ROTEIRO.md`](docs/ROTEIRO.md).

---

## Por Que Construir Isso

A interseção entre **Ciências da Computação e Mercado Financeiro** é um dos campos de maior crescimento e impacto na indústria global. Analistas que dominam tanto o rigor técnico do valuation quanto a capacidade de automatizar e escalar processos via programação representam um diferencial competitivo real em Asset Management, Equity Research e Investment Banking.

O processo tradicional de construção de um modelo DCF em Excel é altamente manual e intensivo em tempo. Um analista experiente leva entre 15 e 40 horas para construir um modelo integrado do zero para uma empresa nova — coletando dados manualmente de relatórios, estruturando as demonstrações financeiras, construindo os schedules, calculando o WACC e gerando os gráficos. Esse tempo é em grande parte gasto em trabalho mecânico repetível: copiar dados, formatar tabelas, aplicar fórmulas que são as mesmas para qualquer empresa do mesmo setor.

Este projeto parte de uma distinção fundamental: **o trabalho mecânico pode e deve ser automatizado. O trabalho intelectual não pode e não deve ser automatizado.** O valor do analista está nas premissas que ele define — a taxa de crescimento da receita que ele projeta para o Ano 3, a margem EBITDA que ele acredita ser sustentável no longo prazo, o g que ele escolhe com responsabilidade sabendo que representa 60% a 80% do valor da empresa. Essas decisões exigem conhecimento do modelo de negócios, leitura do ambiente competitivo, interpretação do ciclo de capital e julgamento sobre o futuro — coisas que nenhum algoritmo substitui.

O sistema automatiza o trabalho mecânico e preserva o trabalho intelectual exatamente onde ele pertence: nas mãos do analista.

---

## O Problema que Este Projeto Resolve

Existem três problemas concretos que motivam a construção deste sistema:

**Problema 1 — Escalabilidade.** Um modelo Excel é feito para uma empresa específica. Cada novo ticker exige um novo modelo construído do zero ou uma adaptação trabalhosa. A arquitetura deste sistema aceita o ticker como input e executa o pipeline automaticamente, adaptando a metodologia ao tipo de empresa detectado. Na v1.0 isso é validado para dois setores não-financeiros; a expansão para os demais é incremental por design.

**Problema 2 — Metodologia inadequada por tipo de empresa.** O modelo FCFF descontado pelo WACC, que é o método padrão para empresas operacionais, é matematicamente incorreto para instituições financeiras. Em um banco, a dívida é matéria-prima do negócio e não passivo financeiro — separar o Enterprise Value do Equity Value da forma convencional não faz sentido. O método correto para bancos, seguradoras e holdings financeiras é o FCFE ou DDM descontado apenas pelo custo do equity (Ke). O sistema detecta o tipo de empresa e executa o método correto, sem intervenção do usuário.

**Problema 3 — Premissas engessadas.** Modelos simplificados assumem uma única taxa de crescimento que se repete por todo o período de projeção. Isso é analiticamente inadequado para qualquer empresa em fase de transição — uma construtora que está acelerando lançamentos nos primeiros anos e desacelerando à medida que o portfólio matura, uma varejista que está expandindo a base de lojas e depois colhendo a alavancagem operacional. Este sistema solicita obrigatoriamente uma taxa de crescimento individual para cada um dos 8 anos de projeção, permitindo que o analista construa uma narrativa de crescimento coerente com a dinâmica específica da empresa.

---

## Arquitetura do Sistema

O sistema é organizado em **5 módulos sequenciais** que se comunicam via arquivos intermediários em formato Parquet e JSON:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ENTRADA DO USUÁRIO                              │
│   Front-end Streamlit  ou  python main.py --ticker DIRR3 --setor ...     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 1 — COLETA AUTOMÁTICA DE DADOS              [100% Automático]   │
│                                                                          │
│  CVM (dados.cvm.gov.br)     → DRE, BP, DFC históricos (5-7 anos)       │
│  yfinance                   → Preço, Beta, Ações, Market Cap, T-Bond    │
│  python-bcb (BACEN)         → Selic, IPCA, CDI, Projeções Focus        │
│                                                                          │
│  Detecção automática: Empresa Financeira ou Não-Financeira?             │
│  Output: data/raw/ e data/processed/                                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 2 — PAINEL HISTÓRICO                        [100% Automático]   │
│                                                                          │
│  Não-Financeiras: ROIC, ROIIC, DSO/DIO/DPO/CCC, Margens, Alavancagem  │
│  Financeiras: ROE, ROA, NIM, Índice de Eficiência, NPL, Basileia       │
│                                                                          │
│  Objetivo: âncora intelectual para as decisões de premissa              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 3 — INTERFACE DE PREMISSAS              [ÚNICO INPUT HUMANO]    │
│                                                                          │
│  8 taxas de crescimento de receita individuais (Ano 1 até Ano 8)       │
│  8 margens EBITDA individuais por ano                                   │
│  8 valores de CAPEX/Receita individuais por ano                         │
│  Prazos de WK, Custo da Dívida, Componentes do WACC, g                 │
│                                                                          │
│  Front-end institucional com campos, sliders e histórico ao lado        │
│  Output: data/premissas/<TICKER>_premissas.json                         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 4 — MOTOR DE CÁLCULO                        [100% Automático]   │
│                                                                          │
│  Não-Financeiras:                                                        │
│  DRE + BP + DFC Projetados → Schedules WK, PP&E, Dívida                │
│  FCFF = NOPAT + D&A − ΔNWC − CAPEX                                     │
│  ROIC = NOPAT / IC | ROIIC = ΔNOPAT_t / ΔIC_(t−1)                      │
│  WACC = (E/V)×Ke + (D/V)×Kd×(1−t)                                     │
│  TV = FCFF₈ × (1+g) / (WACC−g)                                         │
│  EV → Equity Value → Target Price                                       │
│                                                                          │
│  Financeiras (arquitetura pronta, validação em v1.5):                   │
│  FCFE = LL − ΔCapital Regulatório Retido                               │
│  Ke via CAPM com ajuste Brasil                                          │
│  TV = FCFE₈ × (1+g) / (Ke−g)                                           │
│  Equity Value → Target Price (sem bridge EV→Equity)                    │
│                                                                          │
│  Checklist de 10+ verificações de consistência                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 5 — APRESENTAÇÃO E OUTPUTS                  [100% Automático]   │
│                                                                          │
│  App Streamlit — fluxo guiado de 4 etapas:                              │
│    ① Empresa → ② Premissas (as 6) → ③ Resultados → ④ Exportar          │
│  ③ Resultados: Overview · Histórico · Valuation · Modelo · Retornos    │
│  Excel "Modelo" de 8 abas (fórmulas vivas + cores de Lucas):           │
│    Capa · Premissas · Modelo · FCFF · FCFE · Macro · Sensib. · Avisos  │
│  Sensibilidades (WACC×g, Bear/Base/Bull) na aba Sensibilidades         │
│                                                                          │
│  [Semana 10] gráficos vivos no app: Football Field, tornado,           │
│    waterfall, ROIC/ROIIC, sensibilidade viva, comparáveis              │
│    (congelados no 9.0.0; descongelamento planejado)                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Por Que Cada Decisão Foi Tomada Dessa Forma

### Por que 8 anos de horizonte de projeção?

O horizonte de 8 anos representa o equilíbrio entre dois riscos opostos. Horizontes curtos (5 anos) comprimem artificialmente o período explícito e aumentam o peso do Valor Terminal no Enterprise Value — às vezes para mais de 90% — o que torna o modelo sensível demais a uma única premissa (o g). Horizontes longos (10 anos ou mais) criam uma falsa precisão: projetar margens e crescimento com granularidade anual para 2034 é analiticamente desonesto para a maioria das empresas. Oito anos captura pelo menos um ciclo completo de negócios para a maioria dos setores da economia brasileira e mantém o Valor Terminal numa proporção controlável do EV total.

### Por que taxas de crescimento individuais por ano em vez de uma taxa única?

Uma taxa de crescimento única que se repete por 8 anos assume que a empresa cresce linearmente — o que raramente acontece. Empresas passam por fases distintas: aceleração de lançamentos, maturação de portfólio, saturação de mercado, expansão geográfica. Uma construtora com R$ 5 bilhões de REF (Receita de Empreendimentos a Faturar) reconhece receita de forma não-linear ao longo dos anos de construção. Uma varejista em expansão cresce mais no início quando abre novas lojas e desacelera quando a base de lojas está madura. Forçar uma taxa única elimina essa dinâmica e empobrece a narrativa analítica. O sistema solicita 8 taxas individuais porque cada ano conta uma história diferente.

### Por que dois métodos de valuation (FCFF e FCFE)?

A separação entre empresa operacional e instituição financeira não é uma preferência — é uma exigência metodológica. Aswath Damodaran, o principal referencial teórico em valuation contemporâneo, é explícito: o conceito de Capital de Giro, CAPEX e Dívida Financeira não se aplica da mesma forma a bancos. Em uma instituição financeira, a dívida é a matéria-prima — um banco capta a custo de CDI e empresta a CDI mais spread. Tentar calcular Dívida Líquida para obter o Equity Value de um banco gera um número sem sentido econômico. O método correto é descontar o FCFE diretamente pelo custo do equity (Ke).

### Por que Streamlit em vez de HTML estático puro para o front-end?

O front-end precisa ser interativo — o analista deve poder ajustar uma premissa (o WACC, o g, uma margem) e ver o valuation recalcular. HTML estático puro não executa Python, o que forçaria uma de duas más escolhas: reescrever todo o motor de cálculo em JavaScript (duplicação insustentável, duas fontes de verdade que inevitavelmente divergem) ou limitar o input a cenários pré-computados (sem input livre). Streamlit resolve isso: o mesmo código Python que calcula o Excel calcula o dashboard, mantendo **fonte única da verdade**. Quando é necessário compartilhar um resultado sem exigir que o destinatário rode Python, o sistema exporta um HTML estático standalone dos gráficos.

### Por que usar a API da CVM em vez de dados do Yahoo Finance ou Bloomberg?

A CVM (Comissão de Valores Mobiliários) é a fonte primária obrigatória de dados financeiros para empresas brasileiras. Os dados disponíveis em `dados.cvm.gov.br` são os mesmos dados que as empresas reportam oficialmente ao regulador — são auditados, padronizados e completos. Fontes secundárias como Yahoo Finance frequentemente apresentam atrasos, campos ausentes ou valores incorretos para empresas brasileiras menores. Para um modelo de valuation que depende de precisão histórica para calibrar premissas futuras, usar a fonte primária não é opcional.

### Por que salvar dados intermediários em formato Parquet?

Parquet é um formato de armazenamento colunar desenvolvido para dados analíticos. Comparado ao CSV, ele é 5 a 10 vezes menor em tamanho de arquivo, preserva os tipos de dados (datas, floats, inteiros) sem conversão, e é lido de forma significativamente mais rápida pelo pandas. Para um sistema que processa demonstrações financeiras de múltiplos anos e múltiplas empresas, a escolha de formato de armazenamento impacta diretamente a velocidade de execução e a confiabilidade dos tipos de dado ao longo do pipeline.

### Por que o `CONTEXT.md` é considerado o arquivo mais importante do projeto?

O desenvolvimento deste projeto usa um paradigma de vibe coding assistido por IA — o Codex da OpenAI gera e executa o código diretamente no repositório via terminal do VS Code. Em um fluxo de desenvolvimento distribuído entre múltiplas sessões de IA sem memória persistente, o `CONTEXT.md` é o único mecanismo de continuidade. Ele registra o estado atual do projeto, o que foi implementado, o que está em progresso, as convenções de nomenclatura adotadas e a próxima tarefa. Sem ele, cada sessão começa do zero e as IAs tomam decisões de arquitetura conflitantes entre si. É atualizado obrigatoriamente ao final de cada sessão de desenvolvimento.

---

## Stack Tecnológico

### Linguagens

| Linguagem | Papel no Projeto |
|-----------|-----------------|
| Python 3.11+ | Linguagem principal — toda a lógica de coleta, cálculo, visualização e exportação |
| JSON | Arquivos de premissas do analista e configuração por setor |
| Markdown | Documentação de todos os módulos, READMEs e CONTEXT.md |

### Bibliotecas Python

| Biblioteca | Categoria | Uso Específico |
|------------|-----------|----------------|
| `yfinance` | Coleta | Preço, beta, ações em circulação, market cap, dividend yield, T-Bond 10Y |
| `python-bcb` | Coleta | Selic, IPCA, CDI, TJLP e projeções Focus do BACEN |
| `requests` | Coleta | Requisições HTTP à API da CVM |
| `pandas` | Processamento | Estrutura central de todos os DataFrames financeiros |
| `numpy` | Cálculo | Operações vetorizadas, VPL, descontos, interpolações |
| `pyarrow` | Processamento | Backend de leitura/escrita dos arquivos Parquet |
| `plotly` | Visualização | Football Field, Waterfall, Sensibilidades, Dashboard |
| `kaleido` | Exportação | Conversão de gráficos Plotly para PNG estático (inserção no Excel) |
| `openpyxl` | Exportação | Geração do Excel "Modelo" de 8 abas com fórmulas nativas VIVAS que reproduzem o motor (aba Modelo + FCFF/FCFE separadas), linha Check e cores de Lucas |
| `streamlit` | Front-end | Interface institucional interativa (input de premissas + dashboards) |
| `streamlit-aggrid` | Front-end | Renderização de tabelas na etapa ④ Exportar (preview das 8 abas) com aparência de planilha |
| `pytest` | Qualidade | Testes unitários de cada função de cálculo |
| `black` | Qualidade | Formatação automática e padronizada do código |
| `flake8` | Qualidade | Linter para detecção de erros e violações de estilo |
| `python-dotenv` | Infraestrutura | Gerenciamento de variáveis de ambiente |

### Ferramentas de Desenvolvimento

| Ferramenta | Uso |
|------------|-----|
| VS Code | Editor principal com suporte a Python, Jupyter e Git integrado |
| OpenAI Codex CLI | Geração autônoma de código na v1.0 (papel assumido pelo Claude Fable 5 a partir da v2.0) |
| Claude Fable 5 | IA de implementação a partir da v2.0 — lê os documentos de contexto, escreve/edita código e front-end, roda os testes (ver [`PROMPTS_FABLE.md`](PROMPTS_FABLE.md)) |
| Claude Code | Geração/curadoria dos prompts cirúrgicos e revisão final de código |
| GitHub Copilot | Assistência contextual em código dentro do VS Code |
| Git + GitHub | Controle de versão e publicação do repositório |
| Power BI Desktop | Ferramenta externa (gratuita, Windows) — painel executivo sobre as tabelas de `outputs/bi/`; não recalcula, apenas apresenta (backlog pós-v1.0) |

---

## Front-end Institucional

O front-end é construído em Streamlit seguindo princípios de design de interfaces financeiras institucionais — a referência conceitual é a densidade de informação com hierarquia do Bloomberg Terminal e a sobriedade visual de research de bancos como Goldman Sachs, J.P. Morgan e Morgan Stanley. Os princípios aplicados:

- **Densidade de dados com hierarquia.** A tela é informativa, não vazia. O que é decisão (Target Price, Recomendação, Upside) tem destaque tipográfico; o que é suporte (schedules, premissas de detalhe) é agrupado e secundário.
- **Paleta institucional.** Fundo navy profundo (`#0A1628`), superfícies de card (`#0F1E33`), azul âncora para títulos (`#1B4F8C`), acento sóbrio para ação. Semântica de cor estrita: **verde para upside, vermelho para downside**, nunca decorativos.
- **Tipografia com números tabulares.** Texto em fonte sans (Inter / IBM Plex Sans); todos os números financeiros em fonte monoespaçada (IBM Plex Mono) para alinhamento vertical das casas decimais.
- **Cada elemento se justifica.** Sem ícone decorativo, gradiente gratuito ou sombra sem função. Todo output importante é auditável — o Target Price expõe o WACC e o g que o geraram.

A navegação é um **fluxo guiado de 4 etapas** na sidebar (**① Empresa → ② Premissas → ③ Resultados → ④ Exportar**). A etapa ③ Resultados tem 5 sub-abas (**Overview, Histórico, Valuation, Modelo, Retornos**). Os gráficos Plotly (Football Field, tornado, waterfall, ROIC/ROIIC, sensibilidade viva) foram **congelados no Prompt 9.0.0** (Enxugamento) e voltam ao app na **Semana 10** — hoje o app é todo tabelas; as sensibilidades vivem no Excel.

### Camada de BI complementar — Power BI

O Streamlit é o front-end **interativo** (onde o analista ajusta premissas e o motor recalcula). Sobre o mesmo motor, o sistema exporta um **painel executivo em Power BI** — a ferramenta que times de finanças reconhecem de imediato. A arquitetura preserva a **fonte única de verdade**: o motor Python calcula uma vez e grava tabelas planas (formato *long*, organizadas como *star-schema*) em `outputs/bi/`; o Power BI apenas se conecta a essas tabelas e desenha os visuais. **Nenhum cálculo de valuation é reimplementado em DAX** — atualizar o painel significa rodar o Python de novo e clicar em *Refresh*. Streamlit e Power BI não competem: o primeiro é o ambiente de trabalho do analista; o segundo é o entregável de apresentação.

Na v1.0 o sistema já entrega o **contrato de export** (as tabelas planas em `outputs/bi/`). O arquivo `.pbix` do painel é um entregável de backlog pós-v1.0 (ver [Roadmap](#roadmap)), construído sobre essas tabelas sem alterar o motor.

---

## Estrutura do Repositório

```
dcf-automatizado/
│
├── CONTEXT.md                          # Documento central de contexto para sessões de IA
├── README.md                           # Este arquivo
├── CLAUDE.md                           # Guia operacional do repositório (Claude Code)
├── PROMPTS_FABLE.md                    # Plano vigente em prompts progressivos (Semana 9.0)
├── Humano_revisar.md                   # SÓ o que ainda exige uma decisão de Lucas (A-1..A-7)
├── docs/                               # Documentação histórica/consolidada
│   ├── TUTORIAL.md                     # Passo a passo de uso do app (4 etapas + Excel)
│   ├── historico_decisoes.md           # Arquivo morto das decisões D-001..D-079 da IA
│   ├── ROTEIRO.md                      # Plano de desenvolvimento semana a semana (spec v1.0)
│   ├── CHANGELOG.md                    # Histórico de versões e entregas por semana
│   └── CONTRIBUTING.md                 # Convenções de código e fluxo de desenvolvimento
├── LICENSE                             # Licença MIT
├── requirements.txt                    # Dependências Python
├── .env.example                        # Template de variáveis de ambiente
├── .gitignore                          # Ignora .venv, data/, outputs/, .env
├── main.py                             # Orquestrador — ponto de entrada via terminal
├── app.py                              # Front-end institucional (Streamlit)
│
├── .streamlit/
│   └── config.toml                     # Tema institucional (cores, fontes)
│
├── config/
│   ├── setores.json                    # Parâmetros de setores (financeiro/não-financeiro)
│   ├── mapeamento_cvm.json             # Mapeamento de códigos CVM → nomes padronizados
│   └── parametros.json                 # Parâmetros globais (horizonte, thresholds, fórmulas)
│
├── data/                               # Ignorada pelo Git
│   ├── raw/
│   │   ├── cvm/                        # JSONs brutos da API da CVM por empresa
│   │   ├── mercado/                    # Dados brutos do yfinance
│   │   └── macro/                      # Dados brutos do BACEN
│   ├── processed/                      # DataFrames limpos em formato Parquet
│   └── premissas/
│       ├── template_naofinanceiras.json
│       ├── template_financeiras.json
│       └── <TICKER>_premissas.json     # Premissas preenchidas pelo analista
│
├── src/
│   ├── coleta/
│   │   ├── coletor_cvm.py              # Coleta universal via API da CVM
│   │   ├── coletor_mercado.py          # Coleta via yfinance
│   │   └── coletor_macro.py            # Coleta via python-bcb (BACEN)
│   ├── processamento/
│   │   └── limpeza.py                  # Normalização e padronização dos dados brutos
│   ├── metricas/
│   │   └── metricas_historicas.py      # ROIC, ROIIC, WK, margens — duas trilhas por tipo
│   ├── projecao/
│   │   ├── projetor_dre.py             # DRE projetada com 8 taxas individuais por ano
│   │   ├── schedule_wk.py              # Working Capital projetado via DSO/DIO/DPO
│   │   ├── schedule_ppe.py             # Cascata de CAPEX e depreciação
│   │   └── schedule_divida.py          # Amortizações e juros por instrumento
│   ├── valuation/
│   │   ├── calculador_fcff.py          # FCFF (não-financeiras) e FCFE (financeiras)
│   │   ├── calculador_wacc.py          # WACC completo ou apenas Ke por tipo de empresa
│   │   ├── calculador_vt.py            # Valor Terminal com verificações de consistência
│   │   ├── calculador_ev.py            # Bridge EV → Equity Value → Target Price
│   │   └── checklist.py                # 10+ verificações automáticas de consistência
│   ├── visualizacao/
│   │   ├── football_field.py           # Football Field com 7 metodologias
│   │   ├── waterfall_ev.py             # Decomposição do Enterprise Value
│   │   ├── sensibilidade_wacc_g.py     # Tabela 6×6 WACC × g com formatação condicional
│   │   ├── sensibilidade_receita_margem.py
│   │   ├── sensibilidade_setor.py      # Sensibilidade específica por setor
│   │   ├── historico_vs_projetado.py   # Grade 2×2 com 4 métricas principais
│   │   ├── roic_roiic.py               # Reality check de ROIC e ROIIC
│   │   └── dashboard_final.py          # Painel consolidado com Recomendação e Checklist
│   └── exportacao/
│       ├── exportador_excel.py         # Excel "Modelo" de 8 abas (fórmulas vivas + cores de Lucas)
│       └── exportador_bi.py            # Tabelas planas star-schema para o Power BI
│
├── powerbi/                            # Painel Power BI (backlog pós-v1.0)
│   ├── dcf_dashboard.pbix              # Dashboard executivo — consome outputs/bi/
│   └── tema.json                       # Tema institucional do Power BI
│
├── referencias/                        # Modelos de referência (imutáveis; ver referencias/README.md)
│   └── modelos_excel/
│       ├── Direcional_DIRR3_referencia.xlsx  # Benchmark v1.0 + ESTRUTURA_DIRECIONAL.md
│       └── Smartfit_SMFT3_referencia.xlsx    # Benchmark v2.1 + ESTRUTURA_SMARTFIT.md
│
├── tests/
│   ├── test_coleta.py
│   ├── test_projecao.py
│   └── test_valuation.py
│
├── notebooks/
│   ├── 01_exploracao_cvm.ipynb
│   ├── 02_exploracao_yfinance.ipynb
│   └── 03_validacao_calculos.ipynb
│
└── outputs/                            # Ignorada pelo Git
    ├── excel/                          # Arquivos .xlsx gerados
    ├── graficos/                       # HTMLs e PNGs gerados pelo Plotly
    └── bi/                             # Tabelas planas (CSV/Parquet) consumidas pelo Power BI
```

---

## Módulos do Sistema

### Módulo 1 — Coleta Automática de Dados

O coletor da CVM é o componente mais crítico de infraestrutura do sistema. Empresas diferentes têm planos de contas diferentes na CVM — o código numérico que representa "Receita Líquida" para uma construtora é diferente do mesmo campo para um banco. O arquivo `config/mapeamento_cvm.json` resolve isso mapeando todos os códigos conhecidos para nomes padronizados. Qualquer campo não mapeado é registrado em log sem quebrar o pipeline, permitindo que o sistema cresça incrementalmente à medida que novos setores são testados.

A detecção automática do tipo de empresa (financeira ou não-financeira) acontece neste módulo via a classificação setorial da própria CVM, e é salva nos metadados da empresa. Todos os módulos subsequentes leem esses metadados para executar a trilha correta.

### Módulo 2 — Painel Histórico

Antes de qualquer input, o analista visualiza um dashboard calculado automaticamente com as métricas dos últimos 5 a 7 anos. Para empresas não-financeiras: ROIC com decomposição DuPont, ROIIC rolling de 3 anos, DSO/DIO/DPO/CCC, FCO/EBITDA, Dívida Líquida/EBITDA. Para instituições financeiras: ROE, NIM, Índice de Eficiência, NPL Ratio, Coverage Ratio, Índice de Basileia.

O propósito deste módulo é epistemológico: o analista não deve definir premissas no vácuo. Uma margem EBITDA de 28% para o Ano 5 significa algo completamente diferente se a margem histórica foi de 25% (expansão moderada, plausível) ou 15% (salto enorme, exige justificativa). O histórico é a âncora. As premissas são o desvio justificado da âncora.

### Módulo 3 — Interface de Premissas

O único ponto de input humano obrigatório do sistema. Para cada campo de premissa, o front-end exibe os dados históricos relevantes calculados no Módulo 2 — ao solicitar a taxa de crescimento do Ano 1, exibe o CAGR histórico de 3 e 5 anos e o crescimento do último ano. Ao solicitar a margem EBITDA do Ano 3, exibe as margens dos últimos 5 anos e a média do período.

Os campos de crescimento de receita, margem EBITDA e CAPEX/Receita são solicitados individualmente para cada um dos 8 anos — nunca como uma taxa única que se repete. O sistema valida cada input em tempo real, bloqueando configurações matematicamente inválidas (g ≥ taxa de desconto) e alertando para premissas muito distantes do histórico (margem projetada mais de 5pp acima da máxima histórica).

### Módulo 4 — Motor de Cálculo

A cadeia de cálculo é executada em sequência obrigatória porque cada passo depende do anterior. Para empresas não-financeiras: a DRE é projetada primeiro porque o Working Capital depende da Receita e do CMV, o schedule de PP&E depende do CAPEX que é percentual da Receita, o schedule de Dívida gera o Resultado Financeiro que fecha o LL da DRE, o FCFF é calculado com os componentes de todos os schedules, e o WACC desconta os fluxos para chegar no EV. O bloco FCFF também persiste ROIC e ROIIC por ano como reality check de consistência interna, sem impor trajetória crescente ou decrescente. Para instituições financeiras: a DRE adaptada gera o LL diretamente, o FCFE é calculado subtraindo a variação do capital regulatório mínimo retido, e o Ke desconta os fluxos sem bridge EV→Equity.

O checklist de consistência é executado ao final e classifica cada verificação como aprovada ou com alerta. Os itens do checklist são derivados diretamente das condições matemáticas obrigatórias do Gordon Growth Model e das melhores práticas de valuation documentadas por Damodaran, McKinsey e CFA Institute.

### Módulo 5 — Dashboard e Outputs

**Football Field:** Sete metodologias representadas como barras horizontais — DCF Bear, DCF Base, DCF Bull, Trading Comps EV/EBITDA, Trading Comps P/L, Múltiplo de Saída e 52-week Range — com o preço atual marcado por linha vertical. Permite ao analista ver instantaneamente se o DCF está em linha com o que o mercado está precificando ou se há divergência significativa que exige explicação.

**Tabelas de Sensibilidade:** A tabela WACC × g é obrigatória porque ela mapeia o espaço de incerteza das duas premissas mais impactantes do modelo. A tabela Receita × Margem EBITDA mapeia o "espaço de segurança" — as combinações de premissas onde ainda há upside mesmo sob cenários mais conservadores. A sensibilidade setorial é específica por setor porque os principais vetores de incerteza variam: para construtoras é Margem Bruta × VSO (Velocidade de Vendas sobre Oferta), para bancos é NIM × Índice de Eficiência, para mineração é Preço da Commodity × Custo de Produção (C1).

**Front-end e Exportação Excel (v2.1, Semana 9.0):** O front-end Streamlit é um **fluxo guiado de 4 etapas** (① Empresa → ② Premissas → ③ Resultados → ④ Exportar). A etapa ② expõe as 6 premissas de Lucas (crescimento, margem bruta pré-D&A, SG&A, alíquota anual, WACC manual opcional e Outros); a etapa ③ tem sub-abas Overview/Histórico/Valuation/**Modelo**/**Retornos**. O Excel gerado tem **8 abas** no padrão Direcional — Capa, Premissas, **Modelo** (DRE pré-D&A + BP aberto + DFC indireto + WK + Dívida + PP&E, históricos + 8 projetados, com linha Check booleana), **FCFF** e **FCFE** (abas separadas referenciando o Modelo), Macro, Sensibilidades e Avisos. Todas as células projetadas carregam **fórmulas nativas** que reproduzem o motor (não valores colados) sob a **convenção de cores de Lucas** (azul = histórico da CVM, verde = premissa que você escolhe, preto = fórmula), de modo que editar uma premissa verde no próprio Excel propaga pelas fórmulas até o Target das abas FCFF e FCFE. A Aba de Premissas exibe os 8 valores individuais de crescimento de receita por ano com a âncora histórica ao lado.

**Exportação para BI (Power BI):** O mesmo resultado do motor é gravado como tabelas planas (*star-schema*) em `outputs/bi/`, prontas para o Power BI conectar por "Get Data → Folder". Isso separa o *cálculo* (Python, fonte única de verdade) da *apresentação* (Power BI), sem duplicar lógica. Na v1.0 o sistema entrega essas tabelas; o painel `.pbix` é backlog pós-v1.0.

---

## O Que o Analista Faz vs. O Que o Sistema Faz

### O Sistema Faz Automaticamente

- Identificar o código CVM da empresa pelo ticker
- Coletar 5 a 7 anos de DRE, Balanço e DFC da base de dados oficial da CVM
- Detectar se a empresa é financeira ou não-financeira e executar o pipeline correto
- Coletar preço, beta, ações em circulação e market cap via yfinance
- Coletar Selic, IPCA, CDI e projeções Focus via API do BACEN
- Calcular todas as métricas históricas relevantes por tipo de empresa
- Projetar as demonstrações financeiras para 8 anos a partir das premissas
- Verificar o fechamento do balanço em todos os anos projetados
- Calcular FCFF ou FCFE, WACC ou Ke, Valor Terminal, EV, Equity Value, Target Price
- Persistir ROIC e ROIIC por ano no forecast como reality check do crescimento
- Executar o checklist de consistência e sinalizar problemas
- Gerar Football Field, Waterfall, Sensibilidades e Dashboard
- Exportar o Excel "Modelo" de 8 abas (Capa, Premissas, Modelo, FCFF, FCFE, Macro, Sensibilidades, Avisos)

### O Analista Faz — Não Existe Automação para Isso

- Entender o modelo de negócios da empresa e seu posicionamento competitivo
- Interpretar o histórico financeiro no contexto do ciclo de negócios e do setor
- Definir se o crescimento passado é sustentável, excepcional ou estruturalmente declinante
- Determinar a taxa de crescimento de receita de cada um dos 8 anos com base na narrativa da empresa
- Julgar a margem EBITDA futura considerando alavancagem operacional, pressão competitiva e ciclo de custos
- Escolher o g com responsabilidade, sabendo que representa 60% a 80% do EV
- Decidir se o resultado do modelo faz sentido econômico ou se reflete uma premissa inadequada
- Escrever a tese de investimento que justifica cada premissa e conecta os números à narrativa

---

## Outputs Gerados

Para cada empresa analisada, o sistema entrega automaticamente:

| Output | Formato | Conteúdo |
|--------|---------|----------|
| Front-end Institucional (v2.1) | Streamlit | Fluxo guiado de 4 etapas (① Empresa → ② Premissas → ③ Resultados → ④ Exportar); ③ com sub-abas Overview/Histórico/Valuation/Modelo/Retornos |
| Modelo DCF Completo (v2.1) | `.xlsx` (8 abas) | Capa, Premissas, **Modelo** (3 demonstrativos abertos + schedules, com linha Check), **FCFF**, **FCFE** (abas separadas), Macro, Sensibilidades, Avisos — fórmulas vivas + cores de Lucas |
| Sensibilidades (no Excel) | aba `Sensibilidades` | Matriz Target × (WACC, g) com formatação condicional + grade Bear/Base/Bull |
| Football Field, tornado, waterfall, ROIC/ROIIC, sensibilidade viva, comparáveis | `.html` + `.png` | **CONGELADOS no 9.0.0** (D-053); descongelamento e re-integração ao app planejados na **Semana 10** |
| Tabelas para BI | `.csv` / `.parquet` (backlog) | `exportador_bi.py` congelado no 9.0.0 (v2.2) |
| Painel Power BI | `.pbix` (backlog v2.2) | Dashboard executivo conectado às tabelas de `outputs/bi/` |

---

## Instalação e Execução

### Pré-requisitos

- Python 3.11 ou superior
- Git instalado e configurado
- VS Code com extensões Python, Pylance, Jupyter e GitLens
- Conta GitHub com repositório criado

### Instalação

```bash
# Clonar o repositório
git clone https://github.com/<seu-usuario>/dcf-automatizado.git
cd dcf-automatizado

# Criar e ativar ambiente virtual
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
```

### Execução

```bash
# Front-end institucional interativo (recomendado)
streamlit run app.py

# Análise completa via terminal — o sistema detecta o tipo de empresa
python main.py --ticker DIRR3 --setor construcao

# Usando premissas já preenchidas anteriormente
python main.py --ticker DIRR3 --setor construcao --usar-premissas-existentes

# Prova de universalidade — segundo setor não-financeiro
python main.py --ticker MGLU3 --setor varejo --usar-premissas-existentes

# Rodar testes unitários
pytest tests/ -v
```

### Fluxo de Execução no Terminal

```
[1/5] Coletando dados históricos (CVM, yfinance, BACEN)...
      → DIRR3: Dados coletados para 2018-2024 (7 anos)
      → Tipo detectado: Não-Financeira | Setor: Construção Civil

[2/5] Calculando métricas históricas...
      → ROIC médio (5 anos): 18,3%
      → Margem EBITDA média (5 anos): 26,1%
      → Dívida Líquida / EBITDA (último ano): 1,2x

[3/5] Coletando premissas do analista...
      → Crescimento Receita: [18%, 15%, 13%, 11%, 10%, 8%, 7%, 6%]
      → Margem EBITDA: [27%, 28%, 28%, 27%, 26%, 26%, 25%, 25%]

[4/5] Executando motor de cálculo...
      → WACC calculado: 11,8%
      → Valor Terminal: R$ 8,2 bi (71% do EV)
      → Target Price: R$ 24,50 | Upside: +31,2% | COMPRA

[5/5] Gerando outputs...
      → Excel: outputs/excel/DCF_DIRR3_2026-08-06.xlsx
      → Gráficos: outputs/graficos/ (7 arquivos)
      → Checklist: 9/10 itens aprovados | 1 alerta
```

> Os números acima são ilustrativos do formato de saída, não um resultado de valuation validado.

---

## Roadmap

A **v1.0** (tag `versao 1.0`) provou a arquitetura em duas não-financeiras. A **v2.0**
universalizou (roda qualquer ticker da B3). A **v2.1 — Semana 9.0 está CONCLUÍDA** (20/07/2026):
o projeto foi enxugado ao núcleo, a coleta ficou 100% fiel à CVM, o motor virou "padrão
Direcional" (DRE **pré-D&A**, WK multi-driver, DFC indireto, BP aberto com check), ganhou
**FCFE + macro anual + retornos**, o front-end virou um **fluxo guiado de 4 etapas** e o Excel
foi reescrito como **"Modelo" de 8 abas** com FCFF/FCFE em abas separadas, fórmulas vivas e
cores de Lucas. O plano está em [`PROMPTS_FABLE.md`](PROMPTS_FABLE.md), dirigido ao **Claude
Fable 5**. A **Semana 10** (planejada) traz os gráficos de volta ao app.

| Versão | Status | Escopo |
|--------|--------|--------|
| **v1.0** | ✅ Concluída | Pipeline validado para DIRR3 e MGLU3. Motor FCFF/WACC ponta a ponta. 8 taxas de crescimento individuais. Front-end e Excel de referência. |
| **v2.0 — Universalização** | ✅ Concluída (Ondas 1–4) | Roda qualquer ticker da B3: coleta/mapeamento CVM universais (por `CD_CONTA`), classificação automática de tipo/subtipo, relatório de qualidade, coleta em lote; motor por tipo (FCFF/WACC e FCFE/Ke); comparáveis reais; app multi-empresa. |
| **v2.1 — Semana 9.0 (Padrão Direcional)** | ✅ Concluída (9.0.0–9.0.5) | Enxugamento; fidelidade absoluta à CVM (residual < 5%, auditor); motor pré-D&A (WK multi-driver, DFC indireto, BP aberto com check); FCFF+FCFE+macro anual+retornos; front-end guiado de 4 etapas (6 premissas + WACC manual); Excel "Modelo" de 8 abas com fórmulas vivas + cores de Lucas. |
| **v2.1 — Semana 10** | 🟡 Planejada | Descongelar `src/visualizacao/` e religar os gráficos no app: Football Field automatizado (comps reais + bear/base/bull + 52 semanas), tornado, waterfall, ROIC/ROIIC, sensibilidade viva, comparáveis. Resolve os achados menores da revisão. |
| **v2.2 / v3.0** | 🔭 Horizonte | Excel bancário; `exportador_bi.py`/Power BI/PDF; unit economics setorial (VGV×VSO×PoC); LBO; research report multipágina. |

> **Estado técnico da v2.1 (Semana 9.0):** suíte **192 passed / 12 skipped**, `black`/`flake8`
> limpos, `verificar_semana3` **OK**. Auditoria multi-agente (5 agentes) deu PASS em dados,
> Excel, front-end, DCF e sensibilidades. Backlog explícito: gráficos do app (Semana 10),
> Excel bancário e camada BI (v2.2), unit economics (v3.0).

---

## Referências Teóricas e Bibliográficas

Este projeto é construído sobre fundamentos teóricos consolidados pela literatura acadêmica e profissional de finanças corporativas e valuation. As referências abaixo são as bases intelectuais diretas das metodologias implementadas no sistema.

### Valuation e DCF

**DAMODARAN, Aswath. *Investment Valuation: Tools and Techniques for Determining the Value of Any Asset*. 3. ed. Wiley Finance, 2012.**
A principal referência teórica do projeto. As fórmulas de FCFF, FCFE, WACC, custo do equity via CAPM, Valor Terminal pelo Gordon Growth Model, ajuste do custo de capital para mercados emergentes (conversão Ke de USD para BRL), beta desalavancado via fórmula de Hamada, e o tratamento diferenciado de instituições financeiras são todos derivados diretamente de Damodaran. O site do autor (pages.stern.nyu.edu/~adamodar/) é consultado para os parâmetros de ERP (Equity Risk Premium) e Country Risk Premium utilizados no sistema.

**DAMODARAN, Aswath. *The Dark Side of Valuation*. 2. ed. Pearson FT Press, 2009.**
Referência para o tratamento de empresas em situações especiais — prejuízo histórico, FCFF negativo nos anos iniciais, empresas em reestruturação. As soluções implementadas no sistema para FCFF negativo no último ano de projeção (uso do NOPAT normalizado como base do Valor Terminal) são derivadas desta obra.

**KOLLER, Tim; GOEDHART, Marc; WESSELS, David. *Valuation: Measuring and Managing the Value of Companies*. 7. ed. McKinsey & Company / Wiley, 2020.**
Referência para a estrutura do modelo integrado de três demonstrativos (DRE + BP + DFC), a definição de Capital Investido e NOPAT para o cálculo do ROIC, os schedules de Working Capital e PP&E, e os padrões de checklist de consistência do modelo. A aba `Modelo` do Excel exportado é inspirada na **aba Modelo da Direcional** (modelo de referência do mentor); a **convenção de cores é a de Lucas** (histórico AZUL / premissa VERDE / fórmula PRETO), não a convenção WSP azul-input/verde-link.

**PENMAN, Stephen H. *Financial Statement Analysis and Security Valuation*. 5. ed. McGraw-Hill, 2012.**
Referência para a análise de demonstrações financeiras, identificação de itens não-recorrentes, qualidade do lucro (FCO/EBITDA como indicador de accruals) e o conceito de ROIIC (Return on Incremental Invested Capital) como métrica de criação de valor marginal.

### Custo de Capital e CAPM

**SHARPE, William F. Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk. *The Journal of Finance*, v. 19, n. 3, p. 425–442, 1964.**
O artigo seminal que estabelece o CAPM (Capital Asset Pricing Model), base do cálculo de Ke implementado no sistema. A fórmula Ke = Rf + β × (ERP + CRP) é a aplicação direta do modelo de Sharpe ao contexto de mercados emergentes.

**HAMADA, Robert S. The Effect of the Firm's Capital Structure on the Systematic Risk of Common Stocks. *The Journal of Finance*, v. 27, n. 2, p. 435–452, 1972.**
Base teórica da fórmula de Hamada utilizada no sistema para desalavancar o beta histórico da empresa e realavancá-lo com a estrutura de capital alvo, isolando o risco operacional do risco financeiro.

### Análise de Criação de Valor

**MAUBOUSSIN, Michael J.; CALLAHAN, Dan. *Calculating Return on Invested Capital*. Credit Suisse Global Financial Strategies, 2014.**
Referência para a definição precisa de Capital Investido utilizada no sistema (NWC operacional + Imobilizado líquido + Goodwill + Outros ativos operacionais líquidos de imposto), a decomposição DuPont do ROIC (Margem NOPAT × Giro do Capital Investido), e o conceito de ROIIC como indicador da qualidade do crescimento futuro.

**DORSEY, Pat. *The Little Book That Builds Wealth: The Knockout Formula for Finding Great Investments*. Wiley, 2008.**
Referência conceitual para a análise de MOAT (vantagem competitiva sustentável) e sua relação com o spread ROIC − WACC exibido no dashboard final. Um ROIC consistentemente acima do WACC é a evidência quantitativa de um MOAT econômico — o sistema exibe esse spread por ano projetado para que o analista avalie se as premissas são coerentes com a vantagem competitiva da empresa.

### Finanças Corporativas Brasileiras

**ASSAF NETO, Alexandre. *Valuation: Métricas de Valor e Geração de Valor*. 2. ed. Atlas, 2017.**
Referência para as especificidades do mercado de capitais brasileiro — tratamento do RET (Regime Especial de Tributação) para construtoras com alíquota de 4% sobre a Receita Bruta em vez do EBT, ajuste do custo de capital para a estrutura de impostos brasileira (IR + CSLL de 34% para empresas gerais), e as particularidades das métricas de Working Capital para o mercado local.

**Banco Central do Brasil. *Relatório de Inflação* e *Relatório Focus*. Publicação trimestral e semanal.**
Fonte das projeções macroeconômicas utilizadas no sistema — Selic, IPCA e expectativas de mercado coletadas via python-bcb. O sistema usa as projeções Focus para o horizonte de 1 e 2 anos à frente como referência para o analista na definição das premissas de crescimento nominal.

### Análise Setorial — Construção Civil

**ROCHA LIMA JUNIOR, João da. *Análise de Investimentos: Princípios e Técnicas para Empreendimentos do Setor da Construção Civil*. Escola Politécnica da USP, 1993.**
Referência para as métricas específicas do setor de construção civil implementadas no sistema — VGV (Valor Geral de Vendas), VSO (Velocidade de Vendas sobre Oferta), REF (Receita de Empreendimentos a Faturar), PoC (Percentual de Conclusão pelo método IFRS 15) e os modelos unitários de empreendimento com TIR e VPL mensais.

### Análise de Instituições Financeiras

**DAMODARAN, Aswath. *Valuing Financial Service Firms*. Working Paper, Stern School of Business, NYU, 2013.**
Referência específica para o método FCFE aplicado a bancos — a justificativa matemática e econômica de por que o FCFF/WACC não se aplica a instituições financeiras, o cálculo do FCFE bancário como LL menos variação do capital regulatório mínimo retido, e o uso do Ke como única taxa de desconto relevante para o setor.

---

*Este projeto foi desenvolvido como parte das atividades de Ciências da Computação no Insper (2026) com aplicação ao Mercado Financeiro, combinando fundamentos teóricos da literatura acadêmica com implementação prática em Python para análise de empresas listadas na B3.*

---

## Autor

**Lucas Cruz**
Estudante de Ciências da Computação — Insper (2026–2030)
Foco em Inteligência Artificial, Dados e Mercado Financeiro

---

> *"O programa automatiza o trabalho mecânico. O analista resolve o trabalho intelectual. Um DCF sem julgamento humano nas premissas não é valuation — é aritmética."*
