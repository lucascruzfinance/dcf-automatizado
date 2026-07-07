"""Testes do checklist de consistencia do valuation."""

from __future__ import annotations

import json
from pathlib import Path

from src.valuation.checklist import executar_checklist


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_meta(
    raiz: Path,
    ticker: str = "TEST3",
    setor: str = "varejo",
) -> None:
    """Cria metadados minimos para identificar empresa nao-financeira."""
    conteudo = {"ticker": ticker, "setor": setor, "tipo": "nao_financeira"}
    salvar_json(raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json", conteudo)
    salvar_json(raiz / "data" / "premissas" / f"{ticker}_premissas.json", conteudo)


def criar_projecao_checklist(
    raiz: Path,
    ticker: str = "TEST3",
    g: float = 0.03,
    wacc: float = 0.12,
    taxa_reinvestimento: float = 0.20,
    vp_vt: float = 100.0,
    soma_vp_fcff: float = 900.0,
    diferenca_balanco_ano1: float = 0.0,
    divida_bruta_ano8: float = 300.0,
    nopat_ano8: float = 66.0,
    roiic_ano8: float | None = None,
    capex_ano8: float = -30.0,
    delta_nwc_todos: float = 0.0,
    acoes_fully_diluted: float = 1000.0,
) -> None:
    """Cria projecao integrada sintetica sem rodar o pipeline."""
    dre = {}
    fcff = {}
    ppe = {}
    balanco = {}
    divida = {}

    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        roiic = 0.0
        if ano == 8:
            roiic = roiic_ano8 if roiic_ano8 is not None else 0.0
        dre[chave_ano] = {
            "ano_projecao": chave_ano,
            "ebitda": 120.0,
        }
        fcff[chave_ano] = {
            "ano_projecao": chave_ano,
            "nopat": nopat_ano8 if ano == 8 else 66.0,
            "delta_nwc": delta_nwc_todos,
            "roiic": roiic,
            "fcff": 80.0,
        }
        ppe[chave_ano] = {
            "ano_projecao": chave_ano,
            "capex": capex_ano8 if ano == 8 else -30.0,
            "depreciacao_amortizacao": 20.0,
        }
        balanco[chave_ano] = {
            "ano_projecao": chave_ano,
            "diferenca_balanco": (diferenca_balanco_ano1 if ano == 1 else 0.0),
            "caixa_equivalentes": 100.0,
            "aplicacoes_financeiras": 50.0,
        }
        divida[chave_ano] = {
            "ano_projecao": chave_ano,
            "divida_bruta": divida_bruta_ano8 if ano == 8 else 300.0,
        }

    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "ano0": {
                "receita_liquida": 1000.0,
                "divida": {"divida_bruta": 300.0},
                "balanco": {
                    "caixa_equivalentes": 100.0,
                    "aplicacoes_financeiras": 50.0,
                },
            },
            "dre": dre,
            "fcff": fcff,
            "wacc": {"wacc": wacc},
            "valor_terminal": {
                "g": g,
                "wacc": wacc,
                "taxa_reinvestimento": taxa_reinvestimento,
                "vp_vt": vp_vt,
                "soma_vp_fcff": soma_vp_fcff,
                "pct_ev_perpetuidade": vp_vt / (soma_vp_fcff + vp_vt),
            },
            "ev_equity": {"acoes_fully_diluted": acoes_fully_diluted},
            "balanco": balanco,
            "ppe": ppe,
            "divida": divida,
        },
    )


def item_por_id(resultado: dict, identificador: str) -> dict:
    """Busca um item pelo id no resultado do checklist."""
    return next(item for item in resultado["itens"] if item["id"] == identificador)


def test_u1_g_maior_wacc_reprova(tmp_path: Path) -> None:
    """g maior que WACC deve reprovar o checklist."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, g=0.12, wacc=0.10)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "U1")["status"] == "ERRO"
    assert resultado["aprovado"] is False


def test_u2_g_acima_5pct_alerta(tmp_path: Path) -> None:
    """g acima de 5% gera alerta, mas nao reprova se g < WACC."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, g=0.06, wacc=0.12)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "U2")["status"] == "ALERTA"
    assert resultado["aprovado"] is True


def test_u3_taxa_reinvestimento_fora_do_intervalo_reprova(tmp_path: Path) -> None:
    """Taxa de reinvestimento acima de 100% deve reprovar o checklist."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, taxa_reinvestimento=1.5)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "U3")["status"] == "ERRO"
    assert resultado["aprovado"] is False


def test_u5_acoes_fully_diluted_nao_positivas_reprova(tmp_path: Path) -> None:
    """Acoes fully diluted iguais a zero devem reprovar o checklist."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, acoes_fully_diluted=0.0)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "U5")["status"] == "ERRO"
    assert resultado["aprovado"] is False


def test_u4_perpetuidade_acima_85pct(tmp_path: Path) -> None:
    """VP(VT) com 90% do EV deve gerar alerta."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, vp_vt=900.0, soma_vp_fcff=100.0)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "U4")["status"] == "ALERTA"


def test_nf1_balanco_aberto_reprova(tmp_path: Path) -> None:
    """Balanco aberto acima da tolerancia deve reprovar."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, diferenca_balanco_ano1=5.0)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "NF1")["status"] == "ERRO"
    assert resultado["aprovado"] is False


def test_nf2_roiic_acima_de_50pct_alerta(tmp_path: Path) -> None:
    """ROIIC implicito de 100% no ano 8 deve gerar alerta sem reprovar."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, roiic_ano8=1.0)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "NF2")["status"] == "ALERTA"
    assert resultado["aprovado"] is True


def test_nf3_capex_abaixo_da_depreciacao_alerta(tmp_path: Path) -> None:
    """CAPEX do ano 8 menor que a D&A deve alertar sobre a perpetuidade."""
    criar_meta(tmp_path)
    # |CAPEX ano8| = 10 < D&A ano8 = 20 -> perpetuidade encolhe o ativo.
    criar_projecao_checklist(tmp_path, capex_ano8=-10.0)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "NF3")["status"] == "ALERTA"
    assert resultado["aprovado"] is True


def test_nf4_fco_ebitda_abaixo_de_07x_alerta(tmp_path: Path) -> None:
    """FCO/EBITDA abaixo de 0,7x em todos os anos deve gerar alerta."""
    criar_meta(tmp_path)
    # FCO ~= 120 - 20 - 66 x (0,34/0,66) = 66; razao 66/120 = 0,55x < 0,7x.
    criar_projecao_checklist(tmp_path, delta_nwc_todos=20.0)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "NF4")["status"] == "ALERTA"
    assert resultado["aprovado"] is True


def test_nf5_alavancagem_alta_alerta(tmp_path: Path) -> None:
    """Divida liquida / EBITDA de 5x no ano 8 deve alertar."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path, divida_bruta_ano8=750.0)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)

    assert item_por_id(resultado, "NF5")["status"] == "ALERTA"
    assert resultado["aprovado"] is True


def test_checklist_valido_aprovado(tmp_path: Path) -> None:
    """Checklist sem erros deve aprovar e persistir o bloco checklist."""
    criar_meta(tmp_path)
    criar_projecao_checklist(tmp_path)

    resultado = executar_checklist("TEST3", raiz_projeto=tmp_path)
    caminho = tmp_path / "data" / "processed" / "TEST3_projecao.json"
    persistido = json.loads(caminho.read_text(encoding="utf-8"))

    assert resultado["aprovado"] is True
    assert [item for item in resultado["itens"] if item["status"] == "ERRO"] == []
    assert persistido["checklist"]["aprovado"] is True
