"""Testes do bridge EV -> Equity completo (Onda 2): minoritarios,
coligadas, ativos nao operacionais e leasing IFRS16 entram no equity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_ev import calcular_ev

HORIZONTE = 8


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para fixtures."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_projecao_bridge(tmp_path: Path, ticker: str = "TEST3") -> None:
    """Projecao minima com FCFF constante e Ano 0 completo para o bridge."""
    fcff = {
        f"ano{ano}": {"ano_projecao": f"ano{ano}", "fcff": 100.0}
        for ano in range(1, HORIZONTE + 1)
    }
    salvar_json(
        tmp_path / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "fcff": fcff,
            "wacc": {"wacc": 0.10},
            "valor_terminal": {"vp_vt": 500.0},
            "ano0": {
                "divida": {
                    "divida_curto_prazo": 50.0,
                    "divida_longo_prazo": 150.0,
                },
                "balanco": {
                    "caixa_equivalentes": 30.0,
                    "aplicacoes_financeiras": 20.0,
                    "patrimonio_liquido": 1000.0,
                    # Componentes REAIS do bridge completo (Onda 2).
                    "participacao_nao_controladores": 40.0,
                    "investimentos_coligadas": 25.0,
                    "passivo_arrendamento": 10.0,
                },
            },
        },
    )
    salvar_json(
        tmp_path / "data" / "premissas" / f"{ticker}_premissas.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "acoes_fully_diluted": 100.0,
            "ativos_nao_operacionais": 15.0,
        },
    )


def _soma_vp_esperada(wacc: float) -> float:
    """Soma VP de FCFF constante de 100 por 8 anos."""
    return sum(100.0 / (1 + wacc) ** ano for ano in range(1, HORIZONTE + 1))


def test_bridge_completo_com_componentes_reais(tmp_path: Path) -> None:
    """Equity = EV - divida (com leasing) + caixa + aplic - minoritarios
    + coligadas + ativos nao operacionais."""
    criar_projecao_bridge(tmp_path)
    resultado = calcular_ev(
        "TEST3",
        raiz_projeto=tmp_path,
        preco_atual=5.0,
        acoes_fully_diluted=100.0,
        fator_escala_moeda=1.0,
    )

    ajustes = resultado["ajustes_bridge"]
    # Leasing IFRS16 vem do BP real do Ano 0 quando nao ha premissa.
    assert ajustes["leasing_ifrs16"] == pytest.approx(10.0)
    assert ajustes["divida_bruta"] == pytest.approx(50.0 + 150.0 + 10.0)
    assert ajustes["participacoes_minoritarias"] == pytest.approx(40.0)
    assert ajustes["investimentos_coligadas"] == pytest.approx(25.0)
    assert ajustes["ativos_nao_operacionais"] == pytest.approx(15.0)

    ev_esperado = _soma_vp_esperada(0.10) + 500.0
    equity_esperado = ev_esperado - 210.0 + 30.0 + 20.0 - 40.0 + 25.0 + 15.0
    assert resultado["ev"] == pytest.approx(ev_esperado)
    assert resultado["equity_value"] == pytest.approx(equity_esperado)
    assert resultado["target_price"] == pytest.approx(equity_esperado / 100.0)


def test_premissa_de_leasing_sobrepoe_o_balanco(tmp_path: Path) -> None:
    """leasing_ifrs16 informado pelo analista tem precedencia sobre o BP."""
    criar_projecao_bridge(tmp_path)
    caminho = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas = json.loads(caminho.read_text(encoding="utf-8"))
    premissas["leasing_ifrs16"] = 99.0
    salvar_json(caminho, premissas)

    resultado = calcular_ev(
        "TEST3",
        raiz_projeto=tmp_path,
        preco_atual=5.0,
        acoes_fully_diluted=100.0,
        fator_escala_moeda=1.0,
    )
    assert resultado["ajustes_bridge"]["leasing_ifrs16"] == pytest.approx(99.0)
    assert resultado["ajustes_bridge"]["divida_bruta"] == pytest.approx(299.0)
