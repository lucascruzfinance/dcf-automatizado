"""Testes do schedule de divida e fechamento do balanco."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.schedule_divida import projetar_divida


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_parametros(raiz: Path, payout: float = 0.0) -> None:
    """Cria parametros globais minimos para divida e balanco."""
    salvar_json(
        raiz / "config" / "parametros.json",
        {"payout_dividendos": payout},
    )


def criar_premissas(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria premissas minimas de custo da divida."""
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        {
            "ticker": ticker,
            "setor": "varejo",
            "tipo": "nao_financeira",
            "custo_divida_kd": 0.10,
        },
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


def criar_base_historica_bp(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria BP historico minimo para divida, caixa, aplicacoes e PL."""
    base = {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ULTIMO",
    }
    registros = [
        {
            **base,
            "CD_CONTA": "1.01.01",
            "nome_padronizado": "caixa_equivalentes",
            "valor_padronizado": 50.0,
        },
        {
            **base,
            "CD_CONTA": "1.01.02",
            "nome_padronizado": "aplicacoes_financeiras",
            "valor_padronizado": 20.0,
        },
        {
            **base,
            "CD_CONTA": "2.01.04",
            "nome_padronizado": "divida_curto_prazo",
            "valor_padronizado": -100.0,
        },
        {
            **base,
            "CD_CONTA": "2.02.01",
            "nome_padronizado": "divida_longo_prazo",
            "valor_padronizado": -300.0,
        },
        {
            **base,
            "CD_CONTA": "2.03",
            "nome_padronizado": "patrimonio_liquido",
            "valor_padronizado": 1000.0,
        },
    ]
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json", registros)


def criar_projecao_existente(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria DRE, WK e PP&E projetados minimos."""
    dre = {}
    wk = {}
    ppe = {}
    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        dre[chave_ano] = {
            "ano_projecao": chave_ano,
            "receita_liquida": 1000.0,
            "ebit": 100.0,
            "resultado_financeiro": 0.0,
            "ebt": 100.0,
            "ir_csll": -34.0,
            "lucro_liquido": 66.0,
        }
        wk[chave_ano] = {
            "ano_projecao": chave_ano,
            "contas_receber": 100.0,
            "estoques": 50.0,
            "fornecedores": -40.0,
            "delta_nwc": 5.0,
        }
        ppe[chave_ano] = {
            "ano_projecao": chave_ano,
            "capex": -20.0,
            "depreciacao_amortizacao": 10.0,
            "imobilizado": 200.0,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "ano0": {"receita_liquida": 900.0},
            "dre": dre,
            "wk": wk,
            "ppe": ppe,
        },
    )


def criar_ambiente_divida(tmp_path: Path) -> None:
    """Cria todos os arquivos minimos usados pelos testes."""
    criar_parametros(tmp_path)
    criar_premissas(tmp_path)
    criar_metadados(tmp_path)
    criar_base_historica_bp(tmp_path)
    criar_projecao_existente(tmp_path)


def test_projetar_divida_atualiza_dre_e_fecha_balanco(tmp_path: Path) -> None:
    """Valida juros, DRE, DFC e fechamento Ativo = Passivo + PL."""
    criar_ambiente_divida(tmp_path)

    resultado = projetar_divida("TEST3", raiz_projeto=tmp_path)
    divida = resultado["divida"]
    dre = resultado["dre"]
    balanco = resultado["balanco"]
    dfc = resultado["dfc"]

    assert divida["ano1"]["divida_bruta"] == pytest.approx(400.0)
    assert divida["ano1"]["divida_curto_prazo"] == pytest.approx(100.0)
    assert divida["ano1"]["divida_longo_prazo"] == pytest.approx(300.0)
    assert divida["ano1"]["juros"] == pytest.approx(40.0)
    assert divida["ano1"]["resultado_financeiro"] == pytest.approx(-40.0)
    assert divida["ano1"]["delta_divida"] == pytest.approx(0.0)

    assert dre["ano1"]["resultado_financeiro"] == pytest.approx(-40.0)
    assert dre["ano1"]["ebt"] == pytest.approx(60.0)
    assert dre["ano1"]["ir_csll"] == pytest.approx(-20.4)
    assert dre["ano1"]["lucro_liquido"] == pytest.approx(39.6)

    assert balanco["ano1"]["fornecedores"] == pytest.approx(40.0)
    assert balanco["ano1"]["patrimonio_liquido"] == pytest.approx(1039.6)
    assert balanco["ano1"]["ativo_total"] == pytest.approx(
        balanco["ano1"]["passivo_patrimonio_liquido"]
    )
    assert balanco["ano1"]["diferenca_balanco"] == pytest.approx(0.0)

    assert dfc["ano1"]["fluxo_caixa_livre"] == pytest.approx(24.6)

    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    persistido = json.loads(caminho.read_text(encoding="utf-8"))
    assert persistido["divida"]["ano1"]["juros"] == pytest.approx(40.0)
    assert persistido["balanco"]["ano8"]["diferenca_balanco"] == pytest.approx(0.0)
    assert persistido["dfc"]["ano1"]["fluxo_caixa_livre"] == pytest.approx(24.6)
