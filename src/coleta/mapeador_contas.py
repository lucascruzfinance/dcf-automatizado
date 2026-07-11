"""Mapeador universal de contas da CVM para nomes padronizados.

Implementa a cascata de mapeamento da v2.0 (Onda 1 da universalizacao):

    1. Match exato por ``CD_CONTA`` no bloco da demonstracao correta
       (bancos/seguradoras usam os blocos ``*_financeira``).
    2. Fallback por ``DS_CONTA`` normalizado (minusculas, sem acento,
       match por CONTEM) contra ``por_nome_fallback``.
    3. Match por prefixo hierarquico mais proximo (ex.: ``2.01.04.01.01``
       herda o nome de ``2.01.04``). Roda DEPOIS do nome porque agregados
       como ``6.01`` (FCO) absorveriam linhas de ajuste do DFC — como a
       Depreciacao e Amortizacao — que precisam do match por nome.
    4. Nada encontrado -> registra em ``logs/contas_cvm_nao_mapeadas.log``
       com ticker, codigo, nome, demonstracao e valor, SEM quebrar.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_MAPEAMENTO = RAIZ_PROJETO / "config" / "mapeamento_cvm.json"
NOME_LOG_NAO_MAPEADAS = "contas_cvm_nao_mapeadas.log"

# Demonstracoes que possuem plano de contas proprio para financeiras.
DEMONSTRACOES_COM_BLOCO_FINANCEIRO = ("dre", "bp_ativo", "bp_passivo")


def normalizar_texto(valor: Any) -> str:
    """Normaliza texto (minusculas, sem acento) para comparacao defensiva."""
    texto = "" if valor is None else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


def carregar_json(caminho: Path) -> Any:
    """Carrega um JSON e falha com mensagem clara se ele estiver invalido."""
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError as erro:
        raise RuntimeError(f"Arquivo obrigatorio nao encontrado: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise RuntimeError(f"JSON invalido em {caminho}: {erro}") from erro


def carregar_mapeamento(raiz_projeto: Path | None = None) -> dict[str, Any]:
    """Carrega e valida a estrutura v2.0 de config/mapeamento_cvm.json."""
    raiz = RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)
    mapeamento = carregar_json(raiz / "config" / "mapeamento_cvm.json")
    obrigatorios = {"por_codigo", "por_nome_fallback", "campos"}
    faltantes = obrigatorios - set(mapeamento)
    if faltantes:
        raise RuntimeError(
            "config/mapeamento_cvm.json sem blocos obrigatorios da v2.0: "
            f"{sorted(faltantes)}"
        )
    return mapeamento


def normalizar_sinal(valor: Any, sinal_esperado: str | None) -> float | None:
    """Normaliza sinais: despesas e saidas de caixa negativas, receitas positivas."""
    if valor is None or pd.isna(valor):
        return None

    numero = float(valor)
    if sinal_esperado == "negativo":
        return -abs(numero)
    if sinal_esperado == "positivo":
        return abs(numero)
    return numero


def _blocos_por_tipo(
    secao: dict[str, Any],
    demonstracao: str,
    tipo_empresa: str,
) -> list[dict[str, Any]]:
    """Lista os blocos aplicaveis, do mais especifico para o mais generico.

    Financeiras usam o bloco ``<demonstracao>_financeira`` quando ele existe.
    No fallback por nome a financeira tambem consulta o bloco base em seguida
    (ex.: arrendamento em bp_passivo vale para banco); no match por codigo o
    chamador usa apenas o primeiro bloco, porque o mesmo codigo muda de
    significado entre os planos (3.01 de banco != receita_liquida).
    """
    blocos = []
    eh_financeira = normalizar_texto(tipo_empresa) == "financeira"
    if eh_financeira and demonstracao in DEMONSTRACOES_COM_BLOCO_FINANCEIRO:
        bloco_financeiro = secao.get(f"{demonstracao}_financeira")
        if isinstance(bloco_financeiro, dict):
            blocos.append(bloco_financeiro)
    bloco_base = secao.get(demonstracao)
    if isinstance(bloco_base, dict):
        blocos.append(bloco_base)
    return blocos


def _sinal_do_campo(mapeamento: dict[str, Any], nome_padronizado: str) -> str:
    """Le o sinal esperado do catalogo unico de campos."""
    campo = mapeamento.get("campos", {}).get(nome_padronizado, {})
    return str(campo.get("sinal_esperado", "positivo_ou_negativo"))


def _match_por_codigo(
    codigo: str,
    bloco: dict[str, Any],
) -> str | None:
    """Match exato de CD_CONTA no bloco da demonstracao."""
    nome = bloco.get(codigo)
    return str(nome) if nome else None


def _match_por_nome(
    descricao: str,
    blocos_fallback: list[dict[str, Any]],
) -> str | None:
    """Match por CONTEM da descricao normalizada contra os padroes de nome."""
    descricao_normalizada = normalizar_texto(descricao)
    if not descricao_normalizada:
        return None
    for bloco in blocos_fallback:
        for nome_padronizado, padroes in bloco.items():
            for padrao in padroes:
                if normalizar_texto(padrao) in descricao_normalizada:
                    return str(nome_padronizado)
    return None


def _match_por_prefixo(
    codigo: str,
    bloco: dict[str, Any],
    prefixos_nao_expandem: set[str],
) -> str | None:
    """Match pelo ancestral hierarquico mais proximo com pelo menos 2 niveis.

    Ancestrais de nivel 1 (``1``, ``2``, ``3``...) nunca expandem: mapear
    qualquer conta desconhecida para ativo_total/passivo_total seria ruido.
    """
    partes = codigo.split(".")
    while len(partes) > 1:
        partes = partes[:-1]
        if len(partes) < 2:
            return None
        ancestral = ".".join(partes)
        if ancestral in prefixos_nao_expandem:
            return None
        nome = bloco.get(ancestral)
        if nome:
            return str(nome)
    return None


def mapear_conta(
    codigo: Any,
    descricao: Any,
    demonstracao: str,
    tipo_empresa: str,
    mapeamento: dict[str, Any],
) -> dict[str, str] | None:
    """Aplica a cascata de mapeamento a uma unica conta da CVM.

    Devolve ``{"nome_padronizado", "sinal_esperado", "mapeado_por"}`` ou
    ``None`` quando a conta nao pode ser mapeada (o chamador registra no log).
    """
    codigo_texto = "" if codigo is None or pd.isna(codigo) else str(codigo).strip()
    blocos_codigo = _blocos_por_tipo(
        mapeamento.get("por_codigo", {}),
        demonstracao,
        tipo_empresa,
    )
    blocos_nome = _blocos_por_tipo(
        mapeamento.get("por_nome_fallback", {}),
        demonstracao,
        tipo_empresa,
    )
    prefixos_nao_expandem = set(
        mapeamento.get("cascata", {}).get("prefixos_nao_expandem", [])
    )

    # Passo 1 — codigo exato, apenas no bloco mais especifico do tipo: o
    # mesmo CD_CONTA muda de significado entre os planos contabeis.
    if codigo_texto and blocos_codigo:
        nome = _match_por_codigo(codigo_texto, blocos_codigo[0])
        if nome:
            return {
                "nome_padronizado": nome,
                "sinal_esperado": _sinal_do_campo(mapeamento, nome),
                "mapeado_por": "codigo",
            }

    # Passo 2 — nome normalizado (antes do prefixo; ver docstring do modulo).
    nome = _match_por_nome(descricao, blocos_nome)
    if nome:
        return {
            "nome_padronizado": nome,
            "sinal_esperado": _sinal_do_campo(mapeamento, nome),
            "mapeado_por": "nome",
        }

    # Passo 3 — prefixo hierarquico mais proximo.
    if codigo_texto and blocos_codigo:
        nome = _match_por_prefixo(
            codigo_texto,
            blocos_codigo[0],
            prefixos_nao_expandem,
        )
        if nome:
            return {
                "nome_padronizado": nome,
                "sinal_esperado": _sinal_do_campo(mapeamento, nome),
                "mapeado_por": "prefixo",
            }

    return None


def registrar_contas_nao_mapeadas(
    registros: list[dict[str, Any]],
    caminho_log: Path,
) -> None:
    """Persiste contas nao mapeadas no log de auditoria sem quebrar a coleta."""
    if not registros:
        return
    caminho_log.parent.mkdir(parents=True, exist_ok=True)
    linhas = []
    for registro in registros:
        linhas.append(
            "empresa={ticker} | cd_cvm={cd_cvm} | demonstracao={demonstracao} | "
            "codigo={codigo} | descricao={descricao} | valor={valor}".format(**registro)
        )
    with caminho_log.open("a", encoding="utf-8") as arquivo:
        for linha in sorted(set(linhas)):
            arquivo.write(linha + "\n")


def mapear_demonstracao(
    dados: pd.DataFrame,
    demonstracao: str,
    tipo_empresa: str,
    mapeamento: dict[str, Any] | None = None,
    ticker: str = "",
    cd_cvm: Any = "",
    caminho_log: Path | None = None,
    raiz_projeto: Path | None = None,
) -> pd.DataFrame:
    """Mapeia todas as linhas de uma demonstracao pela cascata da v2.0.

    Adiciona as colunas ``nome_padronizado``, ``sinal_esperado``,
    ``valor_padronizado``, ``mapeado_por`` e ``demonstracao_padronizada``
    (todas registradas em config/mapeamento_cvm.json). Contas nao mapeadas
    ficam com nome nulo e vao para o log — nunca derrubam o pipeline.
    """
    if dados.empty:
        return dados

    raiz = RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)
    if mapeamento is None:
        mapeamento = carregar_mapeamento(raiz)
    if caminho_log is None:
        caminho_log = raiz / "logs" / NOME_LOG_NAO_MAPEADAS

    dados = dados.copy()
    dados["demonstracao_padronizada"] = demonstracao

    # Mapeia cada par (codigo, descricao) uma unica vez e distribui o
    # resultado: as demonstracoes repetem a mesma conta em varios exercicios.
    pares = dados[["CD_CONTA", "DS_CONTA"]].astype(str)
    resultados: dict[tuple[str, str], dict[str, str] | None] = {}
    nao_mapeadas: dict[tuple[str, str], dict[str, Any]] = {}
    for indice, (codigo, descricao) in enumerate(
        zip(pares["CD_CONTA"], pares["DS_CONTA"])
    ):
        chave = (codigo, descricao)
        if chave in resultados:
            continue
        resultado = mapear_conta(
            codigo,
            descricao,
            demonstracao,
            tipo_empresa,
            mapeamento,
        )
        resultados[chave] = resultado
        if resultado is None:
            nao_mapeadas[chave] = {
                "ticker": ticker,
                "cd_cvm": cd_cvm,
                "demonstracao": demonstracao,
                "codigo": codigo,
                "descricao": descricao,
                "valor": dados.iloc[indice].get("VL_CONTA"),
            }

    def _coluna(chave_resultado: str) -> list[Any]:
        valores = []
        for codigo, descricao in zip(pares["CD_CONTA"], pares["DS_CONTA"]):
            resultado = resultados[(codigo, descricao)]
            valores.append(None if resultado is None else resultado[chave_resultado])
        return valores

    dados["nome_padronizado"] = _coluna("nome_padronizado")
    dados["sinal_esperado"] = _coluna("sinal_esperado")
    dados["mapeado_por"] = _coluna("mapeado_por")
    dados["valor_padronizado"] = [
        normalizar_sinal(valor, sinal) if nome is not None else None
        for valor, sinal, nome in zip(
            dados["VL_CONTA"],
            dados["sinal_esperado"],
            dados["nome_padronizado"],
        )
    ]

    registrar_contas_nao_mapeadas(list(nao_mapeadas.values()), caminho_log)
    return dados
