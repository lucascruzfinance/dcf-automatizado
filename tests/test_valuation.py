"""Testes do calculador de FCFF e FCFE."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_fcff import calcular_fcff


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_metadados_e_premissas(
    raiz: Path,
    ticker: str = "TEST3",
    setor: str = "varejo",
) -> None:
    """Cria dados minimos para detectar regra tributaria."""
    conteudo = {
        "ticker": ticker,
        "setor": setor,
        "tipo": "nao_financeira",
    }
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json", conteudo)
    salvar_json(raiz / "data" / "premissas" / f"{ticker}_premissas.json", conteudo)


def criar_projecao_fcff(
    raiz: Path,
    ticker: str = "TEST3",
    ebit: float = 100.0,
    depreciacao: float = 10.0,
    lucro_liquido: float = 50.0,
    delta_nwc: float = 5.0,
    capex: float = -20.0,
    delta_divida: float = 3.0,
) -> None:
    """Cria projecao integrada minima para o calculador."""
    dre = {}
    wk = {}
    ppe = {}
    divida = {}
    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        dre[chave_ano] = {
            "ano_projecao": chave_ano,
            "ebit": ebit,
            "depreciacao_amortizacao": depreciacao,
            "lucro_liquido": lucro_liquido,
        }
        wk[chave_ano] = {
            "ano_projecao": chave_ano,
            "delta_nwc": delta_nwc,
        }
        ppe[chave_ano] = {
            "ano_projecao": chave_ano,
            "capex": capex,
        }
        divida[chave_ano] = {
            "ano_projecao": chave_ano,
            "delta_divida": delta_divida,
        }

    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "dre": dre,
            "wk": wk,
            "ppe": ppe,
            "divida": divida,
        },
    )


def test_calcular_fcff_positivo_com_valores_conhecidos(tmp_path: Path) -> None:
    """Valida FCFF positivo pela formula canonica."""
    criar_metadados_e_premissas(tmp_path)
    criar_projecao_fcff(tmp_path)

    resultado = calcular_fcff("TEST3", raiz_projeto=tmp_path)

    assert resultado["fcff"]["ano1"]["nopat"] == pytest.approx(66.0)
    assert resultado["fcff"]["ano1"]["fcff"] == pytest.approx(51.0)


def test_calcular_fcff_negativo_nao_trava(tmp_path: Path) -> None:
    """Garante que FCFF negativo e aceito como resultado valido."""
    criar_metadados_e_premissas(tmp_path)
    criar_projecao_fcff(
        tmp_path,
        ebit=10.0,
        depreciacao=0.0,
        delta_nwc=50.0,
        capex=-40.0,
    )

    resultado = calcular_fcff("TEST3", raiz_projeto=tmp_path)

    assert resultado["fcff"]["ano1"]["fcff"] == pytest.approx(-83.4)


def test_calcular_fcfe_com_delta_divida(tmp_path: Path) -> None:
    """Valida FCFE usando LL, D&A, NWC, CAPEX e delta divida."""
    criar_metadados_e_premissas(tmp_path)
    criar_projecao_fcff(
        tmp_path,
        lucro_liquido=40.0,
        depreciacao=15.0,
        delta_nwc=7.0,
        capex=-25.0,
        delta_divida=12.0,
    )

    resultado = calcular_fcff("TEST3", raiz_projeto=tmp_path)

    assert resultado["fcfe"]["ano1"]["fcfe"] == pytest.approx(35.0)


def test_construtora_ret_usa_aliquota_zero_no_nopat(tmp_path: Path) -> None:
    """Garante que construtora RET nao tributa o EBIT duas vezes no NOPAT."""
    criar_metadados_e_premissas(tmp_path, setor="construcao")
    criar_projecao_fcff(tmp_path, ebit=100.0)

    resultado = calcular_fcff("TEST3", raiz_projeto=tmp_path)

    assert resultado["aliquota_ir_nopat"] == pytest.approx(0.0)
    assert resultado["fcff"]["ano1"]["nopat"] == pytest.approx(100.0)
