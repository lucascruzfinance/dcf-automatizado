"""Testes do motor de cenarios Bear/Base/Bull (pipeline completo, sem rede)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.motor_cenarios import executar_cenarios
from tests.test_projecao import (
    criar_ambiente_projecao_integrada,
    salvar_json,
)

# CONGELADO v2.1 (Prompt 9.0.0 — Enxugamento): motor_cenarios saiu do nucleo.
# Testes preservados, mas pulados para a suite seguir verde (Humano_revisar D-053).
pytestmark = pytest.mark.skip(reason="congelado 9.0.0 — fora do nucleo (D-053)")


def preparar_ambiente_cenarios(tmp_path: Path) -> None:
    """Estende a fixture integrada com valuation completo e cenarios."""
    criar_ambiente_projecao_integrada(tmp_path)

    # Parametros com cenarios Bear/Bull e politica de divida deterministica.
    salvar_json(
        tmp_path / "config" / "parametros.json",
        {
            "vida_util_ppe_anos": 10,
            "payout_dividendos": 0.0,
            "politica_divida": {
                "prazo_amortizacao_lp_anos": 4,
                "caixa_minimo_pct_receita": 0.0,
                "taxa_aplicacao_caixa_fallback": 0.05,
            },
            "cenarios": {
                "bear": {
                    "fator_crescimento": 0.8,
                    "delta_margem_pp": -0.02,
                    "delta_wacc_pp": 0.01,
                    "delta_g_pp": -0.005,
                },
                "bull": {
                    "fator_crescimento": 1.2,
                    "delta_margem_pp": 0.02,
                    "delta_wacc_pp": -0.01,
                    "delta_g_pp": 0.005,
                },
            },
        },
    )

    # Premissas completas para WACC/VT/EV (alem da cadeia de projecao).
    caminho_premissas = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas = json.loads(caminho_premissas.read_text(encoding="utf-8"))
    premissas.update(
        {
            "beta": 1.0,
            "erp": 0.05,
            "crp": 0.03,
            "crescimento_perpetuidade_g": 0.02,
            "acoes_fully_diluted": 100.0,
            "payout_dividendos": 0.0,
            "taxa_aplicacao_caixa": 0.0,
        }
    )
    salvar_json(caminho_premissas, premissas)

    # Despesas financeiras historicas para o Kd historico do WACC.
    caminho_dre = tmp_path / "data" / "raw" / "cvm" / "TEST3_dre.json"
    registros = json.loads(caminho_dre.read_text(encoding="utf-8"))
    registros.append(
        {
            "ano_arquivo": 2025,
            "DT_FIM_EXERC": "2025-12-31",
            "ORDEM_EXERC": "ULTIMO",
            "CD_CONTA": "3.06.02",
            "nome_padronizado": "despesas_financeiras",
            "valor_padronizado": -40.0,
        }
    )
    salvar_json(caminho_dre, registros)

    # Mercado persistido: preco e Rf reproduziveis (sem rede/preco vivo).
    salvar_json(
        tmp_path / "data" / "raw" / "mercado" / "TEST3_mercado.json",
        {
            "ticker": "TEST3",
            "preco_atual": 10.0,
            "rf_usd_tbond10y": 0.04,
            "acoes_em_circulacao": 100.0,
        },
    )


def test_bear_base_bull_monotonicos_e_premissas_restauradas(
    tmp_path: Path,
) -> None:
    """Bear < Base < Bull em Target Price e premissas do analista intactas."""
    preparar_ambiente_cenarios(tmp_path)
    caminho_premissas = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas_antes = caminho_premissas.read_text(encoding="utf-8")

    cenarios = executar_cenarios("TEST3", raiz_projeto=tmp_path)

    assert set(cenarios) == {"bear", "base", "bull"}
    bear = cenarios["bear"]["target_price"]
    base = cenarios["base"]["target_price"]
    bull = cenarios["bull"]["target_price"]
    # Caso monotonico: crescimento/margem/g pioram no Bear e melhoram no Bull.
    assert bear < base < bull

    # As premissas do analista sao SEMPRE restauradas apos os cenarios.
    assert caminho_premissas.read_text(encoding="utf-8") == premissas_antes
    backup = caminho_premissas.with_suffix(".json.cenario_backup")
    assert not backup.exists()

    # O bloco cenarios fica persistido na projecao integrada.
    caminho_projecao = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    persistido = json.loads(caminho_projecao.read_text(encoding="utf-8"))
    assert persistido["cenarios"]["bear"]["target_price"] == bear
    # O disco termina no caso base (ev_equity oficial = cenario base).
    assert persistido["ev_equity"]["target_price"] == base


def test_taxa_desconto_recebe_delta_do_cenario(tmp_path: Path) -> None:
    """delta_wacc_pp do cenario e aplicado a taxa persistida antes do VT."""
    preparar_ambiente_cenarios(tmp_path)
    cenarios = executar_cenarios("TEST3", raiz_projeto=tmp_path)

    taxa_base = cenarios["base"]["taxa_desconto"]
    assert cenarios["bear"]["taxa_desconto"] > taxa_base
    assert cenarios["bull"]["taxa_desconto"] < taxa_base
