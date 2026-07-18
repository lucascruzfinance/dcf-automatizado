"""Testes do auditor de amarracao historica contra a CVM (fixtures sinteticas).

Cobrem as checagens do Prompt 9.0.1 sem rede e sem depender de dados reais:
balanco que fecha -> OK; balanco com furo -> ERRO apontando a diferenca;
residual grande -> AVISO; DFC que nao amarra -> ERRO; identidade da DRE que
so fecha invertendo um sinal -> AVISO explicado; modo estrito -> raise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.coleta.auditor_cvm import auditar_empresa

EXERCICIO = "2025-12-31"


def _linha(
    codigo: str,
    descricao: str,
    valor: float,
    nome: str | None,
    demonstracao: str,
) -> dict:
    """Linha bruta minima no formato persistido pela coleta."""
    return {
        "CD_CONTA": codigo,
        "DS_CONTA": descricao,
        "VL_CONTA": valor,
        "DT_FIM_EXERC": EXERCICIO,
        "ORDEM_EXERC": "ÚLTIMO",
        "ano_arquivo": 2026,
        "ESCALA_MOEDA": "MIL",
        "nome_padronizado": nome,
        "sinal_esperado": None,
        "valor_padronizado": valor,
        "demonstracao_padronizada": demonstracao,
    }


def _bp_que_fecha(furo_no_ativo: float = 0.0) -> list[dict]:
    """BP sintetico 1000 = 400 PC + 300 PNC + 300 PL (opcionalmente furado)."""
    return [
        _linha("1", "Ativo Total", 1000.0 + furo_no_ativo, "ativo_total", "bp_ativo"),
        _linha("1.01", "Ativo Circulante", 600.0, "ativo_circulante", "bp_ativo"),
        _linha("1.01.01", "Caixa", 200.0, "caixa_equivalentes", "bp_ativo"),
        _linha("1.01.03", "Contas a Receber", 250.0, "contas_receber", "bp_ativo"),
        _linha("1.01.04", "Estoques", 150.0, "estoques", "bp_ativo"),
        _linha(
            "1.02",
            "Ativo Nao Circulante",
            400.0 + furo_no_ativo,
            "ativo_nao_circulante",
            "bp_ativo",
        ),
        _linha(
            "1.02.03",
            "Imobilizado",
            400.0 + furo_no_ativo,
            "imobilizado",
            "bp_ativo",
        ),
        _linha("2", "Passivo Total", 1000.0, "passivo_total", "bp_passivo"),
        _linha("2.01", "Passivo Circulante", 400.0, "passivo_circulante", "bp_passivo"),
        _linha("2.01.02", "Fornecedores", 400.0, "fornecedores", "bp_passivo"),
        _linha(
            "2.02",
            "Passivo Nao Circulante",
            300.0,
            "passivo_nao_circulante",
            "bp_passivo",
        ),
        _linha(
            "2.02.01",
            "Emprestimos",
            300.0,
            "divida_longo_prazo",
            "bp_passivo",
        ),
        _linha("2.03", "Patrimonio Liquido", 300.0, "patrimonio_liquido", "bp_passivo"),
    ]


def _dfc_que_amarra() -> list[dict]:
    """DFC sintetico amarrado ao caixa do BP (200 = 150 + 50)."""
    return [
        _linha("6.01", "FCO", 120.0, "fco", "dfc"),
        _linha("6.02", "FCI", -40.0, "fci", "dfc"),
        _linha("6.03", "FCF", -30.0, "fcf", "dfc"),
        _linha("6.05", "Variacao de Caixa", 50.0, "variacao_caixa", "dfc"),
        _linha("6.05.01", "Saldo Inicial", 150.0, "caixa_inicial_dfc", "dfc"),
        _linha("6.05.02", "Saldo Final", 200.0, "caixa_final_dfc", "dfc"),
    ]


def _dre_coerente() -> list[dict]:
    """DRE sintetica com as identidades fechadas (sinais como divulgados)."""
    return [
        _linha("3.01", "Receita Liquida", 500.0, "receita_liquida", "dre"),
        _linha("3.02", "CPV", -300.0, "cpv_cmv", "dre"),
        _linha("3.03", "Lucro Bruto", 200.0, "lucro_bruto", "dre"),
    ]


def _persistir(pasta: Path, ticker: str, bp: list, dre: list, dfc: list) -> None:
    """Grava os 3 JSONs brutos no layout data/raw/cvm/."""
    destino = pasta / "data" / "raw" / "cvm"
    destino.mkdir(parents=True, exist_ok=True)
    for nome, linhas in (("bp", bp), ("dre", dre), ("dfc", dfc)):
        with (destino / f"{ticker}_{nome}.json").open("w", encoding="utf-8") as arquivo:
            json.dump(linhas, arquivo, ensure_ascii=False)


def test_balanco_que_fecha_gera_ok(tmp_path: Path) -> None:
    """BP amarrado + DFC amarrado -> nenhum ERRO e status geral OK."""
    _persistir(tmp_path, "TEST3", _bp_que_fecha(), _dre_coerente(), _dfc_que_amarra())
    laudo = auditar_empresa("TEST3", tmp_path, persistir=False)

    assert laudo["contagem"]["ERRO"] == 0
    assert laudo["status_geral"] == "OK"
    fechamentos = [
        item
        for item in laudo["itens"]
        if item["categoria"] == "balanco_fecha"
        and "Ativo Total = Passivo" in item["descricao"]
    ]
    assert fechamentos and all(item["status"] == "OK" for item in fechamentos)


def test_balanco_com_furo_gera_erro_apontando_diferenca(tmp_path: Path) -> None:
    """Furo de 50 no ativo vira ERRO com a diferenca exata nos detalhes."""
    _persistir(
        tmp_path, "TEST3", _bp_que_fecha(furo_no_ativo=50.0), [], _dfc_que_amarra()
    )
    laudo = auditar_empresa("TEST3", tmp_path, persistir=False)

    assert laudo["status_geral"] == "ERRO"
    erro = next(
        item
        for item in laudo["itens"]
        if item["status"] == "ERRO" and item["categoria"] == "balanco_fecha"
    )
    assert erro["detalhes"]["diferenca"] == pytest.approx(50.0)


def test_residual_grande_gera_aviso_de_cobertura(tmp_path: Path) -> None:
    """Folha sem nome com 25% do ativo -> AVISO de cobertura com a conta."""
    bp = _bp_que_fecha()
    # Troca os 250 de contas a receber por uma folha NAO mapeada (sem nome).
    for linha in bp:
        if linha["CD_CONTA"] == "1.01.03":
            linha["nome_padronizado"] = None
            linha["DS_CONTA"] = "Conta Misteriosa"
    _persistir(tmp_path, "TEST3", bp, _dre_coerente(), _dfc_que_amarra())
    laudo = auditar_empresa("TEST3", tmp_path, persistir=False)

    aviso = next(
        item
        for item in laudo["itens"]
        if item["categoria"] == "cobertura" and item["status"] == "AVISO"
    )
    assert aviso["detalhes"]["pct"] == pytest.approx(0.25)
    maiores = aviso["detalhes"]["maiores_residuais"]
    assert any(residual["conta_cvm"] == "Conta Misteriosa" for residual in maiores)


def test_dfc_que_nao_amarra_gera_erro(tmp_path: Path) -> None:
    """Caixa final do DFC longe do caixa do BP (e das aplicacoes) -> ERRO."""
    dfc = _dfc_que_amarra()
    for linha in dfc:
        if linha["CD_CONTA"] == "6.05.02":
            linha["VL_CONTA"] = 900.0  # caixa do BP e 200
    _persistir(tmp_path, "TEST3", _bp_que_fecha(), _dre_coerente(), dfc)
    laudo = auditar_empresa("TEST3", tmp_path, persistir=False)

    erros_dfc = [
        item
        for item in laudo["itens"]
        if item["categoria"] == "dfc_amarra" and item["status"] == "ERRO"
    ]
    assert any("nao amarra ao caixa do BP" in item["descricao"] for item in erros_dfc)


def test_identidade_dre_com_sinal_invertido_vira_aviso(tmp_path: Path) -> None:
    """CPV divulgado positivo (padrao VALE 2022) -> AVISO explicado, nao ERRO."""
    dre = _dre_coerente()
    for linha in dre:
        if linha["CD_CONTA"] == "3.02":
            linha["VL_CONTA"] = 300.0  # fora da convencao (custo positivo)
    _persistir(tmp_path, "TEST3", _bp_que_fecha(), dre, _dfc_que_amarra())
    laudo = auditar_empresa("TEST3", tmp_path, persistir=False)

    item = next(
        item
        for item in laudo["itens"]
        if item["categoria"] == "subtotais" and "lucro_bruto" in item["descricao"]
    )
    assert item["status"] == "AVISO"
    assert item["detalhes"]["sinal_divulgado_fora_da_convencao"] == "3.02"


def test_modo_estrito_levanta_no_primeiro_erro(tmp_path: Path) -> None:
    """--estrito transforma ERRO em RuntimeError (uso em CI)."""
    _persistir(
        tmp_path, "TEST3", _bp_que_fecha(furo_no_ativo=50.0), [], _dfc_que_amarra()
    )
    with pytest.raises(RuntimeError, match="ESTRITA"):
        auditar_empresa("TEST3", tmp_path, persistir=False, estrito=True)


def test_bp_aberto_persistido_para_o_excel(tmp_path: Path) -> None:
    """O laudo persiste a decomposicao bp_aberto (fonte do Excel 9.0.5)."""
    _persistir(tmp_path, "TEST3", _bp_que_fecha(), _dre_coerente(), _dfc_que_amarra())
    laudo = auditar_empresa("TEST3", tmp_path, persistir=True)

    caminho = tmp_path / "data" / "raw" / "cvm" / "TEST3_auditoria_cvm.json"
    assert caminho.exists()
    persistido = json.loads(caminho.read_text(encoding="utf-8"))
    secoes = persistido["bp_aberto"][EXERCICIO]
    assert secoes["ativo_circulante"]["nomeadas"]["caixa_equivalentes"] == 200.0
    assert secoes["ativo_circulante"]["total_cvm"] == 600.0
    assert laudo["exercicios_auditados"] == [EXERCICIO]
