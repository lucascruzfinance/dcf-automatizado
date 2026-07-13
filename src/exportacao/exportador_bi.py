"""Exportador de tabelas planas para a camada de BI (Power BI).

Nasce na Onda 3 com a ``fato_comparaveis.csv`` (formato long/tidy: uma linha
por peer x multiplo, mais as linhas de estatistica e do alvo). O contrato
completo de export para BI — dim_empresa, fato_demonstracoes, fato_fcff,
sensibilidades etc. — e finalizado na Onda 5; este modulo e a semente dele.

Regra dura do projeto: o Power BI NUNCA recalcula valuation — apenas le os
CSVs gerados aqui. Nomes de coluna registrados em config/mapeamento_cvm.json.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.projecao.projetor_dre import normalizar_ticker, resolver_raiz
from src.valuation.comparaveis import carregar_comparaveis

logger = logging.getLogger(__name__)


def pasta_bi(raiz_projeto: Path, ticker: str) -> Path:
    """Devolve (criando) a pasta de export BI do ticker."""
    pasta = Path(raiz_projeto) / "outputs" / "bi" / normalizar_ticker(ticker)
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def montar_fato_comparaveis(comparaveis: dict) -> pd.DataFrame:
    """Tabela long/tidy dos comparaveis (funcao pura para testes).

    Colunas: ``ticker`` (alvo), ``peer``, ``multiplo``, ``valor_multiplo``,
    ``origem_valor`` (peer | alvo | q1 | mediana | q3).
    """
    linhas: list[dict[str, object]] = []
    ticker_alvo = str(comparaveis.get("ticker", ""))
    multiplos = list(comparaveis.get("multiplos_aplicaveis", []))

    for peer, dados in comparaveis.get("multiplos_por_peer", {}).items():
        for multiplo in multiplos:
            valor = dados.get(multiplo)
            if isinstance(valor, (int, float)):
                linhas.append(
                    {
                        "ticker": ticker_alvo,
                        "peer": peer,
                        "multiplo": multiplo,
                        "valor_multiplo": float(valor),
                        "origem_valor": "peer",
                    }
                )

    alvo = comparaveis.get("multiplos_alvo") or {}
    for multiplo in multiplos:
        valor = alvo.get(multiplo)
        if isinstance(valor, (int, float)):
            linhas.append(
                {
                    "ticker": ticker_alvo,
                    "peer": ticker_alvo,
                    "multiplo": multiplo,
                    "valor_multiplo": float(valor),
                    "origem_valor": "alvo",
                }
            )

    for multiplo, faixa in comparaveis.get("estatisticas", {}).items():
        for ponto in ("q1", "mediana", "q3"):
            linhas.append(
                {
                    "ticker": ticker_alvo,
                    "peer": None,
                    "multiplo": multiplo,
                    "valor_multiplo": float(faixa[ponto]),
                    "origem_valor": ponto,
                }
            )

    return pd.DataFrame(
        linhas,
        columns=["ticker", "peer", "multiplo", "valor_multiplo", "origem_valor"],
    )


def exportar_fato_comparaveis(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> Path:
    """Grava outputs/bi/<TICKER>/fato_comparaveis.csv a partir do JSON."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    comparaveis = carregar_comparaveis(ticker_normalizado, raiz)
    if not comparaveis:
        raise RuntimeError(
            f"Comparaveis nao gerados para {ticker_normalizado}. Rode "
            "python -m src.valuation.comparaveis antes do export BI."
        )

    tabela = montar_fato_comparaveis(comparaveis)
    caminho = pasta_bi(raiz, ticker_normalizado) / "fato_comparaveis.csv"
    # utf-8-sig: o Power BI (Windows) le o BOM e preserva acentuacao.
    tabela.to_csv(caminho, index=False, encoding="utf-8-sig")
    logger.info(
        "fato_comparaveis exportada: %s (%s linhas)",
        caminho,
        len(tabela),
    )
    return caminho


def main() -> None:
    """Exporta a fato_comparaveis para DIRR3 e MGLU3."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    for ticker in ("DIRR3", "MGLU3"):
        try:
            print(exportar_fato_comparaveis(ticker))
        except RuntimeError as erro:
            print(f"Falha no export BI de {ticker}: {erro}")


if __name__ == "__main__":
    main()
