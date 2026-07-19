"""Testes do coletor macro 9.0.3 (funcoes puras, sem rede)."""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from src.coleta.coletor_macro import (
    acumular_12m,
    focus_de_campos_legados,
    mesclar_preservando,
    montar_focus_anuais,
    montar_macro_anual,
    serie_convergente,
)

PARAMETROS_MACRO = {
    "metas_longo_prazo": {"ipca": 0.03, "selic": 0.09, "pib": 0.02},
    "cdi_spread_sobre_selic_pp": -0.001,
}
LOGGER = logging.getLogger("teste_macro")


def test_serie_convergente_focus_e_convergencia_linear() -> None:
    """Focus cobre 3 anos; do ultimo coberto converge LINEAR ate a meta no ano8."""
    conhecidos = {"2026": 0.14, "2027": 0.12, "2028": 0.105}
    serie = serie_convergente(conhecidos, meta=0.09, ano_base=2026, horizonte=8)

    valores = [valor for valor, _ in serie]
    origens = [origem for _, origem in serie]
    assert valores[:3] == pytest.approx([0.14, 0.12, 0.105])
    assert origens[:3] == ["focus", "focus", "focus"]
    # Convergencia: v_t = 0,105 + (0,09 - 0,105) x (t - 3) / (8 - 3).
    assert valores[3] == pytest.approx(0.105 + (0.09 - 0.105) * 1 / 5)
    assert valores[7] == pytest.approx(0.09)
    assert origens[3:] == ["convergencia_linear"] * 5


def test_serie_convergente_sem_focus_usa_meta() -> None:
    """Sem nenhum ano coberto, todos os anos valem a meta."""
    serie = serie_convergente({}, meta=0.02, ano_base=2026, horizonte=8)
    assert all(valor == pytest.approx(0.02) for valor, _ in serie)
    assert all(origem == "meta" for _, origem in serie)


def test_montar_macro_anual_cdi_igual_selic_menos_spread() -> None:
    """CDI anual = Selic esperada - 0,1pp (config), com piso em zero."""
    focus = {"selic": {"2026": 0.14, "2027": 0.12}, "ipca": {"2026": 0.05}}
    macro_anual = montar_macro_anual(focus, 0.1425, PARAMETROS_MACRO, 2026)

    assert macro_anual["ano1"]["cdi"] == pytest.approx(0.139)
    assert macro_anual["ano2"]["cdi"] == pytest.approx(0.119)
    assert macro_anual["ano8"]["selic"] == pytest.approx(0.09)
    assert macro_anual["ano8"]["cdi"] == pytest.approx(0.089)
    assert macro_anual["ano1"]["ano_calendario"] == 2026
    assert macro_anual["ano8"]["origem_selic"] == "convergencia_linear"


def test_montar_macro_anual_offline_ancora_selic_atual() -> None:
    """Sem Focus de Selic, a Selic atual ancora o ano1 e converge a meta."""
    macro_anual = montar_macro_anual({}, 0.1425, PARAMETROS_MACRO, 2026)
    assert macro_anual["ano1"]["selic"] == pytest.approx(0.1425)
    assert macro_anual["ano1"]["origem_selic"] == "focus"
    assert macro_anual["ano8"]["selic"] == pytest.approx(0.09)
    # IPCA sem nenhuma ancora cai direto na meta.
    assert macro_anual["ano3"]["ipca"] == pytest.approx(0.03)
    assert macro_anual["ano3"]["origem_ipca"] == "meta"


def test_acumular_12m() -> None:
    """Acumulado 12m = prod(1 + v/100) - 1 (valores em % a.m.)."""
    assert acumular_12m([1.0] * 12) == pytest.approx(1.01**12 - 1)
    assert acumular_12m([0.0] * 12) == pytest.approx(0.0)


def test_mesclar_preservando_mantem_persistido_quando_coleta_falha() -> None:
    """Campo None na coleta nova preserva o valor persistido (modo offline)."""
    novo = {"selic_atual": None, "cdi_atual": 0.1415, "data_coleta": "hoje"}
    persistido = {"selic_atual": 0.1425, "cdi_atual": 0.10}
    resultado = mesclar_preservando(novo, persistido, LOGGER)
    assert resultado["selic_atual"] == pytest.approx(0.1425)  # preservado
    assert resultado["cdi_atual"] == pytest.approx(0.1415)  # coleta nova vence


def test_focus_de_campos_legados() -> None:
    """Arquivo macro pre-9.0.3 reconstroi o focus_anuais dos campos 1a/2a."""
    dados = {
        "ipca_focus_1a": 0.042,
        "ipca_focus_2a": 0.037,
        "selic_focus_1a": 0.12,
        "selic_focus_2a": None,
    }
    focus = focus_de_campos_legados(dados, 2026)
    assert focus["ipca"] == {"2027": 0.042, "2028": 0.037}
    assert focus["selic"] == {"2027": 0.12}


def test_montar_focus_anuais_converte_percentual_exceto_cambio() -> None:
    """Medianas do Focus dividem por 100; cambio BRL/USD fica bruto."""
    dados = pd.DataFrame(
        [
            {
                "Indicador": "IPCA",
                "DataReferencia": "2026",
                "Mediana": 5.16,
                "Data": "2026-07-01",
            },
            {
                "Indicador": "PIB Total",
                "DataReferencia": "2026",
                "Mediana": 0.5,
                "Data": "2026-07-01",
            },
            {
                "Indicador": "Câmbio",
                "DataReferencia": "2026",
                "Mediana": 5.20,
                "Data": "2026-07-01",
            },
        ]
    )
    focus = montar_focus_anuais(dados, 2026, LOGGER, quantidade_anos=1)
    assert focus["ipca"]["2026"] == pytest.approx(0.0516)
    # PIB de 0,5% NAO pode virar 50% (bug da heuristica legada).
    assert focus["pib"]["2026"] == pytest.approx(0.005)
    assert focus["cambio"]["2026"] == pytest.approx(5.20)
