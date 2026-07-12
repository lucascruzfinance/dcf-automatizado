"""Testes da fundacao e coleta inicial da Semana 0 (contrato v2.0)."""

from __future__ import annotations

import json
from pathlib import Path

from src.coleta.coletor_cvm import (
    EmpresaCvm,
    detectar_tipo_empresa,
    normalizar_sinal,
    salvar_metadados,
)

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


def empresa_de_teste() -> EmpresaCvm:
    """Empresa sintetica no contrato de classificacao da v2.0."""
    return EmpresaCvm(
        ticker="TESTE",
        codigo_cvm=99999,
        cnpj="00.000.000/0001-00",
        razao_social="EMPRESA TESTE SA",
        setor="Bancos",
        tipo="financeira",
        subtipo="banco",
        metodo_valuation="FCFE",
        taxa_desconto="Ke",
    )


def test_meta_json_segue_contrato_v2(tmp_path: Path) -> None:
    """O _meta.json expoe tipo, subtipo, metodo, taxa, consolidado e score."""
    salvar_metadados(empresa_de_teste(), tmp_path, consolidado=True)
    caminho = tmp_path / "data" / "raw" / "cvm" / "TESTE_meta.json"
    meta = json.loads(caminho.read_text(encoding="utf-8"))

    obrigatorios = {
        "ticker",
        "codigo_cvm",
        "cnpj",
        "razao_social",
        "setor",
        "tipo",
        "subtipo",
        "metodo_valuation",
        "taxa_desconto",
        "consolidado",
        "score_confiabilidade",
    }
    assert obrigatorios.issubset(meta)
    assert meta["tipo"] == "financeira"
    assert meta["subtipo"] == "banco"
    assert meta["metodo_valuation"] == "FCFE"
    assert meta["taxa_desconto"] == "Ke"
    assert meta["consolidado"] is True
    assert meta["score_confiabilidade"] is None


def test_salvar_metadados_preserva_score_e_consolidado(tmp_path: Path) -> None:
    """Recoletar sem score novo nao apaga o score gravado pelo relatorio."""
    empresa = empresa_de_teste()
    salvar_metadados(empresa, tmp_path, consolidado=True, score_confiabilidade=88)
    # Nova coleta sem score (o relatorio ainda nao rodou de novo).
    salvar_metadados(empresa, tmp_path)

    caminho = tmp_path / "data" / "raw" / "cvm" / "TESTE_meta.json"
    meta = json.loads(caminho.read_text(encoding="utf-8"))
    assert meta["score_confiabilidade"] == 88
    assert meta["consolidado"] is True
