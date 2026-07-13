"""Testes das metricas historicas da trilha nao-financeira."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.metricas.metricas_historicas import (
    calcular_cagr,
    calcular_metricas_historicas,
)


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def _linha(
    nome: str,
    valor: float,
    ano: int,
    data: str | None = None,
    ordem: str = "ÚLTIMO",
) -> dict:
    """Monta uma linha bruta da CVM no formato persistido pela coleta."""
    return {
        "nome_padronizado": nome,
        "valor_padronizado": valor,
        "DT_FIM_EXERC": data or f"{ano}-12-31",
        "ORDEM_EXERC": ordem,
        "ano_arquivo": ano,
        "CD_CONTA": "3.01",
    }


def criar_fixture_cvm(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria DRE/BP/DFC sinteticos com 4 exercicios anuais + 1 ITR de ruido."""
    dre = []
    bp = []
    dfc = []
    receitas = {2022: 1000.0, 2023: 1100.0, 2024: 1300.0, 2025: 1440.0}
    for ano, receita in receitas.items():
        dre.extend(
            [
                _linha("receita_liquida", receita, ano),
                _linha("lucro_bruto", receita * 0.4, ano),
                _linha("cpv_cmv", -receita * 0.6, ano),
                _linha("ebit", receita * 0.2, ano),
                _linha("ebt", receita * 0.18, ano),
                _linha("ir_csll", -receita * 0.18 * 0.34, ano),
                _linha("lucro_liquido", receita * 0.18 * 0.66, ano),
                _linha("despesas_financeiras", -receita * 0.02, ano),
            ]
        )
        bp.extend(
            [
                _linha("contas_receber", receita * 0.15, ano),
                _linha("estoques", receita * 0.20, ano),
                _linha("fornecedores", -receita * 0.10, ano),
                _linha("imobilizado", receita * 0.50, ano),
                _linha("divida_curto_prazo", -receita * 0.05, ano),
                _linha("divida_longo_prazo", -receita * 0.25, ano),
                _linha("caixa_equivalentes", receita * 0.08, ano),
                _linha("aplicacoes_financeiras", receita * 0.02, ano),
                _linha("patrimonio_liquido", receita * 0.60, ano),
            ]
        )
        dfc.append(_linha("depreciacao_amortizacao", receita * 0.03, ano))

    # Ruido: um ITR trimestral mais recente NAO pode virar exercicio anual.
    dre.append(_linha("receita_liquida", 400.0, 2026, data="2026-03-31"))

    pasta = raiz / "data" / "raw" / "cvm"
    salvar_json(pasta / f"{ticker}_dre.json", dre)
    salvar_json(pasta / f"{ticker}_bp.json", bp)
    salvar_json(pasta / f"{ticker}_dfc.json", dfc)
    salvar_json(
        pasta / f"{ticker}_meta.json",
        {"ticker": ticker, "tipo": "nao_financeira", "setor": "varejo"},
    )


def test_metricas_ignoram_itr_trimestral(tmp_path: Path) -> None:
    """O ITR de 31/03 nao pode aparecer como exercicio nas metricas."""
    criar_fixture_cvm(tmp_path)

    resultado = calcular_metricas_historicas("TEST3", raiz_projeto=tmp_path)

    assert sorted(resultado["metricas_por_ano"]) == ["2022", "2023", "2024", "2025"]


def test_crescimento_e_margens_por_ano(tmp_path: Path) -> None:
    """Crescimento YoY e margens seguem as formulas canonicas."""
    criar_fixture_cvm(tmp_path)

    resultado = calcular_metricas_historicas("TEST3", raiz_projeto=tmp_path)
    linha_2023 = resultado["metricas_por_ano"]["2023"]

    assert abs(linha_2023["crescimento_receita_yoy"] - 0.10) < 1e-9
    assert abs(linha_2023["margem_bruta"] - 0.40) < 1e-9
    # Margem EBITDA = (EBIT + D&A) / Receita = (0,20 + 0,03) = 23%.
    assert abs(linha_2023["margem_ebitda"] - 0.23) < 1e-9


def test_cagr_receita_3_anos(tmp_path: Path) -> None:
    """CAGR de 3 anos usa a razao entre extremos elevada a 1/3."""
    criar_fixture_cvm(tmp_path)

    resultado = calcular_metricas_historicas("TEST3", raiz_projeto=tmp_path)
    esperado = (1440.0 / 1000.0) ** (1.0 / 3.0) - 1.0

    assert abs(resultado["agregados"]["cagr_receita_3a"] - esperado) < 1e-9


def test_cagr_indefinido_com_janela_maior_que_historico() -> None:
    """Janela maior que o historico disponivel devolve None, sem quebrar."""
    assert calcular_cagr({2024: 100.0, 2025: 120.0}, 5) is None


def test_prazos_de_giro(tmp_path: Path) -> None:
    """DSO/DIO/DPO usam receita e CPV com 365 dias."""
    criar_fixture_cvm(tmp_path)

    resultado = calcular_metricas_historicas("TEST3", raiz_projeto=tmp_path)
    linha = resultado["metricas_por_ano"]["2025"]

    assert abs(linha["dso"] - 0.15 * 365) < 1e-6
    assert abs(linha["dio"] - (0.20 / 0.60) * 365) < 1e-6
    assert abs(linha["dpo"] - (0.10 / 0.60) * 365) < 1e-6


def test_persistencia_do_json(tmp_path: Path) -> None:
    """O resultado precisa ser persistido em data/processed."""
    criar_fixture_cvm(tmp_path)

    calcular_metricas_historicas("TEST3", raiz_projeto=tmp_path)
    caminho = tmp_path / "data" / "processed" / "TEST3_metricas.json"

    assert caminho.exists()
    persistido = json.loads(caminho.read_text(encoding="utf-8"))
    assert persistido["trilha"] == "nao_financeira"


def test_trilha_financeira_calcula_roe_e_avisa_basileia(tmp_path: Path) -> None:
    """Financeira usa a trilha bancaria real (Onda 2) com aviso de Basileia."""
    pasta = tmp_path / "data" / "raw" / "cvm"
    salvar_json(
        pasta / "BANK3_meta.json",
        {"ticker": "BANK3", "tipo": "financeira", "setor": "bancos"},
    )
    base = {"ORDEM_EXERC": "ULTIMO", "ano_arquivo": 2025}
    dre = []
    bp = []
    for ano, receita, lucro, pl, ativo in (
        (2024, 1000.0, 150.0, 900.0, 10000.0),
        (2025, 1100.0, 180.0, 1000.0, 11000.0),
    ):
        exercicio = {**base, "DT_FIM_EXERC": f"{ano}-12-31"}
        dre.append(
            {
                **exercicio,
                "CD_CONTA": "3.01",
                "nome_padronizado": "receitas_intermediacao_financeira",
                "valor_padronizado": receita,
            }
        )
        dre.append(
            {
                **exercicio,
                "CD_CONTA": "3.09",
                "nome_padronizado": "lucro_liquido",
                "valor_padronizado": lucro,
            }
        )
        bp.append(
            {
                **exercicio,
                "CD_CONTA": "2.03",
                "nome_padronizado": "patrimonio_liquido",
                "valor_padronizado": pl,
            }
        )
        bp.append(
            {
                **exercicio,
                "CD_CONTA": "1",
                "nome_padronizado": "ativo_total",
                "valor_padronizado": ativo,
            }
        )
    salvar_json(pasta / "BANK3_dre.json", dre)
    salvar_json(pasta / "BANK3_bp.json", bp)

    resultado = calcular_metricas_historicas("BANK3", raiz_projeto=tmp_path)

    assert resultado["trilha"] == "financeira"
    metricas_2025 = resultado["metricas_por_ano"]["2025"]
    # Formula: ROE = LL / PL medio = 180 / 950.
    assert metricas_2025["roe"] == pytest.approx(180.0 / 950.0)
    # Formula: ROA = LL / Ativo medio = 180 / 10500.
    assert metricas_2025["roa"] == pytest.approx(180.0 / 10500.0)
    assert metricas_2025["margem_liquida_receitas"] == pytest.approx(180.0 / 1100.0)
    # Basileia/NPL nao existem na DFP: viram aviso de premissa do analista.
    assert any("Basileia" in aviso for aviso in resultado["avisos"])
