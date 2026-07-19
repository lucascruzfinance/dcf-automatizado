"""Testes do painel de Retornos (Prompt 9.0.3.3) com fixtures fechadas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_retornos import calcular_retornos, calcular_tir

HORIZONTE = 8


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para fixtures."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_projecao_retornos(
    tmp_path: Path,
    ticker: str = "RET3",
    target_price: float = 20.0,
    dividendos: float = 0.0,
    tipo: str = "nao_financeira",
) -> None:
    """Projecao minima: preco 10, EV 2500, equity 2000, EBITDA 50/ano."""
    dre = {}
    dfc = {}
    capital = {}
    fcfe = {}
    for ano in range(1, HORIZONTE + 1):
        chave = f"ano{ano}"
        dre[chave] = {
            "ano_projecao": chave,
            "ebitda": 50.0,
            "receita_liquida": 200.0,
            "lucro_liquido": 20.0,
            "lpa": 0.2,
        }
        dfc[chave] = {"ano_projecao": chave, "dividendos": dividendos}
        capital[chave] = {"ano_projecao": chave, "capital_regulatorio": 400.0}
        fcfe[chave] = {"ano_projecao": chave, "fcfe": dividendos}
    conteudo: dict = {
        "ticker": ticker,
        "tipo": tipo,
        "dre": dre,
        "dfc": dfc,
        "ev_equity": {
            "ev": 2500.0,
            "equity_value": 2000.0,
            "target_price": target_price,
            "preco_atual": 10.0,
            "acoes_fully_diluted": 100.0,
            "fator_escala_moeda": 1.0,
        },
    }
    if tipo == "financeira":
        conteudo["capital_regulatorio"] = capital
        conteudo["fcfe"] = fcfe
    salvar_json(tmp_path / "data" / "processed" / f"{ticker}_projecao.json", conteudo)


def test_calcular_tir_fluxo_conhecido() -> None:
    """[-100, 0, 121] tem TIR exata de 10% a.a."""
    assert calcular_tir([-100.0, 0.0, 121.0]) == pytest.approx(0.10, abs=1e-6)


def test_calcular_tir_sem_mudanca_de_sinal_devolve_none() -> None:
    """Fluxos todos negativos nao tem raiz: TIR None, sem excecao."""
    assert calcular_tir([-100.0, 0.0, 0.0]) is None


def test_tir_moic_sem_dividendos(tmp_path: Path) -> None:
    """Entrada 10, saida 20 no ano 5, sem dividendos: MOIC 2x, TIR 2^(1/5)-1."""
    criar_projecao_retornos(tmp_path)
    resultado = calcular_retornos("RET3", raiz_projeto=tmp_path)
    base = resultado["tir_moic"]["cenarios"]["base"]

    assert base["preco_saida"] == pytest.approx(20.0)
    assert base["moic"] == pytest.approx(2.0)
    assert base["tir_acionista"] == pytest.approx(2.0 ** (1 / 5) - 1, abs=1e-6)
    # Bear/Bull variam a saida em -/+ 20% (config default).
    bear = resultado["tir_moic"]["cenarios"]["bear"]
    bull = resultado["tir_moic"]["cenarios"]["bull"]
    assert bear["preco_saida"] == pytest.approx(16.0)
    assert bull["preco_saida"] == pytest.approx(24.0)
    assert bear["tir_acionista"] < base["tir_acionista"] < bull["tir_acionista"]


def test_tir_moic_com_dividendos(tmp_path: Path) -> None:
    """Dividendos de 1/acao nos anos 1..5: MOIC 2,5x e NPV(TIR) = 0."""
    criar_projecao_retornos(tmp_path, dividendos=100.0)  # 100 / 100 acoes = 1.
    resultado = calcular_retornos("RET3", raiz_projeto=tmp_path)
    tir_moic = resultado["tir_moic"]
    base = tir_moic["cenarios"]["base"]

    assert tir_moic["dividendos_por_acao"]["ano1"] == pytest.approx(1.0)
    assert base["moic"] == pytest.approx((5 * 1.0 + 20.0) / 10.0)

    tir = base["tir_acionista"]
    fluxos = [-10.0, 1.0, 1.0, 1.0, 1.0, 21.0]
    npv = sum(fluxo / (1 + tir) ** ano for ano, fluxo in enumerate(fluxos))
    assert npv == pytest.approx(0.0, abs=1e-6)
    assert tir > 0  # target > preco => TIR positiva (DoD 9.0.3).


def test_target_negativo_trunca_saida_em_zero(tmp_path: Path) -> None:
    """Target negativo: saida 0 (responsabilidade limitada) + flag + TIR None."""
    criar_projecao_retornos(tmp_path, ticker="NEG3", target_price=-5.0)
    resultado = calcular_retornos("NEG3", raiz_projeto=tmp_path)
    base = resultado["tir_moic"]["cenarios"]["base"]
    assert base["preco_saida"] == 0.0
    assert base["preco_saida_truncado_em_zero"] is True
    assert base["moic"] == pytest.approx(0.0)
    assert base["tir_acionista"] is None  # sem entrada positiva no fluxo.


def test_multiplos_implicitos_nas_duas_pontas(tmp_path: Path) -> None:
    """EV/EBITDA, EV/Receita e P/L no preco atual e no target."""
    criar_projecao_retornos(tmp_path)
    resultado = calcular_retornos("RET3", raiz_projeto=tmp_path)
    linha = resultado["multiplos"]["ano1"]

    # EV no preco: 2500 + (10 x 100 - 2000) = 1500; no target: 2500.
    assert linha["ev_ebitda_preco_atual"] == pytest.approx(1500.0 / 50.0)
    assert linha["ev_ebitda_target"] == pytest.approx(2500.0 / 50.0)
    assert linha["ev_receita_preco_atual"] == pytest.approx(1500.0 / 200.0)
    assert linha["ev_receita_target"] == pytest.approx(2500.0 / 200.0)
    # P/L pelo LPA projetado: 10 / 0,2 e 20 / 0,2.
    assert linha["p_l_preco_atual"] == pytest.approx(50.0)
    assert linha["p_l_target"] == pytest.approx(100.0)


def test_financeira_usa_pl_e_pvp_sem_ev(tmp_path: Path) -> None:
    """Financeiras: P/L e P/VP (capital regulatorio como PL); sem EV/EBITDA."""
    criar_projecao_retornos(
        tmp_path,
        ticker="BANK3",
        tipo="financeira",
        dividendos=100.0,
    )
    resultado = calcular_retornos("BANK3", raiz_projeto=tmp_path)
    linha = resultado["multiplos"]["ano1"]

    assert "ev_ebitda_preco_atual" not in linha
    # VPA = 400 / 100 acoes = 4; P/VP = 10 / 4 = 2,5x.
    assert linha["vpa"] == pytest.approx(4.0)
    assert linha["p_vp_preco_atual"] == pytest.approx(2.5)
    assert linha["p_l_preco_atual"] == pytest.approx(50.0)
    # Dividendos da financeira vem do FCFE (capacidade de distribuicao).
    origem = resultado["tir_moic"]["origem_dividendos"]
    assert origem == "fcfe_financeira_truncado_em_zero"
