"""Testes do schedule de capital de giro da Semana 2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.schedule_wk import projetar_wk


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_mapeamento_wk_minimo(raiz: Path) -> None:
    """Cria o mapeamento minimo exigido pelo schedule WK."""
    campos = {
        "ano_projecao": {},
        "contas_receber": {},
        "estoques": {},
        "fornecedores": {},
        "nwc": {},
        "delta_nwc": {},
        "modo_capital_giro": {},
    }
    salvar_json(raiz / "config" / "mapeamento_cvm.json", {"campos": campos})


def criar_premissas_wk(
    raiz: Path,
    ticker: str = "TEST3",
    setor: str = "varejo",
    modo_capital_giro: str | None = None,
    teto_delta_nwc_receita: float | None = None,
) -> None:
    """Cria premissas com prazos medios em dias."""
    premissas = {
        "ticker": ticker,
        "setor": setor,
        "tipo": "nao_financeira",
        "dso": 36.5,
        "dio": 73.0,
        "dpo": 36.5,
    }
    if modo_capital_giro is not None:
        premissas["modo_capital_giro"] = modo_capital_giro
    if teto_delta_nwc_receita is not None:
        premissas["teto_delta_nwc_receita"] = teto_delta_nwc_receita
    salvar_json(raiz / "data" / "premissas" / f"{ticker}_premissas.json", premissas)


def criar_projecao_dre(
    raiz: Path,
    ticker: str = "TEST3",
    receitas: list[float] | None = None,
) -> None:
    """Cria DRE projetada minima com oito anos de receita."""
    dre = {}
    for ano in range(1, 9):
        receita = receitas[ano - 1] if receitas is not None else 900.0 + (ano * 100.0)
        dre[f"ano{ano}"] = {
            "ano_projecao": f"ano{ano}",
            "receita_liquida": receita,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "ano0": {"receita_liquida": 1000.0},
            "dre": dre,
        },
    )


def criar_meta_wk(
    raiz: Path,
    ticker: str = "TEST3",
    setor: str = "varejo",
) -> None:
    """Cria metadados minimos para detectar o modo de giro."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {"ticker": ticker, "setor": setor, "tipo": "nao_financeira"},
    )


def criar_base_historica_wk(
    raiz: Path,
    ticker: str = "TEST3",
    contas_receber: float = 100.0,
    estoques: float = 80.0,
    fornecedores: float = -60.0,
    receita_ano0: float = 1000.0,
    cpv: float = -400.0,
) -> None:
    """Cria saldos historicos CVM minimos para Ano 0 e indice CPV/receita."""
    base = {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
    }
    bp = [
        {
            **base,
            "CD_CONTA": "1.01.03",
            "nome_padronizado": "contas_receber",
            "valor_padronizado": contas_receber,
        },
        {
            **base,
            "CD_CONTA": "1.01.04",
            "nome_padronizado": "estoques",
            "valor_padronizado": estoques,
        },
        {
            **base,
            "CD_CONTA": "2.01.02",
            "nome_padronizado": "fornecedores",
            "valor_padronizado": fornecedores,
        },
    ]
    dre = [
        {
            **base,
            "CD_CONTA": "3.01",
            "nome_padronizado": "receita_liquida",
            "valor_padronizado": receita_ano0,
        },
        {
            **base,
            "CD_CONTA": "3.02",
            "nome_padronizado": "cpv_cmv",
            "valor_padronizado": cpv,
        },
    ]
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json", bp)
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_dre.json", dre)


def test_modo_dias_ciclo_curto_preservado(tmp_path: Path) -> None:
    """Valida formulas de saldos em dias e Delta NWC como consumo."""
    criar_mapeamento_wk_minimo(tmp_path)
    criar_premissas_wk(tmp_path)
    criar_meta_wk(tmp_path)
    criar_projecao_dre(tmp_path)
    criar_base_historica_wk(tmp_path)

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    wk = resultado["wk"]

    assert resultado["ano0_wk"]["nwc"] == pytest.approx(120.0)
    assert wk["ano1"]["contas_receber"] == pytest.approx(100.0)
    assert wk["ano1"]["estoques"] == pytest.approx(80.0)
    assert wk["ano1"]["fornecedores"] == pytest.approx(-40.0)
    assert wk["ano1"]["nwc"] == pytest.approx(140.0)
    assert wk["ano1"]["delta_nwc"] == pytest.approx(20.0)
    assert wk["ano1"]["modo_capital_giro"] == "dias"
    assert wk["ano2"]["delta_nwc"] == pytest.approx(14.0)

    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    persistido = json.loads(caminho.read_text(encoding="utf-8"))
    assert persistido["ano0"]["wk"]["nwc"] == pytest.approx(120.0)
    assert persistido["wk"]["ano1"]["delta_nwc"] == pytest.approx(20.0)


def test_modo_ancorado_construtora_sem_salto_de_giro(tmp_path: Path) -> None:
    """Construtora deve escalar NWC por receita, sem liberar todo o ano0."""
    criar_mapeamento_wk_minimo(tmp_path)
    criar_premissas_wk(tmp_path, setor="construcao")
    criar_meta_wk(tmp_path, setor="construcao")
    criar_projecao_dre(tmp_path, receitas=[1100.0] + [1200.0] * 7)
    criar_base_historica_wk(
        tmp_path,
        contas_receber=3000.0,
        estoques=1000.0,
        fornecedores=-870.0,
    )

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    wk = resultado["wk"]

    nwc_ano0 = 3130.0
    nwc_ano1 = nwc_ano0 / 1000.0 * 1100.0
    assert resultado["modo_capital_giro"] == "percentual_receita"
    assert wk["ano1"]["modo_capital_giro"] == "percentual_receita"
    assert wk["ano1"]["nwc"] == pytest.approx(nwc_ano1)
    assert wk["ano1"]["delta_nwc"] == pytest.approx(nwc_ano1 - nwc_ano0)
    assert wk["ano1"]["delta_nwc"] > 0


def test_salvaguarda_trunca_delta_nwc_ano1(tmp_path: Path) -> None:
    """Delta NWC do ano1 deve respeitar o teto sobre receita."""
    criar_mapeamento_wk_minimo(tmp_path)
    criar_premissas_wk(tmp_path, setor="construcao")
    criar_meta_wk(tmp_path, setor="construcao")
    criar_projecao_dre(tmp_path, receitas=[100.0] + [120.0] * 7)
    criar_base_historica_wk(
        tmp_path,
        contas_receber=4000.0,
        estoques=1500.0,
        fornecedores=-500.0,
    )

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    delta_ano1 = float(resultado["wk"]["ano1"]["delta_nwc"])
    limite = 0.50 * 100.0

    assert abs(delta_ano1) <= limite
    assert delta_ano1 == pytest.approx(-limite)
    assert resultado["wk"]["ano1"]["nwc"] == pytest.approx(4950.0)


# ---------------------------------------------------------------------------
# Modo MULTI-DRIVER (WK expandido — Prompt 9.0.2.3, padrao Direcional)
# ---------------------------------------------------------------------------


def criar_ambiente_multi_driver(raiz: Path, ir_ano0: float = -100.0) -> None:
    """Ambiente do WK expandido: BP com as contas novas + DRE com drivers.

    Numeros redondos em estado estacionario (RL constante = ano0) para os
    dias implicitos reproduzirem exatamente os saldos do Ano 0.
    """
    criar_mapeamento_wk_minimo(raiz)
    salvar_json(
        raiz / "data" / "premissas" / "TEST3_premissas.json",
        {
            "ticker": "TEST3",
            "setor": "varejo",
            "tipo": "nao_financeira",
            "modo_capital_giro": "dias_multi_driver",
        },
    )
    criar_meta_wk(raiz)
    base = {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
    }
    bp = [
        {
            **base,
            "CD_CONTA": "1.01.03",
            "nome_padronizado": "contas_receber",
            "valor_padronizado": 100.0,
        },
        {
            **base,
            "CD_CONTA": "1.01.04",
            "nome_padronizado": "estoques",
            "valor_padronizado": 80.0,
        },
        {
            **base,
            "CD_CONTA": "1.01.06",
            "nome_padronizado": "tributos_a_recuperar",
            "valor_padronizado": 50.0,
        },
        {
            **base,
            "CD_CONTA": "2.01.02",
            "nome_padronizado": "fornecedores",
            "valor_padronizado": -60.0,
        },
        {
            **base,
            "CD_CONTA": "2.01.01",
            "nome_padronizado": "obrigacoes_sociais_trabalhistas",
            "valor_padronizado": -30.0,
        },
        {
            **base,
            "CD_CONTA": "2.01.05.02.04",
            "nome_padronizado": "adiantamento_clientes",
            "valor_padronizado": -20.0,
        },
    ]
    salvar_json(raiz / "data" / "raw" / "cvm" / "TEST3_bp.json", bp)
    dre_raw = [
        {
            **base,
            "CD_CONTA": "3.01",
            "nome_padronizado": "receita_liquida",
            "valor_padronizado": 1000.0,
        },
        {
            **base,
            "CD_CONTA": "3.02",
            "nome_padronizado": "cpv_cmv",
            "valor_padronizado": -400.0,
        },
        {
            **base,
            "CD_CONTA": "3.08",
            "nome_padronizado": "ir_csll",
            "valor_padronizado": ir_ano0,
        },
        {
            **base,
            "CD_CONTA": "3.04.01",
            "nome_padronizado": "despesas_vendas",
            "valor_padronizado": -80.0,
        },
        {
            **base,
            "CD_CONTA": "3.04.02",
            "nome_padronizado": "despesas_gerais_administrativas",
            "valor_padronizado": -40.0,
        },
    ]
    salvar_json(raiz / "data" / "raw" / "cvm" / "TEST3_dre.json", dre_raw)
    dre_projetada = {}
    for ano in range(1, 9):
        dre_projetada[f"ano{ano}"] = {
            "ano_projecao": f"ano{ano}",
            "receita_liquida": 1000.0,
            "cpv_cmv": -400.0,
            "ir_csll": -100.0,
            "sgna": -120.0,
        }
    salvar_json(
        raiz / "data" / "processed" / "TEST3_projecao.json",
        {
            "ticker": "TEST3",
            "tipo": "nao_financeira",
            "setor": "varejo",
            "modo_dre": "completo",
            "ano0": {"receita_liquida": 1000.0},
            "dre": dre_projetada,
        },
    )


def test_multi_driver_projeta_as_contas_novas_com_drivers_corretos(
    tmp_path: Path,
) -> None:
    """WK expandido: 6 contas, cada uma pelo SEU driver (dias implicitos).

    Estado estacionario: os saldos projetados reproduzem o Ano 0 e o
    delta_nwc e zero em todos os anos.
    """
    criar_ambiente_multi_driver(tmp_path)

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    assert resultado["modo_capital_giro"] == "dias_multi_driver"
    dias = resultado["dias_multi_driver"]

    # Drivers nominais corretos (Direcional Modelo L144-L180).
    assert dias["contas_receber"]["driver"] == "receita_liquida"
    assert dias["estoques"]["driver"] == "cpv"
    assert dias["tributos_a_recuperar"]["driver"] == "ir_csll"
    assert dias["fornecedores"]["driver"] == "cpv"
    assert dias["obrigacoes_sociais_trabalhistas"]["driver"] == "sgna"
    assert dias["adiantamento_clientes"]["driver"] == "receita_liquida"

    a1 = resultado["wk"]["ano1"]
    # Estado estacionario: saldos = Ano 0 (dias implicitos exatos).
    assert a1["contas_receber"] == pytest.approx(100.0)
    assert a1["estoques"] == pytest.approx(80.0)
    assert a1["tributos_a_recuperar"] == pytest.approx(50.0)
    assert a1["fornecedores"] == pytest.approx(-60.0)
    assert a1["obrigacoes_sociais_trabalhistas"] == pytest.approx(-30.0)
    assert a1["adiantamento_clientes"] == pytest.approx(-20.0)
    # NWC = (100 + 80 + 50) - (60 + 30 + 20) = 120; delta = 0.
    assert a1["nwc"] == pytest.approx(120.0)
    for ano in range(1, 9):
        assert resultado["wk"][f"ano{ano}"]["delta_nwc"] == pytest.approx(0.0)


def test_multi_driver_premissa_de_dias_sobrescreve_historico(
    tmp_path: Path,
) -> None:
    """Premissa dias_* explicita vence a media historica implicita."""
    criar_ambiente_multi_driver(tmp_path)
    caminho = tmp_path / "data" / "premissas" / "TEST3_premissas.json"
    premissas = json.loads(caminho.read_text(encoding="utf-8"))
    premissas["dias_impostos_recuperar"] = 36.5
    salvar_json(caminho, premissas)

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    dias = resultado["dias_multi_driver"]["tributos_a_recuperar"]
    assert dias["origem"] == "premissa_da_empresa"
    # 36,5 dias de IR (100/ano) => saldo = 36,5/365 x 100 = 10.
    assert resultado["wk"]["ano1"]["tributos_a_recuperar"] == pytest.approx(10.0)


def test_multi_driver_fallback_para_receita_quando_driver_instavel(
    tmp_path: Path,
) -> None:
    """Dias implicitos > 365 pelo driver nominal caem para a receita liquida
    (salvaguarda: tributos de varejo sao ICMS/PIS/COFINS, nao IR)."""
    criar_ambiente_multi_driver(tmp_path, ir_ano0=-5.0)

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    dias = resultado["dias_multi_driver"]["tributos_a_recuperar"]
    # 50 / 5 x 365 = 3.650 dias > 365 => driver vira receita (18,25 dias).
    assert dias["driver"] == "receita_liquida"
    assert dias["origem"] == "fallback_driver_instavel_para_receita"
    assert dias["dias"] == pytest.approx(18.25)
    # Saldo pelo driver receita: 18,25/365 x 1000 = 50 (reproduz o Ano 0).
    assert resultado["wk"]["ano1"]["tributos_a_recuperar"] == pytest.approx(50.0)


def test_modos_antigos_nao_exigem_dias_novos(tmp_path: Path) -> None:
    """Arquivo v2 (so DSO/DIO/DPO, sem modo) segue no modo dias byte a byte."""
    criar_mapeamento_wk_minimo(tmp_path)
    criar_premissas_wk(tmp_path)
    criar_meta_wk(tmp_path)
    criar_projecao_dre(tmp_path, receitas=[1000.0] * 8)
    criar_base_historica_wk(tmp_path)

    resultado = projetar_wk("TEST3", raiz_projeto=tmp_path)
    assert resultado["modo_capital_giro"] == "dias"
    assert "tributos_a_recuperar" not in resultado["wk"]["ano1"]
