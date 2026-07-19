"""Testes do BP aberto com check visivel (Prompt 9.0.2.5).

Valida, no ambiente integrado sintetico, que o bloco ``balanco`` persiste a
abertura linha a linha (incluindo as contas novas do 9.0.2 e o passivo de
arrendamento como linha propria), que a soma das linhas reproduz os totais e
que o check ``verificacao_balanco`` fica ~0 nos 8 anos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.projecao.projetor_dre import projetar_dre
from src.projecao.schedule_divida import projetar_divida
from src.projecao.schedule_ppe import projetar_ppe
from src.projecao.schedule_wk import projetar_wk
from tests.test_projecao import criar_ambiente_projecao_integrada

LINHAS_ATIVO = (
    "caixa_equivalentes",
    "aplicacoes_financeiras",
    "contas_receber",
    "estoques",
    "tributos_a_recuperar",
    "imobilizado",
    "intangivel",
    "outros_ativos",
)
LINHAS_PASSIVO = (
    "fornecedores",
    "obrigacoes_sociais_trabalhistas",
    "adiantamento_clientes",
    "divida_curto_prazo",
    "divida_longo_prazo",
    "passivo_arrendamento",
    "outros_passivos",
)


def _rodar_ate_divida(tmp_path: Path) -> dict:
    """DRE -> WK -> PP&E -> divida no ambiente integrado sintetico."""
    criar_ambiente_projecao_integrada(tmp_path)
    projetar_dre("TEST3", raiz_projeto=tmp_path)
    projetar_wk("TEST3", raiz_projeto=tmp_path)
    projetar_ppe("TEST3", raiz_projeto=tmp_path)
    return projetar_divida("TEST3", raiz_projeto=tmp_path)


def test_abertura_soma_aos_totais(tmp_path: Path) -> None:
    """Soma das linhas de ativo = ativo_total; idem passivo + PL."""
    resultado = _rodar_ate_divida(tmp_path)
    balanco = resultado["balanco"]

    for ano in range(1, 9):
        linha = balanco[f"ano{ano}"]
        # Toda linha da abertura existe (contas novas entram com 0 quando o
        # modo de WK nao as projeta — nunca somem do contrato).
        for campo in LINHAS_ATIVO + LINHAS_PASSIVO:
            assert campo in linha, campo
        soma_ativo = sum(float(linha[campo]) for campo in LINHAS_ATIVO)
        assert soma_ativo == pytest.approx(float(linha["ativo_total"]))
        soma_passivo = sum(float(linha[campo]) for campo in LINHAS_PASSIVO)
        assert soma_passivo == pytest.approx(float(linha["passivo_total"]))
        assert float(linha["passivo_total"]) + float(
            linha["patrimonio_liquido"]
        ) == pytest.approx(float(linha["passivo_patrimonio_liquido"]))


def test_check_visivel_aproximadamente_zero(tmp_path: Path) -> None:
    """verificacao_balanco (|Ativo - Passivo - PL|) ~ 0 nos 8 anos."""
    resultado = _rodar_ate_divida(tmp_path)
    balanco = resultado["balanco"]

    for ano in range(1, 9):
        linha = balanco[f"ano{ano}"]
        escala = max(abs(float(linha["ativo_total"])), 1.0)
        assert float(linha["verificacao_balanco"]) == pytest.approx(
            0.0, abs=1e-6 * escala
        )
    assert resultado["politicas"]["fechamento_ok"] is True
