"""Testes do projetor financeiro (DRE bancaria + capital regulatorio)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.projetor_financeiro import projetar_financeiro


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para fixtures."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_banco_sintetico(tmp_path: Path, ticker: str = "BANK3") -> None:
    """Fixture bancaria: receitas 1000, PL 1200, ativo 10000 no Ano 0."""
    salvar_json(
        tmp_path / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {"ticker": ticker, "tipo": "financeira", "subtipo": "banco", "setor": "Bancos"},
    )
    base = {
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ULTIMO",
        "ano_arquivo": 2025,
    }
    salvar_json(
        tmp_path / "data" / "raw" / "cvm" / f"{ticker}_dre.json",
        [
            {
                **base,
                "CD_CONTA": "3.01",
                "nome_padronizado": "receitas_intermediacao_financeira",
                "valor_padronizado": 1000.0,
            },
            {
                **base,
                "CD_CONTA": "3.09",
                "nome_padronizado": "lucro_liquido",
                "valor_padronizado": 150.0,
            },
        ],
    )
    salvar_json(
        tmp_path / "data" / "raw" / "cvm" / f"{ticker}_bp.json",
        [
            {
                **base,
                "CD_CONTA": "2.03",
                "nome_padronizado": "patrimonio_liquido",
                "valor_padronizado": 1200.0,
            },
            {
                **base,
                "CD_CONTA": "1",
                "nome_padronizado": "ativo_total",
                "valor_padronizado": 10000.0,
            },
        ],
    )

    premissas = {
        "ticker": ticker,
        "tipo": "financeira",
        "indice_capital_alvo": 0.115,
        "fator_rwa_ativos": 0.8,
        "aliquota_ir_financeira": 0.40,
    }
    for ano in range(1, 9):
        # 8 valores individuais (nunca taxa unica replicada).
        premissas[f"crescimento_receita_ano{ano}"] = 0.10 + (ano - 1) * 0.001
        premissas[f"margem_resultado_bruto_ano{ano}"] = 0.40 - (ano - 1) * 0.001
        premissas[f"despesas_operacionais_receita_ano{ano}"] = -0.20 - (ano - 1) * 0.001
    salvar_json(
        tmp_path / "data" / "premissas" / f"{ticker}_premissas.json",
        premissas,
    )


def test_dre_bancaria_ano1_calculada_a_mao(tmp_path: Path) -> None:
    """Receitas -> resultado bruto -> despesas -> EBT -> IR -> LL."""
    criar_banco_sintetico(tmp_path)
    resultado = projetar_financeiro("BANK3", raiz_projeto=tmp_path)
    ano1 = resultado["dre"]["ano1"]

    # Receitas = 1000 x 1,10; RB = 1100 x 0,40; Despesas = 1100 x -0,20.
    assert ano1["receitas_intermediacao_financeira"] == pytest.approx(1100.0)
    assert ano1["resultado_bruto_intermediacao_financeira"] == pytest.approx(440.0)
    assert ano1["despesas_receitas_operacionais_financeira"] == pytest.approx(-220.0)
    # EBT = 220; IR = -40% x 220 = -88; LL = 132.
    assert ano1["ebt"] == pytest.approx(220.0)
    assert ano1["ir_csll"] == pytest.approx(-88.0)
    assert ano1["lucro_liquido"] == pytest.approx(132.0)


def test_capital_regulatorio_nao_e_liberado(tmp_path: Path) -> None:
    """PL acima do minimo nao e devolvido; capital so cresce com o RWA."""
    criar_banco_sintetico(tmp_path)
    resultado = projetar_financeiro("BANK3", raiz_projeto=tmp_path)
    capital = resultado["capital_regulatorio"]

    # cap_0 = max(PL 1200; 0,115 x 0,8 x 10000 = 920) = 1200.
    # ano1: minimo = 920 x 1,10 = 1012 < 1200 -> capital preso em 1200.
    assert capital["ano1"]["capital_regulatorio"] == pytest.approx(1200.0)
    assert capital["ano1"]["delta_capital_regulatorio"] == pytest.approx(0.0)

    # O minimo cresce ~10% a.a.; quando ultrapassa 1200 o delta fica positivo.
    deltas = [
        float(capital[f"ano{ano}"]["delta_capital_regulatorio"]) for ano in range(1, 9)
    ]
    assert any(delta > 0 for delta in deltas)
    # Capital retido nunca cai (nao liberavel).
    capitais = [
        float(capital[f"ano{ano}"]["capital_regulatorio"]) for ano in range(1, 9)
    ]
    assert capitais == sorted(capitais)


def test_nao_financeira_e_rejeitada_com_erro_claro(tmp_path: Path) -> None:
    """Projetor financeiro nao roda para empresa nao-financeira."""
    criar_banco_sintetico(tmp_path)
    salvar_json(
        tmp_path / "data" / "raw" / "cvm" / "BANK3_meta.json",
        {"ticker": "BANK3", "tipo": "nao_financeira", "setor": "Varejo"},
    )
    with pytest.raises(RuntimeError, match="nao e financeira"):
        projetar_financeiro("BANK3", raiz_projeto=tmp_path)
