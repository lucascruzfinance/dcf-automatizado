# 📊 DCF Automatizado — Sistema de Valuation para Ações da B3

> **Projeto de Ciências da Computação aplicado ao Mercado Financeiro**
> Automação completa do processo de valuation por Fluxo de Caixa Descontado com coleta de dados via APIs públicas, motor de cálculo financeiro integrado, interface de premissas guiada por dados históricos, dashboard visual interativo e exportação em Excel de nível institucional — aplicável a qualquer ação listada na B3.

---

## 🧭 Índice

1. [Sobre o Projeto](#sobre-o-projeto)
2. [Por Que Construir Isso](#por-que-construir-isso)
3. [O Problema que Este Projeto Resolve](#o-problema-que-este-projeto-resolve)
4. [Arquitetura do Sistema](#arquitetura-do-sistema)
5. [Por Que Cada Decisão Foi Tomada Dessa Forma](#por-que-cada-decisão-foi-tomada-dessa-forma)
6. [Stack Tecnológico](#stack-tecnológico)
7. [Estrutura do Repositório](#estrutura-do-repositório)
8. [Módulos do Sistema](#módulos-do-sistema)
9. [O Que o Analista Faz vs. O Que o Sistema Faz](#o-que-o-analista-faz-vs-o-que-o-sistema-faz)
10. [Outputs Gerados](#outputs-gerados)
11. [Instalação e Execução](#instalação-e-execução)
12. [Roadmap](#roadmap)
13. [Referências Teóricas e Bibliográficas](#referências-teóricas-e-bibliográficas)
14. [Autor](#autor)

---

## Sobre o Projeto

Este projeto constrói um **sistema automatizado de valuation por DCF (Discounted Cash Flow)** capaz de analisar qualquer empresa de capital aberto listada na B3, independentemente do setor. A partir do ticker da empresa, o sistema identifica automaticamente se ela é uma empresa operacional ou uma instituição financeira, coleta dados históricos de múltiplas fontes públicas, calcula métricas financeiras, apresenta esse histórico ao analista como âncora intelectual, solicita as premissas que exigem julgamento humano — incluindo taxas de crescimento de receita individuais para cada um dos 8 anos de projeção — executa toda a cadeia de cálculo do valuation pelo método correto para cada tipo de empresa, e entrega um dashboard visual completo com Football Field, tabelas de sensibilidade, análise de criação de valor e exportação profissional em Excel.

O benchmark de qualidade mínima é o modelo Excel desenvolvido para a **Direcional Engenharia (DIRR3)** durante o programa trainee do InFinance/Insper em 2026 — um modelo integrado com DRE, Balanço Patrimonial e DFC projetados, schedules completos de Working Capital, PP&E e Dívida, modelos unitários de empreendimento, Football Field e tabelas de sensibilidade. O objetivo deste sistema é replicar e superar esse nível de análise de forma programática, escalável e aplicável a qualquer empresa e setor da economia brasileira.

---

## Por Que Construir Isso

A interseção entre **Ciências da Computação e Mercado Financeiro** é um dos campos de maior crescimento e impacto na indústria global. Analistas que dominam tanto o rigor técnico do valuation quanto a capacidade de automatizar e escalar processos via programação representam um diferencial competitivo real em Asset Management, Equity Research e Investment Banking.

O processo tradicional de construção de um modelo DCF em Excel é altamente manual e intensivo em tempo. Um analista experiente leva entre 15 e 40 horas para construir um modelo integrado do zero para uma empresa nova — coletando dados manualmente de relatórios, estruturando as demonstrações financeiras, construindo os schedules, calculando o WACC e gerando os gráficos. Esse tempo é em grande parte gasto em trabalho mecânico repetível: copiar dados, formatar tabelas, aplicar fórmulas que são as mesmas para qualquer empresa do mesmo setor.

Este projeto parte de uma distinção fundamental: **o trabalho mecânico pode e deve ser automatizado. O trabalho intelectual não pode e não deve ser automatizado.** O valor do analista está nas premissas que ele define — a taxa de crescimento da receita que ele projeta para o Ano 3, a margem EBITDA que ele acredita ser sustentável no longo prazo, o g que ele escolhe com responsabilidade sabendo que representa 60% a 80% do valor da empresa. Essas decisões exigem conhecimento do modelo de negócios, leitura do ambiente competitivo, interpretação do ciclo de capital e julgamento sobre o futuro — coisas que nenhum algoritmo substitui.

O sistema automatiza o trabalho mecânico e preserva o trabalho intelectual exatamente onde ele pertence: nas mãos do analista.

---

## O Problema que Este Projeto Resolve

Existem três problemas concretos que motivam a construção deste sistema:

**Problema 1 — Escalabilidade.** Um modelo Excel é feito para uma empresa específica. Cada novo ticker exige um novo modelo construído do zero ou uma adaptação trabalhosa. Este sistema aceita qualquer ticker da B3 como input e executa o pipeline completo automaticamente, adaptando a metodologia ao tipo de empresa detectado.

**Problema 2 — Metodologia inadequada por tipo de empresa.** O modelo FCFF descontado pelo WACC, que é o método padrão para empresas operacionais, é matematicamente incorreto para instituições financeiras. Em um banco, a dívida é matéria-prima do negócio e não passivo financeiro — separar o Enterprise Value do Equity Value da forma convencional não faz sentido. O método correto para bancos, seguradoras e holdings financeiras é o FCFE ou DDM descontado apenas pelo custo do equity (Ke). Este sistema detecta automaticamente o tipo de empresa e executa o método correto para cada caso, sem intervenção do usuário.

**Problema 3 — Premissas engessadas.** Modelos simplificados assumem uma única taxa de crescimento que se repete por todo o período de projeção. Isso é analiticamente inadequado para qualquer empresa em fase de transição — uma construtora que está acelerando lançamentos nos primeiros anos e desacelerando à medida que o portfólio matura, uma varejista que está expandindo a base de lojas e depois colhendo a alavancagem operacional, uma empresa de commodities que está no topo do ciclo e deve desacelerar. Este sistema solicita obrigatoriamente uma taxa de crescimento individual para cada um dos 8 anos de projeção, permitindo que o analista construa uma narrativa de crescimento coerente com a dinâmica específica da empresa.

---

## Arquitetura do Sistema

O sistema é organizado em **5 módulos sequenciais** que se comunicam via arquivos intermediários em formato Parquet e JSON:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ENTRADA DO USUÁRIO                              │
│              python main.py --ticker DIRR3 --setor construcao           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 1 — COLETA AUTOMÁTICA DE DADOS              [100% Automático]   │
│                                                                          │
│  CVM (dados.cvm.gov.br)     → DRE, BP, DFC históricos (5-7 anos)       │
│  yfinance                   → Preço, Beta, Ações, Market Cap            │
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
│  Cada campo exibe o histórico relevante como referência                 │
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
│  WACC = (E/V)×Ke + (D/V)×Kd×(1−t)                                     │
│  TV = FCFF₈ × (1+g) / (WACC−g)                                         │
│  EV → Equity Value → Target Price                                       │
│                                                                          │
│  Financeiras:                                                            │
│  FCFE = LL − ΔCapital Regulatório Retido                               │
│  Ke via CAPM com ajuste Brasil                                          │
│  TV = FCFE₈ × (1+g) / (Ke−g)                                           │
│  Equity Value → Target Price (sem bridge EV→Equity)                    │
│                                                                          │
│  Checklist de 10+ verificações de consistência para ambos os tipos      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MÓDULO 5 — DASHBOARD E OUTPUTS                     [100% Automático]   │
│                                                                          │
│  Football Field (7 metodologias)                                         │
│  Waterfall de decomposição do EV                                        │
│  Tabela de Sensibilidade WACC × g (ou Ke × g para financeiras)         │
│  Tabela de Sensibilidade Receita × Margem EBITDA                        │
│  Sensibilidade Setorial específica por setor                            │
│  Histórico vs. Projetado (grade 2×2 com 4 métricas)                    │
│  Dashboard consolidado com Recomendação e Checklist                     │
│  Exportação Excel com 7 abas formatadas profissionalmente               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Por Que Cada Decisão Foi Tomada Dessa Forma

### Por que 8 anos de horizonte de projeção?

O horizonte de 8 anos representa o equilíbrio entre dois riscos opostos. Horizontes curtos (5 anos) comprimem artificialmente o período explícito e aumentam o peso do Valor Terminal no Enterprise Value — às vezes para mais de 90% — o que torna o modelo sensível demais a uma única premissa (o g). Horizontes longos (10 anos ou mais) criam uma falsa precisão: projetar margens e crescimento com granularidade anual para 2034 é analiticamente desonesto para a maioria das empresas. Oito anos captura pelo menos um ciclo completo de negócios para a maioria dos setores da economia brasileira e mantém o Valor Terminal numa proporção controlável do EV total.

### Por que taxas de crescimento individuais por ano em vez de uma taxa única?

Uma taxa de crescimento única que se repete por 8 anos assume que a empresa cresce linearmente — o que raramente acontece. Empresas passam por fases distintas: aceleração de lançamentos, maturação de portfólio, saturação de mercado, expansão geográfica. Uma construtora com R$ 5 bilhões de REF (Receita de Empreendimentos a Faturar) reconhece receita de forma não-linear ao longo dos anos de construção. Uma varejista em expansão cresce mais no início quando abre novas lojas e desacelera quando a base de lojas está madura. Forçar uma taxa única elimina essa dinâmica e empobrece a narrativa analítica. O sistema solicita 8 taxas individuais porque cada ano conta uma história diferente.

### Por que dois métodos de valuation (FCFF e FCFE)?

A separação entre empresa operacional e instituição financeira não é uma preferência — é uma exigência metodológica. Aswath Damodaran, o principal referencial teórico em valuation contemporâneo, é explícito: o conceito de Capital de Giro, CAPEX e Dívida Financeira não se aplica da mesma forma a bancos. Em uma instituição financeira, a dívida é a matéria-prima — um banco capta a custo de CDI e empresta a CDI mais spread. Tentar calcular Dívida Líquida para obter o Equity Value de um banco gera um número sem sentido econômico. O método correto é descontar o FCFE diretamente pelo custo do equity (Ke), que é o que este sistema faz automaticamente para qualquer empresa classificada como financeira.

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
| `plotly` | Visualização | Football Field, Waterfall, Sensibilidades, Dashboard |
| `kaleido` | Exportação | Conversão de gráficos Plotly para PNG estático (inserção no Excel) |
| `openpyxl` | Exportação | Geração do Excel com 7 abas, formatação condicional, gráficos embutidos |
| `pytest` | Qualidade | Testes unitários de cada função de cálculo |
| `black` | Qualidade | Formatação automática e padronizada do código |
| `flake8` | Qualidade | Linter para detecção de erros e violações de estilo |
| `python-dotenv` | Infraestrutura | Gerenciamento de variáveis de ambiente |

### Ferramentas de Desenvolvimento

| Ferramenta | Uso |
|------------|-----|
| VS Code | Editor principal com suporte a Python, Jupyter e Git integrado |
| OpenAI Codex CLI | Geração autônoma de código via terminal com acesso ao repositório |
| GitHub Copilot | Assistência contextual em código dentro do VS Code |
| Git + GitHub | Controle de versão e publicação do repositório |

---

## Estrutura do Repositório

```
dcf-automatizado/
│
├── CONTEXT.md                          # Documento central de contexto para sessões de IA
├── README.md                           # Este arquivo
├── CHANGELOG.md                        # Histórico de versões e entregas por semana
├── requirements.txt                    # Dependências Python
├── .env.example                        # Template de variáveis de ambiente
├── .gitignore                          # Ignora .venv, data/, outputs/, .env
├── main.py                             # Orquestrador — ponto de entrada do sistema
│
├── config/
│   ├── setores.json                    # Parâmetros de todos os setores da B3
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
│   │   └── dashboard_final.py          # Painel consolidado com Recomendação e Checklist
│   └── exportacao/
│       └── exportador_excel.py         # Excel com 7 abas formatadas profissionalmente
│
├── interface/
│   └── interface_premissas.py          # Input guiado via terminal com contexto histórico
│
├── tests/
│   ├── test_coleta.py
│   ├── test_projecao.py
│   ├── test_valuation.py
│   └── fixtures/
│       └── Direcional_DIRR3_referencia.xlsx  # Benchmark de validação
│
├── notebooks/
│   ├── 01_exploracao_cvm.ipynb
│   ├── 02_exploracao_yfinance.ipynb
│   └── 03_validacao_calculos.ipynb
│
└── outputs/                            # Ignorada pelo Git
    ├── excel/                          # Arquivos .xlsx gerados
    └── graficos/                       # HTMLs e PNGs gerados pelo Plotly
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

O único ponto de input humano obrigatório do sistema. Para cada campo de premissa, o sistema exibe os dados históricos relevantes calculados no Módulo 2 — ao solicitar a taxa de crescimento do Ano 1, exibe o CAGR histórico de 3 e 5 anos e o crescimento do último ano. Ao solicitar a margem EBITDA do Ano 3, exibe as margens dos últimos 5 anos e a média do período.

Os campos de crescimento de receita, margem EBITDA e CAPEX/Receita são solicitados individualmente para cada um dos 8 anos — nunca como uma taxa única que se repete. O sistema valida cada input em tempo real, bloqueando configurações matematicamente inválidas (g ≥ taxa de desconto) e alertando para premissas muito distantes do histórico (margem projetada mais de 5pp acima da máxima histórica).

### Módulo 4 — Motor de Cálculo

A cadeia de cálculo é executada em sequência obrigatória porque cada passo depende do anterior. Para empresas não-financeiras: a DRE é projetada primeiro porque o Working Capital depende da Receita e do CMV, o schedule de PP&E depende do CAPEX que é percentual da Receita, o schedule de Dívida gera o Resultado Financeiro que fecha o LL da DRE, o FCFF é calculado com os componentes de todos os schedules, e o WACC desconta os fluxos para chegar no EV. Para instituições financeiras: a DRE adaptada gera o LL diretamente, o FCFE é calculado subtraindo a variação do capital regulatório mínimo retido, e o Ke desconta os fluxos sem bridge EV→Equity.

O checklist de consistência é executado ao final e classifica cada verificação como aprovada ou com alerta. Os itens do checklist são derivados diretamente das condições matemáticas obrigatórias do Gordon Growth Model e das melhores práticas de valuation documentadas por Damodaran, McKinsey e CFA Institute.

### Módulo 5 — Dashboard e Outputs

**Football Field:** Sete metodologias representadas como barras horizontais — DCF Bear, DCF Base, DCF Bull, Trading Comps EV/EBITDA, Trading Comps P/L, Múltiplo de Saída e 52-week Range — com o preço atual marcado por linha vertical. Permite ao analista ver instantaneamente se o DCF está em linha com o que o mercado está precificando ou se há divergência significativa que exige explicação.

**Tabelas de Sensibilidade:** A tabela WACC × g é obrigatória porque ela mapeia o espaço de incerteza das duas premissas mais impactantes do modelo. A tabela Receita × Margem EBITDA mapeia o "espaço de segurança" — as combinações de premissas onde ainda há upside mesmo sob cenários mais conservadores. A sensibilidade setorial é específica por setor porque os principais vetores de incerteza variam: para construtoras é Margem Bruta × VSO (Velocidade de Vendas sobre Oferta), para bancos é NIM × Índice de Eficiência, para mineração é Preço da Commodity × Custo de Produção (C1).

**Exportação Excel:** As 7 abas seguem a lógica do modelo Direcional e os padrões de estruturação de Wall Street Prep (WSP) — Capa, Premissas, Modelo Integrado, Schedules, Valuation, Sensibilidades e Output. A Aba de Premissas exibe explicitamente os 8 valores individuais de crescimento de receita por ano com a referência histórica ao lado, tornando o raciocínio do analista auditável por qualquer leitor do modelo.

---

## O Que o Analista Faz vs. O Que o Sistema Faz

### O Sistema Faz Automaticamente

- Identificar o código CVM de qualquer empresa pelo ticker
- Coletar 5 a 7 anos de DRE, Balanço e DFC da base de dados oficial da CVM
- Detectar se a empresa é financeira ou não-financeira e executar o pipeline correto
- Coletar preço, beta, ações em circulação e market cap via yfinance
- Coletar Selic, IPCA, CDI e projeções Focus via API do BACEN
- Calcular todas as métricas históricas relevantes por tipo de empresa
- Projetar as demonstrações financeiras para 8 anos a partir das premissas
- Verificar o fechamento do balanço em todos os anos projetados
- Calcular FCFF ou FCFE, WACC ou Ke, Valor Terminal, EV, Equity Value, Target Price
- Executar o checklist de consistência e sinalizar problemas
- Gerar Football Field, Waterfall, Sensibilidades e Dashboard
- Exportar o Excel com 7 abas formatadas profissionalmente

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
| Modelo DCF Completo | `.xlsx` (7 abas) | Capa, Premissas, Modelo Integrado, Schedules, Valuation, Sensibilidades, Dashboard |
| Football Field | `.html` + `.png` | 7 metodologias com preço atual destacado |
| Tabela WACC × g | `.html` + `.png` | 6×6 com formatação condicional e % do EV na perpetuidade |
| Tabela Receita × Margem | `.html` + `.png` | Espaço de segurança visual do valuation |
| Sensibilidade Setorial | `.html` + `.png` | Margem × VSO (construção), NIM × Eficiência (bancos), Preço × C1 (mineração) |
| Waterfall do EV | `.html` + `.png` | Decomposição por componente com % de cada contribuição |
| Dashboard Final | `.html` | Target Price, Recomendação, MOIC, Checklist consolidados |

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
# Análise completa — o sistema detecta automaticamente o tipo de empresa
python main.py --ticker DIRR3 --setor construcao

# Usando premissas já preenchidas anteriormente
python main.py --ticker DIRR3 --setor construcao --usar-premissas-existentes

# Empresa financeira — o sistema usa FCFE e Ke automaticamente
python main.py --ticker ITUB4 --setor banco

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
      → Excel: outputs/excel/DCF_DIRR3_2026-07-15.xlsx
      → Gráficos: outputs/graficos/ (7 arquivos)
      → Checklist: 9/10 itens aprovados | 1 alerta
```

---

## Roadmap

| Versão | Prazo | Escopo |
|--------|-------|--------|
| **v1.0** | Agosto 2026 | Pipeline completo para qualquer ação da B3. Dois métodos de valuation (FCFF e FCFE). 8 taxas de crescimento individuais por ano. Football Field, WACC×g, Dashboard, Excel 7 abas. Interface via terminal. |
| **v1.5** | Out 2026 | Interface web via Streamlit substituindo o terminal. Suporte expandido a novos setores com sensibilidades específicas. |
| **v2.0** | Jan 2027 | Trading Comps automatizado via yfinance para peers do setor. Módulo de qualidade de lucro (FCO/EBITDA histórico, accruals). Build-up de receita setorial para construtoras (VGV × VSO × PoC). |
| **v3.0** | Mid 2027 | Exportação em PDF estilo research report institucional. Módulo de LBO simplificado. Integração com modelos unitários de empreendimento para construtoras. |

---

## Referências Teóricas e Bibliográficas

Este projeto é construído sobre fundamentos teóricos consolidados pela literatura acadêmica e profissional de finanças corporativas e valuation. As referências abaixo são as bases intelectuais diretas das metodologias implementadas no sistema.

---

### Valuation e DCF

**DAMODARAN, Aswath. *Investment Valuation: Tools and Techniques for Determining the Value of Any Asset*. 3. ed. Wiley Finance, 2012.**
A principal referência teórica do projeto. As fórmulas de FCFF, FCFE, WACC, custo do equity via CAPM, Valor Terminal pelo Gordon Growth Model, ajuste do custo de capital para mercados emergentes (conversão Ke de USD para BRL), beta desalavancado via fórmula de Hamada, e o tratamento diferenciado de instituições financeiras são todos derivados diretamente de Damodaran. O site do autor (pages.stern.nyu.edu/~adamodar/) é consultado para os parâmetros de ERP (Equity Risk Premium) e Country Risk Premium utilizados no sistema.

**DAMODARAN, Aswath. *The Dark Side of Valuation*. 2. ed. Pearson FT Press, 2009.**
Referência para o tratamento de empresas em situações especiais — prejuízo histórico, FCFF negativo nos anos iniciais, empresas em reestruturação. As soluções implementadas no sistema para FCFF negativo no último ano de projeção (uso do NOPAT normalizado como base do Valor Terminal) são derivadas desta obra.

**KOLLER, Tim; GOEDHART, Marc; WESSELS, David. *Valuation: Measuring and Managing the Value of Companies*. 7. ed. McKinsey & Company / Wiley, 2020.**
Referência para a estrutura do modelo integrado de três demonstrativos (DRE + BP + DFC), a definição de Capital Investido e NOPAT para o cálculo do ROIC, os schedules de Working Capital e PP&E, e os padrões de checklist de consistência do modelo. A estrutura de abas do Excel exportado pelo sistema é inspirada nos padrões WSP documentados nesta obra.

**PENMAN, Stephen H. *Financial Statement Analysis and Security Valuation*. 5. ed. McGraw-Hill, 2012.**
Referência para a análise de demonstrações financeiras, identificação de itens não-recorrentes, qualidade do lucro (FCO/EBITDA como indicador de accruals) e o conceito de ROIIC (Return on Incremental Invested Capital) como métrica de criação de valor marginal.

---

### Custo de Capital e CAPM

**SHARPE, William F. Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk. *The Journal of Finance*, v. 19, n. 3, p. 425–442, 1964.**
O artigo seminal que estabelece o CAPM (Capital Asset Pricing Model), base do cálculo de Ke implementado no sistema. A fórmula Ke = Rf + β × (ERP + CRP) é a aplicação direta do modelo de Sharpe ao contexto de mercados emergentes.

**HAMADA, Robert S. The Effect of the Firm's Capital Structure on the Systematic Risk of Common Stocks. *The Journal of Finance*, v. 27, n. 2, p. 435–452, 1972.**
Base teórica da fórmula de Hamada utilizada no sistema para desalavancar o beta histórico da empresa e realavaancá-lo com a estrutura de capital alvo, isolando o risco operacional do risco financeiro.

---

### Análise de Criação de Valor

**MAUBOUSSIN, Michael J.; CALLAHAN, Dan. *Calculating Return on Invested Capital*. Credit Suisse Global Financial Strategies, 2014.**
Referência para a definição precisa de Capital Investido utilizada no sistema (NWC operacional + Imobilizado líquido + Goodwill + Outros ativos operacionais líquidos de imposto), a decomposição DuPont do ROIC (Margem NOPAT × Giro do Capital Investido), e o conceito de ROIIC como indicador da qualidade do crescimento futuro.

**DORSEY, Pat. *The Little Book That Builds Wealth: The Knockout Formula for Finding Great Investments*. Wiley, 2008.**
Referência conceitual para a análise de MOAT (vantagem competitiva sustentável) e sua relação com o spread ROIC − WACC exibido no dashboard final. Um ROIC consistentemente acima do WACC é a evidência quantitativa de um MOAT econômico — o sistema exibe esse spread por ano projetado para que o analista avalie se as premissas são coerentes com a vantagem competitiva da empresa.

---

### Finanças Corporativas Brasileiras

**ASSAF NETO, Alexandre. *Valuation: Métricas de Valor e Geração de Valor*. 2. ed. Atlas, 2017.**
Referência para as especificidades do mercado de capitais brasileiro — tratamento do RET (Regime Especial de Tributação) para construtoras com alíquota de 4% sobre a Receita Bruta em vez do EBT, ajuste do custo de capital para a estrutura de impostos brasileira (IR + CSLL de 34% para empresas gerais), e as particularidades das métricas de Working Capital para o mercado local.

**Banco Central do Brasil. *Relatório de Inflação* e *Relatório Focus*. Publicação trimestral e semanal.**
Fonte das projeções macroeconômicas utilizadas no sistema — Selic, IPCA e expectativas de mercado coletadas via python-bcb. O sistema usa as projeções Focus para o horizonte de 1 e 2 anos à frente como referência para o analista na definição das premissas de crescimento nominal.

---

### Análise Setorial — Construção Civil

**ROCHA LIMA JUNIOR, João da. *Análise de Investimentos: Princípios e Técnicas para Empreendimentos do Setor da Construção Civil*. Escola Politécnica da USP, 1993.**
Referência para as métricas específicas do setor de construção civil implementadas no sistema — VGV (Valor Geral de Vendas), VSO (Velocidade de Vendas sobre Oferta), REF (Receita de Empreendimentos a Faturar), PoC (Percentual de Conclusão pelo método IFRS 15) e os modelos unitários de empreendimento com TIR e VPL mensais.

---

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
