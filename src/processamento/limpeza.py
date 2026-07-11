"""Limpeza real dos dados brutos da CVM com persistencia em Parquet.

A partir da v2.0 a projecao le Parquet limpo de ``data/processed/`` (o
``projetor_dre`` ja prefere Parquet, com fallback documentado ao JSON bruto
para nao quebrar o que ja roda). Este modulo transforma os JSONs de
``data/raw/cvm/`` em ``data/processed/<TICKER>_<demonstracao>.parquet``:

- normaliza sinais (idempotente: recalcula ``valor_padronizado`` quando o
  coletor nao o preencheu mas a conta esta mapeada);
- separa divida financeira de passivos operacionais sem juros (NIBCLs) via
  flags booleanas ``eh_divida_financeira`` / ``eh_passivo_operacional``;
- sinaliza itens potencialmente nao-recorrentes (``eh_nao_recorrente``)
  SEM remover nenhuma linha — a decisao de normalizar e do analista;
- estabiliza dtypes (texto como string, medidas como float) para o Parquet.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.coleta.mapeador_contas import (  # noqa: E402
    carregar_json,
    normalizar_sinal,
    normalizar_texto,
)

# dre/bp/dfc sao obrigatorias para o pipeline; a DVA e opcional (apoia
# bancos e a Receita Bruta do RET, mas nem todo recorte tem DVA).
DEMONSTRACOES_OBRIGATORIAS = ("dre", "bp", "dfc")
DEMONSTRACOES_OPCIONAIS = ("dva",)

CONTAS_DIVIDA_FINANCEIRA = (
    "divida_curto_prazo",
    "divida_longo_prazo",
    "passivo_arrendamento",
)
CONTAS_PASSIVO_OPERACIONAL = (
    "fornecedores",
    "obrigacoes_sociais_trabalhistas",
    "obrigacoes_fiscais",
    "outras_obrigacoes_cp",
    "outras_obrigacoes_lp",
    "provisoes_cp",
    "provisoes_lp",
)

COLUNAS_NUMERICAS = ("VL_CONTA", "valor_padronizado", "CD_CVM", "ano_projecao")
COLUNAS_INTEIRAS = ("ano_arquivo",)

logger = logging.getLogger(__name__)


def resolver_raiz(raiz_projeto: Path | None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    return RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)


def _padroes_nao_recorrentes(raiz_projeto: Path) -> list[str]:
    """Le os padroes de itens nao-recorrentes de config/parametros.json."""
    parametros = carregar_json(raiz_projeto / "config" / "parametros.json")
    padroes = parametros.get("limpeza", {}).get("padroes_nao_recorrentes", [])
    return [normalizar_texto(padrao) for padrao in padroes if padrao]


def _normalizar_sinais(dados: pd.DataFrame) -> pd.DataFrame:
    """Garante valor_padronizado para toda linha mapeada (idempotente)."""
    if "valor_padronizado" not in dados.columns:
        dados["valor_padronizado"] = None
    if "sinal_esperado" not in dados.columns:
        dados["sinal_esperado"] = None

    valores = []
    for valor_atual, bruto, sinal, nome in zip(
        dados["valor_padronizado"],
        dados.get("VL_CONTA", pd.Series([None] * len(dados))),
        dados["sinal_esperado"],
        dados.get("nome_padronizado", pd.Series([None] * len(dados))),
    ):
        if valor_atual is not None and pd.notna(valor_atual):
            valores.append(float(valor_atual))
        elif nome is not None and pd.notna(nome):
            valores.append(normalizar_sinal(bruto, sinal))
        else:
            valores.append(None)
    dados["valor_padronizado"] = valores
    return dados


def _separar_divida_de_operacional(dados: pd.DataFrame) -> pd.DataFrame:
    """Flags de divida financeira x passivo operacional sem juros (NIBCL)."""
    nomes = dados.get("nome_padronizado", pd.Series([None] * len(dados)))
    dados["eh_divida_financeira"] = [
        nome in CONTAS_DIVIDA_FINANCEIRA if nome is not None else False
        for nome in nomes
    ]
    dados["eh_passivo_operacional"] = [
        nome in CONTAS_PASSIVO_OPERACIONAL if nome is not None else False
        for nome in nomes
    ]
    return dados


def _sinalizar_nao_recorrentes(
    dados: pd.DataFrame,
    padroes: list[str],
) -> pd.DataFrame:
    """Marca linhas potencialmente nao-recorrentes pela descricao (sem remover)."""
    descricoes = dados.get("DS_CONTA", pd.Series([""] * len(dados)))
    flags = []
    for descricao in descricoes:
        descricao_normalizada = normalizar_texto(descricao)
        flags.append(
            any(padrao in descricao_normalizada for padrao in padroes)
            if descricao_normalizada
            else False
        )
    dados["eh_nao_recorrente"] = flags
    return dados


def _estabilizar_dtypes(dados: pd.DataFrame) -> pd.DataFrame:
    """Coage dtypes para um Parquet estavel (texto string, medidas float)."""
    for coluna in dados.columns:
        if coluna in COLUNAS_NUMERICAS:
            dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")
        elif coluna in COLUNAS_INTEIRAS:
            dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce").astype(
                "Int64"
            )
        elif dados[coluna].dtype == object:
            dados[coluna] = [
                None if valor is None or pd.isna(valor) else str(valor)
                for valor in dados[coluna]
            ]
    return dados


def limpar_demonstracao(
    dados: pd.DataFrame,
    padroes_nao_recorrentes: list[str],
) -> pd.DataFrame:
    """Aplica a limpeza completa a uma demonstracao ja mapeada."""
    dados = dados.copy()
    dados = _normalizar_sinais(dados)
    dados = _separar_divida_de_operacional(dados)
    dados = _sinalizar_nao_recorrentes(dados, padroes_nao_recorrentes)
    dados = _estabilizar_dtypes(dados)
    return dados


def limpar_empresa(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Path]:
    """Limpa os dados brutos de um ticker e grava os Parquets processados.

    Devolve ``{demonstracao: caminho_parquet}``. Demonstracao obrigatoria
    ausente e erro claro; a DVA ausente vira aviso.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = str(ticker).upper().replace(".SA", "").strip()
    pasta_bruta = raiz / "data" / "raw" / "cvm"
    pasta_processados = raiz / "data" / "processed"
    pasta_processados.mkdir(parents=True, exist_ok=True)
    padroes = _padroes_nao_recorrentes(raiz)

    caminhos: dict[str, Path] = {}
    for demonstracao in DEMONSTRACOES_OBRIGATORIAS + DEMONSTRACOES_OPCIONAIS:
        caminho_bruto = pasta_bruta / f"{ticker_normalizado}_{demonstracao}.json"
        obrigatoria = demonstracao in DEMONSTRACOES_OBRIGATORIAS
        if not caminho_bruto.exists():
            if obrigatoria:
                raise RuntimeError(
                    f"Dado bruto obrigatorio ausente: {caminho_bruto}. "
                    f"Rode a coleta ({ticker_normalizado}) antes da limpeza."
                )
            logger.warning("DVA ausente para %s; seguindo sem ela.", ticker)
            continue

        registros = carregar_json(caminho_bruto)
        if not registros:
            if obrigatoria:
                raise RuntimeError(
                    f"Dado bruto vazio: {caminho_bruto}. Recolete o ticker."
                )
            logger.warning("DVA vazia para %s; seguindo sem ela.", ticker)
            continue

        dados = limpar_demonstracao(pd.DataFrame(registros), padroes)
        caminho_parquet = pasta_processados / (
            f"{ticker_normalizado}_{demonstracao}.parquet"
        )
        dados.to_parquet(caminho_parquet, index=False)
        caminhos[demonstracao] = caminho_parquet
        logger.info(
            "Parquet limpo gravado: %s (%s linhas)",
            caminho_parquet,
            len(dados),
        )
    return caminhos


def carregar_parquet_limpo(
    ticker: str,
    demonstracao: str,
    raiz_projeto: Path | None = None,
) -> pd.DataFrame:
    """Le um Parquet limpo de volta; vazio se ele nao existir."""
    raiz = resolver_raiz(raiz_projeto)
    caminho = raiz / "data" / "processed" / f"{ticker}_{demonstracao}.parquet"
    if not caminho.exists():
        logger.warning("Parquet limpo ausente: %s", caminho)
        return pd.DataFrame()
    return pd.read_parquet(caminho)


def executar_validacao_padrao() -> None:
    """Roda a limpeza para DIRR3 e MGLU3 (regressao dourada da Onda 1)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    for ticker in ("DIRR3", "MGLU3"):
        try:
            caminhos = limpar_empresa(ticker)
        except RuntimeError as erro:
            print(f"Falha na limpeza de {ticker}: {erro}")
            continue
        print(f"\n{ticker}: {len(caminhos)} demonstracoes limpas")
        for demonstracao, caminho in caminhos.items():
            print(f"  {demonstracao}: {caminho}")


if __name__ == "__main__":
    executar_validacao_padrao()
