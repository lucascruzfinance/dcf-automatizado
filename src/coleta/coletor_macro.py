"""Coleta de dados macroeconomicos do Brasil via python-bcb."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from bcb import Expectativas, sgs

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CODIGO_SELIC_META = 432


def resolver_raiz(raiz_projeto: Path | None = None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    if raiz_projeto is None:
        return RAIZ_PROJETO
    return Path(raiz_projeto)


def configurar_logger(raiz_projeto: Path) -> logging.Logger:
    """Configura log de coleta macro sem duplicar handlers."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    caminho_log = raiz_projeto / "logs" / "coletor_macro.log"
    caminho_log.parent.mkdir(parents=True, exist_ok=True)
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == caminho_log
        for handler in logger.handlers
    ):
        handler = logging.FileHandler(caminho_log, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def salvar_json(caminho: Path, conteudo: dict[str, Any]) -> None:
    """Salva JSON com indentacao estavel."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)


def percentual_para_decimal(valor: Any) -> float | None:
    """Converte percentuais do BCB/Focus para decimal."""
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if pd.isna(numero):
        return None
    if abs(numero) > 1:
        return numero / 100
    return numero


def coletar_selic_atual(logger: logging.Logger) -> float | None:
    """Coleta a Selic meta vigente pela serie SGS 432."""
    try:
        dados = sgs.get({"selic_atual": CODIGO_SELIC_META}, last=1)
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.exception("Falha ao coletar Selic atual no SGS: %s", erro)
        return None

    if dados.empty or "selic_atual" not in dados.columns:
        logger.warning("SGS 432 retornou sem coluna selic_atual.")
        return None
    return percentual_para_decimal(dados["selic_atual"].dropna().iloc[-1])


def coletar_expectativas_anuais(logger: logging.Logger) -> pd.DataFrame:
    """Coleta endpoint anual do Focus para IPCA e Selic."""
    try:
        endpoint = Expectativas().get_endpoint("ExpectativasMercadoAnuais")
        filtro = (endpoint.Indicador == "IPCA") | (endpoint.Indicador == "Selic")
        return endpoint.get(filter=filtro, orderby=endpoint.Data.desc(), limit=500)
    except Exception as erro:  # pragma: no cover - depende de rede/API externa.
        logger.exception("Falha ao coletar Expectativas Focus: %s", erro)
        return pd.DataFrame()


def selecionar_mediana_focus(
    dados: pd.DataFrame,
    indicador: str,
    ano_referencia: int,
    logger: logging.Logger,
) -> float | None:
    """Seleciona a mediana Focus mais recente para indicador e ano."""
    if dados.empty:
        return None
    colunas_obrigatorias = {"Indicador", "DataReferencia", "Mediana"}
    if not colunas_obrigatorias.issubset(dados.columns):
        logger.warning("Focus sem colunas esperadas: %s", sorted(dados.columns))
        return None

    filtrado = dados[
        (dados["Indicador"] == indicador)
        & (dados["DataReferencia"].astype(str) == str(ano_referencia))
    ].copy()
    if filtrado.empty:
        logger.warning(
            "Focus sem %s para DataReferencia %s.", indicador, ano_referencia
        )
        return None
    if "Data" in filtrado.columns:
        filtrado = filtrado.sort_values("Data")

    return percentual_para_decimal(filtrado.iloc[-1]["Mediana"])


def coletar_macro(raiz_projeto: Path | None = None) -> dict[str, Any]:
    """Coleta Selic atual e expectativas Focus de IPCA/Selic para 1 e 2 anos."""
    raiz = resolver_raiz(raiz_projeto)
    logger = configurar_logger(raiz)
    ano_atual = date.today().year
    ano_1a = ano_atual + 1
    ano_2a = ano_atual + 2

    dados_focus = coletar_expectativas_anuais(logger)
    resultado = {
        "selic_atual": coletar_selic_atual(logger),
        "ipca_focus_1a": selecionar_mediana_focus(
            dados_focus,
            "IPCA",
            ano_1a,
            logger,
        ),
        "ipca_focus_2a": selecionar_mediana_focus(
            dados_focus,
            "IPCA",
            ano_2a,
            logger,
        ),
        "selic_focus_1a": selecionar_mediana_focus(
            dados_focus,
            "Selic",
            ano_1a,
            logger,
        ),
        "selic_focus_2a": selecionar_mediana_focus(
            dados_focus,
            "Selic",
            ano_2a,
            logger,
        ),
        "data_coleta": datetime.now(timezone.utc).isoformat(),
    }
    salvar_json(raiz / "data" / "raw" / "macro" / "macro_brasil.json", resultado)
    return resultado


def main() -> None:
    """Executa a coleta macro e imprime os valores salvos."""
    resultado = coletar_macro()
    for campo, valor in resultado.items():
        print(f"{campo}: {valor}")


if __name__ == "__main__":
    main()
