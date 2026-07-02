"""Testes do calculador de Valor Terminal (perpetuidade de Gordon)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_vt import calcular_valor_terminal


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_premissas_vt(
    raiz: Path,
    ticker: str = "TEST3",
    g: float = 0.03,
    taxa_reinvestimento: float = 0.20,
) -> None:
    """Cria premissas minimas com g e taxa de reinvestimento."""
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        {
            "ticker": ticker,
            "crescimento_perpetuidade": g,
            "taxa_reinvestimento_perpetuidade": taxa_reinvestimento,
        },
    )


def criar_projecao_vt(
    raiz: Path,
    ticker: str = "TEST3",
    wacc: float = 0.12,
    fcff_ano8: float = 120.0,
    nopat_ano8: float = 100.0,
    ebitda_ano8: float = 150.0,
    fcff_demais: float = 100.0,
) -> None:
    """Cria projecao integrada minima com blocos dre, fcff e wacc."""
    dre = {}
    fcff = {}
    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        dre[chave_ano] = {"ano_projecao": chave_ano, "ebitda": ebitda_ano8}
        fcff[chave_ano] = {
            "ano_projecao": chave_ano,
            "fcff": fcff_ano8 if ano == 8 else fcff_demais,
            "nopat": nopat_ano8,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "dre": dre,
            "fcff": fcff,
            "wacc": {"wacc": wacc},
        },
    )


def test_g_maior_ou_igual_wacc_levanta_erro(tmp_path: Path) -> None:
    """g >= WACC deve travar o calculo (modelo Gordon explode)."""
    criar_premissas_vt(tmp_path, g=0.12)
    criar_projecao_vt(tmp_path, wacc=0.12)

    with pytest.raises(ValueError, match="Gordon explode"):
        calcular_valor_terminal("TEST3", raiz_projeto=tmp_path)


def test_g_acima_de_5pct_emite_warning(tmp_path: Path) -> None:
    """g > 5% deve emitir alerta amarelo sem travar."""
    criar_premissas_vt(tmp_path, g=0.06)
    criar_projecao_vt(tmp_path, wacc=0.12)

    with pytest.warns(UserWarning, match="acima de 5%"):
        resultado = calcular_valor_terminal("TEST3", raiz_projeto=tmp_path)

    assert resultado["vt_bruto"] > 0


def test_fcff8_negativo_usa_nopat_normalizado(tmp_path: Path) -> None:
    """FCFF_8 negativo deve usar NOPAT_8 como base do VT."""
    criar_premissas_vt(tmp_path, g=0.03)
    criar_projecao_vt(tmp_path, fcff_ano8=-50.0, nopat_ano8=100.0)

    resultado = calcular_valor_terminal("TEST3", raiz_projeto=tmp_path)

    assert resultado["base_vt"] == "nopat_normalizado"
    assert resultado["base_utilizada"] == pytest.approx(100.0)


def test_vp_vt_positivo_para_inputs_validos(tmp_path: Path) -> None:
    """VP(VT) deve ser positivo para inputs razoaveis."""
    criar_premissas_vt(tmp_path, g=0.03)
    criar_projecao_vt(tmp_path, wacc=0.12)

    resultado = calcular_valor_terminal("TEST3", raiz_projeto=tmp_path)

    assert resultado["vp_vt"] > 0


def test_pct_ev_perpetuidade_entre_0_e_1(tmp_path: Path) -> None:
    """% do EV na perpetuidade deve ser uma fracao valida."""
    criar_premissas_vt(tmp_path, g=0.03)
    criar_projecao_vt(tmp_path, wacc=0.12)

    resultado = calcular_valor_terminal("TEST3", raiz_projeto=tmp_path)

    assert 0.0 < resultado["pct_ev_perpetuidade"] < 1.0


def test_multiplo_saida_em_faixa_de_sanidade(tmp_path: Path) -> None:
    """Multiplo de saida implicito deve ficar entre 3x e 25x."""
    criar_premissas_vt(tmp_path, g=0.03)
    criar_projecao_vt(
        tmp_path,
        wacc=0.12,
        fcff_ano8=120.0,
        ebitda_ano8=150.0,
    )

    resultado = calcular_valor_terminal("TEST3", raiz_projeto=tmp_path)

    assert 3.0 <= resultado["multiplo_saida_implicito"] <= 25.0


def test_taxa_reinvestimento_fora_do_intervalo_levanta_erro(tmp_path: Path) -> None:
    """Taxa de reinvestimento fora de [0, 1] deve travar o calculo."""
    criar_premissas_vt(tmp_path, g=0.03, taxa_reinvestimento=1.5)
    criar_projecao_vt(tmp_path, wacc=0.12)

    with pytest.raises(ValueError, match="reinvestimento"):
        calcular_valor_terminal("TEST3", raiz_projeto=tmp_path)
