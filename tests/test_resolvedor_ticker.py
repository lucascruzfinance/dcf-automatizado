"""Testes do resolvedor universal de ticker B3 -> CD_CVM (sem rede)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.coleta.resolvedor_ticker import (
    TickerNaoEncontradoErro,
    caminho_cache_cadastro,
    resolver_ticker,
)


def mapa_sintetico() -> pd.DataFrame:
    """Mapa ticker -> CD_CVM sintetico com ON/PN/UNIT e uma deslistada."""
    return pd.DataFrame(
        {
            "ticker": ["PETR3", "PETR4", "ITUB4", "SANB11", "OIBR3"],
            "codigo_cvm": [9512, 9512, 19348, 20766, 11312],
            "cnpj": [
                "33.000.167/0001-01",
                "33.000.167/0001-01",
                "60.872.504/0001-23",
                "90.400.888/0001-42",
                "76.535.764/0001-43",
            ],
            "razao_social": [
                "PETROLEO BRASILEIRO SA",
                "PETROLEO BRASILEIRO SA",
                "ITAU UNIBANCO HOLDING SA",
                "BANCO SANTANDER BRASIL SA",
                "OI SA",
            ],
            "setor_cvm": [
                "Petróleo e Gás",
                "Petróleo e Gás",
                "Bancos",
                "Bancos",
                "Telecomunicações",
            ],
            "situacao": ["ATIVO", "ATIVO", "ATIVO", "ATIVO", "Cancelada"],
            "ano_referencia": [2026, 2026, 2026, 2026, 2026],
        }
    )


def construtor_sintetico(raiz: Path) -> pd.DataFrame:
    """Substitui a construcao com rede pelo mapa sintetico."""
    return mapa_sintetico()


def test_resolve_on_pn_da_mesma_empresa(tmp_path: Path) -> None:
    """ON e PN da mesma companhia resolvem para o mesmo CD_CVM."""
    on = resolver_ticker("PETR3", tmp_path, construtor=construtor_sintetico)
    pn = resolver_ticker("petr4.sa", tmp_path, construtor=construtor_sintetico)
    assert on.codigo_cvm == pn.codigo_cvm == 9512
    assert pn.ticker == "PETR4"
    assert pn.razao_social == "PETROLEO BRASILEIRO SA"


def test_resolve_unit_com_seis_caracteres(tmp_path: Path) -> None:
    """UNITs (6 caracteres) tambem resolvem pelo cadastro."""
    unit = resolver_ticker("SANB11", tmp_path, construtor=construtor_sintetico)
    assert unit.codigo_cvm == 20766
    assert unit.setor_cvm == "Bancos"


def test_ticker_inexistente_levanta_erro_claro(tmp_path: Path) -> None:
    """Ticker fora do cadastro levanta erro acionavel, sem stack cru."""
    with pytest.raises(TickerNaoEncontradoErro, match="nao encontrado"):
        resolver_ticker("XXXX9", tmp_path, construtor=construtor_sintetico)


def test_ticker_deslistado_levanta_erro_claro(tmp_path: Path) -> None:
    """Registro cancelado na CVM e reportado como deslistagem."""
    with pytest.raises(TickerNaoEncontradoErro, match="deslistada"):
        resolver_ticker("OIBR3", tmp_path, construtor=construtor_sintetico)


def test_cache_parquet_evita_reconstrucao(tmp_path: Path) -> None:
    """Depois da primeira resolucao, o cache em Parquet e reutilizado."""
    resolver_ticker("ITUB4", tmp_path, construtor=construtor_sintetico)
    assert caminho_cache_cadastro(tmp_path).exists()

    def construtor_que_nao_deve_rodar(raiz: Path) -> pd.DataFrame:
        raise AssertionError("cache fresco nao deveria ser reconstruido")

    empresa = resolver_ticker(
        "ITUB4",
        tmp_path,
        construtor=construtor_que_nao_deve_rodar,
    )
    assert empresa.codigo_cvm == 19348
