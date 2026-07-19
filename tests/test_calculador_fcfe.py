"""Testes do valuation FCFE/Ke: trilha financeira + nao-financeira (9.0.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_fcfe import (
    calcular_fcfe_financeira,
    calcular_fcfe_naofinanceira,
)

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


# ---------------------------------------------------------------------------
# FCFE de NAO-financeiras (Prompt 9.0.3.1)
# ---------------------------------------------------------------------------

KE_NF = 0.13
G_NF = 0.03


def criar_projecao_naofinanceira(
    tmp_path: Path,
    ticker: str = "TEST3",
    fcfe_anual: float = 80.0,
    equity_bridge: float = 700.0,
    lucro_liquido: float = 90.0,
) -> None:
    """Projecao NF fechada: FCFF 100, juros 30, rec. fin. 5, ΔDivida 0.

    Decomposicao esperada (aliquota 34%): FCFE via FCFF = 100 - 35 x 0,66 +
    5 x 0,66 + 0 = 80,2; o campo ``fcfe`` da fixture define o lado LL e o
    residuo captura a diferenca.
    """
    fcff = {}
    fcfe = {}
    divida = {}
    dre = {}
    balanco = {}
    for ano in range(1, HORIZONTE + 1):
        chave = f"ano{ano}"
        fcff[chave] = {
            "ano_projecao": chave,
            "fcff": 100.0,
            "aliquota_ir_nopat": 0.34,
        }
        fcfe[chave] = {
            "ano_projecao": chave,
            "lucro_liquido": lucro_liquido,
            "delta_divida": 0.0,
            "fcfe": fcfe_anual,
        }
        divida[chave] = {
            "ano_projecao": chave,
            "juros": 30.0,
            "juros_arrendamento": 5.0,
            "receita_financeira_caixa": 5.0,
            "divida_bruta": 100.0,
        }
        dre[chave] = {"ano_projecao": chave, "lucro_liquido": lucro_liquido}
        balanco[chave] = {"ano_projecao": chave, "patrimonio_liquido": 600.0}
    salvar_json(
        tmp_path / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "dre": dre,
            "fcff": fcff,
            "fcfe": fcfe,
            "divida": divida,
            "balanco": balanco,
            "wacc": {"ke_brl": KE_NF},
            "ev_equity": {
                "equity_value": equity_bridge,
                "acoes_fully_diluted": 100.0,
                "fator_escala_moeda": 1.0,
                "preco_atual": 5.0,
            },
        },
    )
    salvar_json(
        tmp_path / "data" / "premissas" / f"{ticker}_premissas.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "crescimento_perpetuidade_g": G_NF,
        },
    )


def test_fcfe_naofinanceira_valuation_fechado(tmp_path: Path) -> None:
    """Equity FCFE/Ke = Σ VP(80; 13%) + VP(VT com ΔDivida normalizada)."""
    criar_projecao_naofinanceira(tmp_path)
    resultado = calcular_fcfe_naofinanceira("TEST3", raiz_projeto=tmp_path)
    valuation = resultado["fcfe_valuation"]

    # Base do VT: FCFE_8 - ΔDivida_8 + g x Divida_8 = 80 - 0 + 0,03 x 100.
    assert valuation["base_vt"] == "fcfe_ano8_delta_divida_normalizada"
    base = 80.0 + G_NF * 100.0
    assert valuation["base_utilizada"] == pytest.approx(base)

    soma_vp = sum(80.0 / (1 + KE_NF) ** ano for ano in range(1, HORIZONTE + 1))
    vt = base * (1 + G_NF) / (KE_NF - G_NF)
    equity_esperado = soma_vp + vt / (1 + KE_NF) ** HORIZONTE
    assert valuation["equity_value_fcfe"] == pytest.approx(equity_esperado)
    assert valuation["target_price_fcfe"] == pytest.approx(equity_esperado / 100.0)
    assert valuation["ke"] == pytest.approx(KE_NF)


def test_fcfe_naofinanceira_decomposicao_via_fcff(tmp_path: Path) -> None:
    """FCFE via FCFF = FCFF - juros apos IR + rec. fin. apos IR + ΔDivida."""
    criar_projecao_naofinanceira(tmp_path)
    resultado = calcular_fcfe_naofinanceira("TEST3", raiz_projeto=tmp_path)
    linha = resultado["fcfe"]["ano1"]

    # juros apos IR = (30 + 5) x (1 - 0,34) = 23,1; rec. fin. = 5 x 0,66.
    assert linha["juros_apos_ir"] == pytest.approx(35.0 * 0.66)
    assert linha["receita_financeira_apos_ir"] == pytest.approx(5.0 * 0.66)
    fcfe_via_fcff = 100.0 - 35.0 * 0.66 + 5.0 * 0.66 + 0.0
    assert linha["fcfe_via_fcff"] == pytest.approx(fcfe_via_fcff)
    # Residuo amarra as duas formas: fcfe (LL) - fcfe via FCFF.
    assert linha["residuo_regime_tributario"] == pytest.approx(80.0 - fcfe_via_fcff)


def test_fcfe_naofinanceira_reconciliacao_com_bridge(tmp_path: Path) -> None:
    """Bridge proximo -> sem aviso; bridge distante -> aviso (nunca erro)."""
    criar_projecao_naofinanceira(tmp_path, equity_bridge=700.0)
    resultado = calcular_fcfe_naofinanceira("TEST3", raiz_projeto=tmp_path)
    valuation = resultado["fcfe_valuation"]
    equity_fcfe = valuation["equity_value_fcfe"]
    assert valuation["divergencia_vs_bridge"] == pytest.approx(equity_fcfe / 700.0 - 1)
    assert valuation["divergencia_acima_limiar"] == (
        abs(equity_fcfe / 700.0 - 1) > 0.15
    )

    criar_projecao_naofinanceira(tmp_path, ticker="LONGE3", equity_bridge=10_000.0)
    divergente = calcular_fcfe_naofinanceira("LONGE3", raiz_projeto=tmp_path)
    assert divergente["fcfe_valuation"]["divergencia_acima_limiar"] is True


def test_fcfe_naofinanceira_sem_base_perpetuidade_nao_quebra(
    tmp_path: Path,
) -> None:
    """FCFE_8 <= 0 e LL <= 0: valuation persiste None + aviso, sem excecao."""
    criar_projecao_naofinanceira(
        tmp_path,
        ticker="NEG3",
        fcfe_anual=-50.0,
        lucro_liquido=-10.0,
    )
    resultado = calcular_fcfe_naofinanceira("NEG3", raiz_projeto=tmp_path)
    valuation = resultado["fcfe_valuation"]
    assert valuation["base_vt"] == "sem_base_perpetuidade"
    assert valuation["equity_value_fcfe"] is None
    assert valuation["aviso"] is not None
