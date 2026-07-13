"""Projetor da DRE bancaria e do capital regulatorio retido (v2.0, Onda 2).

Projeta a trilha FINANCEIRA (bancos/seguradoras) pelas linhas que a DFP da
CVM sustenta de fato:

- receitas de intermediacao financeira (crescimento anual, 8 valores);
- resultado bruto de intermediacao via margem anual (8 valores) — o spread
  e a PDD do template v1 ficam como referencia analitica: a DFP nao expoe
  carteira media confiavel para projeta-los diretamente;
- despesas/receitas operacionais liquidas como % das receitas (8 valores,
  negativas) -> EBT -> IR (aliquota financeira) -> lucro liquido.

Capital regulatorio retido (insumo do FCFE = LL - ΔCapital):
    RWA_t = fator_rwa_ativos x Ativo_t, com Ativo_t crescendo junto com as
    receitas (proxy documentada); capital_minimo_t = indice_capital_alvo x
    RWA_t; capital_t = max(capital_minimo_t, capital_(t-1)) — o banco nao
    libera capital ja constituido nem deixa o indice cair; o excesso do
    Ano 0 (PL real > minimo) nao e distribuido de uma vez (conservador).

Persiste os blocos ``dre``, ``capital_regulatorio`` e o Ano 0 bancario em
``data/processed/<TICKER>_projecao.json`` para o ``calculador_fcfe``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.projecao.projetor_dre import (
    HORIZONTE_PROJECAO,
    carregar_json,
    carregar_metadados,
    normalizar_ticker,
    normalizar_valor_json,
    resolver_raiz,
    salvar_json,
    selecionar_ultimo_exercicio,
    valor_numerico_obrigatorio,
)

VETORES_FINANCEIRA = (
    "crescimento_receita",
    "margem_resultado_bruto",
    "despesas_operacionais_receita",
)

logger = logging.getLogger(__name__)


def carregar_premissas_financeiras(
    ticker: str,
    raiz_projeto: Path,
) -> dict[str, Any]:
    """Carrega e valida as premissas bancarias (24 campos anuais + escalares)."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    premissas = carregar_json(caminho)
    for vetor in VETORES_FINANCEIRA:
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            valor_numerico_obrigatorio(premissas, f"{vetor}_ano{ano}")
    for escalar in ("indice_capital_alvo", "fator_rwa_ativos"):
        valor_numerico_obrigatorio(premissas, escalar)
    return premissas


def carregar_ano0_financeiro(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Ano 0 bancario: receitas de intermediacao, LL, PL e ativo total."""
    pasta = raiz_projeto / "data" / "raw" / "cvm"
    dre = pd.DataFrame(carregar_json(pasta / f"{ticker}_dre.json"))
    bp = pd.DataFrame(carregar_json(pasta / f"{ticker}_bp.json"))

    linha_receitas = selecionar_ultimo_exercicio(
        dre,
        "receitas_intermediacao_financeira",
    )
    linha_lucro = selecionar_ultimo_exercicio(dre, "lucro_liquido")
    linha_pl = selecionar_ultimo_exercicio(bp, "patrimonio_liquido")
    linha_ativo = selecionar_ultimo_exercicio(bp, "ativo_total")

    return {
        "fonte": f"data/raw/cvm/{ticker}_dre.json + _bp.json",
        "data_exercicio": normalizar_valor_json(linha_receitas.get("DT_FIM_EXERC")),
        "ano_arquivo": normalizar_valor_json(linha_receitas.get("ano_arquivo")),
        "receitas_intermediacao_financeira": float(linha_receitas["valor_padronizado"]),
        "lucro_liquido": float(linha_lucro["valor_padronizado"]),
        "patrimonio_liquido": float(linha_pl["valor_padronizado"]),
        "ativo_total": float(linha_ativo["valor_padronizado"]),
    }


def obter_aliquota_financeira(
    premissas: dict[str, Any],
    raiz_projeto: Path,
) -> float:
    """Aliquota de IR da trilha financeira: premissa > padrao da config."""
    valor = premissas.get("aliquota_ir_financeira")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    parametros = carregar_json(raiz_projeto / "config" / "parametros.json")
    return float(
        parametros.get("trilha_financeira", {}).get(
            "aliquota_ir_financeira_padrao",
            0.45,
        )
    )


def projetar_dre_bancaria(
    ano0: dict[str, Any],
    premissas: dict[str, Any],
    aliquota_ir: float,
) -> dict[str, dict[str, float | str]]:
    """Projeta a DRE bancaria de ano1 a ano8."""
    linhas: dict[str, dict[str, float | str]] = {}
    receitas_anterior = float(ano0["receitas_intermediacao_financeira"])

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        crescimento = float(premissas[f"crescimento_receita_ano{ano}"])
        margem = float(premissas[f"margem_resultado_bruto_ano{ano}"])
        razao_despesas = float(premissas[f"despesas_operacionais_receita_ano{ano}"])

        # Formula: Receitas_t = Receitas_(t-1) x (1 + crescimento_t).
        receitas = receitas_anterior * (1 + crescimento)
        # Formula: Resultado Bruto Intermediacao_t = Receitas_t x margem_t.
        resultado_bruto = receitas * margem
        # Formula: Despesas Operacionais_t = Receitas_t x razao_t (negativa).
        despesas_operacionais = receitas * razao_despesas
        ebt = resultado_bruto + despesas_operacionais
        # Formula: IR financeira = -aliquota x EBT positivo (45% padrao).
        ir_csll = -(max(ebt, 0.0) * aliquota_ir)
        lucro_liquido = ebt + ir_csll

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "taxa_crescimento_receita": crescimento,
            "receitas_intermediacao_financeira": receitas,
            "margem_resultado_bruto": margem,
            "resultado_bruto_intermediacao_financeira": resultado_bruto,
            "despesas_operacionais_receita": razao_despesas,
            "despesas_receitas_operacionais_financeira": despesas_operacionais,
            "ebt": ebt,
            "ir_csll": ir_csll,
            "lucro_liquido": lucro_liquido,
        }
        receitas_anterior = receitas

    return linhas


def projetar_capital_regulatorio(
    ano0: dict[str, Any],
    dre: dict[str, dict[str, float | str]],
    premissas: dict[str, Any],
) -> dict[str, dict[str, float | str]]:
    """Projeta RWA, capital minimo e o capital retido ano a ano.

    O ROE projetado usa o capital do inicio do ano (base efetivamente
    comprometida antes do retorno).
    """
    indice_alvo = float(premissas["indice_capital_alvo"])
    fator_rwa = float(premissas["fator_rwa_ativos"])
    ativo_anterior = float(ano0["ativo_total"])
    capital_anterior = max(
        float(ano0["patrimonio_liquido"]),
        indice_alvo * fator_rwa * ativo_anterior,
    )

    linhas: dict[str, dict[str, float | str]] = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        crescimento = float(dre[chave_ano]["taxa_crescimento_receita"])
        lucro = float(dre[chave_ano]["lucro_liquido"])

        # Proxy documentada: os ativos (e o RWA) crescem com as receitas.
        ativo = ativo_anterior * (1 + crescimento)
        rwa = fator_rwa * ativo
        capital_minimo = indice_alvo * rwa
        # O banco nao libera capital ja constituido (conservador).
        capital = max(capital_minimo, capital_anterior)
        delta_capital = capital - capital_anterior
        # Formula: ROE projetado = LL_t / capital no inicio do ano.
        roe_projetado = lucro / capital_anterior if capital_anterior > 0 else None

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "ativo_total": ativo,
            "rwa": rwa,
            "indice_capital_alvo": indice_alvo,
            "fator_rwa_ativos": fator_rwa,
            "capital_regulatorio_minimo": capital_minimo,
            "capital_regulatorio": capital,
            "delta_capital_regulatorio": delta_capital,
            "roe_projetado": roe_projetado,
        }
        ativo_anterior = ativo
        capital_anterior = capital

    return linhas


def projetar_financeiro(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa a projecao bancaria e persiste na projecao integrada."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    if str(metadados.get("tipo")) != "financeira":
        raise RuntimeError(
            f"{ticker_normalizado} nao e financeira "
            f"(tipo={metadados.get('tipo')}); use o projetor nao-financeiro."
        )

    premissas = carregar_premissas_financeiras(ticker_normalizado, raiz)
    ano0 = carregar_ano0_financeiro(ticker_normalizado, raiz)
    aliquota = obter_aliquota_financeira(premissas, raiz)
    dre = projetar_dre_bancaria(ano0, premissas, aliquota)
    capital = projetar_capital_regulatorio(ano0, dre, premissas)

    caminho = raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
    conteudo = carregar_json(caminho) if caminho.exists() else {}
    conteudo["ticker"] = ticker_normalizado
    conteudo["tipo"] = "financeira"
    conteudo["setor"] = metadados.get("setor")
    conteudo["subtipo"] = metadados.get("subtipo")
    conteudo["ano0"] = {**conteudo.get("ano0", {}), **{"financeiro": ano0}}
    conteudo["dre"] = dre
    conteudo["capital_regulatorio"] = capital
    politicas = conteudo.get("politicas_projecao")
    if not isinstance(politicas, dict):
        politicas = {}
    politicas["trilha_financeira"] = {
        "aliquota_ir_financeira": aliquota,
        "proxy_rwa": "ativos_crescem_com_receitas",
        "capital_nao_liberado": True,
    }
    conteudo["politicas_projecao"] = politicas
    salvar_json(caminho, conteudo)

    return {
        "ticker": ticker_normalizado,
        "ano0": ano0,
        "dre": dre,
        "capital_regulatorio": capital,
        "caminho_saida": caminho,
    }


def main() -> None:
    """Projeta a trilha financeira para ITUB4 e BBAS3."""
    for ticker in ("ITUB4", "BBAS3"):
        try:
            resultado = projetar_financeiro(ticker)
        except (RuntimeError, ValueError) as erro:
            print(f"Falha em {ticker}: {erro}")
            continue
        ano8 = resultado["dre"]["ano8"]
        capital8 = resultado["capital_regulatorio"]["ano8"]
        print(
            f"{ticker}: LL ano8 = {float(ano8['lucro_liquido']):,.0f} | "
            f"ROE ano8 = {float(capital8['roe_projetado'] or 0):.1%}"
        )


if __name__ == "__main__":
    main()
