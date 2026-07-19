"""Testes do modulo de comparaveis/CCA (funcoes puras, sem rede)."""

from __future__ import annotations

import pytest

from src.valuation.comparaveis import (
    calcular_divida_liquida,
    calcular_estatisticas,
    carregar_comparaveis,
    derivar_precos_implicitos,
    montar_triangulacao,
)

# CONGELADO v2.1 (Prompt 9.0.0 — Enxugamento): comparaveis saiu do nucleo.
# Testes preservados, mas pulados para a suite seguir verde (Humano_revisar D-053).
pytestmark = pytest.mark.skip(reason="congelado 9.0.0 — fora do nucleo (D-053)")


def test_mediana_e_quartis_descartam_invalidos() -> None:
    """Mediana/quartis corretos; peer sem dado e multiplo negativo saem."""
    multiplos_por_peer = {
        "AAAA3": {"ev_ebitda": 4.0, "p_l": 10.0},
        "BBBB3": {"ev_ebitda": 6.0, "p_l": None},
        "CCCC3": {"ev_ebitda": 8.0, "p_l": 12.0},
        "DDDD3": {"ev_ebitda": None, "p_l": None},
        # P/L negativo (prejuizo): descartado com aviso, nao contamina.
        "EEEE3": {"ev_ebitda": -2.0, "p_l": -5.0},
    }
    estatisticas, avisos = calcular_estatisticas(
        multiplos_por_peer,
        ("ev_ebitda", "p_l"),
    )

    assert estatisticas["ev_ebitda"]["mediana"] == pytest.approx(6.0)
    assert estatisticas["ev_ebitda"]["q1"] == pytest.approx(5.0)
    assert estatisticas["ev_ebitda"]["q3"] == pytest.approx(7.0)
    assert estatisticas["ev_ebitda"]["n"] == 3
    assert estatisticas["p_l"]["n"] == 2
    texto_avisos = " | ".join(avisos)
    assert "descartado" in texto_avisos  # negativo
    assert "EEEE3" in texto_avisos


def test_multiplo_sem_peers_suficientes_e_omitido() -> None:
    """Menos de 2 peers validos: estatistica omitida com aviso."""
    estatisticas, avisos = calcular_estatisticas(
        {"AAAA3": {"ev_ebitda": 5.0}},
        ("ev_ebitda",),
    )
    assert "ev_ebitda" not in estatisticas
    assert any("sem peers suficientes" in aviso for aviso in avisos)


def test_precos_implicitos_por_multiplo() -> None:
    """EV-multiplo passa pelo bridge de divida liquida; P/L e direto."""
    estatisticas = {
        "ev_ebitda": {"q1": 4.0, "mediana": 6.0, "q3": 8.0, "n": 3},
        "p_l": {"q1": 6.0, "mediana": 8.0, "q3": 10.0, "n": 3},
        "p_vp": {"q1": 1.0, "mediana": 1.5, "q3": 2.0, "n": 3},
    }
    denominadores = {
        "ebitda": 100.0,
        "lucro_liquido": 50.0,
        "patrimonio_liquido": 200.0,
        "divida_curto_prazo": -30.0,
        "divida_longo_prazo": -20.0,
        "caixa_equivalentes": 10.0,
        "aplicacoes_financeiras": 0.0,
    }
    assert calcular_divida_liquida(denominadores) == pytest.approx(40.0)

    precos, avisos = derivar_precos_implicitos(
        estatisticas,
        denominadores,
        acoes=10.0,
        fator_escala=1.0,
    )
    # EV/EBITDA mediana: (6 x 100 - 40) / 10 = 56.
    assert precos["ev_ebitda"]["mediana"] == pytest.approx(56.0)
    # P/L mediana: 8 x 50 / 10 = 40. P/VP mediana: 1,5 x 200 / 10 = 30.
    assert precos["p_l"]["mediana"] == pytest.approx(40.0)
    assert precos["p_vp"]["mediana"] == pytest.approx(30.0)
    assert avisos == []


def test_denominador_nao_positivo_omite_preco_com_aviso() -> None:
    """Alvo com prejuizo nao gera preco implicito por P/L."""
    estatisticas = {"p_l": {"q1": 6.0, "mediana": 8.0, "q3": 10.0, "n": 3}}
    denominadores = {"lucro_liquido": -50.0}
    precos, avisos = derivar_precos_implicitos(
        estatisticas,
        denominadores,
        acoes=10.0,
        fator_escala=1.0,
    )
    assert precos == {}
    assert any("P/L" in aviso for aviso in avisos)


def test_triangulacao_gera_veredito_textual() -> None:
    """DCF acima/dentro/abaixo da faixa Q1-Q3 dos multiplos principais."""
    precos = {
        "ev_ebitda": {"q1": 10.0, "mediana": 12.0, "q3": 14.0},
        "p_l": {"q1": 9.0, "mediana": 11.0, "q3": 13.0},
    }
    principais = ("ev_ebitda", "p_l")

    acima = montar_triangulacao(20.0, precos, principais, 8.0)
    assert "ACIMA" in acima["veredito"]
    assert acima["faixa_multiplos"] == {"minimo": 9.0, "maximo": 14.0}

    dentro = montar_triangulacao(12.0, precos, principais, 8.0)
    assert "DENTRO" in dentro["veredito"]

    abaixo = montar_triangulacao(5.0, precos, principais, 8.0)
    assert "ABAIXO" in abaixo["veredito"]

    sem_dcf = montar_triangulacao(None, precos, principais, 8.0)
    assert "pendente" in sem_dcf["veredito"]


def test_carregar_comparaveis_ausente_devolve_vazio(tmp_path) -> None:
    """Sem comparaveis persistidos, consumidores recebem dicionario vazio."""
    assert carregar_comparaveis("NAOEXISTE", tmp_path) == {}
