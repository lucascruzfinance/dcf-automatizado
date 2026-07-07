"""Testes da fundacao e coleta inicial da Semana 0."""

from __future__ import annotations

import json
from pathlib import Path

from src.coleta.coletor_cvm import detectar_tipo_empresa, normalizar_sinal

RAIZ_PROJETO = Path(__file__).resolve().parents[1]


def carregar_json(caminho_relativo: str) -> dict:
    """Carrega um JSON do projeto para validacoes estruturais."""
    caminho = RAIZ_PROJETO / caminho_relativo
    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def test_mapeamento_cvm_tem_contas_principais() -> None:
    """Valida a cobertura minima exigida para o mapeamento da CVM."""
    mapeamento = carregar_json("config/mapeamento_cvm.json")
    campos = set(mapeamento["campos"])
    obrigatorios = {
        "receita_liquida",
        "cpv_cmv",
        "ebit",
        "lucro_liquido",
        "caixa_equivalentes",
        "divida_curto_prazo",
        "divida_longo_prazo",
    }
    assert obrigatorios.issubset(campos)


def test_template_naofinanceiro_tem_oito_anos_individuais() -> None:
    """Garante que premissas nao usam taxa unica replicada para 8 anos."""
    template = carregar_json("data/premissas/template_naofinanceiras.json")
    for prefixo in (
        "crescimento_receita",
        "margem_ebitda",
        "capex_receita",
    ):
        campos = [f"{prefixo}_ano{ano}" for ano in range(1, 9)]
        assert all(campo in template for campo in campos)


def test_detectar_tipo_empresa_classifica_financeiras_e_naofinanceiras() -> None:
    """Valida a classificacao automatica de trilha por setor CVM."""
    assert detectar_tipo_empresa("Construção Civil") == "nao_financeira"
    assert detectar_tipo_empresa("Comércio Varejista") == "nao_financeira"
    assert detectar_tipo_empresa("Banco / Financeiro") == "financeira"


def test_normalizar_sinal_respeita_convencao_financeira() -> None:
    """Valida receitas positivas e despesas/saidas de caixa negativas."""
    assert normalizar_sinal(-100, "positivo") == 100
    assert normalizar_sinal(100, "negativo") == -100
    assert normalizar_sinal(-50, "positivo_ou_negativo") == -50
