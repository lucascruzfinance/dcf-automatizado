"""Testes do DFC indireto (Prompt 9.0.2.5): abertura por conta + amarracao.

Usa o ambiente integrado de ``test_projecao`` (DRE -> WK -> PP&E -> divida)
e valida que o DFC indireto abre o Delta WK linha a linha, reconcilia cada
bloco e amarra o caixa final ao caixa do BP projetado (dif < 1e-6).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.dfc_indireto import projetar_dfc_indireto
from src.projecao.projetor_dre import projetar_dre
from src.projecao.schedule_divida import projetar_divida
from src.projecao.schedule_ppe import projetar_ppe
from src.projecao.schedule_wk import projetar_wk
from tests.test_projecao import criar_ambiente_projecao_integrada


def _rodar_cadeia(tmp_path: Path) -> dict:
    """DRE -> WK -> PP&E -> divida -> DFC indireto no ambiente integrado."""
    criar_ambiente_projecao_integrada(tmp_path)
    projetar_dre("TEST3", raiz_projeto=tmp_path)
    projetar_wk("TEST3", raiz_projeto=tmp_path)
    projetar_ppe("TEST3", raiz_projeto=tmp_path)
    projetar_divida("TEST3", raiz_projeto=tmp_path)
    return projetar_dfc_indireto("TEST3", raiz_projeto=tmp_path)


def test_dfc_indireto_amarra_caixa_ao_bp(tmp_path: Path) -> None:
    """Caixa EoP do DFC = caixa do BP e variacao = delta caixa (dif < 1e-6)."""
    resultado = _rodar_cadeia(tmp_path)

    assert resultado["fecha"] is True
    assert resultado["avisos"] == []
    for ano in range(1, 9):
        verificacao = resultado["verificacao_dfc"][f"ano{ano}"]
        assert verificacao["fecha"] is True
        assert abs(verificacao["diferenca_caixa"]) < 1e-6
        assert abs(verificacao["diferenca_abertura_wk"]) < 1e-6


def test_dfc_indireto_abre_o_delta_wk_por_conta(tmp_path: Path) -> None:
    """Cada bloco reconcilia: soma das variacoes por conta = -Delta NWC;
    FCO = LL + D&A + variacoes; caixa BoP + FCO + FCI + FCFin = caixa EoP."""
    _rodar_cadeia(tmp_path)
    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    dfc = conteudo["dfc"]

    for ano in range(1, 9):
        linha = dfc[f"ano{ano}"]
        variacoes = [
            valor
            for campo, valor in linha.items()
            if campo.startswith("variacao_")
            and campo != "variacao_caixa"
            and campo != "variacao_caixa_plug"
        ]
        # Soma das linhas abertas = -Delta NWC (consumo positivo de caixa).
        assert sum(variacoes) == pytest.approx(-float(linha["delta_nwc"]))
        # FCO = LL + D&A - Delta WK (identica ao bloco legado).
        assert float(linha["fco"]) == pytest.approx(
            float(linha["lucro_liquido"])
            + float(linha["depreciacao_amortizacao"])
            - float(linha["delta_nwc"])
        )
        # Caixa BoP + (FCO + FCI + FCFin) = Caixa EoP.
        assert float(linha["caixa_inicial"]) + float(linha["fco"]) + float(
            linha["fci"]
        ) + float(linha["fcfin"]) == pytest.approx(float(linha["caixa_final"]))
        # Delta emprestimos = captacoes - amortizacoes (= delta_divida).
        assert float(linha["delta_emprestimos"]) == pytest.approx(
            float(linha["delta_divida"])
        )


def test_dfc_simplificado_preserva_o_formato_legado(tmp_path: Path) -> None:
    """O bloco dfc_simplificado mantem o contrato v2 (sem linhas abertas)."""
    _rodar_cadeia(tmp_path)
    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    simplificado = conteudo["dfc_simplificado"]

    for ano in range(1, 9):
        linha = simplificado[f"ano{ano}"]
        assert "fco" in linha and "fci" in linha and "fcf" in linha
        assert not any(campo.startswith("variacao_contas") for campo in linha)
        assert "caixa_inicial" not in linha
        # Valores identicos ao superset (mesma aritmetica, so sem abertura).
        assert float(linha["fco"]) == pytest.approx(
            float(conteudo["dfc"][f"ano{ano}"]["fco"])
        )


def test_dfc_indireto_reporta_quando_nao_amarra(tmp_path: Path) -> None:
    """Caixa do BP adulterado -> fecha=False com aviso (nunca raise)."""
    criar_ambiente_projecao_integrada(tmp_path)
    projetar_dre("TEST3", raiz_projeto=tmp_path)
    projetar_wk("TEST3", raiz_projeto=tmp_path)
    projetar_ppe("TEST3", raiz_projeto=tmp_path)
    projetar_divida("TEST3", raiz_projeto=tmp_path)
    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    conteudo["balanco"]["ano8"]["caixa_equivalentes"] = 999999.0
    caminho.write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")

    resultado = projetar_dfc_indireto("TEST3", raiz_projeto=tmp_path)
    assert resultado["fecha"] is False
    assert any("ano8" in aviso for aviso in resultado["avisos"])
