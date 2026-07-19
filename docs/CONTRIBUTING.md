# Guia de Contribuição e Convenções — DCF Automatizado

Este projeto é desenvolvido em um fluxo assistido por IA (OpenAI Codex como driver
principal). Este documento define as convenções que **todo código** — escrito por
humano ou por IA — deve seguir. O objetivo é impedir que sessões diferentes de IA
tomem decisões conflitantes e produzam um repositório inconsistente.

---

## 1. Fluxo de Desenvolvimento

O ciclo de trabalho de cada módulo segue sempre a mesma ordem:

1. **Humano** faz o trabalho manual da etapa (ativar venv, preencher premissas, validar dados).
2. **Humano** solicita ao Claude o prompt da tarefa.
3. **Claude** gera o prompt cirúrgico.
4. **Humano** cola o prompt no Codex.
5. **Codex** escreve/edita o código.
6. **Humano** roda o roteiro de teste da etapa.
7. **Humano** faz `git commit` + `git push` e atualiza o `CONTEXT.md`.

O detalhamento semana a semana está em [`ROTEIRO.md`](ROTEIRO.md).

---

## 2. Regra de Continuidade — o CONTEXT.md é sagrado

- O `CONTEXT.md` é colado no **início de cada sessão** do Codex.
- É atualizado obrigatoriamente no **final de cada sessão** com: o que foi feito, decisões de arquitetura tomadas, e a próxima tarefa.
- Nenhuma sessão de IA deve começar sem ler o `CONTEXT.md` primeiro.

---

## 3. Convenções de Código

### Idioma e nomenclatura
- Nomes de funções, variáveis e comentários em **português** (o domínio é o mercado financeiro brasileiro).
- Exemplos: `calcular_wacc()`, `receita_liquida`, `projetar_dre()`, `divida_bruta`.
- Funções em `snake_case`, constantes em `MAIÚSCULAS_COM_UNDERSCORE`.

### Nomes de colunas de DataFrame
- Padronizados via `config/mapeamento_cvm.json`.
- A **mesma grandeza tem o mesmo nome de coluna em todos os módulos** (coleta, projeção, valuation, exportação). Inconsistência de nome entre módulos é o bug mais caro deste projeto — evite-o.
- Nunca introduzir um nome de coluna novo sem registrá-lo no mapeamento.

### Convenções financeiras
- **Sinais:** despesas e saídas de caixa sempre negativas; receitas e entradas positivas.
- **Anos de projeção:** sempre 8, nomeados `ano1` a `ano8`.
- **8 valores individuais:** crescimento de receita, margem EBITDA e CAPEX/Receita têm 8 campos separados. **Nunca** replicar uma taxa única pelos 8 anos.
- **Valores negativos válidos:** ROIC, FCFF e LL podem ser negativos. O código não deve travar nesses casos.
- **Tributação:** empresas gerais → 34% sobre o EBT; construtoras no RET → 4% sobre a Receita Bruta.

### Robustez
- Todo acesso a campo da CVM trata campo ausente ou renomeado **sem quebrar silenciosamente**. Campo não mapeado vai para log.
- Tratamento explícito de erros de API (fora do ar, dados ausentes, estrutura diferente).

### Documentação e estilo
- Toda função tem **docstring**.
- Todo cálculo financeiro tem um **comentário com a fórmula**.
- Rodar `black .` e `flake8 .` antes de cada commit.

---

## 4. Testes

- Todo cálculo financeiro tem um teste `pytest` correspondente em `tests/`.
- Testes críticos obrigatórios: fechamento do balanço nos 8 anos (`test_projecao.py`) e cada cálculo de valuation (`test_valuation.py`).
- `pytest tests/ -v` deve estar verde antes de qualquer tag de versão.

---

## 5. Mensagens de Commit

Padrão recomendado (Conventional Commits):

```
feat: adiciona coletor da CVM universal
fix: corrige sinal invertido no CPV do balanço
docs: atualiza CONTEXT.md com estado da Semana 2
test: adiciona teste de fechamento de balanço
refactor: padroniza nome da coluna receita_liquida entre módulos
```

---

## 6. O Que NÃO Fazer

- **Não expandir o escopo da v1.0** para além de DIRR3 + MGLU3 sem decisão explícita.
- **Não reimplementar o motor de cálculo em JavaScript** — o Python é a fonte única de verdade.
- **Não commitar** `.env`, a pasta `data/`, a pasta `outputs/` ou a `.venv` (todos no `.gitignore`).
- **Não hard-codar** valores que deveriam ser premissas ou vir de config.
