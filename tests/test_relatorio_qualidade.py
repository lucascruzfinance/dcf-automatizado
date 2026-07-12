"""Testes do relatorio de qualidade de dados por empresa (sem rede)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.coleta.relatorio_qualidade import (
    avaliar_qualidade,
    calcular_score,
    gerar_relatorio_qualidade,
)


def linha_mapeada(
    nome: str,
    codigo: str,
    valor: float,
    ano: int,
) -> dict:
    """Linha DFP anual mapeada no contrato da coleta."""
    return {
        "CD_CONTA": codigo,
        "DS_CONTA": nome,
        "VL_CONTA": valor,
        "nome_padronizado": nome,
        "sinal_esperado": "positivo_ou_negativo",
        "valor_padronizado": valor,
        "tipo_documento": "DFP",
        "DT_FIM_EXERC": f"{ano}-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
        "ano_arquivo": ano,
    }


def quadros_completos() -> dict[str, pd.DataFrame]:
    """Sete exercicios anuais com todas as contas-chave nao-financeiras."""
    dre = []
    for ano in range(2019, 2026):
        dre.append(linha_mapeada("receita_liquida", "3.01", 100.0 + ano, ano))
        dre.append(linha_mapeada("ebit", "3.05", 10.0, ano))
        dre.append(linha_mapeada("lucro_liquido", "3.11", 5.0, ano))
    bp = [
        linha_mapeada("ativo_total", "1", 500.0, 2025),
        linha_mapeada("patrimonio_liquido", "2.03", 200.0, 2025),
        linha_mapeada("caixa_equivalentes", "1.01.01", 50.0, 2025),
        linha_mapeada("divida_curto_prazo", "2.01.04", -40.0, 2025),
    ]
    return {
        "dre": pd.DataFrame(dre),
        "bp": pd.DataFrame(bp),
        "dfc": pd.DataFrame(),
        "dva": pd.DataFrame(),
    }


def test_empresa_completa_atinge_score_maximo() -> None:
    """Contas-chave completas + 7 anos + consolidado + tudo mapeado = 100."""
    meta = {
        "ticker": "TESTE",
        "tipo": "nao_financeira",
        "subtipo": "varejo",
        "consolidado": True,
    }
    relatorio = avaliar_qualidade(meta, quadros_completos(), alvo_anos=7)

    assert relatorio["score_confiabilidade"] == 100
    assert relatorio["quantidade_anos"] == 7
    assert relatorio["contas_chave_ausentes"] == []
    assert relatorio["avisos"] == []
    assert relatorio["contas_nao_mapeadas"]["quantidade_pares"] == 0


def test_empresa_degradada_perde_pontos_e_ganha_avisos() -> None:
    """Historico curto, contas faltando e individual rebaixam o score."""
    dre = pd.DataFrame(
        [
            linha_mapeada("receita_liquida", "3.01", 100.0, 2020),
            linha_mapeada("receita_liquida", "3.01", 90.0, 2021),
            # Linha nao mapeada (nome nulo) para derrubar a cobertura.
            {
                "CD_CONTA": "9.99",
                "DS_CONTA": "Conta Desconhecida",
                "VL_CONTA": 1.0,
                "nome_padronizado": None,
                "sinal_esperado": None,
                "valor_padronizado": None,
                "tipo_documento": "DFP",
                "DT_FIM_EXERC": "2021-12-31",
                "ORDEM_EXERC": "ÚLTIMO",
                "ano_arquivo": 2021,
            },
        ]
    )
    meta = {
        "ticker": "TESTE",
        "tipo": "nao_financeira",
        "subtipo": "outros",
        "consolidado": False,
    }
    quadros = {
        "dre": dre,
        "bp": pd.DataFrame(),
        "dfc": pd.DataFrame(),
        "dva": pd.DataFrame(),
    }
    relatorio = avaliar_qualidade(meta, quadros, alvo_anos=7)

    assert relatorio["score_confiabilidade"] < 40
    assert relatorio["quantidade_anos"] == 2
    for conta in ("ebit", "lucro_liquido", "ativo_total", "divida_cp_ou_lp"):
        assert conta in relatorio["contas_chave_ausentes"]
    avisos = " | ".join(relatorio["avisos"])
    assert "individuais usadas como fallback" in avisos
    assert "2021" in avisos  # DFP defasada
    assert relatorio["contas_nao_mapeadas"]["quantidade_pares"] == 1


def test_patrimonio_liquido_negativo_gera_aviso_sem_erro() -> None:
    """PL negativo e valido (nao trava), mas entra nos avisos."""
    quadros = quadros_completos()
    bp = quadros["bp"].copy()
    bp.loc[bp["nome_padronizado"] == "patrimonio_liquido", "valor_padronizado"] = -150.0
    quadros["bp"] = bp
    meta = {"ticker": "TESTE", "tipo": "nao_financeira", "consolidado": True}
    relatorio = avaliar_qualidade(meta, quadros, alvo_anos=7)

    assert any("negativo" in aviso for aviso in relatorio["avisos"])
    assert relatorio["contas_chave"]["patrimonio_liquido"] is True


def test_calcular_score_limita_e_decompoe() -> None:
    """Score fica em 0-100 e expoe os componentes da formula."""
    score_cheio, componentes = calcular_score(
        contas_chave={"a": True, "b": True},
        anos_coletados=[2019, 2020, 2021, 2022, 2023, 2024, 2025],
        alvo_anos=7,
        consolidado=True,
        linhas_totais=10,
        linhas_mapeadas=10,
    )
    assert score_cheio == 100
    assert componentes["contas_chave"] == 40.0
    assert componentes["anos_historicos"] == 30.0
    assert componentes["consolidado"] == 15.0
    assert componentes["linhas_mapeadas"] == 15.0

    score_zero, _ = calcular_score(
        contas_chave={},
        anos_coletados=[],
        alvo_anos=7,
        consolidado=None,
        linhas_totais=0,
        linhas_mapeadas=0,
    )
    assert score_zero == 0


def test_gerar_relatorio_persiste_json_e_score_no_meta(tmp_path: Path) -> None:
    """O relatorio e persistido e o score atualiza o _meta.json (contrato)."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "parametros.json").write_text(
        json.dumps({"anos_historicos_coleta": 7}),
        encoding="utf-8",
    )
    pasta = tmp_path / "data" / "raw" / "cvm"
    pasta.mkdir(parents=True)
    meta = {
        "ticker": "TESTE",
        "tipo": "nao_financeira",
        "subtipo": "varejo",
        "consolidado": True,
        "score_confiabilidade": None,
    }
    (pasta / "TESTE_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    quadros = quadros_completos()
    for demonstracao in ("dre", "bp"):
        registros = quadros[demonstracao].to_dict(orient="records")
        (pasta / f"TESTE_{demonstracao}.json").write_text(
            json.dumps(registros),
            encoding="utf-8",
        )

    relatorio = gerar_relatorio_qualidade("TESTE", raiz_projeto=tmp_path)

    caminho_qualidade = pasta / "TESTE_qualidade.json"
    assert caminho_qualidade.exists()
    persistido = json.loads(caminho_qualidade.read_text(encoding="utf-8"))
    assert persistido["score_confiabilidade"] == relatorio["score_confiabilidade"]

    meta_atualizado = json.loads(
        (pasta / "TESTE_meta.json").read_text(encoding="utf-8")
    )
    assert meta_atualizado["score_confiabilidade"] == relatorio["score_confiabilidade"]
