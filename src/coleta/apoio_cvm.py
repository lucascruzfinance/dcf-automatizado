"""Apoio de acesso aos dados abertos da CVM (HTTP, ZIPs e cache em disco).

Centraliza o download defensivo de CSVs e ZIPs da CVM para o resolvedor de
ticker e o coletor universal. O cache de ZIPs em disco existe para a coleta
em lote: sem ele, o mesmo ZIP anual de DFP/ITR seria baixado dezenas de vezes
(uma por empresa por demonstrativo), rebaixando a CVM a cada run.
"""

from __future__ import annotations

import logging
import time
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd
import requests

URL_CVM = "https://dados.cvm.gov.br/dados"
TIMEOUT_SEGUNDOS = 120
NOME_PASTA_CACHE_ZIPS = "_cache_zips"

logger = logging.getLogger(__name__)


def baixar_bytes(url: str) -> bytes:
    """Baixa o conteudo bruto de uma URL da CVM com erros explicitos."""
    try:
        resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException as erro:
        raise RuntimeError(f"Falha ao acessar CVM em {url}: {erro}") from erro
    return resposta.content


def baixar_csv(url: str, sep: str = ";") -> pd.DataFrame:
    """Baixa um CSV da CVM com tratamento explicito de erros de estrutura."""
    conteudo = baixar_bytes(url)
    try:
        return pd.read_csv(BytesIO(conteudo), sep=sep, encoding="latin1")
    except Exception as erro:
        raise RuntimeError(
            f"Falha ao interpretar CSV da CVM em {url}: {erro}"
        ) from erro


def pasta_cache_zips(raiz_projeto: Path) -> Path:
    """Devolve (criando) a pasta de cache de ZIPs da CVM."""
    pasta = Path(raiz_projeto) / "data" / "raw" / "cvm" / NOME_PASTA_CACHE_ZIPS
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _cache_valido(caminho: Path, ttl_horas: float | None) -> bool:
    """True quando o arquivo em cache existe e nao expirou pelo TTL."""
    if not caminho.exists() or caminho.stat().st_size == 0:
        return False
    if ttl_horas is None:
        return True
    idade_horas = (time.time() - caminho.stat().st_mtime) / 3600.0
    return idade_horas < ttl_horas


def obter_zip(
    url: str,
    pasta_cache: Path | None = None,
    ttl_horas: float | None = None,
) -> ZipFile:
    """Baixa um ZIP da CVM, reutilizando o cache em disco quando valido.

    ``ttl_horas=None`` significa cache sem expiracao (arquivos de anos ja
    encerrados nao mudam); um TTL finito e usado para o ano corrente, cujos
    ZIPs ganham novas entregas ao longo do ano.
    """
    if pasta_cache is not None:
        caminho_cache = pasta_cache / url.rsplit("/", 1)[-1]
        if _cache_valido(caminho_cache, ttl_horas):
            try:
                return ZipFile(caminho_cache)
            except BadZipFile:
                logger.warning("Cache de ZIP corrompido, rebaixando: %s", caminho_cache)
        conteudo = baixar_bytes(url)
        caminho_cache.write_bytes(conteudo)
        try:
            return ZipFile(caminho_cache)
        except BadZipFile as erro:
            raise RuntimeError(
                f"Arquivo ZIP invalido recebido da CVM em {url}: {erro}"
            ) from erro

    conteudo = baixar_bytes(url)
    try:
        return ZipFile(BytesIO(conteudo))
    except BadZipFile as erro:
        raise RuntimeError(
            f"Arquivo ZIP invalido recebido da CVM em {url}: {erro}"
        ) from erro


def ler_csv_do_zip(arquivo_zip: ZipFile, nome_arquivo: str) -> pd.DataFrame:
    """Le um CSV especifico dentro de um ZIP baixado da CVM."""
    if nome_arquivo not in arquivo_zip.namelist():
        raise RuntimeError(f"Arquivo {nome_arquivo} nao encontrado no ZIP da CVM.")

    with arquivo_zip.open(nome_arquivo) as arquivo:
        return pd.read_csv(arquivo, sep=";", encoding="latin1")
