"""Testes do schedule de divida v2: amortizacao, captacao e verificacao.

Fixture com Ano 0 CONSISTENTE (Ativo Total real = soma dos ativos
modelados; PL = Ativo - passivos), o que zera os residuais e permite
conferir o fechamento exato do balanco sem plug. Numeros calculaveis a mao:

    caixa0=500 aplic0=100 CR0=900 Est0=400 Imob0=800 -> AT0=2700
    Forn0=300 CP0=100 LP0=300 -> PL0 = 2700-300-400 = 2000
    Kd=10% (saldo inicial) | taxa aplicacao=5% | payout=50% (premissa)
    prazo LP=3 anos | WK constante (delta_nwc=0) | capex=-20 | D&A=10
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.schedule_divida import projetar_divida


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_parametros(raiz: Path, caixa_minimo_pct: float = 0.0) -> None:
    """Parametros globais: payout global zero e politica de divida v2."""
    salvar_json(
        raiz / "config" / "parametros.json",
        {
            "payout_dividendos": 0.0,
            "politica_divida": {
                "prazo_amortizacao_lp_anos": 3,
                "caixa_minimo_pct_receita": caixa_minimo_pct,
                "taxa_aplicacao_caixa_fallback": 0.10,
            },
        },
    )


def criar_premissas(raiz: Path, ticker: str = "TEST3") -> None:
    """Premissas com Kd, taxa de aplicacao e payout explicitos."""
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        {
            "ticker": ticker,
            "setor": "varejo",
            "tipo": "nao_financeira",
            "custo_divida_kd": 0.10,
            "taxa_aplicacao_caixa": 0.05,
            "payout_dividendos": 0.5,
        },
    )


def criar_metadados(raiz: Path, ticker: str = "TEST3") -> None:
    """Metadados minimos para a regra de IR/CSLL."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {"ticker": ticker, "setor": "varejo", "tipo": "nao_financeira"},
    )


def criar_base_historica_bp(raiz: Path, ticker: str = "TEST3") -> None:
    """BP historico consistente (AT = soma dos ativos modelados)."""
    base = {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ULTIMO",
    }
    registros = [
        {
            **base,
            "CD_CONTA": "1",
            "nome_padronizado": "ativo_total",
            "valor_padronizado": 2700.0,
        },
        {
            **base,
            "CD_CONTA": "1.01.01",
            "nome_padronizado": "caixa_equivalentes",
            "valor_padronizado": 500.0,
        },
        {
            **base,
            "CD_CONTA": "1.01.02",
            "nome_padronizado": "aplicacoes_financeiras",
            "valor_padronizado": 100.0,
        },
        {
            **base,
            "CD_CONTA": "2.01.04",
            "nome_padronizado": "divida_curto_prazo",
            "valor_padronizado": -100.0,
        },
        {
            **base,
            "CD_CONTA": "2.02.01",
            "nome_padronizado": "divida_longo_prazo",
            "valor_padronizado": -300.0,
        },
        {
            **base,
            "CD_CONTA": "2.03",
            "nome_padronizado": "patrimonio_liquido",
            "valor_padronizado": 2000.0,
        },
    ]
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json", registros)


def criar_projecao_existente(raiz: Path, ticker: str = "TEST3") -> None:
    """DRE, WK (constante) e PP&E coerentes com o Ano 0 da fixture."""
    dre = {}
    wk = {}
    ppe = {}
    imobilizado = 800.0
    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        dre[chave_ano] = {
            "ano_projecao": chave_ano,
            "receita_liquida": 1000.0,
            "ebit": 100.0,
            "resultado_financeiro": 0.0,
            "ebt": 100.0,
            "ir_csll": -34.0,
            "lucro_liquido": 66.0,
        }
        wk[chave_ano] = {
            "ano_projecao": chave_ano,
            "contas_receber": 900.0,
            "estoques": 400.0,
            "fornecedores": -300.0,
            "delta_nwc": 0.0,
        }
        # PP&E cresce pela magnitude do capex: 800 + 20 - 10 = +10/ano.
        imobilizado = imobilizado + 20.0 - 10.0
        ppe[chave_ano] = {
            "ano_projecao": chave_ano,
            "capex": -20.0,
            "depreciacao_amortizacao": 10.0,
            "imobilizado": imobilizado,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "ano0": {
                "receita_liquida": 900.0,
                "wk": {
                    "contas_receber": 900.0,
                    "estoques": 400.0,
                    "fornecedores": -300.0,
                },
                "ppe": {"imobilizado": 800.0},
            },
            "dre": dre,
            "wk": wk,
            "ppe": ppe,
        },
    )


def criar_ambiente_divida(tmp_path: Path, caixa_minimo_pct: float = 0.0) -> None:
    """Cria todos os arquivos minimos usados pelos testes."""
    criar_parametros(tmp_path, caixa_minimo_pct)
    criar_premissas(tmp_path)
    criar_metadados(tmp_path)
    criar_base_historica_bp(tmp_path)
    criar_projecao_existente(tmp_path)


def test_amortizacao_juros_e_fechamento_v2(tmp_path: Path) -> None:
    """CP amortiza no ano 1, LP linear em 3 anos e o balanco fecha exato."""
    criar_ambiente_divida(tmp_path)

    resultado = projetar_divida("TEST3", raiz_projeto=tmp_path)
    divida = resultado["divida"]
    dre = resultado["dre"]
    balanco = resultado["balanco"]
    dfc = resultado["dfc"]

    # Juros sobre o saldo INICIAL: 10% x 400 = 40 (captacao nao paga juros
    # no proprio ano — convencao documentada da v2).
    assert divida["ano1"]["juros"] == pytest.approx(40.0)
    # Receita financeira sobre caixa inicial + aplicacoes: 5% x 600 = 30.
    assert divida["ano1"]["receita_financeira_caixa"] == pytest.approx(30.0)
    assert divida["ano1"]["resultado_financeiro"] == pytest.approx(-10.0)

    # Amortizacao ano 1 = CP0 (100) + parcela LP (300/3): 200.
    assert divida["ano1"]["amortizacao"] == pytest.approx(200.0)
    assert divida["ano1"]["captacao"] == pytest.approx(0.0)
    assert divida["ano1"]["divida_bruta"] == pytest.approx(200.0)
    # Reclassificacao: CP do fechamento = amortizacao programada de t+1.
    assert divida["ano1"]["divida_curto_prazo"] == pytest.approx(100.0)
    assert divida["ano1"]["divida_longo_prazo"] == pytest.approx(100.0)
    assert divida["ano1"]["delta_divida"] == pytest.approx(-200.0)

    # DRE: EBT = 100 - 10 = 90; IR = -30,6; LL = 59,4.
    assert dre["ano1"]["ebt"] == pytest.approx(90.0)
    assert dre["ano1"]["lucro_liquido"] == pytest.approx(59.4)

    # Payout 50% da premissa: dividendos = 29,7; PL = 2000 + 59,4 - 29,7.
    assert dfc["ano1"]["dividendos"] == pytest.approx(29.7)
    assert balanco["ano1"]["patrimonio_liquido"] == pytest.approx(2029.7)
    assert resultado["politicas"]["origem_payout"] == "premissa_da_empresa"

    # Caixa via DFC: 500 + FCO(69,4) + FCI(-20) + FCF(-229,7) = 319,7.
    assert dfc["ano1"]["fco"] == pytest.approx(69.4)
    assert dfc["ano1"]["fci"] == pytest.approx(-20.0)
    assert dfc["ano1"]["fcf"] == pytest.approx(-229.7)
    assert balanco["ano1"]["caixa_equivalentes"] == pytest.approx(319.7)

    # Fechamento e VERIFICACAO (sem plug): diferenca ~0 nos 8 anos.
    for ano in range(1, 9):
        assert balanco[f"ano{ano}"]["diferenca_balanco"] == pytest.approx(0.0, abs=1e-6)
    assert resultado["politicas"]["fechamento_ok"] is True


def test_captacao_cobre_caixa_minimo(tmp_path: Path) -> None:
    """Deficit contra o caixa minimo gera captacao nova no fim do ano."""
    criar_ambiente_divida(tmp_path, caixa_minimo_pct=0.5)

    resultado = projetar_divida("TEST3", raiz_projeto=tmp_path)
    divida = resultado["divida"]
    dfc = resultado["dfc"]

    # Caixa pre-captacao do ano 1 = 319,7 < minimo (0,5 x 1000 = 500):
    # capta exatamente a diferenca e fecha o ano no caixa minimo.
    assert divida["ano1"]["captacao"] == pytest.approx(180.3)
    assert dfc["ano1"]["caixa_final"] == pytest.approx(500.0)
    # A captacao entra no fim do ano: nao paga juros no proprio ano.
    assert divida["ano1"]["juros"] == pytest.approx(40.0)
    # Nova divida amortiza a partir do ano seguinte (carencia de 1 ano):
    # CP1 = parcela LP0 (100) + parcela da nova tranche (180,3 / 3).
    assert divida["ano1"]["divida_curto_prazo"] == pytest.approx(100.0 + 60.1)

    for ano in range(1, 9):
        assert resultado["balanco"][f"ano{ano}"]["diferenca_balanco"] == pytest.approx(
            0.0, abs=1e-6
        )


def test_residuais_ancoram_no_bp_real(tmp_path: Path) -> None:
    """outros_ativos/passivos vem do residual do BP real do Ano 0."""
    criar_ambiente_divida(tmp_path)
    # Ativo total maior que os ativos modelados: residuo vira outros_ativos
    # e o passivo residual mantem o fechamento exato.
    caminho_bp = tmp_path / "data" / "raw" / "cvm" / "TEST3_bp.json"
    registros = json.loads(caminho_bp.read_text(encoding="utf-8"))
    for linha in registros:
        if linha["nome_padronizado"] == "ativo_total":
            linha["valor_padronizado"] = 3000.0  # +300 de intangivel/RLP
    salvar_json(caminho_bp, registros)

    resultado = projetar_divida("TEST3", raiz_projeto=tmp_path)
    balanco = resultado["balanco"]

    assert balanco["ano1"]["outros_ativos"] == pytest.approx(300.0)
    # OP = (3000 - 2000) - 300 - 400 = 300.
    assert balanco["ano1"]["outros_passivos"] == pytest.approx(300.0)
    for ano in range(1, 9):
        assert balanco[f"ano{ano}"]["diferenca_balanco"] == pytest.approx(0.0, abs=1e-6)
