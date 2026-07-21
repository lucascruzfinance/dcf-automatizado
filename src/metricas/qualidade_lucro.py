"""Qualidade do lucro: FCO/EBITDA, accruals e normalizacao (v2.0, Onda 2).

Diagnosticos historicos que separam lucro contabil de geracao de caixa:

- ``fco_ebitda`` por ano (FCO do DFC 6.01 / EBITDA historico) — abaixo de
  ~0,7x por varios anos sugere lucro de baixa qualidade;
- ``accruals`` = LL - FCO por ano (accruals positivos e persistentes sao o
  sinal classico de resultado descolado do caixa);
- itens NAO-RECORRENTES do ultimo exercicio anual, sinalizados pela limpeza
  da Onda 1 (flag ``eh_nao_recorrente`` no Parquet, sem remocao de linhas);
- ``ebitda_normalizado_ano0`` = EBITDA do Ano 0 - itens nao-recorrentes
  (assinados) e ``nopat_normalizado_ano0`` = EBIT normalizado x (1 - t
  marginal) — a base que o motor ja usa quando FCFF_8 < 0 no VT.

Persiste o bloco ``qualidade_lucro`` em ``<TICKER>_projecao.json`` (quando o
arquivo existe) e sempre em ``<TICKER>_metricas.json``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from src.metricas.metricas_historicas import (
    montar_series_anuais,
    serie_anual_por_ano,
)
from src.processamento.limpeza import carregar_parquet_limpo
from src.projecao.projetor_dre import (
    carregar_json,
    carregar_metadados,
    empresa_usa_ret,
    normalizar_ticker,
    normalizar_texto,
    resolver_raiz,
    salvar_json,
)

ALIQUOTA_MARGINAL = 0.34
JANELA_MEDIA = 3

logger = logging.getLogger(__name__)


def _quadro_bruto(ticker: str, raiz: Path, demonstrativo: str) -> pd.DataFrame:
    """JSON bruto da CVM em DataFrame; vazio se ausente."""
    caminho = raiz / "data" / "raw" / "cvm" / f"{ticker}_{demonstrativo}.json"
    if not caminho.exists():
        return pd.DataFrame()
    return pd.DataFrame(carregar_json(caminho))


def levantar_nao_recorrentes_ano0(
    ticker: str,
    raiz: Path,
) -> tuple[list[dict[str, Any]], float]:
    """Itens da DRE do ultimo exercicio anual sinalizados como nao-recorrentes.

    Le o Parquet limpo (flag ``eh_nao_recorrente`` da Onda 1). Devolve a
    lista de itens e a soma ASSINADA dos valores (despesa negativa reduz o
    EBITDA reportado; remove-la aumenta o normalizado).
    """
    dre = carregar_parquet_limpo(ticker, "dre", raiz)
    if dre.empty or "eh_nao_recorrente" not in dre.columns:
        return [], 0.0

    filtro = dre["eh_nao_recorrente"].fillna(False)
    if "tipo_documento" in dre.columns:
        filtro &= dre["tipo_documento"] == "DFP"
    marcados = dre[filtro].copy()
    if marcados.empty:
        return [], 0.0

    datas = pd.to_datetime(marcados.get("DT_FIM_EXERC"), errors="coerce")
    marcados = marcados[(datas.dt.month == 12) & (datas.dt.day == 31)]
    if marcados.empty:
        return [], 0.0
    datas = pd.to_datetime(marcados["DT_FIM_EXERC"], errors="coerce")
    marcados = marcados[datas == datas.max()]
    if "ORDEM_EXERC" in marcados.columns:
        # Convencao unica do projeto: ORDEM_EXERC normalizada == "ultimo".
        # (str.contains("LT") casava PENULTIMO tambem — pen-uLTimo.)
        ultimos = marcados[marcados["ORDEM_EXERC"].map(normalizar_texto) == "ultimo"]
        if not ultimos.empty:
            marcados = ultimos

    itens: list[dict[str, Any]] = []
    soma = 0.0
    vistos: set[tuple[str, str]] = set()
    for _, linha in marcados.iterrows():
        chave = (str(linha.get("CD_CONTA")), str(linha.get("DS_CONTA")))
        if chave in vistos:
            continue
        vistos.add(chave)
        valor = linha.get("VL_CONTA")
        valor_float = (
            float(valor) if isinstance(valor, (int, float)) and pd.notna(valor) else 0.0
        )
        itens.append(
            {
                "codigo": chave[0],
                "descricao": chave[1],
                "valor": valor_float,
            }
        )
        soma += valor_float
    return itens, soma


def calcular_qualidade_lucro(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Calcula e persiste o bloco de qualidade do lucro do ticker."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    metadados = carregar_metadados(ticker_normalizado, raiz)

    series = montar_series_anuais(ticker_normalizado, raiz)
    dfc = _quadro_bruto(ticker_normalizado, raiz, "dfc")
    fco_por_ano = serie_anual_por_ano(dfc, "fco")

    receitas = series["receita_liquida"]
    ebit = series["ebit"]
    depreciacao = series["depreciacao_amortizacao"]
    lucro = series["lucro_liquido"]

    anos = sorted(set(receitas) & set(fco_por_ano))
    por_ano: dict[str, dict[str, float | None]] = {}
    razoes: list[float] = []
    for ano in anos:
        fco = fco_por_ano.get(ano)
        ebitda = None
        if ebit.get(ano) is not None and depreciacao.get(ano) is not None:
            # Formula: EBITDA = EBIT + |D&A| (D&A vem negativa do DFC).
            ebitda = ebit[ano] + abs(depreciacao[ano])
        fco_ebitda = None
        if fco is not None and ebitda not in (None, 0):
            fco_ebitda = fco / ebitda
            razoes.append(fco_ebitda)
        accruals = None
        if lucro.get(ano) is not None and fco is not None:
            # Formula: accruals = LL - FCO (positivo persistente = alerta).
            accruals = lucro[ano] - fco
        por_ano[str(ano)] = {
            "fco": fco,
            "ebitda": ebitda,
            "fco_ebitda": fco_ebitda,
            "lucro_liquido": lucro.get(ano),
            "accruals": accruals,
        }

    media_fco_ebitda = (
        sum(razoes[-JANELA_MEDIA:]) / len(razoes[-JANELA_MEDIA:]) if razoes else None
    )

    itens_nao_recorrentes, soma_nao_recorrentes = levantar_nao_recorrentes_ano0(
        ticker_normalizado,
        raiz,
    )
    ano0 = max(anos) if anos else None
    ebitda_ano0 = por_ano.get(str(ano0), {}).get("ebitda") if ano0 else None

    ebitda_normalizado = None
    nopat_normalizado = None
    if ebitda_ano0 is not None:
        # Remover o efeito assinado dos itens nao-recorrentes do EBITDA.
        ebitda_normalizado = float(ebitda_ano0) - soma_nao_recorrentes
        depreciacao_ano0 = depreciacao.get(ano0)
        if depreciacao_ano0 is not None:
            aliquota = 0.0 if empresa_usa_ret({}, metadados) else ALIQUOTA_MARGINAL
            # Formula: NOPAT normalizado = (EBITDA_norm - |D&A|) x (1 - t).
            nopat_normalizado = (ebitda_normalizado - abs(depreciacao_ano0)) * (
                1 - aliquota
            )

    resultado = {
        "ticker": ticker_normalizado,
        "por_ano": por_ano,
        "fco_ebitda_media_3a": media_fco_ebitda,
        "itens_nao_recorrentes_ano0": itens_nao_recorrentes,
        "soma_nao_recorrentes_ano0": soma_nao_recorrentes,
        "ebitda_normalizado_ano0": ebitda_normalizado,
        "nopat_normalizado_ano0": nopat_normalizado,
    }

    caminho_metricas = (
        raiz / "data" / "processed" / f"{ticker_normalizado}_metricas.json"
    )
    if caminho_metricas.exists():
        metricas = carregar_json(caminho_metricas)
        metricas["qualidade_lucro"] = resultado
        salvar_json(caminho_metricas, metricas)

    caminho_projecao = (
        raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
    )
    if caminho_projecao.exists():
        conteudo = carregar_json(caminho_projecao)
        conteudo["qualidade_lucro"] = resultado
        salvar_json(caminho_projecao, conteudo)

    return resultado


def main() -> None:
    """Executa a qualidade do lucro para DIRR3 e MGLU3."""
    for ticker in ("DIRR3", "MGLU3"):
        resultado = calcular_qualidade_lucro(ticker)
        media = resultado["fco_ebitda_media_3a"]
        print(
            (
                f"{ticker}: FCO/EBITDA 3a = " f"{media:.2f}x"
                if media is not None
                else f"{ticker}: n/d"
            ),
            f"| nao-recorrentes ano0 = {resultado['soma_nao_recorrentes_ano0']:,.0f}"
            f" ({len(resultado['itens_nao_recorrentes_ano0'])} itens)",
        )


if __name__ == "__main__":
    main()
