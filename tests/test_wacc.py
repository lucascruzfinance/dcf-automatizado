"""Testes do calculador de WACC (BRL nominal)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.valuation.calculador_wacc import calcular_kd_historico, calcular_wacc


def salvar_json(caminho: Path, conteudo: object) -> None:
    """Salva JSON auxiliar para montar fixtures temporarias."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def criar_meta_e_premissas(
    raiz: Path,
    ticker: str = "TEST3",
    setor: str = "varejo",
    beta_desalavancado: float = 1.0,
    erp_eua: float = 0.05,
    crp_brasil: float = 0.03,
    ipca: float = 0.045,
    cpi_eua: float = 0.020,
) -> None:
    """Cria metadados e premissas minimos com os nomes canonicos da Semana 3."""
    salvar_json(
        raiz / "data" / "raw" / "cvm" / f"{ticker}_meta.json",
        {"ticker": ticker, "setor": setor, "tipo": "nao_financeira"},
    )
    salvar_json(
        raiz / "data" / "premissas" / f"{ticker}_premissas.json",
        {
            "ticker": ticker,
            "setor": setor,
            "tipo": "nao_financeira",
            "beta_desalavancado": beta_desalavancado,
            "erp_eua": erp_eua,
            "crp_brasil": crp_brasil,
            "ipca_longo_prazo": ipca,
            "cpi_eua_longo_prazo": cpi_eua,
        },
    )


def criar_projecao_wacc(
    raiz: Path,
    ticker: str = "TEST3",
    divida_bruta: float = 300.0,
    patrimonio_liquido: float = 700.0,
) -> None:
    """Cria projecao integrada minima com blocos divida e balanco."""
    divida = {}
    balanco = {}
    for ano in range(1, 9):
        chave_ano = f"ano{ano}"
        divida[chave_ano] = {
            "ano_projecao": chave_ano,
            "divida_bruta": divida_bruta,
        }
        balanco[chave_ano] = {
            "ano_projecao": chave_ano,
            "patrimonio_liquido": patrimonio_liquido,
        }
    salvar_json(
        raiz / "data" / "processed" / f"{ticker}_projecao.json",
        {
            "ticker": ticker,
            "tipo": "nao_financeira",
            "setor": "varejo",
            "divida": divida,
            "balanco": balanco,
        },
    )


def test_wacc_em_faixa_razoavel(tmp_path: Path) -> None:
    """WACC calculado deve ficar entre 5% e 30% para inputs plausiveis."""
    criar_meta_e_premissas(tmp_path)
    criar_projecao_wacc(tmp_path)

    resultado = calcular_wacc(
        "TEST3",
        raiz_projeto=tmp_path,
        rf_usd=0.044,
        kd_historico=0.12,
    )

    assert 0.05 <= resultado["wacc"] <= 0.30


def test_ke_brl_maior_que_ke_usd_quando_ipca_maior(tmp_path: Path) -> None:
    """Diferencial de inflacao eleva Ke quando IPCA > CPI EUA."""
    criar_meta_e_premissas(tmp_path, ipca=0.06, cpi_eua=0.02)
    criar_projecao_wacc(tmp_path)

    resultado = calcular_wacc(
        "TEST3",
        raiz_projeto=tmp_path,
        rf_usd=0.044,
        kd_historico=0.12,
    )

    assert resultado["ke_brl"] > resultado["ke_usd"]


def test_beta_realavancado_maior_com_divida(tmp_path: Path) -> None:
    """Hamada eleva o beta quando ha divida na estrutura (D/E > 0)."""
    criar_meta_e_premissas(tmp_path)
    criar_projecao_wacc(tmp_path, divida_bruta=400.0, patrimonio_liquido=600.0)

    resultado = calcular_wacc(
        "TEST3",
        raiz_projeto=tmp_path,
        rf_usd=0.044,
        kd_historico=0.12,
    )

    assert resultado["beta_realavancado"] > resultado["beta_desalavancado"]


def test_kd_liquido_menor_com_escudo_fiscal(tmp_path: Path) -> None:
    """Kd liquido deve ser menor que Kd historico quando ha aliquota > 0."""
    criar_meta_e_premissas(tmp_path, setor="varejo")
    criar_projecao_wacc(tmp_path)

    resultado = calcular_wacc(
        "TEST3",
        raiz_projeto=tmp_path,
        rf_usd=0.044,
        kd_historico=0.12,
    )

    assert resultado["aliquota_ir"] == pytest.approx(0.34)
    assert resultado["kd_liquido"] < resultado["kd_historico"]


def test_rf_usd_nao_positivo_levanta_erro(tmp_path: Path) -> None:
    """Rf em USD <= 0 deve travar o calculo com erro claro."""
    criar_meta_e_premissas(tmp_path)
    criar_projecao_wacc(tmp_path)

    with pytest.raises(ValueError):
        calcular_wacc(
            "TEST3",
            raiz_projeto=tmp_path,
            rf_usd=-0.01,
            kd_historico=0.12,
        )


def test_construtora_ret_zera_escudo_fiscal(tmp_path: Path) -> None:
    """Construtora RET nao aplica escudo fiscal: Kd liquido = Kd historico."""
    criar_meta_e_premissas(tmp_path, setor="construcao")
    criar_projecao_wacc(tmp_path)

    resultado = calcular_wacc(
        "TEST3",
        raiz_projeto=tmp_path,
        rf_usd=0.044,
        kd_historico=0.12,
    )

    assert resultado["aliquota_ir"] == pytest.approx(0.0)
    assert resultado["kd_liquido"] == pytest.approx(resultado["kd_historico"])


def _linha_cvm(nome: str, data_fim: str, ano_arquivo: int, valor: float) -> dict:
    """Monta uma linha bruta anual (31/12, ULTIMO) no formato da CVM."""
    return {
        "nome_padronizado": nome,
        "DT_FIM_EXERC": data_fim,
        "ORDEM_EXERC": "ULTIMO",
        "ano_arquivo": ano_arquivo,
        "CD_CONTA": "3.06",
        "valor_padronizado": valor,
    }


def test_kd_historico_de_dados_brutos(tmp_path: Path) -> None:
    """Kd historico = media(desp. financeira) / media(divida bruta) anual."""
    ticker = "TEST3"
    dre = [
        _linha_cvm("despesas_financeiras", "2023-12-31", 2024, -100.0),
        _linha_cvm("despesas_financeiras", "2024-12-31", 2025, -120.0),
        _linha_cvm("despesas_financeiras", "2025-12-31", 2026, -140.0),
        # Ruido trimestral que deve ser ignorado.
        _linha_cvm("despesas_financeiras", "2025-06-30", 2026, -70.0),
    ]
    bp = []
    for data, ano, cp, lp in [
        ("2023-12-31", 2024, -200.0, -800.0),
        ("2024-12-31", 2025, -250.0, -850.0),
        ("2025-12-31", 2026, -300.0, -900.0),
    ]:
        bp.append(_linha_cvm("divida_curto_prazo", data, ano, cp))
        bp.append(_linha_cvm("divida_longo_prazo", data, ano, lp))

    salvar_json(tmp_path / "data" / "raw" / "cvm" / f"{ticker}_dre.json", dre)
    salvar_json(tmp_path / "data" / "raw" / "cvm" / f"{ticker}_bp.json", bp)

    kd = calcular_kd_historico(ticker, tmp_path)

    media_despesas = (100.0 + 120.0 + 140.0) / 3
    media_divida = (1000.0 + 1100.0 + 1200.0) / 3
    assert kd == pytest.approx(media_despesas / media_divida)
