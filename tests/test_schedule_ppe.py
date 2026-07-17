"""Testes do schedule PP&E (modelo simples: CAPEX % receita, D&A % PP&E)."""

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


def criar_metadados(
    raiz: Path,
    ticker: str = "TEST3",
    subtipo: str | None = None,
) -> None:
    """Cria metadados minimos para a regra de IR/CSLL e defaults por subtipo."""
    meta = {
        "ticker": ticker,
        "setor": "varejo",
        "tipo": "nao_financeira",
    }
    if subtipo is not None:
        meta["subtipo"] = subtipo
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json", meta)


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
    intangivel: float | None = None,
) -> None:
    """Cria saldo historico CVM minimo para o PP&E Ano 0."""
    linhas = [
        {
            "ano_arquivo": 2025,
            "DT_FIM_EXERC": "2025-12-31",
            "ORDEM_EXERC": "ÚLTIMO",
            "CD_CONTA": "1.02.03",
            "nome_padronizado": "imobilizado",
            "valor_padronizado": imobilizado,
        }
    ]
    if intangivel is not None:
        linhas.append(
            {
                "ano_arquivo": 2025,
                "DT_FIM_EXERC": "2025-12-31",
                "ORDEM_EXERC": "ÚLTIMO",
                "CD_CONTA": "1.02.04",
                "nome_padronizado": "intangivel",
                "valor_padronizado": intangivel,
            }
        )
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json", linhas)


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
    # Modelo simples (D-047): D&A = taxa (1/5 = 20%) x PP&E de abertura.
    # ano1: D&A = 0,20 x 500 = 100; PP&E = 500 + 100 - 100 = 500.
    assert ppe["ano1"]["da_imobilizado"] == pytest.approx(100.0)
    assert ppe["ano1"]["depreciacao_amortizacao"] == pytest.approx(100.0)
    assert ppe["ano1"]["imobilizado"] == pytest.approx(500.0)
    # ano2: D&A = 0,20 x 500 = 100; PP&E = 500 + 200 - 100 = 600.
    assert ppe["ano2"]["da_imobilizado"] == pytest.approx(100.0)
    assert ppe["ano2"]["imobilizado"] == pytest.approx(600.0)
    # Capex split expansao (80%) x manutencao (20%).
    assert ppe["ano1"]["capex_expansao"] == pytest.approx(80.0)
    assert ppe["ano1"]["capex_manutencao"] == pytest.approx(20.0)

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


def criar_projecao_dre_completa(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria projecao no modo COMPLETO: EBIT fixo, D&A embutida em CPV/SG&A."""
    dre = {}
    for ano in range(1, 9):
        dre[f"ano{ano}"] = {
            "ano_projecao": f"ano{ano}",
            "receita_liquida": 1000.0,
            "receita_bruta": 1100.0,
            "deducoes": -100.0,
            "cpv_cmv": -600.0,
            "lucro_bruto": 400.0,
            "sgna": -150.0,
            "outras_receitas_despesas": 0.0,
            "equivalencia_patrimonial": 0.0,
            "ebit": 250.0,
            "da_direito_uso": 0.0,
            "da_imobilizado": 0.0,
            "da_intangivel": 0.0,
            "depreciacao_amortizacao": 0.0,
            "ebitda": 250.0,
            "resultado_financeiro": -10.0,
            "ebt": 240.0,
            "ir_csll": -81.6,
            "lucro_liquido": 158.4,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "modo_dre": "completo",
            "ano0": {"receita_liquida": 900.0},
            "dre": dre,
        },
    )


def test_ppe_modo_completo_mantem_ebit_e_deriva_ebitda(tmp_path: Path) -> None:
    """Modo completo: a D&A do PP&E entra em da_imobilizado e o EBITDA vira
    EBIT + D&A; EBIT/EBT/IR/LL NAO mudam (a D&A ja esta embutida em CPV/SG&A)."""
    criar_parametros_ppe(tmp_path)
    criar_premissas_ppe(tmp_path)
    criar_metadados(tmp_path)
    criar_projecao_dre_completa(tmp_path)
    criar_base_historica_ppe(tmp_path)

    resultado = projetar_ppe("TEST3", raiz_projeto=tmp_path)
    dre = resultado["dre"]
    ppe = resultado["ppe"]

    # D&A simples (taxa 20%): 0,20 x 500 = 100.
    assert ppe["ano1"]["da_imobilizado"] == pytest.approx(100.0)
    assert dre["ano1"]["da_imobilizado"] == pytest.approx(100.0)
    assert dre["ano1"]["depreciacao_amortizacao"] == pytest.approx(100.0)
    # EBITDA = EBIT + D&A total; EBIT permanece fixo.
    assert dre["ano1"]["ebit"] == pytest.approx(250.0)
    assert dre["ano1"]["ebitda"] == pytest.approx(350.0)
    # EBT/IR/LL nao sao recalculados pela D&A no modo completo.
    assert dre["ano1"]["ebt"] == pytest.approx(240.0)
    assert dre["ano1"]["ir_csll"] == pytest.approx(-81.6)
    assert dre["ano1"]["lucro_liquido"] == pytest.approx(158.4)


def criar_dfc_da(raiz: Path, ticker: str = "TEST3", da: float = -200.0) -> None:
    """DFC minimo com a D&A historica (insumo do prazo medio do leasing)."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_dfc.json",
        [
            {
                "ano_arquivo": 2025,
                "DT_FIM_EXERC": "2025-12-31",
                "ORDEM_EXERC": "ÚLTIMO",
                "CD_CONTA": "6.01.01.02",
                "nome_padronizado": "depreciacao_amortizacao",
                "valor_padronizado": da,
            }
        ],
    )


def test_ppe_usa_taxa_da_config_mesmo_com_da_historica(tmp_path: Path) -> None:
    """Modelo simples (D-047): a taxa de D&A vem SEMPRE da config
    (1/vida_util_ppe_anos); a D&A historica do DFC nao muda a taxa, mas segue
    persistida em ano0.ppe (insumo do prazo medio do schedule de leasing)."""
    criar_parametros_ppe(tmp_path, vida_util=10.0)
    criar_premissas_ppe(tmp_path)
    criar_metadados(tmp_path)
    criar_projecao_dre(tmp_path)
    criar_base_historica_ppe(tmp_path, imobilizado=1000.0)
    criar_dfc_da(tmp_path, da=-200.0)

    resultado = projetar_ppe("TEST3", raiz_projeto=tmp_path)
    # taxa = 1/10 = 10% => D&A ano1 = 0,10 x 1000 = 100 (e nao 1000/5 = 200).
    assert resultado["ppe"]["ano1"]["da_imobilizado"] == pytest.approx(100.0)
    assert "vida_util_derivada" not in resultado
    assert resultado["ano0_ppe"]["da_historica"] == pytest.approx(200.0)


def test_ppe_intangivel_constante_sem_amortizacao(tmp_path: Path) -> None:
    """O intangivel NAO amortiza (D-047): da_intangivel = 0 em todos os anos e
    o saldo do Ano 0 permanece constante como linha propria do balanco."""
    criar_parametros_ppe(tmp_path)
    criar_premissas_ppe(tmp_path)
    criar_metadados(tmp_path)
    criar_projecao_dre(tmp_path)
    criar_base_historica_ppe(tmp_path, imobilizado=500.0, intangivel=200.0)

    resultado = projetar_ppe("TEST3", raiz_projeto=tmp_path)
    ppe = resultado["ppe"]

    assert resultado["ano0_ppe"]["intangivel"] == pytest.approx(200.0)
    for ano in range(1, 9):
        chave = f"ano{ano}"
        assert float(ppe[chave]["da_intangivel"]) == pytest.approx(0.0)
        assert float(ppe[chave]["intangivel"]) == pytest.approx(200.0)
        assert float(ppe[chave]["depreciacao_amortizacao"]) == pytest.approx(
            float(ppe[chave]["da_imobilizado"])
        )


def test_capex_expansao_default_do_subtipo(tmp_path: Path) -> None:
    """Sem premissa capex_expansao_pct_anoN, o default vem do subtipo em
    config/setores.json (premissas_default.capex_expansao_pct) antes do global."""
    criar_parametros_ppe(tmp_path)
    criar_premissas_ppe(tmp_path)
    criar_metadados(tmp_path, subtipo="academias")
    criar_projecao_dre(tmp_path)
    criar_base_historica_ppe(tmp_path)
    salvar_json(
        tmp_path / "config" / "setores.json",
        {
            "subtipos": {
                "academias": {"premissas_default": {"capex_expansao_pct": 0.60}}
            }
        },
    )

    resultado = projetar_ppe("TEST3", raiz_projeto=tmp_path)
    ppe = resultado["ppe"]

    assert resultado["origem_capex_expansao_padrao"] == "default_do_subtipo_academias"
    assert ppe["ano1"]["capex_expansao_pct"] == pytest.approx(0.60)
    assert ppe["ano1"]["capex_expansao"] == pytest.approx(60.0)
    assert ppe["ano1"]["capex_manutencao"] == pytest.approx(40.0)


def test_capex_assinado_investe_pela_magnitude(tmp_path: Path) -> None:
    """CAPEX negativo (convencao de caixa) AUMENTA o PP&E pela magnitude.

    Correcao da Onda 2: na v1 o capex assinado encolhia o ativo e o
    caixa-plug escondia a inconsistencia no balanco.
    """
    criar_ambiente_ppe(tmp_path)
    criar_premissas_ppe(tmp_path, capex_ano1=-1.0, capex_ano2=0.0)
    criar_base_historica_ppe(tmp_path, imobilizado=100.0)

    resultado = projetar_ppe("TEST3", raiz_projeto=tmp_path)
    ppe = resultado["ppe"]

    # O capex persiste ASSINADO (saida de caixa)...
    assert ppe["ano1"]["capex"] == pytest.approx(-1000.0)
    # ...mas o ativo cresce pela magnitude. D&A = 0,20 x 100 = 20;
    # imob = 100 + 1000 - 20 = 1080.
    assert ppe["ano1"]["da_imobilizado"] == pytest.approx(20.0)
    assert ppe["ano1"]["imobilizado"] == pytest.approx(1080.0)
    # Ano 2 sem capex: D&A = 0,20 x 1080 = 216; imob = 1080 - 216 = 864.
    assert ppe["ano2"]["da_imobilizado"] == pytest.approx(216.0)
    assert ppe["ano2"]["imobilizado"] == pytest.approx(864.0)
