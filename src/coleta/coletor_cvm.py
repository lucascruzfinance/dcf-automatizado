"""Coletor universal de demonstrativos financeiros da CVM."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pandas as pd
import requests

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_PARAMETROS = RAIZ_PROJETO / "config" / "parametros.json"
CAMINHO_MAPEAMENTO = RAIZ_PROJETO / "config" / "mapeamento_cvm.json"
PASTA_CVM = RAIZ_PROJETO / "data" / "raw" / "cvm"
PASTA_LOGS = RAIZ_PROJETO / "logs"
URL_CVM = "https://dados.cvm.gov.br/dados"
TIMEOUT_SEGUNDOS = 60


@dataclass(frozen=True)
class EmpresaCvm:
    """Representa os metadados essenciais de uma companhia aberta na CVM."""

    ticker: str
    codigo_cvm: int
    razao_social: str
    setor: str
    tipo: str


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


def carregar_json(caminho: Path) -> dict[str, Any]:
    """Carrega um arquivo JSON e falha com mensagem clara se ele estiver invalido."""
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError as erro:
        raise RuntimeError(f"Arquivo obrigatorio nao encontrado: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise RuntimeError(f"JSON invalido em {caminho}: {erro}") from erro


def baixar_csv(url: str, sep: str = ";") -> pd.DataFrame:
    """Baixa um CSV da CVM com tratamento explicito de erros de rede e estrutura."""
    try:
        resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException as erro:
        raise RuntimeError(f"Falha ao acessar CVM em {url}: {erro}") from erro

    try:
        return pd.read_csv(BytesIO(resposta.content), sep=sep, encoding="latin1")
    except Exception as erro:
        raise RuntimeError(
            f"Falha ao interpretar CSV da CVM em {url}: {erro}"
        ) from erro


def baixar_arquivo_zip(url: str) -> ZipFile:
    """Baixa um ZIP da CVM e devolve um objeto ZipFile validado."""
    try:
        resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException as erro:
        raise RuntimeError(f"Falha ao baixar ZIP da CVM em {url}: {erro}") from erro

    try:
        return ZipFile(BytesIO(resposta.content))
    except Exception as erro:
        raise RuntimeError(
            f"Arquivo ZIP invalido recebido da CVM em {url}: {erro}"
        ) from erro


def ler_csv_do_zip(arquivo_zip: ZipFile, nome_arquivo: str) -> pd.DataFrame:
    """Le um CSV especifico dentro de um ZIP baixado da CVM."""
    if nome_arquivo not in arquivo_zip.namelist():
        raise RuntimeError(f"Arquivo {nome_arquivo} nao encontrado no ZIP da CVM.")

    with arquivo_zip.open(nome_arquivo) as arquivo:
        return pd.read_csv(arquivo, sep=";", encoding="latin1")


def carregar_cadastro_companhias() -> pd.DataFrame:
    """Carrega o cadastro de companhias abertas da CVM."""
    url = f"{URL_CVM}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
    cadastro = baixar_csv(url)
    colunas_obrigatorias = {"CD_CVM", "DENOM_SOCIAL"}
    if not colunas_obrigatorias.issubset(cadastro.columns):
        raise RuntimeError(
            "Cadastro CVM veio com estrutura inesperada. "
            f"Colunas recebidas: {list(cadastro.columns)}"
        )
    return cadastro


def carregar_valores_mobiliarios(anos: list[int]) -> pd.DataFrame:
    """Carrega arquivos FCA usados para relacionar ticker negociado ao CD_CVM."""
    quadros = []
    for ano in anos:
        url = f"{URL_CVM}/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"
        nome_csv = f"fca_cia_aberta_valor_mobiliario_{ano}.csv"
        try:
            arquivo_zip = baixar_arquivo_zip(url)
            quadro = ler_csv_do_zip(arquivo_zip, nome_csv)
        except RuntimeError as erro:
            logging.warning("Nao foi possivel carregar FCA %s: %s", ano, erro)
            continue
        quadro["ANO_REFERENCIA"] = ano
        quadros.append(quadro)

    if not quadros:
        raise RuntimeError("Nenhum arquivo FCA foi carregado para descobrir tickers.")
    return pd.concat(quadros, ignore_index=True)


def normalizar_texto(valor: Any) -> str:
    """Normaliza valores textuais da CVM para comparacoes defensivas."""
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper()


def encontrar_coluna_ticker(colunas: list[str]) -> str:
    """Encontra a coluna de ticker no arquivo FCA mesmo se a CVM renomear o campo."""
    candidatas = [
        "COD_NEGOCIACAO",
        "CODIGO_NEGOCIACAO",
        "CD_NEGOCIACAO",
        "CODIGO DE NEGOCIACAO",
        "CÓDIGO DE NEGOCIAÇÃO",
        "DS_IDENTIFICACAO",
    ]
    mapa_colunas = {normalizar_texto(coluna): coluna for coluna in colunas}
    for candidata in candidatas:
        if candidata in mapa_colunas:
            return mapa_colunas[candidata]

    for coluna in colunas:
        nome = normalizar_texto(coluna)
        if "NEGOCI" in nome or "TICKER" in nome:
            return coluna
    raise RuntimeError(f"Coluna de ticker nao encontrada no FCA. Colunas: {colunas}")


def detectar_tipo_empresa(setor: str) -> str:
    """Detecta se a empresa deve seguir a trilha financeira ou nao-financeira."""
    setor_normalizado = normalizar_texto(setor)
    termos_financeiros = [
        "FINANCEIRO",
        "BANCO",
        "BANCOS",
        "SEGURADORA",
        "SEGUROS",
        "PREVIDENCIA",
        "INTERMEDIARIOS FINANCEIROS",
        "SERVICOS FINANCEIROS",
    ]
    if any(termo in setor_normalizado for termo in termos_financeiros):
        return "financeira"
    return "nao_financeira"


def descobrir_empresa_por_ticker(ticker: str) -> EmpresaCvm:
    """Descobre CD_CVM e metadados da empresa a partir do ticker negociado na B3."""
    ticker_normalizado = normalizar_texto(ticker).replace(".SA", "")
    ano_atual = date.today().year
    anos_fca = list(range(ano_atual, ano_atual - 8, -1))
    cadastro = carregar_cadastro_companhias()
    valores = carregar_valores_mobiliarios(anos_fca)
    coluna_ticker = encontrar_coluna_ticker(list(valores.columns))

    valores["_ticker_normalizado"] = valores[coluna_ticker].map(normalizar_texto)
    encontrados = valores[valores["_ticker_normalizado"] == ticker_normalizado]
    if encontrados.empty:
        raise ValueError(
            f"Ticker {ticker_normalizado} nao encontrado nos arquivos FCA da CVM. "
            "Confira o ticker ou a disponibilidade dos dados na CVM."
        )

    encontrado_recente = encontrados.sort_values("ANO_REFERENCIA").iloc[-1]
    if "CD_CVM" in encontrados.columns and pd.notna(encontrado_recente.get("CD_CVM")):
        codigo_cvm = int(encontrado_recente["CD_CVM"])
        cadastro_empresa = cadastro[cadastro["CD_CVM"].astype(int) == codigo_cvm]
    elif "CNPJ_Companhia" in encontrados.columns:
        cnpj = encontrado_recente["CNPJ_Companhia"]
        cadastro_empresa = cadastro[cadastro["CNPJ_CIA"] == cnpj]
        if cadastro_empresa.empty:
            raise RuntimeError(
                f"CNPJ {cnpj} encontrado para {ticker_normalizado}, "
                "mas ausente no cadastro de companhias abertas."
            )
        codigo_cvm = int(cadastro_empresa.iloc[0]["CD_CVM"])
    else:
        raise RuntimeError(
            "FCA nao trouxe CD_CVM nem CNPJ_Companhia. "
            f"Colunas recebidas: {list(encontrados.columns)}"
        )

    if cadastro_empresa.empty:
        raise RuntimeError(
            f"CD_CVM {codigo_cvm} encontrado para {ticker_normalizado}, "
            "mas ausente no cadastro de companhias abertas."
        )

    linha = cadastro_empresa.iloc[0]
    setor = str(linha.get("SETOR_ATIV", ""))
    return EmpresaCvm(
        ticker=ticker_normalizado,
        codigo_cvm=codigo_cvm,
        razao_social=str(linha["DENOM_SOCIAL"]),
        setor=setor,
        tipo=detectar_tipo_empresa(setor),
    )


def criar_mapa_contas() -> dict[str, dict[str, str]]:
    """Cria indice CD_CONTA -> metadados padronizados a partir do mapeamento."""
    mapeamento = carregar_json(CAMINHO_MAPEAMENTO)
    mapa = {}
    for nome_padronizado, detalhes in mapeamento.get("campos", {}).items():
        for codigo in detalhes.get("codigos_cvm", []):
            mapa[str(codigo)] = {
                "nome_padronizado": nome_padronizado,
                "sinal_esperado": detalhes.get("sinal_esperado", ""),
                "descricao_padronizada": detalhes.get("descricao", ""),
            }
    if not mapa:
        raise RuntimeError("Mapeamento CVM nao possui codigos configurados.")
    return mapa


def anos_para_coleta() -> list[int]:
    """Define os anos que devem ser coletados com base em config/parametros.json."""
    parametros = carregar_json(CAMINHO_PARAMETROS)
    quantidade = int(parametros.get("anos_historicos_coleta", 7))
    ano_atual = date.today().year
    return list(range(ano_atual - quantidade + 1, ano_atual + 1))


def nome_arquivo_demonstrativo(
    tipo_documento: str,
    demonstrativo: str,
    ano: int,
) -> str:
    """Monta o nome oficial do CSV de demonstrativo dentro dos ZIPs da CVM."""
    return f"{tipo_documento.lower()}_cia_aberta_{demonstrativo}_con_{ano}.csv"


def url_zip_demonstrativo(tipo_documento: str, ano: int) -> str:
    """Monta a URL oficial do ZIP anual de DFP ou ITR da CVM."""
    return (
        f"{URL_CVM}/CIA_ABERTA/DOC/{tipo_documento.upper()}/DADOS/"
        f"{tipo_documento.lower()}_cia_aberta_{ano}.zip"
    )


def coletar_demonstrativo_ano(
    empresa: EmpresaCvm,
    tipo_documento: str,
    demonstrativo: str,
    ano: int,
) -> pd.DataFrame:
    """Coleta um demonstrativo especifico de uma empresa em um ano."""
    url = url_zip_demonstrativo(tipo_documento, ano)
    nome_csv = nome_arquivo_demonstrativo(tipo_documento, demonstrativo, ano)
    arquivo_zip = baixar_arquivo_zip(url)
    dados = ler_csv_do_zip(arquivo_zip, nome_csv)

    colunas_obrigatorias = {"CD_CVM", "CD_CONTA", "DS_CONTA", "VL_CONTA", "DT_REFER"}
    if not colunas_obrigatorias.issubset(dados.columns):
        raise RuntimeError(
            f"{nome_csv} veio com estrutura inesperada. "
            f"Colunas recebidas: {list(dados.columns)}"
        )

    dados_empresa = dados[dados["CD_CVM"].astype(int) == empresa.codigo_cvm].copy()
    if dados_empresa.empty:
        logging.warning(
            "Sem dados para %s em %s %s %s",
            empresa.ticker,
            tipo_documento,
            demonstrativo,
            ano,
        )
        return pd.DataFrame()

    dados_empresa["tipo_documento"] = tipo_documento.upper()
    dados_empresa["demonstrativo"] = demonstrativo
    dados_empresa["ano_arquivo"] = ano
    return dados_empresa


def normalizar_sinal(valor: Any, sinal_esperado: str) -> float | None:
    """Normaliza sinais: despesas e saidas de caixa negativas, receitas positivas."""
    if pd.isna(valor):
        return None

    numero = float(valor)
    if sinal_esperado == "negativo":
        return -abs(numero)
    if sinal_esperado == "positivo":
        return abs(numero)
    return numero


def registrar_contas_nao_mapeadas(
    empresa: EmpresaCvm,
    dados: pd.DataFrame,
    mapa_contas: dict[str, dict[str, str]],
) -> None:
    """Registra contas da CVM ausentes do mapeamento sem interromper o pipeline."""
    caminho_log = PASTA_LOGS / "contas_cvm_nao_mapeadas.log"
    contas = dados[["CD_CONTA", "DS_CONTA"]].drop_duplicates()
    linhas = []
    for _, linha in contas.iterrows():
        codigo = str(linha["CD_CONTA"])
        if codigo in mapa_contas:
            continue
        linhas.append(
            f"empresa={empresa.ticker} | cd_cvm={empresa.codigo_cvm} | "
            f"codigo={codigo} | descricao={linha['DS_CONTA']}"
        )

    if linhas:
        PASTA_LOGS.mkdir(parents=True, exist_ok=True)
        with caminho_log.open("a", encoding="utf-8") as arquivo:
            for linha in sorted(set(linhas)):
                arquivo.write(linha + "\n")
        logging.info(
            "%s contas nao mapeadas registradas para %s",
            len(set(linhas)),
            empresa.ticker,
        )


def mapear_contas(
    empresa: EmpresaCvm,
    dados: pd.DataFrame,
    mapa_contas: dict[str, dict[str, str]],
) -> pd.DataFrame:
    """Traduz CD_CONTA para nomes padronizados e aplica convencao de sinais."""
    if dados.empty:
        return dados

    registrar_contas_nao_mapeadas(empresa, dados, mapa_contas)
    dados = dados.copy()
    dados["nome_padronizado"] = (
        dados["CD_CONTA"]
        .astype(str)
        .map(lambda codigo: mapa_contas.get(codigo, {}).get("nome_padronizado"))
    )
    dados["sinal_esperado"] = (
        dados["CD_CONTA"]
        .astype(str)
        .map(lambda codigo: mapa_contas.get(codigo, {}).get("sinal_esperado"))
    )
    dados["valor_padronizado"] = dados.apply(
        lambda linha: normalizar_sinal(linha["VL_CONTA"], linha["sinal_esperado"]),
        axis=1,
    )
    return dados


def salvar_json(caminho: Path, conteudo: Any) -> None:
    """Salva conteudo JSON com UTF-8 e indentacao estavel."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False, indent=2, default=str)


def salvar_metadados(empresa: EmpresaCvm) -> None:
    """Persiste metadados no contrato data/raw/cvm/<TICKER>_meta.json."""
    salvar_json(PASTA_CVM / f"{empresa.ticker}_meta.json", empresa.__dict__)


def salvar_demonstrativo(ticker: str, demonstrativo: str, dados: pd.DataFrame) -> None:
    """Persiste dados brutos e mapeados de um demonstrativo em JSON auditavel."""
    registros = dados.where(pd.notna(dados), None).to_dict(orient="records")
    salvar_json(PASTA_CVM / f"{ticker}_{demonstrativo.lower()}.json", registros)


def coletar_empresa(ticker: str) -> dict[str, pd.DataFrame]:
    """Executa a coleta CVM completa para um ticker da B3."""
    empresa = descobrir_empresa_por_ticker(ticker)
    salvar_metadados(empresa)
    mapa_contas = criar_mapa_contas()
    anos = anos_para_coleta()
    demonstrativos = {
        "DRE": ["DRE"],
        "BP": ["BPA", "BPP"],
        "DFC": ["DFC_MI", "DFC_MD"],
    }
    resultado = {}

    logging.info(
        "Iniciando coleta CVM para %s | CD_CVM=%s | tipo=%s",
        empresa.ticker,
        empresa.codigo_cvm,
        empresa.tipo,
    )
    for nome_saida, arquivos_cvm in demonstrativos.items():
        quadros = []
        for ano in anos:
            for tipo_documento in ("DFP", "ITR"):
                for arquivo_cvm in arquivos_cvm:
                    try:
                        quadro = coletar_demonstrativo_ano(
                            empresa, tipo_documento, arquivo_cvm, ano
                        )
                    except RuntimeError as erro:
                        logging.warning(
                            "Falha em %s %s %s %s: %s",
                            empresa.ticker,
                            tipo_documento,
                            arquivo_cvm,
                            ano,
                            erro,
                        )
                        continue
                    if not quadro.empty:
                        quadros.append(quadro)

        if not quadros:
            logging.error(
                "Nenhum dado de %s coletado para %s",
                nome_saida,
                empresa.ticker,
            )
            resultado[nome_saida] = pd.DataFrame()
            salvar_demonstrativo(empresa.ticker, nome_saida, pd.DataFrame())
            continue

        dados = pd.concat(quadros, ignore_index=True)
        dados_mapeados = mapear_contas(empresa, dados, mapa_contas)
        salvar_demonstrativo(empresa.ticker, nome_saida, dados_mapeados)
        resultado[nome_saida] = dados_mapeados

    return resultado


def selecionar_valor_anual(
    dados: pd.DataFrame,
    nome_padronizado: str,
) -> pd.DataFrame:
    """Seleciona valores anuais DFP para uma conta padronizada."""
    if dados.empty or "nome_padronizado" not in dados.columns:
        return pd.DataFrame(columns=["ano", nome_padronizado])

    filtro = (
        (dados["tipo_documento"] == "DFP")
        & (dados["nome_padronizado"] == nome_padronizado)
        & (dados["valor_padronizado"].notna())
    )
    selecionado = dados.loc[filtro, ["DT_REFER", "valor_padronizado"]].copy()
    if selecionado.empty:
        return pd.DataFrame(columns=["ano", nome_padronizado])

    selecionado["ano"] = pd.to_datetime(selecionado["DT_REFER"]).dt.year
    selecionado = selecionado.sort_values("DT_REFER").drop_duplicates(
        "ano",
        keep="last",
    )
    return selecionado[["ano", "valor_padronizado"]].rename(
        columns={"valor_padronizado": nome_padronizado}
    )


def imprimir_resumo(ticker: str, dados: dict[str, pd.DataFrame]) -> None:
    """Imprime resumo comparativo para validacao manual pelo analista."""
    meta = carregar_json(PASTA_CVM / f"{ticker}_meta.json")
    dre = dados.get("DRE", pd.DataFrame())
    receita = selecionar_valor_anual(dre, "receita_liquida")
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
    print(f"Tipo detectado: {meta['tipo']}")
    print(f"Setor CVM: {meta['setor']}")
    print(f"Anos coletados: {anos}")
    print("Receita Liquida e Lucro Liquido - ultimos 3 anos:")
    if resumo.empty:
        print("  Sem valores anuais mapeados para Receita Liquida/Lucro Liquido.")
    else:
        for _, linha in resumo.iterrows():
            print(
                f"  {int(linha['ano'])}: "
                f"receita_liquida={linha.get('receita_liquida')} | "
                f"lucro_liquido={linha.get('lucro_liquido')}"
            )


def executar_validacao_padrao() -> None:
    """Executa a validacao local da Semana 0 para DIRR3 e MGLU3."""
    configurar_log()
    for ticker in ("DIRR3", "MGLU3"):
        try:
            dados = coletar_empresa(ticker)
            imprimir_resumo(ticker, dados)
        except Exception as erro:
            logging.exception("Coleta falhou para %s: %s", ticker, erro)
            print(f"Falha na coleta de {ticker}: {erro}")


if __name__ == "__main__":
    executar_validacao_padrao()
