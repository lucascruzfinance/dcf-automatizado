"""Testes das utilidades da coleta em lote (sem rede)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.coleta.coleta_lote import ler_tickers_de_arquivo, preparar_tickers


def test_ler_tickers_de_arquivo_ignora_comentarios(tmp_path: Path) -> None:
    """Arquivo de tickers aceita comentarios e linhas em branco."""
    caminho = tmp_path / "tickers.txt"
    caminho.write_text(
        "dirr3\n# lote de teste\nMGLU3  # varejo\n\nvale3.sa\n",
        encoding="utf-8",
    )
    assert ler_tickers_de_arquivo(caminho) == ["dirr3", "MGLU3", "vale3.sa"]


def test_preparar_tickers_normaliza_e_deduplica(tmp_path: Path) -> None:
    """Tickers de argumento e arquivo sao normalizados sem duplicatas."""
    caminho = tmp_path / "tickers.txt"
    caminho.write_text("dirr3\nMGLU3\nvale3.sa\n", encoding="utf-8")
    preparados = preparar_tickers(["dirr3", "DIRR3.SA"], str(caminho))
    assert preparados == ["DIRR3", "MGLU3", "VALE3"]


def test_preparar_tickers_sem_entrada_e_erro_claro() -> None:
    """Lote vazio falha com instrucao de uso, nao com stack cru."""
    with pytest.raises(RuntimeError, match="Nenhum ticker"):
        preparar_tickers(None, None)


def test_arquivo_inexistente_e_erro_claro(tmp_path: Path) -> None:
    """Arquivo de tickers ausente gera erro acionavel."""
    with pytest.raises(RuntimeError, match="nao encontrado"):
        ler_tickers_de_arquivo(tmp_path / "nao_existe.txt")
