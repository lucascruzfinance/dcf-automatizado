"""Testes do projetor de DRE da Semana 2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.projetor_dre import projetar_dre


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_mapeamento_minimo(raiz: Path) -> None:
    """Cria o mapeamento minimo exigido pelo projetor."""
    campos = {
        "ano_projecao": {},
        "taxa_crescimento_receita": {},
        "receita_liquida": {},
        "margem_ebitda": {},
        "ebitda": {},
        "depreciacao_amortizacao": {},
        "ebit": {},
        "resultado_financeiro": {},
        "ebt": {},
        "ir_csll": {},
        "lucro_liquido": {},
    }
    salvar_json(raiz / "config" / "mapeamento_cvm.json", {"campos": campos})


def criar_base_historica_minima(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria dados brutos CVM minimos para a receita liquida do Ano 0."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {
            "ticker": ticker,
            "setor": "varejo",
            "tipo": "nao_financeira",
        },
    )
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_dre.json",
        [
            {
                "ano_arquivo": 2025,
                "DT_FIM_EXERC": "2025-12-31",
                "ORDEM_EXERC": "ÚLTIMO",
                "CD_CONTA": "3.01",
                "nome_padronizado": "receita_liquida",
                "valor_padronizado": 1000.0,
            }
        ],
    )


def criar_premissas_minimas(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria premissas com oito taxas individuais de receita e margem."""
    premissas = {
        "ticker": ticker,
        "setor": "varejo",
        "tipo": "nao_financeira",
    }
    for ano in range(1, 9):
        premissas[f"crescimento_receita_ano{ano}"] = ano / 100
        premissas[f"margem_ebitda_ano{ano}"] = (9 + ano) / 100
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        premissas,
    )


def test_projetar_dre_usa_taxas_anuais_individuais(tmp_path: Path) -> None:
    """Valida que cada ano usa seu campo individual de crescimento."""
    criar_mapeamento_minimo(tmp_path)
    criar_base_historica_minima(tmp_path)
    criar_premissas_minimas(tmp_path)

    resultado = projetar_dre("TEST3", raiz_projeto=tmp_path)
    dre = resultado["dre"]

    assert dre["ano1"]["taxa_crescimento_receita"] == pytest.approx(0.01)
    assert dre["ano8"]["taxa_crescimento_receita"] == pytest.approx(0.08)
    assert dre["ano1"]["receita_liquida"] == pytest.approx(1010.0)
    assert dre["ano2"]["receita_liquida"] == pytest.approx(1010.0 * 1.02)
    assert dre["ano1"]["ir_csll"] == pytest.approx(-(101.0 * 0.34))
    assert (tmp_path / "data" / "processed" / "TEST3_projecao.json").exists()


def test_projetar_dre_falha_sem_premissa_individual(tmp_path: Path) -> None:
    """Garante erro claro quando um dos 16 campos obrigatorios faltar."""
    criar_mapeamento_minimo(tmp_path)
    criar_base_historica_minima(tmp_path)
    criar_premissas_minimas(tmp_path)
    caminho = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas = json.loads(caminho.read_text(encoding="utf-8"))
    premissas["margem_ebitda_ano8"] = None
    salvar_json(caminho, premissas)

    with pytest.raises(ValueError, match="margem_ebitda_ano8"):
        projetar_dre("TEST3", raiz_projeto=tmp_path)
