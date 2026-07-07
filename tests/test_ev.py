"""Testes do bridge EV -> Equity -> Target Price -> Upside -> Recomendacao."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_ev import calcular_ev


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_premissas_ev(
    raiz: Path,
    ticker: str = "TEST3",
    acoes_fully_diluted: float | None = 1000.0,
) -> None:
    """Cria premissas minimas do bridge; acoes opcionais para testar erro."""
    conteudo: dict[str, object] = {"ticker": ticker}
    if acoes_fully_diluted is not None:
        conteudo["acoes_fully_diluted"] = acoes_fully_diluted
    salvar_json(raiz / "data" / "premissas" / f"{ticker}_premissas.json", conteudo)


def criar_projecao_ev(
    raiz: Path,
    ticker: str = "TEST3",
    wacc: float = 0.10,
    fcff: float = 100.0,
    vp_vt: float = 1000.0,
    divida_curto: float = 0.0,
    divida_longo: float = 0.0,
    caixa: float = 0.0,
    aplicacoes: float = 0.0,
) -> None:
    """Cria projecao integrada minima com blocos fcff, wacc, VT e ano0."""
    bloco_fcff = {}
    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        bloco_fcff[chave_ano] = {"ano_projecao": chave_ano, "fcff": fcff}
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "fcff": bloco_fcff,
            "wacc": {"wacc": wacc},
            "valor_terminal": {"vp_vt": vp_vt},
            "ano0": {
                "divida": {
                    "divida_curto_prazo": divida_curto,
                    "divida_longo_prazo": divida_longo,
                },
                "balanco": {
                    "caixa_equivalentes": caixa,
                    "aplicacoes_financeiras": aplicacoes,
                },
            },
        },
    )


def test_ev_igual_soma_vp_fcff_mais_vp_vt(tmp_path: Path) -> None:
    """EV deve ser exatamente a soma dos VP(FCFF) com o VP(VT)."""
    criar_premissas_ev(tmp_path)
    criar_projecao_ev(tmp_path)

    resultado = calcular_ev(
        "TEST3", raiz_projeto=tmp_path, preco_atual=1.0, acoes_fully_diluted=1000.0
    )

    assert resultado["ev"] == pytest.approx(
        resultado["soma_vp_fcff"] + resultado["vp_vt"], abs=1e-6
    )


def test_target_price_igual_equity_sobre_acoes(tmp_path: Path) -> None:
    """Target price deve ser equity value dividido pelas acoes fully diluted."""
    criar_premissas_ev(tmp_path)
    criar_projecao_ev(tmp_path)

    resultado = calcular_ev(
        "TEST3", raiz_projeto=tmp_path, preco_atual=1.0, acoes_fully_diluted=1000.0
    )

    assert resultado["target_price"] == pytest.approx(
        resultado["equity_value"] / resultado["acoes_fully_diluted"], abs=1e-6
    )


def test_upside_acima_de_20pct_gera_compra(tmp_path: Path) -> None:
    """Upside > +20% deve resultar em recomendacao COMPRA."""
    criar_premissas_ev(tmp_path)
    criar_projecao_ev(tmp_path)

    resultado = calcular_ev(
        "TEST3", raiz_projeto=tmp_path, preco_atual=1.0, acoes_fully_diluted=1000.0
    )

    # equity ~ 1533; target ~ 1.533; preco 1.0 -> upside ~ +53%.
    assert resultado["upside"] > 0.20
    assert resultado["recomendacao"] == "COMPRA"


def test_upside_intermediario_gera_neutro(tmp_path: Path) -> None:
    """Upside entre -5% e +20% deve resultar em NEUTRO."""
    criar_premissas_ev(tmp_path)
    criar_projecao_ev(tmp_path)

    resultado = calcular_ev(
        "TEST3", raiz_projeto=tmp_path, preco_atual=1.4, acoes_fully_diluted=1000.0
    )

    # target ~ 1.533; preco 1.4 -> upside ~ +9,5%.
    assert -0.05 <= resultado["upside"] <= 0.20
    assert resultado["recomendacao"] == "NEUTRO"


def test_upside_abaixo_de_menos_5pct_gera_venda(tmp_path: Path) -> None:
    """Upside < -5% deve resultar em recomendacao VENDA."""
    criar_premissas_ev(tmp_path)
    criar_projecao_ev(tmp_path)

    resultado = calcular_ev(
        "TEST3", raiz_projeto=tmp_path, preco_atual=2.0, acoes_fully_diluted=1000.0
    )

    # target ~ 1.533; preco 2.0 -> upside ~ -23%.
    assert resultado["upside"] < -0.05
    assert resultado["recomendacao"] == "VENDA"


def test_acoes_ausente_levanta_erro(tmp_path: Path) -> None:
    """acoes_fully_diluted ausente (e sem mercado) deve travar o bridge."""
    criar_premissas_ev(tmp_path, acoes_fully_diluted=None)
    criar_projecao_ev(tmp_path)

    with pytest.raises(ValueError, match="acoes_fully_diluted"):
        calcular_ev("TEST3", raiz_projeto=tmp_path, preco_atual=1.0)


def test_acoes_nao_positivo_levanta_erro(tmp_path: Path) -> None:
    """acoes_fully_diluted <= 0 deve travar o bridge."""
    criar_premissas_ev(tmp_path, acoes_fully_diluted=0.0)
    criar_projecao_ev(tmp_path)

    with pytest.raises(ValueError, match="acoes_fully_diluted"):
        calcular_ev("TEST3", raiz_projeto=tmp_path, preco_atual=1.0)


def test_escala_moeda_mil_converte_target_para_absoluto(tmp_path: Path) -> None:
    """ESCALA_MOEDA=MIL deve multiplicar o equity por 1000 no target price."""
    ticker = "TEST3"
    criar_premissas_ev(tmp_path, ticker=ticker)
    criar_projecao_ev(tmp_path, ticker=ticker)
    salvar_json(
        tmp_path / "data" / "raw" / "cvm" / f"{ticker}_bp.json",
        [{"ESCALA_MOEDA": "MIL", "nome_padronizado": "caixa_equivalentes"}],
    )

    resultado = calcular_ev(
        ticker, raiz_projeto=tmp_path, preco_atual=1.0, acoes_fully_diluted=1000.0
    )

    assert resultado["fator_escala_moeda"] == pytest.approx(1000.0)
    esperado = resultado["equity_value"] * 1000.0 / resultado["acoes_fully_diluted"]
    assert resultado["target_price"] == pytest.approx(esperado, abs=1e-6)


def test_bridge_desconta_divida_liquida(tmp_path: Path) -> None:
    """Equity deve refletir subtracao da divida e soma de caixa/aplicacoes."""
    criar_premissas_ev(tmp_path)
    criar_projecao_ev(
        tmp_path,
        divida_curto=200.0,
        divida_longo=300.0,
        caixa=100.0,
        aplicacoes=50.0,
    )

    resultado = calcular_ev(
        "TEST3", raiz_projeto=tmp_path, preco_atual=1.0, acoes_fully_diluted=1000.0
    )

    esperado = resultado["ev"] - 500.0 + 100.0 + 50.0
    assert resultado["equity_value"] == pytest.approx(esperado, abs=1e-6)
