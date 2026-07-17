"""Testes do schedule de arrendamento IFRS-16 (Prompt 8.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.projecao.schedule_leasing import projetar_leasing


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_parametros(raiz: Path) -> None:
    """parametros.json minimo com o bloco leasing."""
    salvar_json(
        raiz / "config" / "parametros.json",
        {
            "leasing": {
                "limiar_leasing_relevante_pct_ativo": 0.01,
                "spread_arrendamento_sobre_cdi": 0.02,
                "clamp_taxa_min_sobre_cdi_pp": -0.02,
                "clamp_taxa_max_sobre_cdi_pp": 0.08,
                "prazo_medio_leasing_min_anos": 2,
                "prazo_medio_leasing_max_anos": 15,
                "prazo_medio_leasing_padrao_anos": 5,
            }
        },
    )


def criar_projecao(raiz: Path, ticker: str = "TEST3", da_imob: float = 100.0) -> None:
    """Projecao com DRE e PP&E (da_imobilizado) ja calculados."""
    dre = {}
    ppe = {}
    for ano in range(1, 9):
        chave = f"ano{ano}"
        dre[chave] = {
            "ano_projecao": chave,
            "receita_liquida": 1000.0,
            "ebitda": 300.0,
            "ebit": 200.0,
            "da_imobilizado": da_imob,
            "da_intangivel": 0.0,
            "depreciacao_amortizacao": da_imob,
            "resultado_financeiro": 0.0,
        }
        ppe[chave] = {
            "ano_projecao": chave,
            "da_imobilizado": da_imob,
            "da_intangivel": 0.0,
            "imobilizado": 1000.0,
            "intangivel": 0.0,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "modo_dre": "legado",
            "ano0": {"ppe": {"imobilizado": 1000.0, "da_historica": 100.0}},
            "dre": dre,
            "ppe": ppe,
        },
    )


def linha_bp(
    cd_conta: str, ds_conta: str, nome: str, valor: float
) -> dict[str, object]:
    """Monta uma linha bruta do BP."""
    return {
        "ano_arquivo": 2025,
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
        "CD_CONTA": cd_conta,
        "DS_CONTA": ds_conta,
        "nome_padronizado": nome,
        "valor_padronizado": valor,
    }


def criar_bp(raiz: Path, ticker: str = "TEST3", passivo_total: float = 500.0) -> None:
    """BP com passivo de arrendamento em 2 sub-contas e direito de uso."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_bp.json",
        [
            linha_bp("1", "Ativo Total", "ativo_total", 5000.0),
            linha_bp("1.02.03", "Imobilizado", "imobilizado", 1000.0),
            linha_bp(
                "1.02.03.02", "Direito de Uso em Arrendamento", "imobilizado", 400.0
            ),
            linha_bp(
                "2.01.05.01",
                "Passivo por arrendamento CP",
                "passivo_arrendamento",
                -(passivo_total * 0.4),
            ),
            linha_bp(
                "2.02.02.01",
                "Passivo por arrendamento LP",
                "passivo_arrendamento",
                -(passivo_total * 0.6),
            ),
        ],
    )


def criar_premissas(raiz: Path, ticker: str = "TEST3") -> None:
    """Premissas minimas (leasing derivado das ancoras, sem overrides)."""
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        {"ticker": ticker, "tipo": "nao_financeira"},
    )


def montar_ambiente(raiz: Path, passivo_total: float = 500.0) -> None:
    """Fixtures comuns do schedule de leasing."""
    criar_parametros(raiz)
    criar_projecao(raiz)
    criar_bp(raiz, passivo_total=passivo_total)
    criar_premissas(raiz)


def test_leasing_rollforward_e_juros(tmp_path: Path) -> None:
    """Leasing relevante: juros sobre saldo de abertura e D&A do direito de uso
    reclassificada proporcionalmente (direito_uso / imobilizado)."""
    montar_ambiente(tmp_path, passivo_total=500.0)

    resultado = projetar_leasing("TEST3", raiz_projeto=tmp_path)
    assert resultado["relevante"] is True
    assert resultado["ano0"]["passivo_arrendamento"] == pytest.approx(500.0)
    assert resultado["ano0"]["direito_uso_ativo"] == pytest.approx(400.0)
    # proporcao = 400 / 1000 = 0,40 => da_direito_uso ano1 = 0,40 x 100 = 40.
    assert resultado["proporcao_direito_uso"] == pytest.approx(0.40)
    l1 = resultado["leasing"]["ano1"]
    assert float(l1["da_direito_uso"]) == pytest.approx(40.0)
    # juros ano1 = taxa x passivo de ABERTURA (500).
    taxa = resultado["taxa_arrendamento"]
    assert float(l1["juros_arrendamento"]) == pytest.approx(taxa * 500.0)

    # A DRE reclassifica: da_imobilizado reduz em da_direito_uso; total intacto.
    dre1 = resultado["dre"]["ano1"]
    assert float(dre1["da_direito_uso"]) == pytest.approx(40.0)
    assert float(dre1["da_imobilizado"]) == pytest.approx(60.0)
    assert float(dre1["depreciacao_amortizacao"]) == pytest.approx(100.0)
    assert float(dre1["juros_arrendamento"]) == pytest.approx(taxa * 500.0)


def test_leasing_zera_sem_arrendamento_relevante(tmp_path: Path) -> None:
    """Passivo abaixo do limiar (1% do ativo) => bloco zerado, sem erro."""
    # ativo 5000 -> limiar 50; passivo 10 < 50 => nao relevante.
    montar_ambiente(tmp_path, passivo_total=10.0)

    resultado = projetar_leasing("TEST3", raiz_projeto=tmp_path)
    assert resultado["relevante"] is False
    for ano in range(1, 9):
        chave = f"ano{ano}"
        assert float(resultado["leasing"][chave]["juros_arrendamento"]) == 0.0
        assert float(resultado["leasing"][chave]["da_direito_uso"]) == 0.0
        assert float(resultado["dre"][chave]["da_direito_uso"]) == 0.0


def test_leasing_fallback_direito_uso_igual_passivo(tmp_path: Path) -> None:
    """Sem ativo de direito de uso no BP, estima direito de uso = passivo."""
    criar_parametros(tmp_path)
    criar_projecao(tmp_path)
    criar_premissas(tmp_path)
    # BP sem a linha 'Direito de Uso'.
    salvar_json(
        tmp_path / "data" / "raw" / "cvm" / "TEST3_bp.json",
        [
            linha_bp("1", "Ativo Total", "ativo_total", 5000.0),
            linha_bp("1.02.03", "Imobilizado", "imobilizado", 1000.0),
            linha_bp(
                "2.02.02.01", "Passivo por arrendamento", "passivo_arrendamento", -500.0
            ),
        ],
    )

    resultado = projetar_leasing("TEST3", raiz_projeto=tmp_path)
    assert resultado["ano0"]["origem_direito_uso"] == "fallback_passivo_arrendamento"
    assert resultado["ano0"]["direito_uso_ativo"] == pytest.approx(500.0)
