"""Testes do Football Field v2: comps reais no lugar dos placeholders."""

from __future__ import annotations

from src.visualizacao.football_field import montar_metodologias


def comparaveis_sinteticos() -> dict:
    """Bloco de comparaveis persistido (contrato da Onda 3)."""
    return {
        "ticker": "TEST3",
        "subtipo": "varejo",
        "peers_validos": ["AAAA3", "BBBB3", "CCCC3"],
        "multiplos_principais": ["ev_ebitda", "p_l"],
        "estatisticas": {
            "ev_ebitda": {"q1": 5.0, "mediana": 6.0, "q3": 7.0, "n": 3},
            "p_l": {"q1": 8.0, "mediana": 9.0, "q3": 10.0, "n": 3},
        },
        "precos_implicitos": {
            "ev_ebitda": {"q1": 11.0, "mediana": 13.0, "q3": 15.0},
            "p_l": {"q1": 9.0, "mediana": 10.0, "q3": 12.0},
        },
        "alvo": {"preco_atual": 10.0},
    }


def test_barras_de_comps_vem_do_comparaveis_json() -> None:
    """As faixas de comps usam Q1-Q3 reais dos peers, nao placeholders."""
    metodologias = montar_metodologias(
        conteudo=None,
        mercado={"preco_minimo_52s": 7.0, "preco_maximo_52s": 14.0},
        parametros={},
        comparaveis=comparaveis_sinteticos(),
    )
    rotulos = [item["rotulo"] for item in metodologias]

    assert "Comps EV/EBITDA" in rotulos
    assert "Comps P/L" in rotulos
    assert "Faixa 52 semanas" in rotulos
    # Placeholders da v1 eliminados (nao existe mais barra com asterisco).
    assert not any("*" in rotulo for rotulo in rotulos)

    comps_ebitda = next(m for m in metodologias if m["rotulo"] == "Comps EV/EBITDA")
    assert comps_ebitda["minimo"] == 11.0
    assert comps_ebitda["maximo"] == 15.0
    assert comps_ebitda["marcador"] == 13.0  # mediana dos peers reais
    assert "peers reais" in comps_ebitda["observacao"]


def test_sem_valuation_dcf_renderiza_field_parcial() -> None:
    """Ticker sem DCF (ex.: banco antes das premissas) nao gera barras DCF."""
    metodologias = montar_metodologias(
        conteudo=None,
        mercado={},
        parametros={},
        comparaveis=comparaveis_sinteticos(),
    )
    rotulos = [item["rotulo"] for item in metodologias]
    assert all(not rotulo.startswith("DCF") for rotulo in rotulos)
    assert len(rotulos) == 2  # apenas os dois comps


def test_dcf_bear_base_bull_preferem_motor_de_cenarios() -> None:
    """Com o bloco cenarios persistido, as barras DCF vem do pipeline."""
    conteudo = {
        "ev_equity": {"target_price": 10.0, "preco_atual": 9.0},
        "cenarios": {
            "bear": {"target_price": 8.0},
            "base": {"target_price": 10.0},
            "bull": {"target_price": 12.5},
        },
        "valor_terminal": {},
    }
    metodologias = montar_metodologias(
        conteudo=conteudo,
        mercado={},
        parametros={},
        comparaveis=None,
    )
    por_rotulo = {item["rotulo"]: item for item in metodologias}

    assert por_rotulo["DCF Bear"]["marcador"] == 8.0
    assert por_rotulo["DCF Bull"]["marcador"] == 12.5
    assert "motor_cenarios" in por_rotulo["DCF Bear"]["observacao"]
