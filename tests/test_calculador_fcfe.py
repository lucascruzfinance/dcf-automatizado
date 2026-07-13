"""Testes do valuation FCFE/Ke da trilha financeira (fixtures sinteticas)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_fcfe import calcular_fcfe_financeira

HORIZONTE = 8


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para fixtures."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_projecao_bancaria(
    tmp_path: Path,
    ticker: str = "BANK3",
    delta_ano8: float = 20.0,
) -> None:
    """Projecao bancaria sintetica: LL 100/ano, ΔCapital 20/ano, Ke 13%."""
    dre = {}
    capital = {}
    for ano in range(1, HORIZONTE + 1):
        chave = f"ano{ano}"
        delta = delta_ano8 if ano == HORIZONTE else 20.0
        dre[chave] = {"ano_projecao": chave, "lucro_liquido": 100.0}
        capital[chave] = {
            "ano_projecao": chave,
            "delta_capital_regulatorio": delta,
            "roe_projetado": 0.15,
        }
    salvar_json(
        tmp_path / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "financeira",
            "dre": dre,
            "capital_regulatorio": capital,
            "ke": {"ke_brl": 0.13},
        },
    )
    salvar_json(
        tmp_path / "data" / "premissas" / f"{ticker}_premissas.json",
        {
            "ticker": ticker,
            "tipo": "financeira",
            "crescimento_perpetuidade_g": 0.03,
        },
    )


def test_fcfe_e_valuation_calculados_a_mao(tmp_path: Path) -> None:
    """FCFE = LL - ΔCapital; equity direto sem bridge; target por acao."""
    criar_projecao_bancaria(tmp_path)
    resultado = calcular_fcfe_financeira(
        "BANK3",
        raiz_projeto=tmp_path,
        preco_atual=5.0,
        acoes_fully_diluted=100.0,
        fator_escala_moeda=1.0,
    )

    # FCFE = 100 - 20 = 80 em todos os anos; payout implicito = 80%.
    for ano in range(1, HORIZONTE + 1):
        assert resultado["fcfe"][f"ano{ano}"]["fcfe"] == pytest.approx(80.0)
        assert resultado["fcfe"][f"ano{ano}"]["payout_implicito"] == pytest.approx(0.8)

    ke, g = 0.13, 0.03
    soma_vp = sum(80.0 / (1 + ke) ** ano for ano in range(1, HORIZONTE + 1))
    vt = 80.0 * (1 + g) / (ke - g)
    vp_vt = vt / (1 + ke) ** HORIZONTE
    equity_esperado = soma_vp + vp_vt

    ev_equity = resultado["ev_equity"]
    assert ev_equity["equity_value"] == pytest.approx(equity_esperado)
    assert ev_equity["target_price"] == pytest.approx(equity_esperado / 100.0)
    assert ev_equity["metodo_valuation"] == "fcfe_direto_sem_bridge"
    # Compatibilidade com o checklist universal: taxa em "wacc" = Ke.
    assert resultado["valor_terminal"]["wacc"] == pytest.approx(ke)


def test_g_maior_que_ke_bloqueia(tmp_path: Path) -> None:
    """g >= Ke explode a perpetuidade de Gordon e deve bloquear."""
    criar_projecao_bancaria(tmp_path)
    premissas = tmp_path / "data" / "premissas" / "BANK3_premissas.json"
    conteudo = json.loads(premissas.read_text(encoding="utf-8"))
    conteudo["crescimento_perpetuidade_g"] = 0.14
    salvar_json(premissas, conteudo)

    with pytest.raises(ValueError, match="Gordon"):
        calcular_fcfe_financeira(
            "BANK3",
            raiz_projeto=tmp_path,
            preco_atual=5.0,
            acoes_fully_diluted=100.0,
            fator_escala_moeda=1.0,
        )


def test_fcfe8_negativo_usa_payout_sustentavel(tmp_path: Path) -> None:
    """FCFE_8 <= 0 troca a base do VT por LL8 x (1 - g/ROE8), com aviso."""
    criar_projecao_bancaria(tmp_path, delta_ano8=200.0)  # FCFE_8 = -100.
    resultado = calcular_fcfe_financeira(
        "BANK3",
        raiz_projeto=tmp_path,
        preco_atual=5.0,
        acoes_fully_diluted=100.0,
        fator_escala_moeda=1.0,
    )

    valor_terminal = resultado["valor_terminal"]
    assert valor_terminal["base_vt"] == "payout_sustentavel_ll8"
    # base = 100 x (1 - 0,03/0,15) = 80.
    assert valor_terminal["base_utilizada"] == pytest.approx(80.0)
