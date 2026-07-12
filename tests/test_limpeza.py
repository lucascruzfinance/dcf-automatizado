"""Testes da limpeza real (Parquet limpo em data/processed/), sem rede."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.processamento.limpeza import (
    carregar_parquet_limpo,
    limpar_demonstracao,
    limpar_empresa,
)


def linha_cvm(
    codigo: str,
    descricao: str,
    valor: float,
    nome: str | None = None,
    sinal: str | None = None,
    valor_padronizado: float | None = None,
) -> dict:
    """Linha bruta minima no contrato persistido pela coleta."""
    return {
        "CD_CONTA": codigo,
        "DS_CONTA": descricao,
        "VL_CONTA": valor,
        "nome_padronizado": nome,
        "sinal_esperado": sinal,
        "valor_padronizado": valor_padronizado,
        "tipo_documento": "DFP",
        "DT_FIM_EXERC": "2025-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
        "ano_arquivo": 2025,
    }


def montar_raiz_sintetica(tmp_path: Path) -> Path:
    """Monta raiz de projeto com config e JSONs brutos de um ticker TESTE."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "parametros.json").write_text(
        json.dumps(
            {
                "anos_historicos_coleta": 7,
                "limpeza": {"padroes_nao_recorrentes": ["impairment", "reestrutura"]},
            }
        ),
        encoding="utf-8",
    )
    pasta = tmp_path / "data" / "raw" / "cvm"
    pasta.mkdir(parents=True)

    dre = [
        # valor_padronizado ausente com conta mapeada: a limpeza recalcula.
        linha_cvm("3.01", "Receita", 100.0, "receita_liquida", "positivo"),
        linha_cvm("3.02", "Custo", 80.0, "cpv_cmv", "negativo", -80.0),
        linha_cvm("3.04.99", "Provisão para Impairment de Ativos", -5.0),
    ]
    bp = [
        linha_cvm(
            "2.01.04",
            "Empréstimos e Financiamentos",
            50.0,
            "divida_curto_prazo",
            "negativo",
            -50.0,
        ),
        linha_cvm("2.01.02", "Fornecedores", 30.0, "fornecedores", "negativo", -30.0),
        linha_cvm(
            "1.01.01",
            "Caixa e Equivalentes",
            10.0,
            "caixa_equivalentes",
            "positivo",
            10.0,
        ),
    ]
    dfc = [
        linha_cvm(
            "6.01",
            "Caixa Líquido Atividades Operacionais",
            40.0,
            "fco",
            "positivo_ou_negativo",
            40.0,
        ),
    ]
    (pasta / "TESTE_dre.json").write_text(json.dumps(dre), encoding="utf-8")
    (pasta / "TESTE_bp.json").write_text(json.dumps(bp), encoding="utf-8")
    (pasta / "TESTE_dfc.json").write_text(json.dumps(dfc), encoding="utf-8")
    return tmp_path


def test_limpar_empresa_gera_parquets_normalizados(tmp_path: Path) -> None:
    """Limpeza grava Parquet por demonstracao com sinais normalizados."""
    raiz = montar_raiz_sintetica(tmp_path)
    caminhos = limpar_empresa("TESTE", raiz_projeto=raiz)

    assert set(caminhos) == {"dre", "bp", "dfc"}
    assert "dva" not in caminhos  # opcional ausente nao quebra
    for caminho in caminhos.values():
        assert caminho.exists()

    dre = carregar_parquet_limpo("TESTE", "dre", raiz)
    # Receita mapeada sem valor_padronizado e recalculada pelo sinal.
    assert dre.loc[0, "valor_padronizado"] == 100.0
    # Valor ja padronizado pela coleta e preservado (idempotencia).
    assert dre.loc[1, "valor_padronizado"] == -80.0
    # Conta nao mapeada nao ganha valor padronizado inventado.
    assert pd.isna(dre.loc[2, "valor_padronizado"])
    # Item com padrao de nao-recorrencia e sinalizado SEM ser removido.
    assert list(dre["eh_nao_recorrente"]) == [False, False, True]
    assert len(dre) == 3


def test_flags_separam_divida_de_passivo_operacional(tmp_path: Path) -> None:
    """Divida financeira e NIBCLs recebem flags booleanas distintas."""
    raiz = montar_raiz_sintetica(tmp_path)
    limpar_empresa("TESTE", raiz_projeto=raiz)
    bp = carregar_parquet_limpo("TESTE", "bp", raiz)

    por_nome = bp.set_index("nome_padronizado")
    assert bool(por_nome.loc["divida_curto_prazo", "eh_divida_financeira"]) is True
    assert bool(por_nome.loc["divida_curto_prazo", "eh_passivo_operacional"]) is False
    assert bool(por_nome.loc["fornecedores", "eh_passivo_operacional"]) is True
    assert bool(por_nome.loc["fornecedores", "eh_divida_financeira"]) is False
    assert bool(por_nome.loc["caixa_equivalentes", "eh_divida_financeira"]) is False
    assert bool(por_nome.loc["caixa_equivalentes", "eh_passivo_operacional"]) is False


def test_demonstracao_obrigatoria_ausente_e_erro_claro(tmp_path: Path) -> None:
    """Sem BP bruto a limpeza falha com instrucao de recoleta."""
    raiz = montar_raiz_sintetica(tmp_path)
    (raiz / "data" / "raw" / "cvm" / "TESTE_bp.json").unlink()
    with pytest.raises(RuntimeError, match="obrigatorio"):
        limpar_empresa("TESTE", raiz_projeto=raiz)


def test_limpar_demonstracao_e_pura_e_nao_altera_entrada() -> None:
    """A funcao de limpeza nao muta o DataFrame original."""
    dados = pd.DataFrame(
        [linha_cvm("3.01", "Receita", 100.0, "receita_liquida", "positivo")]
    )
    copia = dados.copy(deep=True)
    resultado = limpar_demonstracao(dados, ["impairment"])
    pd.testing.assert_frame_equal(dados, copia)
    assert resultado.loc[0, "valor_padronizado"] == 100.0


def test_carregar_parquet_limpo_ausente_devolve_vazio(tmp_path: Path) -> None:
    """Parquet inexistente devolve DataFrame vazio com aviso, sem quebrar."""
    resultado = carregar_parquet_limpo("NAOEXISTE", "dre", tmp_path)
    assert resultado.empty
