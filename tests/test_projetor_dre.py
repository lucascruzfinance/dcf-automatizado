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


def test_projetar_dre_legado_ignora_falta_dos_campos_novos(tmp_path: Path) -> None:
    """Contrato de retrocompatibilidade: arquivo v2 (sem campos novos) roda no
    modo legado sem KeyError e sem ligar a DRE completa."""
    criar_mapeamento_minimo(tmp_path)
    criar_base_historica_minima(tmp_path)
    criar_premissas_minimas(tmp_path)

    resultado = projetar_dre("TEST3", raiz_projeto=tmp_path)

    assert resultado["modo_dre"] == "legado"
    linha = resultado["dre"]["ano1"]
    assert "cpv_cmv" not in linha
    assert "receita_bruta" not in linha
    conteudo = json.loads(
        (tmp_path / "data" / "processed" / "TEST3_projecao.json").read_text(
            encoding="utf-8"
        )
    )
    assert conteudo["modo_dre"] == "legado"


# ---------------------------------------------------------------------------
# Modo COMPLETO (DRE Padrao Smartfit — Prompt 8.1)
# ---------------------------------------------------------------------------

CAMPOS_COMPLETOS = (
    "receita_bruta",
    "deducoes",
    "cpv_cmv",
    "lucro_bruto",
    "margem_bruta",
    "sgna",
    "sgna_pct_receita",
    "outras_receitas_despesas",
    "equivalencia_patrimonial",
    "aliquota_efetiva_usada",
    "da_direito_uso",
    "da_imobilizado",
    "da_intangivel",
    "modo_dre",
    "modo_aliquota",
    # Campos novos do padrao Direcional PRE-D&A (Prompt 9.0.2).
    "ebit_ex_depreciacao",
    "aliquota_ir_ano",
    "ll_antes_minoritarios",
    "participacao_minoritarios",
    "minoritarios_pct_ll",
    "lpa",
)


def criar_mapeamento_completo(raiz: Path) -> None:
    """Mapeamento com os campos legado + os campos da DRE completa."""
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
    for campo in CAMPOS_COMPLETOS:
        campos[campo] = {}
    salvar_json(raiz / "config" / "mapeamento_cvm.json", {"campos": campos})


def criar_parametros_dre_completa(raiz: Path) -> None:
    """parametros.json minimo com o bloco dre_completa."""
    salvar_json(
        raiz / "config" / "parametros.json",
        {
            "dre_completa": {
                "modo_aliquota_padrao": "marginal",
                "aliquota_marginal": 0.34,
                "aliquota_efetiva_min": 0.15,
                "aliquota_efetiva_max": 0.45,
                "deducoes_pct_receita_bruta_padrao": 0.0,
                "outras_despesas_pct_receita_padrao": 0.0,
                "equivalencia_pct_receita_padrao": 0.0,
            }
        },
    )


def criar_premissas_completas(
    raiz: Path,
    ticker: str = "TEST3",
    modo_aliquota: str = "marginal",
    aliquota_efetiva: float | None = None,
) -> None:
    """Premissas com os vetores definidores da DRE completa."""
    premissas = {
        "ticker": ticker,
        "setor": "varejo",
        "tipo": "nao_financeira",
        "modo_aliquota": modo_aliquota,
        "outras_despesas_pct_receita": 0.0,
        "equivalencia_pct_receita": 0.0,
    }
    for ano in range(1, 9):
        premissas[f"crescimento_receita_ano{ano}"] = 0.10
        premissas[f"margem_bruta_ano{ano}"] = 0.40
        premissas[f"sgna_pct_receita_ano{ano}"] = 0.15
        premissas[f"deducoes_pct_receita_bruta_ano{ano}"] = 0.10
    if aliquota_efetiva is not None:
        premissas["aliquota_efetiva"] = aliquota_efetiva
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        premissas,
    )


def test_dre_completa_bruta_liquida_cpv_sgna(tmp_path: Path) -> None:
    """Cascata PRE-D&A (9.0.2): margens de nivel EBITDA geram o EBIT
    ex-Depreciacao; EBIT = ex-D&A - D&A (linha propria); EBITDA = ex-D&A."""
    criar_mapeamento_completo(tmp_path)
    criar_parametros_dre_completa(tmp_path)
    criar_base_historica_minima(tmp_path)
    criar_premissas_completas(tmp_path)

    resultado = projetar_dre("TEST3", raiz_projeto=tmp_path)
    assert resultado["modo_dre"] == "completo"
    a1 = resultado["dre"]["ano1"]

    # RL1 = 1000 x 1,10 = 1100; RB = RL / (1 - 0,10).
    assert a1["receita_liquida"] == pytest.approx(1100.0)
    assert a1["receita_bruta"] == pytest.approx(1100.0 / 0.9)
    assert a1["deducoes"] == pytest.approx(1100.0 - 1100.0 / 0.9)
    # CPV PRE-D&A = -(RL x (1 - margem_bruta)); Lucro Bruto = RL x margem.
    assert a1["cpv_cmv"] == pytest.approx(-(1100.0 * 0.6))
    assert a1["lucro_bruto"] == pytest.approx(1100.0 * 0.4)
    assert a1["sgna"] == pytest.approx(-(1100.0 * 0.15))
    # EBIT ex-Depreciacao = Lucro Bruto + SG&A + Outras + Equivalencia
    # (nivel EBITDA — nenhuma D&A embutida nas margens).
    ebit_ex_esperado = 1100.0 * 0.4 - 1100.0 * 0.15
    assert a1["ebit_ex_depreciacao"] == pytest.approx(ebit_ex_esperado)
    # EBIT = EBIT ex-D&A - D&A (linha propria; 0 no projetor puro).
    assert a1["ebit"] == pytest.approx(
        a1["ebit_ex_depreciacao"] - a1["depreciacao_amortizacao"]
    )
    # Memo: EBITDA = EBIT ex-Depreciacao (invariante sob a D&A).
    assert a1["ebitda"] == pytest.approx(a1["ebit_ex_depreciacao"])
    # Imposto marginal 34% sobre EBT positivo.
    assert a1["ir_csll"] == pytest.approx(-(a1["ebt"] * 0.34))
    # Sem minoritarios (default 0): LL = LL antes de minoritarios.
    assert a1["ll_antes_minoritarios"] == pytest.approx(a1["ebt"] + a1["ir_csll"])
    assert a1["participacao_minoritarios"] == pytest.approx(0.0)
    assert a1["lucro_liquido"] == pytest.approx(a1["ll_antes_minoritarios"])


def test_dre_completa_aliquota_anual_vence_escalar(tmp_path: Path) -> None:
    """Vetor aliquota_ir_ano1..8 VENCE o modo escalar (efetiva/marginal)."""
    criar_mapeamento_completo(tmp_path)
    criar_parametros_dre_completa(tmp_path)
    criar_base_historica_minima(tmp_path)
    criar_premissas_completas(
        tmp_path,
        modo_aliquota="efetiva_historica",
        aliquota_efetiva=0.40,
    )
    caminho = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas = json.loads(caminho.read_text(encoding="utf-8"))
    for ano in range(1, 9):
        premissas[f"aliquota_ir_ano{ano}"] = 0.20
    salvar_json(caminho, premissas)

    resultado = projetar_dre("TEST3", raiz_projeto=tmp_path)
    a1 = resultado["dre"]["ano1"]
    # O vetor anual (20%) vence a efetiva escalar (40%).
    assert a1["aliquota_ir_ano"] == pytest.approx(0.20)
    assert a1["ir_csll"] == pytest.approx(-(a1["ebt"] * 0.20))


def test_dre_completa_minoritarios_e_lpa(tmp_path: Path) -> None:
    """Minoritarios = -pct x LL antes; LL final = LL antes x (1-pct);
    LPA = LL final / acoes fully diluted."""
    criar_mapeamento_completo(tmp_path)
    criar_parametros_dre_completa(tmp_path)
    criar_base_historica_minima(tmp_path)
    criar_premissas_completas(tmp_path)
    caminho = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas = json.loads(caminho.read_text(encoding="utf-8"))
    premissas["minoritarios_pct_ll"] = 0.10
    premissas["acoes_fully_diluted"] = 100.0
    salvar_json(caminho, premissas)

    resultado = projetar_dre("TEST3", raiz_projeto=tmp_path)
    a1 = resultado["dre"]["ano1"]
    ll_antes = float(a1["ll_antes_minoritarios"])
    assert a1["participacao_minoritarios"] == pytest.approx(-0.10 * ll_antes)
    assert a1["lucro_liquido"] == pytest.approx(0.90 * ll_antes)
    assert a1["lpa"] == pytest.approx(float(a1["lucro_liquido"]) / 100.0)


def test_dre_completa_aliquota_efetiva_com_clamp(tmp_path: Path) -> None:
    """modo_aliquota efetiva_historica: aliquota fora da faixa e clampada em
    [15%, 45%] antes de aplicar sobre o EBT."""
    criar_mapeamento_completo(tmp_path)
    criar_parametros_dre_completa(tmp_path)
    criar_base_historica_minima(tmp_path)
    criar_premissas_completas(
        tmp_path,
        modo_aliquota="efetiva_historica",
        aliquota_efetiva=0.60,
    )

    resultado = projetar_dre("TEST3", raiz_projeto=tmp_path)
    a1 = resultado["dre"]["ano1"]
    # 0,60 -> clamp 0,45.
    assert a1["aliquota_efetiva_usada"] == pytest.approx(0.45)
    assert a1["ir_csll"] == pytest.approx(-(a1["ebt"] * 0.45))


def test_dre_completa_ret_sobre_receita_bruta(tmp_path: Path) -> None:
    """Construtora no modo completo: RET = -4% sobre a Receita BRUTA
    projetada ano a ano (nao mais sobre a razao fixa RB/RL)."""
    criar_mapeamento_completo(tmp_path)
    criar_parametros_dre_completa(tmp_path)
    criar_base_historica_minima(tmp_path, ticker="CONS3")
    # setor construcao ativa o RET em empresa_usa_ret.
    meta = tmp_path / "data" / "raw" / "cvm" / "CONS3_meta.json"
    salvar_json(
        meta,
        {"ticker": "CONS3", "setor": "construcao", "tipo": "nao_financeira"},
    )
    criar_premissas_completas(tmp_path, ticker="CONS3")
    caminho = tmp_path / "data" / "premissas" / "CONS3_premissas.json"
    premissas = json.loads(caminho.read_text(encoding="utf-8"))
    premissas["setor"] = "construcao"
    salvar_json(caminho, premissas)

    resultado = projetar_dre("CONS3", raiz_projeto=tmp_path)
    a1 = resultado["dre"]["ano1"]
    assert a1["ir_csll"] == pytest.approx(-(a1["receita_bruta"] * 0.04))
