"""Testes do grafico ROIC/ROIIC."""

from __future__ import annotations

import json
from pathlib import Path

from src.visualizacao import roic_roiic


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_projecao_e_metricas(raiz: Path, ticker: str = "TEST3") -> None:
    """Cria projecao e metricas minimas consumidas pelo grafico."""
    fcff = {}
    dre = {}
    for ano in range(1, 9):
        chave = f"ano{ano}"
        fcff[chave] = {
            "ano_projecao": chave,
            "fcff": 100.0 + ano,
            "roic": 0.10 + ano * 0.005,
            "roiic": None if ano == 1 else 0.12 + ano * 0.004,
        }
        dre[chave] = {"ano_projecao": chave, "receita_liquida": 1000.0 + ano}

    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "ano0": {"receita_liquida": 900.0},
            "dre": dre,
            "fcff": fcff,
            "wacc": {"wacc": 0.12},
            "valor_terminal": {"g": 0.03},
            "ev_equity": {"target_price": 10.0},
        },
    )
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_metricas.json",
        {
            "ticker": ticker,
            "metricas_por_ano": {
                "2023": {"roic": 0.08, "roiic": None},
                "2024": {"roic": 0.09, "roiic": 0.10},
                "2025": {"roic": 0.11, "roiic": 0.14},
            },
            "agregados": {
                "roic_media_3a": 0.0933,
                "roic_mediana_3a": 0.09,
                "roiic_media_3a": 0.12,
                "roiic_mediana_3a": 0.12,
            },
        },
    )


def test_gerar_roic_roiic_monta_figura(monkeypatch, tmp_path: Path) -> None:
    """Grafico deve expor ROIC e ROIIC historico vs projetado."""
    criar_projecao_e_metricas(tmp_path)

    def salvar_stub(figura, raiz_projeto, ticker, nome):
        """Stub de salvar_grafico que evita escrever HTML/PNG no teste."""
        return {"html": raiz_projeto / f"{ticker}_{nome}.html", "png": None}

    monkeypatch.setattr(roic_roiic, "salvar_grafico", salvar_stub)

    resultado = roic_roiic.gerar_roic_roiic("TEST3", tmp_path)

    assert resultado["html"].name == "TEST3_roic_roiic.html"
    assert resultado["figura"].layout.title.text.startswith("<b>ROIC e ROIIC")
    assert len(resultado["figura"].data) >= 6
