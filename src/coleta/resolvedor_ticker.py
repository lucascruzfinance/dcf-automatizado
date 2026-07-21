"""Resolvedor universal de ticker B3 -> CD_CVM.

Cruza o cadastro de companhias abertas (``cad_cia_aberta``) com os arquivos
FCA de valores mobiliarios da CVM (``CNPJ_Companhia`` <-> ``CNPJ_CIA``) para
resolver QUALQUER ticker negociado na B3, incluindo multiplos tickers da
mesma empresa (ON/PN/UNIT). O mapa completo ticker -> CD_CVM fica cacheado
em ``data/raw/cvm/_cadastro_b3.parquet`` para nao rebaixar a CVM a cada run.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from src.coleta.apoio_cvm import (
    URL_CVM,
    baixar_csv,
    ler_csv_do_zip,
    obter_zip,
    pasta_cache_zips,
)
from src.coleta.mapeador_contas import normalizar_texto

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
NOME_CACHE_CADASTRO = "_cadastro_b3.parquet"
VALIDADE_CACHE_DIAS = 7
ANOS_FCA_PESQUISADOS = 8

COLUNAS_CACHE = (
    "ticker",
    "codigo_cvm",
    "cnpj",
    "razao_social",
    "setor_cvm",
    "situacao",
    "ano_referencia",
)

logger = logging.getLogger(__name__)


class TickerNaoEncontradoErro(ValueError):
    """Ticker nao localizado (ou deslistado) nos dados abertos da CVM."""


@dataclass(frozen=True)
class EmpresaResolvida:
    """Identidade CVM de um ticker da B3 resolvida pelo cadastro oficial."""

    ticker: str
    codigo_cvm: int
    cnpj: str
    razao_social: str
    setor_cvm: str
    situacao: str


def normalizar_ticker(ticker: str) -> str:
    """Normaliza ticker B3 removendo sufixo de bolsa e padronizando caixa."""
    return str(ticker).upper().replace(".SA", "").strip()


def caminho_cache_cadastro(raiz_projeto: Path) -> Path:
    """Caminho do cache parquet do mapa ticker -> CD_CVM."""
    return Path(raiz_projeto) / "data" / "raw" / "cvm" / NOME_CACHE_CADASTRO


def encontrar_coluna_ticker(colunas: list[str]) -> str:
    """Encontra a coluna de ticker no FCA mesmo se a CVM renomear o campo."""
    candidatas = [
        "COD_NEGOCIACAO",
        "CODIGO_NEGOCIACAO",
        "CD_NEGOCIACAO",
        "CODIGO DE NEGOCIACAO",
        "DS_IDENTIFICACAO",
    ]
    mapa_colunas = {normalizar_texto(coluna).upper(): coluna for coluna in colunas}
    for candidata in candidatas:
        if candidata in mapa_colunas:
            return mapa_colunas[candidata]

    for coluna in colunas:
        nome = normalizar_texto(coluna).upper()
        if "NEGOCI" in nome or "TICKER" in nome:
            return coluna
    raise RuntimeError(f"Coluna de ticker nao encontrada no FCA. Colunas: {colunas}")


def carregar_cadastro_companhias() -> pd.DataFrame:
    """Baixa o cadastro de companhias abertas da CVM (funcao com rede)."""
    url = f"{URL_CVM}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
    cadastro = baixar_csv(url)
    obrigatorias = {"CD_CVM", "DENOM_SOCIAL", "CNPJ_CIA"}
    if not obrigatorias.issubset(cadastro.columns):
        raise RuntimeError(
            "Cadastro CVM veio com estrutura inesperada. "
            f"Colunas recebidas: {list(cadastro.columns)}"
        )
    return cadastro


def carregar_valores_mobiliarios(
    anos: list[int],
    raiz_projeto: Path,
) -> pd.DataFrame:
    """Carrega arquivos FCA de valores mobiliarios (funcao com rede)."""
    pasta_cache = pasta_cache_zips(raiz_projeto)
    ano_corrente = date.today().year
    quadros = []
    for ano in anos:
        url = f"{URL_CVM}/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"
        nome_csv = f"fca_cia_aberta_valor_mobiliario_{ano}.csv"
        # ZIPs de anos encerrados nao mudam; o do ano corrente expira em 24h.
        ttl_horas = 24.0 if ano >= ano_corrente else None
        try:
            arquivo_zip = obter_zip(url, pasta_cache=pasta_cache, ttl_horas=ttl_horas)
            quadro = ler_csv_do_zip(arquivo_zip, nome_csv)
        except RuntimeError as erro:
            logger.warning("Nao foi possivel carregar FCA %s: %s", ano, erro)
            continue
        quadro["ANO_REFERENCIA"] = ano
        quadros.append(quadro)

    if not quadros:
        raise RuntimeError("Nenhum arquivo FCA foi carregado para descobrir tickers.")
    return pd.concat(quadros, ignore_index=True)


def _deduplicar_cadastro(cadastro: pd.DataFrame) -> pd.DataFrame:
    """Um registro por CNPJ, preferindo situacao ATIVO (registros vivos)."""
    cadastro = cadastro.copy()
    coluna_situacao = "SIT" if "SIT" in cadastro.columns else None
    if coluna_situacao:
        situacao_normalizada = cadastro[coluna_situacao].map(normalizar_texto)
        cadastro["_prioridade_situacao"] = (situacao_normalizada != "ativo").astype(int)
    else:
        cadastro["_prioridade_situacao"] = 0
    cadastro = cadastro.sort_values("_prioridade_situacao")
    return cadastro.drop_duplicates("CNPJ_CIA", keep="first")


def construir_cadastro_b3(raiz_projeto: Path) -> pd.DataFrame:
    """Monta o mapa completo ticker -> CD_CVM cruzando cadastro e FCA."""
    ano_atual = date.today().year
    anos_fca = list(range(ano_atual, ano_atual - ANOS_FCA_PESQUISADOS, -1))
    cadastro = _deduplicar_cadastro(carregar_cadastro_companhias())
    valores = carregar_valores_mobiliarios(anos_fca, raiz_projeto)

    coluna_ticker = encontrar_coluna_ticker(list(valores.columns))
    valores = valores.copy()
    valores["ticker"] = valores[coluna_ticker].map(
        lambda valor: normalizar_ticker(valor) if pd.notna(valor) else ""
    )
    valores = valores[valores["ticker"].str.len().between(5, 7)]

    if "CNPJ_Companhia" in valores.columns:
        coluna_cnpj_fca = "CNPJ_Companhia"
    elif "CNPJ_CIA" in valores.columns:
        coluna_cnpj_fca = "CNPJ_CIA"
    else:
        raise RuntimeError(
            "FCA sem coluna de CNPJ para cruzar com o cadastro. "
            f"Colunas recebidas: {list(valores.columns)}"
        )

    # Um ticker pode aparecer em varios anos de FCA: vale o mais recente.
    valores = valores.sort_values("ANO_REFERENCIA")
    valores = valores.drop_duplicates("ticker", keep="last")

    cruzado = valores.merge(
        cadastro,
        left_on=coluna_cnpj_fca,
        right_on="CNPJ_CIA",
        how="inner",
    )
    if cruzado.empty:
        raise RuntimeError(
            "Cruzamento FCA x cadastro nao produziu nenhum ticker. "
            "Estrutura dos dados da CVM pode ter mudado."
        )

    mapa = pd.DataFrame(
        {
            "ticker": cruzado["ticker"],
            "codigo_cvm": pd.to_numeric(cruzado["CD_CVM"], errors="coerce"),
            "cnpj": cruzado["CNPJ_CIA"].astype(str),
            "razao_social": cruzado["DENOM_SOCIAL"].astype(str),
            "setor_cvm": cruzado.get(
                "SETOR_ATIV", pd.Series("", index=cruzado.index)
            ).fillna(""),
            "situacao": cruzado.get("SIT", pd.Series("", index=cruzado.index)).fillna(
                ""
            ),
            "ano_referencia": pd.to_numeric(cruzado["ANO_REFERENCIA"], errors="coerce"),
        }
    )
    mapa = mapa[mapa["codigo_cvm"].notna()].copy()
    mapa["codigo_cvm"] = mapa["codigo_cvm"].astype(int)
    return mapa.reset_index(drop=True)


def _cache_esta_fresco(caminho: Path) -> bool:
    """True quando o parquet de cadastro existe e esta dentro da validade."""
    if not caminho.exists():
        return False
    idade_dias = (time.time() - caminho.stat().st_mtime) / 86400.0
    return idade_dias < VALIDADE_CACHE_DIAS


def carregar_cadastro_b3(
    raiz_projeto: Path | None = None,
    atualizar: bool = False,
    construtor: Callable[[Path], pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Carrega o mapa ticker -> CD_CVM do cache, reconstruindo se preciso."""
    raiz = RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)
    caminho = caminho_cache_cadastro(raiz)
    if construtor is None:
        construtor = construir_cadastro_b3

    if not atualizar and _cache_esta_fresco(caminho):
        try:
            mapa = pd.read_parquet(caminho)
            if set(COLUNAS_CACHE).issubset(mapa.columns):
                return mapa
            logger.warning("Cache de cadastro com colunas antigas; reconstruindo.")
        except Exception as erro:  # noqa: BLE001 - cache corrompido nao e fatal
            logger.warning("Cache de cadastro ilegivel (%s); reconstruindo.", erro)

    mapa = construtor(raiz)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    mapa.to_parquet(caminho, index=False)
    logger.info("Cadastro B3 cacheado em %s (%s tickers).", caminho, len(mapa))
    return mapa


def _linha_para_empresa(linha: pd.Series) -> EmpresaResolvida:
    """Converte uma linha do mapa cacheado em EmpresaResolvida."""
    return EmpresaResolvida(
        ticker=str(linha["ticker"]),
        codigo_cvm=int(linha["codigo_cvm"]),
        cnpj=str(linha["cnpj"]),
        razao_social=str(linha["razao_social"]),
        setor_cvm=str(linha["setor_cvm"]),
        situacao=str(linha["situacao"]),
    )


def resolver_ticker(
    ticker: str,
    raiz_projeto: Path | None = None,
    atualizar_cache: bool = False,
    construtor: Callable[[Path], pd.DataFrame] | None = None,
) -> EmpresaResolvida:
    """Resolve um ticker da B3 para a identidade CVM da companhia.

    Ticker ausente do cache dispara UMA reconstrucao (o papel pode ser um
    IPO recente); persistindo a ausencia, levanta ``TickerNaoEncontradoErro``
    com mensagem acionavel em vez de stack trace cru.
    """
    raiz = RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    if not ticker_normalizado:
        raise TickerNaoEncontradoErro("Ticker vazio: informe um codigo da B3.")

    mapa = carregar_cadastro_b3(raiz, atualizar=atualizar_cache, construtor=construtor)
    encontrados = mapa[mapa["ticker"] == ticker_normalizado]

    if encontrados.empty and not atualizar_cache:
        logger.info(
            "Ticker %s fora do cache; reconstruindo o cadastro da CVM.",
            ticker_normalizado,
        )
        mapa = carregar_cadastro_b3(raiz, atualizar=True, construtor=construtor)
        encontrados = mapa[mapa["ticker"] == ticker_normalizado]

    if encontrados.empty:
        raise TickerNaoEncontradoErro(
            f"Ticker {ticker_normalizado} nao encontrado no cadastro da CVM/B3. "
            "Confira a grafia (ex.: PETR4, ITUB4, VALE3); se a empresa for "
            "estrangeira (BDR) ou fechou capital, ela nao possui DFP na CVM."
        )

    empresa = _linha_para_empresa(encontrados.iloc[-1])
    if empresa.situacao and normalizar_texto(empresa.situacao) != "ativo":
        raise TickerNaoEncontradoErro(
            f"Ticker {ticker_normalizado} pertence a {empresa.razao_social}, "
            f"mas o registro na CVM esta '{empresa.situacao}' (empresa "
            "deslistada ou com registro cancelado). Nao ha demonstrativos "
            "correntes para valuation."
        )
    return empresa
