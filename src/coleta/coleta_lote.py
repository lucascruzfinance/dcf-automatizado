"""Coleta em lote de multiplas empresas da B3 (v2.0, Onda 1).

Uso:
    python -m src.coleta.coleta_lote --tickers DIRR3 MGLU3 VALE3 WEGE3
    python -m src.coleta.coleta_lote --arquivo data/tickers.txt

Fluxo por lote: coleta CVM (cada ZIP anual e aberto UMA vez e filtrado para
todas as empresas) -> limpeza real (Parquet em ``data/processed/``) ->
relatorio de qualidade (score persistido no ``_meta.json``). Falha em um
ticker NAO derruba o lote: o erro fica registrado por etapa e aparece na
tabela-resumo final (ticker, tipo, subtipo, anos, score).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from src.coleta.coletor_cvm import (
    coletar_empresas,
    configurar_log,
    pasta_cvm,
    resolver_raiz,
)
from src.coleta.mapeador_contas import carregar_json
from src.coleta.relatorio_qualidade import gerar_relatorio_qualidade
from src.coleta.resolvedor_ticker import normalizar_ticker
from src.processamento.limpeza import limpar_empresa

LARGURA_OBSERVACAO = 48

logger = logging.getLogger(__name__)


def ler_tickers_de_arquivo(caminho: Path) -> list[str]:
    """Le tickers de um arquivo-texto (um por linha; ``#`` inicia comentario)."""
    if not caminho.exists():
        raise RuntimeError(f"Arquivo de tickers nao encontrado: {caminho}")
    tickers = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        conteudo = linha.split("#", 1)[0].strip()
        if conteudo:
            tickers.append(conteudo)
    return tickers


def preparar_tickers(
    tickers_argumento: list[str] | None,
    caminho_arquivo: str | None,
) -> list[str]:
    """Normaliza e deduplica os tickers do lote preservando a ordem."""
    brutos: list[str] = list(tickers_argumento or [])
    if caminho_arquivo:
        brutos.extend(ler_tickers_de_arquivo(Path(caminho_arquivo)))

    vistos: set[str] = set()
    preparados: list[str] = []
    for ticker in brutos:
        normalizado = normalizar_ticker(ticker)
        if normalizado and normalizado not in vistos:
            vistos.add(normalizado)
            preparados.append(normalizado)
    if not preparados:
        raise RuntimeError(
            "Nenhum ticker informado: use --tickers T1 T2 ... ou --arquivo."
        )
    return preparados


def _resultado_falha(etapa: str, erro: Exception) -> dict[str, Any]:
    """Formata o registro de falha de um ticker sem derrubar o lote."""
    return {
        "status": "FALHA",
        "etapa_falha": etapa,
        "erro": str(erro),
        "tipo": "n/d",
        "subtipo": "n/d",
        "quantidade_anos": None,
        "score": None,
        "avisos": [],
    }


def processar_pos_coleta(
    ticker: str,
    raiz: Path,
) -> dict[str, Any]:
    """Roda limpeza + relatorio de qualidade para um ticker ja coletado."""
    limpar_empresa(ticker, raiz_projeto=raiz)
    relatorio = gerar_relatorio_qualidade(ticker, raiz_projeto=raiz)
    meta = carregar_json(pasta_cvm(raiz) / f"{ticker}_meta.json")
    return {
        "status": "OK",
        "etapa_falha": None,
        "erro": None,
        "tipo": meta.get("tipo", "n/d"),
        "subtipo": meta.get("subtipo", "n/d"),
        "quantidade_anos": relatorio["quantidade_anos"],
        "score": relatorio["score_confiabilidade"],
        "avisos": relatorio["avisos"],
    }


def executar_lote(
    tickers: list[str],
    raiz_projeto: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Coleta, limpa e avalia a qualidade de uma lista de tickers da B3.

    Devolve ``{ticker: resultado}`` na ordem de entrada. Cada resultado
    carrega status OK/FALHA, a etapa que falhou (coleta, limpeza ou
    qualidade), tipo/subtipo, anos coletados e score de confiabilidade.
    """
    raiz = resolver_raiz(raiz_projeto)
    resultados: dict[str, dict[str, Any]] = {}

    _, erros_coleta = coletar_empresas(tickers, raiz)
    for ticker in tickers:
        if ticker in erros_coleta:
            resultados[ticker] = _resultado_falha("coleta", erros_coleta[ticker])
            continue
        try:
            resultados[ticker] = processar_pos_coleta(ticker, raiz)
        except Exception as erro:  # noqa: BLE001 - contrato: falha de 1 ticker
            # nao derruba o lote (limpeza/qualidade pode levantar ValueError/
            # ArrowInvalid de pandas/pyarrow, nao so RuntimeError).
            logger.error("Pos-coleta falhou para %s: %s", ticker, erro)
            resultados[ticker] = _resultado_falha("limpeza/qualidade", erro)
    return resultados


def _observacao(resultado: dict[str, Any]) -> str:
    """Resume erro ou primeiro aviso para a coluna final da tabela."""
    if resultado["status"] != "OK":
        texto = f"[{resultado['etapa_falha']}] {resultado['erro']}"
    elif resultado["avisos"]:
        quantidade = len(resultado["avisos"])
        texto = resultado["avisos"][0]
        if quantidade > 1:
            texto += f" (+{quantidade - 1} avisos)"
    else:
        texto = "-"
    texto = " ".join(texto.split())
    if len(texto) > LARGURA_OBSERVACAO:
        texto = texto[: LARGURA_OBSERVACAO - 3] + "..."
    return texto


def imprimir_tabela_resumo(resultados: dict[str, dict[str, Any]]) -> None:
    """Imprime a tabela-resumo do lote (ticker, tipo, subtipo, anos, score)."""
    cabecalho = (
        f"{'Ticker':<8} {'Status':<7} {'Tipo':<15} {'Subtipo':<20} "
        f"{'Anos':>4} {'Score':>5}  Observacao"
    )
    print("\n" + "=" * len(cabecalho))
    print("RESUMO DA COLETA EM LOTE")
    print("=" * len(cabecalho))
    print(cabecalho)
    print("-" * len(cabecalho))
    for ticker, resultado in resultados.items():
        anos = resultado["quantidade_anos"]
        score = resultado["score"]
        print(
            f"{ticker:<8} "
            f"{resultado['status']:<7} "
            f"{str(resultado['tipo']):<15} "
            f"{str(resultado['subtipo']):<20} "
            f"{'-' if anos is None else anos:>4} "
            f"{'-' if score is None else score:>5}  "
            f"{_observacao(resultado)}"
        )
    total = len(resultados)
    sucesso = sum(1 for r in resultados.values() if r["status"] == "OK")
    print("-" * len(cabecalho))
    print(f"{sucesso}/{total} tickers coletados com sucesso.")


def main(argumentos_cli: list[str] | None = None) -> int:
    """Ponto de entrada da coleta em lote via linha de comando."""
    parser = argparse.ArgumentParser(
        description=(
            "Coleta CVM em lote: coleta -> limpeza Parquet -> relatorio de "
            "qualidade, com tabela-resumo por ticker."
        )
    )
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=None,
        help="Tickers da B3 separados por espaco (ex.: DIRR3 MGLU3 VALE3).",
    )
    parser.add_argument(
        "--arquivo",
        default=None,
        help="Arquivo-texto com um ticker por linha (# inicia comentario).",
    )
    argumentos = parser.parse_args(argumentos_cli)

    configurar_log()
    try:
        tickers = preparar_tickers(argumentos.tickers, argumentos.arquivo)
    except RuntimeError as erro:
        print(f"Erro: {erro}")
        return 2

    resultados = executar_lote(tickers)
    imprimir_tabela_resumo(resultados)
    todos_ok = all(r["status"] == "OK" for r in resultados.values())
    return 0 if todos_ok else 1


if __name__ == "__main__":
    sys.exit(main())
