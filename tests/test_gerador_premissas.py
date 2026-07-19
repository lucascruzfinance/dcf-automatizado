"""Testes do gerador de premissas de partida (DRE completa — Prompt 8.1)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.projecao.gerador_premissas import gerar_premissas_automaticas


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def _linha_dre(codigo: str, nome: str, valor: float) -> dict[str, object]:
    """Monta uma linha bruta da DRE no contrato da coleta CVM."""
    return {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
        "CD_CONTA": codigo,
        "nome_padronizado": nome,
        "valor_padronizado": valor,
    }


def montar_fixtures(raiz: Path, ticker: str = "TEST3", com_dva: bool = True) -> None:
    """Cria meta, metricas, DRE bruta, DVA e setores para o gerador."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "subtipo": "varejo",
            "setor": "Varejo",
        },
    )
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_metricas.json",
        {
            "agregados": {
                "cagr_receita_3a": 0.08,
                "margem_ebitda_media_3a": 0.12,
                "margem_bruta_media_3a": 0.30,
                "capex_receita_media_3a": 0.03,
                "dso_media_3a": 40.0,
                "dio_media_3a": 50.0,
                "dpo_media_3a": 45.0,
                "aliquota_efetiva_media_3a": 0.25,
                "beta_desalavancado": 0.8,
            }
        },
    )
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_dre.json",
        [
            _linha_dre("3.01", "receita_liquida", 1000.0),
            _linha_dre("3.04.01", "despesas_vendas", -100.0),
            _linha_dre("3.04.02", "despesas_gerais_administrativas", -50.0),
            _linha_dre("3.04.05", "outras_despesas_operacionais", -10.0),
            _linha_dre("3.04.06", "resultado_equivalencia_patrimonial", 5.0),
        ],
    )
    if com_dva:
        salvar_json(
            raiz / "data" / "raw" / "cvm" / f"{ticker}_dva.json",
            [_linha_dre("7.01.01", "receita_bruta", 1200.0)],
        )
    salvar_json(
        raiz / "config" / "setores.json",
        {
            "subtipos": {
                "varejo": {
                    "tipo": "nao_financeira",
                    "premissas_default": {
                        "crescimento_receita": 0.05,
                        "margem_ebitda": 0.10,
                        "capex_receita": -0.03,
                        "payout_dividendos": 0.2,
                    },
                }
            },
            "defaults_dre_completa": {
                "varejo": {"margem_bruta": 0.28, "sgna_pct_receita": 0.20},
                "outros": {"margem_bruta": 0.30, "sgna_pct_receita": 0.15},
            },
        },
    )


def test_gerador_gera_conjunto_dre_completa(tmp_path: Path) -> None:
    """O gerador SEMPRE emite o conjunto completo com 8 valores individuais."""
    montar_fixtures(tmp_path)

    _, premissas = gerar_premissas_automaticas(
        "TEST3", raiz_projeto=tmp_path, sobrescrever=True
    )

    for prefixo in ("margem_bruta", "sgna_pct_receita", "deducoes_pct_receita_bruta"):
        valores = [premissas[f"{prefixo}_ano{ano}"] for ano in range(1, 9)]
        assert all(isinstance(v, (int, float)) for v in valores)
        # 8 valores individuais (nunca uma taxa unica replicada).
        assert len(set(valores)) > 1
    # margem EBITDA permanece (retrocompat com consumidores v2).
    assert "margem_ebitda_ano1" in premissas
    assert premissas["modo_aliquota"] == "marginal"
    assert premissas["aliquota_efetiva"] == 0.25
    # margem bruta ancorada no historico (0,30) para o ano 1.
    assert abs(premissas["margem_bruta_ano1"] - 0.30) < 0.01
    # SG&A ano 1 = (100 + 50)/1000 = 0,15.
    assert abs(premissas["sgna_pct_receita_ano1"] - 0.15) < 0.01
    # Deducoes via DVA: 1 - 1000/1200 = 0,1667.
    assert 0.15 < premissas["deducoes_pct_receita_bruta_ano1"] < 0.185


def test_gerador_sem_dva_deducoes_zero_com_aviso(
    tmp_path: Path,
    caplog,
) -> None:
    """Sem DVA/receita bruta, as deducoes caem para ~0 com aviso logado."""
    montar_fixtures(tmp_path, com_dva=False)

    with caplog.at_level(logging.WARNING):
        _, premissas = gerar_premissas_automaticas(
            "TEST3", raiz_projeto=tmp_path, sobrescrever=True
        )

    deducoes = [
        premissas[f"deducoes_pct_receita_bruta_ano{ano}"] for ano in range(1, 9)
    ]
    assert max(deducoes) < 0.01
    assert "deducoes = 0" in caplog.text
