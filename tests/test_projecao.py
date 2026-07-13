"""Testes integrados da Semana 2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.projetor_dre import projetar_dre
from src.projecao.schedule_divida import projetar_divida
from src.projecao.schedule_ppe import projetar_ppe
from src.projecao.schedule_wk import projetar_wk


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_mapeamento_integrado_minimo(raiz: Path) -> None:
    """Cria o mapeamento minimo exigido por DRE e WK."""
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
        "contas_receber": {},
        "estoques": {},
        "fornecedores": {},
        "nwc": {},
        "delta_nwc": {},
        "modo_capital_giro": {},
    }
    salvar_json(raiz / "config" / "mapeamento_cvm.json", {"campos": campos})


def criar_parametros_integrados(raiz: Path) -> None:
    """Cria parametros globais usados por PP&E e divida."""
    salvar_json(
        raiz / "config" / "parametros.json",
        {
            "vida_util_ppe_anos": 10,
            "payout_dividendos": 0,
        },
    )


def criar_premissas_integradas(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria premissas completas com oito taxas individuais diferentes."""
    premissas = {
        "ticker": ticker,
        "setor": "varejo",
        "tipo": "nao_financeira",
        "dso": 30,
        "dio": 45,
        "dpo": 35,
        "custo_divida_kd": 0.10,
    }
    for ano in range(1, 9):
        premissas[f"crescimento_receita_ano{ano}"] = ano / 100
        premissas[f"margem_ebitda_ano{ano}"] = (12 + ano) / 100
        premissas[f"capex_receita_ano{ano}"] = -0.02

    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        premissas,
    )


def criar_base_historica_integrada(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria dados CVM minimos para rodar a cadeia DRE, WK, PP&E e divida."""
    base = {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ULTIMO",
    }
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
                **base,
                "CD_CONTA": "3.01",
                "nome_padronizado": "receita_liquida",
                "valor_padronizado": 1000.0,
            },
            {
                **base,
                "CD_CONTA": "3.02",
                "nome_padronizado": "cpv_cmv",
                "valor_padronizado": -600.0,
            },
        ],
    )
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json",
        [
            {
                # Ativo total REAL do Ano 0: ancora os residuais
                # outros_ativos/outros_passivos do balanco v2 (PL 1000 +
                # fornecedores 70 + divida 400 = 1470).
                **base,
                "CD_CONTA": "1",
                "nome_padronizado": "ativo_total",
                "valor_padronizado": 1470.0,
            },
            {
                **base,
                "CD_CONTA": "1.01.01",
                "nome_padronizado": "caixa_equivalentes",
                "valor_padronizado": 100.0,
            },
            {
                **base,
                "CD_CONTA": "1.01.02",
                "nome_padronizado": "aplicacoes_financeiras",
                "valor_padronizado": 50.0,
            },
            {
                **base,
                "CD_CONTA": "1.01.03",
                "nome_padronizado": "contas_receber",
                "valor_padronizado": 90.0,
            },
            {
                **base,
                "CD_CONTA": "1.01.04",
                "nome_padronizado": "estoques",
                "valor_padronizado": 80.0,
            },
            {
                **base,
                "CD_CONTA": "1.02.03",
                "nome_padronizado": "imobilizado",
                "valor_padronizado": 500.0,
            },
            {
                **base,
                "CD_CONTA": "2.01.02",
                "nome_padronizado": "fornecedores",
                "valor_padronizado": -70.0,
            },
            {
                **base,
                "CD_CONTA": "2.01.04",
                "nome_padronizado": "divida_curto_prazo",
                "valor_padronizado": -120.0,
            },
            {
                **base,
                "CD_CONTA": "2.02.01",
                "nome_padronizado": "divida_longo_prazo",
                "valor_padronizado": -280.0,
            },
            {
                **base,
                "CD_CONTA": "2.03",
                "nome_padronizado": "patrimonio_liquido",
                "valor_padronizado": 1000.0,
            },
        ],
    )


def criar_ambiente_projecao_integrada(tmp_path: Path) -> None:
    """Cria todos os arquivos temporarios para o pipeline integrado."""
    criar_mapeamento_integrado_minimo(tmp_path)
    criar_parametros_integrados(tmp_path)
    criar_premissas_integradas(tmp_path)
    criar_base_historica_integrada(tmp_path)


def test_pipeline_integrado_semana2_fecha_balanco_e_preserva_taxas(
    tmp_path: Path,
) -> None:
    """Valida DRE -> WK -> PP&E -> divida sem dados reais do projeto."""
    criar_ambiente_projecao_integrada(tmp_path)

    projetar_dre("TEST3", raiz_projeto=tmp_path)
    projetar_wk("TEST3", raiz_projeto=tmp_path)
    projetar_ppe("TEST3", raiz_projeto=tmp_path)
    resultado = projetar_divida("TEST3", raiz_projeto=tmp_path)

    dre = resultado["dre"]
    balanco = resultado["balanco"]
    taxas = [float(dre[f"ano{ano}"]["taxa_crescimento_receita"]) for ano in range(1, 9)]
    assert len(set(taxas)) == 8
    assert taxas == pytest.approx([ano / 100 for ano in range(1, 9)])

    patrimonio_liquido_anterior = 1000.0
    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        assert balanco[chave_ano]["diferenca_balanco"] == pytest.approx(0.0)

        lucro_liquido = float(dre[chave_ano]["lucro_liquido"])
        patrimonio_liquido = float(balanco[chave_ano]["patrimonio_liquido"])
        assert lucro_liquido == pytest.approx(
            patrimonio_liquido - patrimonio_liquido_anterior
        )
        patrimonio_liquido_anterior = patrimonio_liquido
