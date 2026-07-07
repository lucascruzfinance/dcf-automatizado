"""Testes do schedule de capital de giro da Semana 2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.schedule_wk import projetar_wk


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_mapeamento_wk_minimo(raiz: Path) -> None:
    """Cria o mapeamento minimo exigido pelo schedule WK."""
    campos = {
        "ano_projecao": {},
        "contas_receber": {},
        "estoques": {},
        "fornecedores": {},
        "nwc": {},
        "delta_nwc": {},
        "modo_capital_giro": {},
    }
    salvar_json(raiz / "config" / "mapeamento_cvm.json", {"campos": campos})


def criar_premissas_wk(
    raiz: Path,
    ticker: str = "TEST3",
    setor: str = "varejo",
    modo_capital_giro: str | None = None,
    teto_delta_nwc_receita: float | None = None,
) -> None:
    """Cria premissas com prazos medios em dias."""
    premissas = {
        "ticker": ticker,
        "setor": setor,
        "tipo": "nao_financeira",
        "dso": 36.5,
        "dio": 73.0,
        "dpo": 36.5,
    }
    if modo_capital_giro is not None:
        premissas["modo_capital_giro"] = modo_capital_giro
    if teto_delta_nwc_receita is not None:
        premissas["teto_delta_nwc_receita"] = teto_delta_nwc_receita
    salvar_json(raiz / "data" / "premissas" / f"{ticker}_premissas.json", premissas)


def criar_projecao_dre(
    raiz: Path,
    ticker: str = "TEST3",
    receitas: list[float] | None = None,
) -> None:
    """Cria DRE projetada minima com oito anos de receita."""
    dre = {}
    for ano in range(1, 9):
        receita = receitas[ano - 1] if receitas is not None else 900.0 + (ano * 100.0)
        dre[f"ano{ano}"] = {
            "ano_projecao": f"ano{ano}",
            "receita_liquida": receita,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "ano0": {"receita_liquida": 1000.0},
            "dre": dre,
        },
    )


def criar_meta_wk(
    raiz: Path,
    ticker: str = "TEST3",
    setor: str = "varejo",
) -> None:
    """Cria metadados minimos para detectar o modo de giro."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {"ticker": ticker, "setor": setor, "tipo": "nao_financeira"},
    )


def criar_base_historica_wk(
    raiz: Path,
    ticker: str = "TEST3",
    contas_receber: float = 100.0,
    estoques: float = 80.0,
    fornecedores: float = -60.0,
    receita_ano0: float = 1000.0,
    cpv: float = -400.0,
) -> None:
    """Cria saldos historicos CVM minimos para Ano 0 e indice CPV/receita."""
    base = {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
    }
    bp = [
        {
            **base,
            "CD_CONTA": "1.01.03",
            "nome_padronizado": "contas_receber",
            "valor_padronizado": contas_receber,
        },
        {
            **base,
            "CD_CONTA": "1.01.04",
            "nome_padronizado": "estoques",
            "valor_padronizado": estoques,
        },
        {
            **base,
            "CD_CONTA": "2.01.02",
            "nome_padronizado": "fornecedores",
            "valor_padronizado": fornecedores,
        },
    ]
    dre = [
        {
            **base,
            "CD_CONTA": "3.01",
            "nome_padronizado": "receita_liquida",
            "valor_padronizado": receita_ano0,
        },
        {
            **base,
            "CD_CONTA": "3.02",
            "nome_padronizado": "cpv_cmv",
            "valor_padronizado": cpv,
        },
    ]
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json", bp)
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_dre.json", dre)


def test_modo_dias_ciclo_curto_preservado(tmp_path: Path) -> None:
    """Valida formulas de saldos em dias e Delta NWC como consumo."""
    criar_mapeamento_wk_minimo(tmp_path)
    criar_premissas_wk(tmp_path)
    criar_meta_wk(tmp_path)
    criar_projecao_dre(tmp_path)
    criar_base_historica_wk(tmp_path)

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    wk = resultado["wk"]

    assert resultado["ano0_wk"]["nwc"] == pytest.approx(120.0)
    assert wk["ano1"]["contas_receber"] == pytest.approx(100.0)
    assert wk["ano1"]["estoques"] == pytest.approx(80.0)
    assert wk["ano1"]["fornecedores"] == pytest.approx(-40.0)
    assert wk["ano1"]["nwc"] == pytest.approx(140.0)
    assert wk["ano1"]["delta_nwc"] == pytest.approx(20.0)
    assert wk["ano1"]["modo_capital_giro"] == "dias"
    assert wk["ano2"]["delta_nwc"] == pytest.approx(14.0)

    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    persistido = json.loads(caminho.read_text(encoding="utf-8"))
    assert persistido["ano0"]["wk"]["nwc"] == pytest.approx(120.0)
    assert persistido["wk"]["ano1"]["delta_nwc"] == pytest.approx(20.0)


def test_modo_ancorado_construtora_sem_salto_de_giro(tmp_path: Path) -> None:
    """Construtora deve escalar NWC por receita, sem liberar todo o ano0."""
    criar_mapeamento_wk_minimo(tmp_path)
    criar_premissas_wk(tmp_path, setor="construcao")
    criar_meta_wk(tmp_path, setor="construcao")
    criar_projecao_dre(tmp_path, receitas=[1100.0] + [1200.0] * 7)
    criar_base_historica_wk(
        tmp_path,
        contas_receber=3000.0,
        estoques=1000.0,
        fornecedores=-870.0,
    )

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    wk = resultado["wk"]

    nwc_ano0 = 3130.0
    nwc_ano1 = nwc_ano0 / 1000.0 * 1100.0
    assert resultado["modo_capital_giro"] == "percentual_receita"
    assert wk["ano1"]["modo_capital_giro"] == "percentual_receita"
    assert wk["ano1"]["nwc"] == pytest.approx(nwc_ano1)
    assert wk["ano1"]["delta_nwc"] == pytest.approx(nwc_ano1 - nwc_ano0)
    assert wk["ano1"]["delta_nwc"] > 0


def test_salvaguarda_trunca_delta_nwc_ano1(tmp_path: Path) -> None:
    """Delta NWC do ano1 deve respeitar o teto sobre receita."""
    criar_mapeamento_wk_minimo(tmp_path)
    criar_premissas_wk(tmp_path, setor="construcao")
    criar_meta_wk(tmp_path, setor="construcao")
    criar_projecao_dre(tmp_path, receitas=[100.0] + [120.0] * 7)
    criar_base_historica_wk(
        tmp_path,
        contas_receber=4000.0,
        estoques=1500.0,
        fornecedores=-500.0,
    )

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    delta_ano1 = float(resultado["wk"]["ano1"]["delta_nwc"])
    limite = 0.50 * 100.0

    assert abs(delta_ano1) <= limite
    assert delta_ano1 == pytest.approx(-limite)
    assert resultado["wk"]["ano1"]["nwc"] == pytest.approx(4950.0)
