"""Coletor universal de demonstrativos financeiros da CVM (v2.0).

Aceita QUALQUER ticker da B3: resolve o CD_CVM via ``resolvedor_ticker``,
classifica tipo/subtipo via ``classificador_empresa`` e mapeia contas via
``mapeador_contas`` (cascata CD_CONTA -> nome -> prefixo -> log). Coleta
DFP + ITR de DRE, BP (ativo e passivo), DFC (MI/MD) e DVA, preferindo
demonstracoes CONSOLIDADAS com fallback para individuais (com aviso).

Contratos persistidos em ``data/raw/cvm/``:
    <TICKER>_meta.json  — identidade + tipo, subtipo, metodo_valuation,
                          taxa_desconto, consolidado, score_confiabilidade
    <TICKER>_dre.json / _bp.json / _dfc.json / _dva.json — linhas brutas da
    CVM acrescidas de nome_padronizado, sinal_esperado, valor_padronizado,
    mapeado_por, demonstracao_padronizada e origem_consolidacao.

A coleta em lote (``coleta_lote.py``) usa ``coletar_empresas``: cada ZIP
anual da CVM e aberto UMA vez e filtrado para todas as empresas do lote.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.coleta.apoio_cvm import (
    URL_CVM,
    ler_csv_do_zip,
    obter_zip,
    pasta_cache_zips,
)
from src.coleta.classificador_empresa import carregar_setores, classificar_empresa

# Reexports de compatibilidade v1: testes e chamadores antigos importam
# estes nomes daqui (o noqa precisa ficar na linha do proprio import).
from src.coleta.classificador_empresa import detectar_tipo_empresa  # noqa: F401
from src.coleta.mapeador_contas import (
    carregar_json,
    carregar_mapeamento,
    mapear_demonstracao,
)
from src.coleta.mapeador_contas import normalizar_sinal  # noqa: F401
from src.coleta.resolvedor_ticker import TickerNaoEncontradoErro  # noqa: F401
from src.coleta.resolvedor_ticker import normalizar_ticker, resolver_ticker

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
PASTA_LOGS = RAIZ_PROJETO / "logs"
# O timeout HTTP efetivo vive em apoio_cvm.TIMEOUT_SEGUNDOS (=120); nao
# duplicar aqui para nao divergir.

# nome_saida -> [(arquivo CSV da CVM, demonstracao padronizada do mapeamento)]
DEMONSTRATIVOS: dict[str, list[tuple[str, str]]] = {
    "DRE": [("DRE", "dre")],
    "BP": [("BPA", "bp_ativo"), ("BPP", "bp_passivo")],
    "DFC": [("DFC_MI", "dfc"), ("DFC_MD", "dfc")],
    "DVA": [("DVA", "dva")],
}

COLUNAS_OBRIGATORIAS_CSV = {"CD_CVM", "CD_CONTA", "DS_CONTA", "VL_CONTA", "DT_REFER"}


@dataclass(frozen=True)
class EmpresaCvm:
    """Identidade e classificacao de uma companhia aberta para a coleta."""

    ticker: str
    codigo_cvm: int
    cnpj: str
    razao_social: str
    setor: str
    tipo: str
    subtipo: str
    metodo_valuation: str
    taxa_desconto: str


def configurar_log() -> None:
    """Configura logs operacionais e de contas CVM nao mapeadas."""
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(PASTA_LOGS / "coletor_cvm.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def resolver_raiz(raiz_projeto: Path | None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    return RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)


def pasta_cvm(raiz_projeto: Path) -> Path:
    """Pasta de persistencia dos dados brutos da CVM."""
    return raiz_projeto / "data" / "raw" / "cvm"


def anos_para_coleta(raiz_projeto: Path) -> list[int]:
    """Define os anos coletados com base em config/parametros.json."""
    parametros = carregar_json(raiz_projeto / "config" / "parametros.json")
    quantidade = int(parametros.get("anos_historicos_coleta", 7))
    ano_atual = date.today().year
    return list(range(ano_atual - quantidade + 1, ano_atual + 1))


def nome_arquivo_demonstrativo(
    tipo_documento: str,
    demonstrativo: str,
    consolidacao: str,
    ano: int,
) -> str:
    """Monta o nome oficial do CSV de demonstrativo dentro dos ZIPs da CVM."""
    return (
        f"{tipo_documento.lower()}_cia_aberta_{demonstrativo}_"
        f"{consolidacao}_{ano}.csv"
    )


def url_zip_demonstrativo(tipo_documento: str, ano: int) -> str:
    """Monta a URL oficial do ZIP anual de DFP ou ITR da CVM."""
    return (
        f"{URL_CVM}/CIA_ABERTA/DOC/{tipo_documento.upper()}/DADOS/"
        f"{tipo_documento.lower()}_cia_aberta_{ano}.zip"
    )


def montar_empresa(
    ticker: str,
    raiz_projeto: Path,
    setores: dict[str, Any] | None = None,
) -> EmpresaCvm:
    """Resolve a identidade CVM do ticker e classifica tipo/subtipo."""
    resolvida = resolver_ticker(ticker, raiz_projeto)
    classificacao = classificar_empresa(
        resolvida.setor_cvm,
        ticker=resolvida.ticker,
        setores=setores,
        raiz_projeto=raiz_projeto,
    )
    return EmpresaCvm(
        ticker=resolvida.ticker,
        codigo_cvm=resolvida.codigo_cvm,
        cnpj=resolvida.cnpj,
        razao_social=resolvida.razao_social,
        setor=resolvida.setor_cvm,
        tipo=classificacao["tipo"],
        subtipo=classificacao["subtipo"],
        metodo_valuation=classificacao["metodo_valuation"],
        taxa_desconto=classificacao["taxa_desconto"],
    )


def salvar_json(caminho: Path, conteudo: Any) -> None:
    """Salva conteudo JSON com UTF-8 e indentacao estavel."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False, indent=2, default=str)


def salvar_metadados(
    empresa: EmpresaCvm,
    raiz_projeto: Path,
    consolidado: bool | None = None,
    score_confiabilidade: int | None = None,
) -> None:
    """Persiste o contrato v2.0 de data/raw/cvm/<TICKER>_meta.json.

    Preserva o score ja gravado pelo relatorio de qualidade quando esta
    funcao roda de novo sem um score novo (coleta antes do relatorio).
    """
    caminho = pasta_cvm(raiz_projeto) / f"{empresa.ticker}_meta.json"
    conteudo = asdict(empresa)
    if caminho.exists():
        try:
            anterior = carregar_json(caminho)
        except RuntimeError:
            anterior = {}
        if score_confiabilidade is None:
            score_confiabilidade = anterior.get("score_confiabilidade")
        if consolidado is None:
            consolidado = anterior.get("consolidado")
    conteudo["consolidado"] = consolidado
    conteudo["score_confiabilidade"] = score_confiabilidade
    salvar_json(caminho, conteudo)


def salvar_demonstrativo(
    ticker: str,
    demonstrativo: str,
    dados: pd.DataFrame,
    raiz_projeto: Path,
) -> None:
    """Persiste dados brutos e mapeados de um demonstrativo em JSON auditavel."""
    if dados.empty:
        registros: list[dict[str, Any]] = []
    else:
        registros = dados.where(pd.notna(dados), None).to_dict(orient="records")
    salvar_json(
        pasta_cvm(raiz_projeto) / f"{ticker}_{demonstrativo.lower()}.json",
        registros,
    )


def _filtrar_empresas_no_csv(
    quadro: pd.DataFrame,
    codigos_pendentes: set[int],
    consolidacao: str,
) -> dict[int, pd.DataFrame]:
    """Extrai as linhas de cada empresa pendente de um CSV da CVM."""
    if not COLUNAS_OBRIGATORIAS_CSV.issubset(quadro.columns):
        raise RuntimeError(
            "CSV da CVM com estrutura inesperada. "
            f"Colunas recebidas: {list(quadro.columns)}"
        )
    codigos_csv = pd.to_numeric(quadro["CD_CVM"], errors="coerce")
    resultado: dict[int, pd.DataFrame] = {}
    for codigo in codigos_pendentes:
        linhas = quadro[codigos_csv == codigo]
        if linhas.empty:
            continue
        linhas = linhas.copy()
        linhas["origem_consolidacao"] = consolidacao
        resultado[codigo] = linhas
    return resultado


def _coletar_arquivo_para_lote(
    arquivo_zip: Any,
    tipo_documento: str,
    arquivo_cvm: str,
    ano: int,
    codigos: set[int],
) -> dict[int, pd.DataFrame]:
    """Coleta um demonstrativo do ZIP para todas as empresas do lote.

    Prefere o CSV consolidado (``_con_``); empresas ausentes dele caem para
    o individual (``_ind_``) — a decisao e por empresa/ano/arquivo, porque
    uma companhia pode ter consolidado em uns exercicios e nao em outros.
    """
    resultado: dict[int, pd.DataFrame] = {}
    for consolidacao in ("con", "ind"):
        pendentes = codigos - set(resultado)
        if not pendentes:
            break
        nome_csv = nome_arquivo_demonstrativo(
            tipo_documento,
            arquivo_cvm,
            consolidacao,
            ano,
        )
        try:
            quadro = ler_csv_do_zip(arquivo_zip, nome_csv)
        except RuntimeError as erro:
            logging.warning("CSV ausente no ZIP da CVM (%s): %s", nome_csv, erro)
            continue
        resultado.update(_filtrar_empresas_no_csv(quadro, pendentes, consolidacao))
    return resultado


def coletar_empresas(
    tickers: list[str],
    raiz_projeto: Path | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, Exception]]:
    """Executa a coleta CVM completa para uma lista de tickers da B3.

    Devolve ``(dados_por_ticker, erros_por_ticker)``: falha em um ticker
    (ex.: ticker inexistente) nao derruba o lote — o erro fica registrado
    e a coleta segue para os demais.
    """
    raiz = resolver_raiz(raiz_projeto)
    setores = carregar_setores(raiz)
    mapeamento = carregar_mapeamento(raiz)
    anos = anos_para_coleta(raiz)
    pasta_cache = pasta_cache_zips(raiz)
    ano_corrente = date.today().year

    empresas: dict[str, EmpresaCvm] = {}
    erros: dict[str, Exception] = {}
    for ticker in tickers:
        ticker_normalizado = normalizar_ticker(ticker)
        try:
            empresas[ticker_normalizado] = montar_empresa(
                ticker_normalizado,
                raiz,
                setores,
            )
        except Exception as erro:  # noqa: BLE001 - falha isolada por ticker
            logging.error("Falha ao resolver %s: %s", ticker_normalizado, erro)
            erros[ticker_normalizado] = erro

    if not empresas:
        return {}, erros

    codigo_para_ticker = {
        empresa.codigo_cvm: ticker for ticker, empresa in empresas.items()
    }
    codigos = set(codigo_para_ticker)
    # brutos[ticker][arquivo_cvm] = lista de quadros (um por ano/tipo_doc)
    brutos: dict[str, dict[str, list[pd.DataFrame]]] = {
        ticker: {} for ticker in empresas
    }

    for ano in anos:
        for tipo_documento in ("DFP", "ITR"):
            url = url_zip_demonstrativo(tipo_documento, ano)
            # ZIPs de anos encerrados nao mudam; o do ano corrente expira 24h.
            ttl_horas = 24.0 if ano >= ano_corrente else None
            try:
                arquivo_zip = obter_zip(
                    url,
                    pasta_cache=pasta_cache,
                    ttl_horas=ttl_horas,
                )
            except RuntimeError as erro:
                logging.warning(
                    "ZIP %s %s indisponivel: %s",
                    tipo_documento,
                    ano,
                    erro,
                )
                continue
            for arquivos in DEMONSTRATIVOS.values():
                for arquivo_cvm, _ in arquivos:
                    por_codigo = _coletar_arquivo_para_lote(
                        arquivo_zip,
                        tipo_documento,
                        arquivo_cvm,
                        ano,
                        codigos,
                    )
                    for codigo, quadro in por_codigo.items():
                        quadro["tipo_documento"] = tipo_documento
                        quadro["demonstrativo"] = arquivo_cvm
                        quadro["ano_arquivo"] = ano
                        ticker = codigo_para_ticker[codigo]
                        brutos[ticker].setdefault(arquivo_cvm, []).append(quadro)

    resultado: dict[str, dict[str, pd.DataFrame]] = {}
    for ticker, empresa in empresas.items():
        resultado[ticker] = _consolidar_e_salvar_empresa(
            empresa,
            brutos[ticker],
            mapeamento,
            raiz,
        )
    return resultado, erros


def _consolidar_e_salvar_empresa(
    empresa: EmpresaCvm,
    brutos: dict[str, list[pd.DataFrame]],
    mapeamento: dict[str, Any],
    raiz_projeto: Path,
) -> dict[str, pd.DataFrame]:
    """Mapeia contas, persiste JSONs e o _meta.json de uma empresa."""
    caminho_log = raiz_projeto / "logs" / "contas_cvm_nao_mapeadas.log"
    resultado: dict[str, pd.DataFrame] = {}
    houve_individual = False

    for nome_saida, arquivos in DEMONSTRATIVOS.items():
        quadros_mapeados = []
        for arquivo_cvm, demonstracao_padronizada in arquivos:
            quadros = brutos.get(arquivo_cvm, [])
            if not quadros:
                continue
            dados = pd.concat(quadros, ignore_index=True)
            if (dados["origem_consolidacao"] == "ind").any():
                houve_individual = True
            dados_mapeados = mapear_demonstracao(
                dados,
                demonstracao=demonstracao_padronizada,
                tipo_empresa=empresa.tipo,
                mapeamento=mapeamento,
                ticker=empresa.ticker,
                cd_cvm=empresa.codigo_cvm,
                caminho_log=caminho_log,
                raiz_projeto=raiz_projeto,
            )
            quadros_mapeados.append(dados_mapeados)

        if quadros_mapeados:
            dados_saida = pd.concat(quadros_mapeados, ignore_index=True)
        else:
            dados_saida = pd.DataFrame()
            logging.error(
                "Nenhum dado de %s coletado para %s",
                nome_saida,
                empresa.ticker,
            )
        salvar_demonstrativo(empresa.ticker, nome_saida, dados_saida, raiz_projeto)
        resultado[nome_saida] = dados_saida

    if houve_individual:
        logging.warning(
            "%s: demonstracoes consolidadas ausentes em parte dos exercicios; "
            "demonstracoes INDIVIDUAIS usadas como fallback (ver _meta.json).",
            empresa.ticker,
        )
    salvar_metadados(empresa, raiz_projeto, consolidado=not houve_individual)
    return resultado


def coletar_empresa(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Executa a coleta CVM completa para um unico ticker da B3."""
    ticker_normalizado = normalizar_ticker(ticker)
    resultado, erros = coletar_empresas([ticker_normalizado], raiz_projeto)
    if ticker_normalizado in erros:
        raise erros[ticker_normalizado]
    return resultado[ticker_normalizado]


def selecionar_valor_anual(
    dados: pd.DataFrame,
    nome_padronizado: str,
) -> pd.DataFrame:
    """Seleciona valores anuais DFP para uma conta padronizada.

    Prefere o codigo de conta mais curto (a conta-mae consolidada) para que
    linhas mapeadas por prefixo nao substituam o total oficial.
    """
    if dados.empty or "nome_padronizado" not in dados.columns:
        return pd.DataFrame(columns=["ano", nome_padronizado])

    filtro = (
        (dados["tipo_documento"] == "DFP")
        & (dados["nome_padronizado"] == nome_padronizado)
        & (dados["valor_padronizado"].notna())
    )
    selecionado = dados.loc[
        filtro, ["DT_REFER", "CD_CONTA", "valor_padronizado"]
    ].copy()
    if selecionado.empty:
        return pd.DataFrame(columns=["ano", nome_padronizado])

    selecionado["ano"] = pd.to_datetime(selecionado["DT_REFER"]).dt.year
    selecionado["_prioridade"] = selecionado["CD_CONTA"].astype(str).str.len()
    selecionado = selecionado.sort_values(["_prioridade", "DT_REFER"])
    selecionado = selecionado.drop_duplicates("ano", keep="first")
    return (
        selecionado[["ano", "valor_padronizado"]]
        .rename(columns={"valor_padronizado": nome_padronizado})
        .sort_values("ano")
    )


def imprimir_resumo(
    ticker: str,
    dados: dict[str, pd.DataFrame],
    raiz_projeto: Path | None = None,
) -> None:
    """Imprime resumo comparativo para validacao manual pelo analista."""
    raiz = resolver_raiz(raiz_projeto)
    meta = carregar_json(pasta_cvm(raiz) / f"{ticker}_meta.json")
    dre = dados.get("DRE", pd.DataFrame())
    receita_nome = (
        "receitas_intermediacao_financeira"
        if meta.get("tipo") == "financeira"
        else "receita_liquida"
    )
    receita = selecionar_valor_anual(dre, receita_nome)
    lucro = selecionar_valor_anual(dre, "lucro_liquido")
    resumo = receita.merge(lucro, on="ano", how="outer").sort_values("ano").tail(3)
    if dre.empty or "ano_arquivo" not in dre.columns:
        anos = []
    else:
        anos = sorted(dre["ano_arquivo"].dropna().astype(int).unique().tolist())

    print("\n" + "=" * 80)
    print(f"Ticker: {ticker}")
    print(f"Razao social: {meta['razao_social']}")
    print(f"CD_CVM: {meta['codigo_cvm']}")
    print(f"Tipo/subtipo: {meta['tipo']} / {meta.get('subtipo', 'n/d')}")
    print(
        "Metodo: "
        f"{meta.get('metodo_valuation', 'n/d')} | "
        f"taxa de desconto: {meta.get('taxa_desconto', 'n/d')} | "
        f"consolidado: {meta.get('consolidado', 'n/d')}"
    )
    print(f"Setor CVM: {meta['setor']}")
    print(f"Anos coletados: {anos}")
    print(f"{receita_nome} e lucro_liquido - ultimos 3 anos:")
    if resumo.empty:
        print("  Sem valores anuais mapeados para receita/lucro.")
    else:
        for _, linha in resumo.iterrows():
            print(
                f"  {int(linha['ano'])}: "
                f"{receita_nome}={linha.get(receita_nome)} | "
                f"lucro_liquido={linha.get('lucro_liquido')}"
            )


def executar_validacao_padrao() -> None:
    """Executa a validacao local para DIRR3 e MGLU3 (regressao dourada)."""
    configurar_log()
    for ticker in ("DIRR3", "MGLU3"):
        try:
            dados = coletar_empresa(ticker)
            imprimir_resumo(ticker, dados)
        except Exception as erro:  # noqa: BLE001 - validacao manual
            logging.exception("Coleta falhou para %s: %s", ticker, erro)
            print(f"Falha na coleta de {ticker}: {erro}")


if __name__ == "__main__":
    executar_validacao_padrao()
