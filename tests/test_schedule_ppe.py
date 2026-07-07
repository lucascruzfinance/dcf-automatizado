"""Testes do schedule PP&E da Semana 2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.schedule_ppe import projetar_ppe


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_parametros_ppe(raiz: Path, vida_util: float = 5.0) -> None:
    """Cria parametros globais minimos para o schedule PP&E."""
    salvar_json(
        raiz / "config" / "parametros.json",
        {"vida_util_ppe_anos": vida_util},
    )


def criar_premissas_ppe(
    raiz: Path,
    ticker: str = "TEST3",
    capex_ano1: float = 0.10,
    capex_ano2: float = 0.20,
) -> None:
    """Cria premissas com oito taxas individuais de CAPEX/Receita."""
    premissas = {
        "ticker": ticker,
        "setor": "varejo",
        "tipo": "nao_financeira",
    }
    for ano in range(1, 9):
        premissas[f"capex_receita_ano{ano}"] = 0.0
    premissas["capex_receita_ano1"] = capex_ano1
    premissas["capex_receita_ano2"] = capex_ano2
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        premissas,
    )


def criar_metadados(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria metadados minimos para a regra de IR/CSLL."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {
            "ticker": ticker,
            "setor": "varejo",
            "tipo": "nao_financeira",
        },
    )


def criar_projecao_dre(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria DRE projetada minima com receita, EBITDA e resultado financeiro."""
    dre = {}
    for ano in range(1, 9):
        dre[f"ano{ano}"] = {
            "ano_projecao": f"ano{ano}",
            "receita_liquida": 1000.0,
            "ebitda": 300.0,
            "depreciacao_amortizacao": 0.0,
            "ebit": 300.0,
            "resultado_financeiro": -10.0,
            "ebt": 290.0,
            "ir_csll": -98.6,
            "lucro_liquido": 191.4,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "ano0": {"receita_liquida": 900.0},
            "dre": dre,
        },
    )


def criar_base_historica_ppe(
    raiz: Path,
    ticker: str = "TEST3",
    imobilizado: float = 500.0,
) -> None:
    """Cria saldo historico CVM minimo para o PP&E Ano 0."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json",
        [
            {
                "ano_arquivo": 2025,
                "DT_FIM_EXERC": "2025-12-31",
                "ORDEM_EXERC": "ÚLTIMO",
                "CD_CONTA": "1.02.03",
                "nome_padronizado": "imobilizado",
                "valor_padronizado": imobilizado,
            }
        ],
    )


def criar_ambiente_ppe(tmp_path: Path) -> None:
    """Cria fixtures minimas comuns aos testes do schedule PP&E."""
    criar_parametros_ppe(tmp_path)
    criar_premissas_ppe(tmp_path)
    criar_metadados(tmp_path)
    criar_projecao_dre(tmp_path)
    criar_base_historica_ppe(tmp_path)


def test_projetar_ppe_atualiza_dre_e_persiste(tmp_path: Path) -> None:
    """Valida a cascata PP&E e a devolucao da D&A para a DRE."""
    criar_ambiente_ppe(tmp_path)

    resultado = projetar_ppe("TEST3", raiz_projeto=tmp_path)
    ppe = resultado["ppe"]
    dre = resultado["dre"]

    assert ppe["ano1"]["capex_receita"] == pytest.approx(0.10)
    assert ppe["ano2"]["capex_receita"] == pytest.approx(0.20)
    assert ppe["ano1"]["capex"] == pytest.approx(100.0)
    assert ppe["ano2"]["capex"] == pytest.approx(200.0)
    assert ppe["ano1"]["depreciacao_amortizacao"] == pytest.approx(100.0)
    assert ppe["ano1"]["imobilizado"] == pytest.approx(500.0)
    assert ppe["ano2"]["imobilizado"] == pytest.approx(600.0)

    assert dre["ano1"]["depreciacao_amortizacao"] == pytest.approx(
        ppe["ano1"]["depreciacao_amortizacao"]
    )
    assert dre["ano1"]["ebit"] == pytest.approx(200.0)
    assert dre["ano1"]["ebt"] == pytest.approx(190.0)
    assert dre["ano1"]["ir_csll"] == pytest.approx(-64.6)
    assert dre["ano1"]["lucro_liquido"] == pytest.approx(125.4)

    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    persistido = json.loads(caminho.read_text(encoding="utf-8"))
    assert persistido["ano0"]["ppe"]["imobilizado"] == pytest.approx(500.0)
    assert persistido["ppe"]["ano1"]["capex"] == pytest.approx(100.0)
    assert persistido["dre"]["ano1"]["depreciacao_amortizacao"] == pytest.approx(100.0)


def test_projetar_ppe_falha_sem_premissa_individual(tmp_path: Path) -> None:
    """Garante erro claro quando uma das oito premissas de CAPEX faltar."""
    criar_ambiente_ppe(tmp_path)
    caminho = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas = json.loads(caminho.read_text(encoding="utf-8"))
    premissas.pop("capex_receita_ano8")
    salvar_json(caminho, premissas)

    with pytest.raises(ValueError, match="capex_receita_ano8"):
        projetar_ppe("TEST3", raiz_projeto=tmp_path)


def test_projetar_ppe_nao_deixa_imobilizado_negativo(tmp_path: Path) -> None:
    """Valida que o ativo para de depreciar quando o saldo chega a zero."""
    criar_ambiente_ppe(tmp_path)
    criar_premissas_ppe(tmp_path, capex_ano1=-1.0, capex_ano2=0.0)
    criar_base_historica_ppe(tmp_path, imobilizado=100.0)

    resultado = projetar_ppe("TEST3", raiz_projeto=tmp_path)
    ppe = resultado["ppe"]

    assert ppe["ano1"]["capex"] == pytest.approx(-1000.0)
    assert ppe["ano1"]["depreciacao_amortizacao"] == pytest.approx(0.0)
    assert ppe["ano1"]["imobilizado"] == pytest.approx(0.0)
    assert ppe["ano2"]["depreciacao_amortizacao"] == pytest.approx(0.0)
    assert ppe["ano2"]["imobilizado"] == pytest.approx(0.0)
