"""Classificador universal de tipo e subtipo de empresa da B3.

A partir do setor de atividade da CVM (``SETOR_ATIV`` do cadastro/FCA),
classifica a empresa em ``tipo`` (``financeira`` | ``nao_financeira``) e
``subtipo`` (banco, seguradora, holding, utility_energia, saneamento,
telecom, mineracao, oleo_gas, construcao_civil, varejo, industria, consumo,
saude, agro, papel_celulose, transporte_logistica, tecnologia, outros).

Todo o conhecimento setorial vive em ``config/setores.json`` (configuracao,
nao hard-code): o bloco ``mapa_setor_cvm`` traduz o texto do setor CVM por
palavras-chave normalizadas e o bloco ``subtipos`` carrega metodo de
valuation, taxa de desconto, tributacao, peers e defaults. Setor nao
reconhecido cai em ``outros`` (FCFF/WACC, default seguro) e vai para log.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.coleta.mapeador_contas import carregar_json, normalizar_texto

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
SUBTIPO_DEFAULT = "outros"
NOME_LOG_SETORES = "setores_nao_reconhecidos.log"

logger = logging.getLogger(__name__)


def carregar_setores(raiz_projeto: Path | None = None) -> dict[str, Any]:
    """Carrega e valida config/setores.json no esquema v2.0."""
    raiz = RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)
    setores = carregar_json(raiz / "config" / "setores.json")
    if "subtipos" not in setores or "mapa_setor_cvm" not in setores:
        raise RuntimeError(
            "config/setores.json sem os blocos v2.0 'subtipos'/'mapa_setor_cvm'."
        )
    if SUBTIPO_DEFAULT not in setores["subtipos"]:
        raise RuntimeError(
            f"config/setores.json precisa do subtipo default '{SUBTIPO_DEFAULT}'."
        )
    return setores


def _registrar_setor_nao_reconhecido(
    setor_cvm: str,
    ticker: str,
    raiz_projeto: Path,
) -> None:
    """Audita setores CVM sem regra no mapa, sem interromper o pipeline."""
    pasta_logs = raiz_projeto / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    with (pasta_logs / NOME_LOG_SETORES).open("a", encoding="utf-8") as arquivo:
        arquivo.write(f"ticker={ticker} | setor_cvm={setor_cvm}\n")


def _subtipo_por_regras(
    setor_normalizado: str,
    setores: dict[str, Any],
) -> str | None:
    """Aplica o mapa de palavras-chave (primeiro match vence)."""
    for regra in setores.get("mapa_setor_cvm", []):
        for termo in regra.get("contem", []):
            if normalizar_texto(termo) in setor_normalizado:
                return str(regra["subtipo"])
    return None


def resolver_subtipo(setor_cvm: str, setores: dict[str, Any]) -> str | None:
    """Resolve o subtipo pelo mapa de palavras-chave (primeiro match vence).

    Setores 'Emp. Adm. Part. - <segmento>' sao classificados pelo SEGMENTO:
    a CVM registra operadoras consolidadas (ex.: WEG) nesse formato, e trata-
    las como holding esconderia o negocio real. Holding e o fallback apenas
    quando o segmento nao e reconhecivel (ex.: 'Sem Setor Principal').
    """
    setor_normalizado = normalizar_texto(setor_cvm)
    if not setor_normalizado:
        return None

    prefixo_holding = normalizar_texto(setores.get("prefixo_holding_cvm", ""))
    if prefixo_holding and prefixo_holding in setor_normalizado:
        segmento = setor_normalizado.replace(prefixo_holding, " ")
        subtipo_segmento = _subtipo_por_regras(segmento, setores)
        return subtipo_segmento or "holding"

    return _subtipo_por_regras(setor_normalizado, setores)


def classificar_empresa(
    setor_cvm: str,
    ticker: str = "",
    setores: dict[str, Any] | None = None,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Classifica tipo/subtipo e devolve o contrato setorial completo.

    Devolve ``{"tipo", "subtipo", "metodo_valuation", "taxa_desconto",
    "config_subtipo"}``. Os modulos posteriores leem esses campos do
    ``_meta.json`` — nunca reclassificam por conta propria.
    """
    raiz = RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)
    if setores is None:
        setores = carregar_setores(raiz)

    subtipo = resolver_subtipo(setor_cvm, setores)
    if subtipo is None or subtipo not in setores["subtipos"]:
        logger.warning(
            "Setor CVM '%s' (%s) sem regra em config/setores.json; "
            "usando subtipo '%s' com FCFF/WACC (default seguro).",
            setor_cvm,
            ticker or "sem ticker",
            SUBTIPO_DEFAULT,
        )
        _registrar_setor_nao_reconhecido(setor_cvm, ticker, raiz)
        subtipo = SUBTIPO_DEFAULT

    config_subtipo = setores["subtipos"][subtipo]
    return {
        "tipo": str(config_subtipo.get("tipo", "nao_financeira")),
        "subtipo": subtipo,
        "metodo_valuation": str(config_subtipo.get("metodo_valuation", "FCFF")),
        "taxa_desconto": str(config_subtipo.get("taxa_desconto", "WACC")),
        "config_subtipo": config_subtipo,
    }


def detectar_tipo_empresa(setor: str, raiz_projeto: Path | None = None) -> str:
    """Compatibilidade v1: devolve apenas o tipo (financeira/nao_financeira)."""
    return classificar_empresa(setor, raiz_projeto=raiz_projeto)["tipo"]
