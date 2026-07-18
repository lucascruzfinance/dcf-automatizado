"""Testes da cascata universal de mapeamento de contas da CVM (sem rede)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.coleta.mapeador_contas import (
    carregar_mapeamento,
    mapear_conta,
    mapear_demonstracao,
    normalizar_sinal,
)

MAPEAMENTO = carregar_mapeamento()


def test_match_por_codigo_exato_na_dre() -> None:
    """CD_CONTA 3.01 de nao-financeira mapeia para receita_liquida."""
    resultado = mapear_conta(
        "3.01",
        "Receita de Venda de Bens e/ou Serviços",
        "dre",
        "nao_financeira",
        MAPEAMENTO,
    )
    assert resultado is not None
    assert resultado["nome_padronizado"] == "receita_liquida"
    assert resultado["mapeado_por"] == "codigo"
    assert resultado["sinal_esperado"] == "positivo"


def test_mesmo_codigo_muda_de_significado_para_financeira() -> None:
    """O 3.01 de banco usa o bloco financeiro (plano de contas proprio)."""
    resultado = mapear_conta(
        "3.01",
        "Receitas da Intermediação Financeira",
        "dre",
        "financeira",
        MAPEAMENTO,
    )
    assert resultado is not None
    assert resultado["nome_padronizado"] == "receitas_intermediacao_financeira"
    assert resultado["mapeado_por"] == "codigo"


def test_nome_fallback_roda_antes_do_prefixo_no_dfc() -> None:
    """D&A dentro do FCO mapeia por nome, nao por prefixo do 6.01."""
    resultado = mapear_conta(
        "6.01.01.02",
        "Depreciação e Amortização",
        "dfc",
        "nao_financeira",
        MAPEAMENTO,
    )
    assert resultado is not None
    assert resultado["nome_padronizado"] == "depreciacao_amortizacao"
    assert resultado["mapeado_por"] == "nome"


def test_match_por_prefixo_hierarquico_no_bp() -> None:
    """Sub-conta desconhecida herda o nome do ancestral mais proximo."""
    resultado = mapear_conta(
        "2.02.01.09",
        "Debêntures Perpétuas",
        "bp_passivo",
        "nao_financeira",
        MAPEAMENTO,
    )
    assert resultado is not None
    assert resultado["nome_padronizado"] == "divida_longo_prazo"
    assert resultado["mapeado_por"] == "prefixo"


def test_prefixo_nao_expande_agregados_do_dfc() -> None:
    """Linhas de ajuste do FCO sem nome conhecido NAO viram fco por prefixo."""
    resultado = mapear_conta(
        "6.01.01.05",
        "Ajuste Contabil Especifico Desconhecido",
        "dfc",
        "nao_financeira",
        MAPEAMENTO,
    )
    assert resultado is None


def test_conta_desconhecida_devolve_none() -> None:
    """Conta fora do plano e dos padroes de nome nao e mapeada."""
    resultado = mapear_conta(
        "9.99",
        "Conta Completamente Desconhecida",
        "dre",
        "nao_financeira",
        MAPEAMENTO,
    )
    assert resultado is None


def test_mapear_demonstracao_completa_com_log(tmp_path: Path) -> None:
    """A cascata roda no DataFrame inteiro e loga contas nao mapeadas."""
    dados = pd.DataFrame(
        [
            {"CD_CONTA": "3.01", "DS_CONTA": "Receita", "VL_CONTA": 100.0},
            {"CD_CONTA": "3.02", "DS_CONTA": "Custo dos Bens", "VL_CONTA": 80.0},
            {"CD_CONTA": "9.99", "DS_CONTA": "Conta Marciana", "VL_CONTA": 1.0},
        ]
    )
    caminho_log = tmp_path / "logs" / "contas_cvm_nao_mapeadas.log"
    resultado = mapear_demonstracao(
        dados,
        demonstracao="dre",
        tipo_empresa="nao_financeira",
        mapeamento=MAPEAMENTO,
        ticker="TESTE",
        cd_cvm=123,
        caminho_log=caminho_log,
    )

    nomes = list(resultado["nome_padronizado"])
    assert nomes[:2] == ["receita_liquida", "cpv_cmv"]
    # O pandas converte None em NaN ao materializar a coluna.
    assert pd.isna(nomes[2])
    # Sinal: CPV e despesa e fica negativo mesmo vindo positivo da CVM.
    assert resultado.loc[1, "valor_padronizado"] == -80.0
    assert pd.isna(resultado.loc[2, "valor_padronizado"])
    assert set(resultado["demonstracao_padronizada"]) == {"dre"}

    conteudo_log = caminho_log.read_text(encoding="utf-8")
    assert "9.99" in conteudo_log
    assert "TESTE" in conteudo_log


def test_normalizar_sinal_trata_nulos() -> None:
    """Valores nulos nunca viram zero silencioso."""
    assert normalizar_sinal(None, "positivo") is None
    assert normalizar_sinal(float("nan"), "negativo") is None
    assert normalizar_sinal(-10, "positivo") == 10.0


# ---------------------------------------------------------------------------
# Contas novas do Prompt 9.0.1 (fidelidade a CVM: BP aberto por codigo/nome)
# ---------------------------------------------------------------------------


def test_realizavel_lp_aberto_por_codigo() -> None:
    """As sub-contas padrao do 1.02.01 ganham nome proprio por CD_CONTA."""
    casos = {
        "1.02.01.04": "contas_receber_lp",
        "1.02.01.05": "estoques_lp",
        "1.02.01.07": "tributos_diferidos_ativo_lp",
        "1.02.01.10": "outros_ativos_nao_circulantes",
    }
    for codigo, esperado in casos.items():
        resultado = mapear_conta(
            codigo,
            "Conta do Realizavel LP",
            "bp_ativo",
            "nao_financeira",
            MAPEAMENTO,
        )
        assert resultado is not None, codigo
        assert resultado["nome_padronizado"] == esperado
        assert resultado["mapeado_por"] == "codigo"


def test_outros_buckets_do_passivo_por_codigo() -> None:
    """Partes relacionadas e baldes Outros do passivo mapeiam por codigo."""
    casos = {
        "2.01.05.01": "partes_relacionadas_passivo_cp",
        "2.01.05.02": "outros_passivos_circulantes",
        "2.02.02.01": "partes_relacionadas_passivo_lp",
        "2.02.02.02": "outros_passivos_nao_circulantes",
    }
    for codigo, esperado in casos.items():
        resultado = mapear_conta(
            codigo,
            "Outros",
            "bp_passivo",
            "nao_financeira",
            MAPEAMENTO,
        )
        assert resultado is not None, codigo
        assert resultado["nome_padronizado"] == esperado


def test_sub_contas_recorrentes_por_nome() -> None:
    """Sub-contas de nivel 5 recorrentes (por DS_CONTA) ganham nome proprio."""
    casos = (
        ("bp_passivo", "Adiantamento de clientes", "adiantamento_clientes"),
        ("bp_passivo", "Dividendos e JCP a Pagar", "dividendos_a_pagar"),
        # Typo real do arquivo da Direcional ("imovies") coberto pelo padrao.
        ("bp_passivo", "Credores por imóvies compromissados", "credores_por_imoveis"),
        ("bp_ativo", "Depósitos Judiciais", "depositos_judiciais"),
        ("bp_ativo", "Impostos a Recuperar", "tributos_a_recuperar"),
    )
    for demonstracao, descricao, esperado in casos:
        resultado = mapear_conta(
            "2.02.02.02.99" if demonstracao == "bp_passivo" else "1.02.01.10.99",
            descricao,
            demonstracao,
            "nao_financeira",
            MAPEAMENTO,
        )
        assert resultado is not None, descricao
        assert resultado["nome_padronizado"] == esperado
        assert resultado["mapeado_por"] == "nome"


def test_arrendamento_continua_vencendo_nos_fallbacks_do_passivo() -> None:
    """Leasing em sub-conta de Outros segue como passivo_arrendamento (D-044)."""
    resultado = mapear_conta(
        "2.02.02.02.06",
        "Passivo por arrendamento",
        "bp_passivo",
        "nao_financeira",
        MAPEAMENTO,
    )
    assert resultado is not None
    assert resultado["nome_padronizado"] == "passivo_arrendamento"
    assert resultado["mapeado_por"] == "nome"


def test_caixa_do_dfc_mapeado_por_codigo() -> None:
    """Saldos inicial/final de caixa do DFC (6.05.01/6.05.02) tem nome proprio."""
    for codigo, esperado in (
        ("6.05.01", "caixa_inicial_dfc"),
        ("6.05.02", "caixa_final_dfc"),
    ):
        resultado = mapear_conta(
            codigo,
            "Saldo de Caixa e Equivalentes",
            "dfc",
            "nao_financeira",
            MAPEAMENTO,
        )
        assert resultado is not None
        assert resultado["nome_padronizado"] == esperado
