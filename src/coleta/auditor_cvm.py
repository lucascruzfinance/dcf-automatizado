"""Auditor de amarracao historica contra a propria CVM (Prompt 9.0.1).

Valida, SEM REDE, que a base historica persistida em ``data/raw/cvm/`` bate
com a aritmetica dos proprios demonstrativos divulgados (DFP/ITR):

1. **Balanco fecha:** Ativo Total (conta 1) = Passivo Total (conta 2, que na
   CVM ja inclui o PL), e cada total = soma dos proprios subtotais.
2. **Subtotais batem:** AC/ANC/PC/PNC/PL = soma das contas de nivel 3; DRE
   reconstroi Lucro Bruto -> EBIT -> EBT -> LL pelas identidades do plano.
3. **DFC amarra:** FCO+FCI+FCF+variacao cambial = variacao de caixa; saldo
   final do DFC (6.05.02) = caixa do BP (com fallback caixa+aplicacoes,
   conceito de caixa ampliado, reportado como AVISO).
4. **Cobertura de mapeamento:** % do Ativo/Passivo que fica em residual
   (linhas sem nome proprio + baldes "Outros"); meta < 5% do total.
5. **Escala e sinais:** ESCALA_MOEDA uniforme; despesas da DRE negativas;
   subtotais do BP nao-negativos.

O auditor NUNCA derruba o pipeline: reporta OK/AVISO/ERRO e persiste
``data/raw/cvm/<TICKER>_auditoria_cvm.json`` (o bloco ``bp_aberto`` e a fonte
do BP historico linha a linha para o Excel do 9.0.5). O modo ``--estrito``
levanta RuntimeError no primeiro ERRO (uso em CI).

Inclui ``remapear_empresa``: reaplica a cascata de mapeamento ATUAL aos JSONs
brutos ja coletados (recoleta OFFLINE apos expandir o mapeamento) e atualiza
o Parquet limpo correspondente.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.coleta.mapeador_contas import (  # noqa: E402
    carregar_json,
    carregar_mapeamento,
    mapear_demonstracao,
    normalizar_texto,
)

logger = logging.getLogger(__name__)

# Nomes GENERICOS: subtotais e baldes que nao contam como "linha propria".
# Uma folha com um destes nomes (ou sem nome) entra no residual da cobertura.
NOMES_GENERICOS = frozenset(
    {
        "ativo_total",
        "ativo_circulante",
        "ativo_nao_circulante",
        "ativo_realizavel_longo_prazo",
        "passivo_total",
        "passivo_circulante",
        "passivo_nao_circulante",
        "outras_obrigacoes_cp",
        "outras_obrigacoes_lp",
        "outros_ativos_circulantes",
        "outros_ativos_nao_circulantes",
        "outros_passivos_circulantes",
        "outros_passivos_nao_circulantes",
    }
)

# Secoes do BP abertas pela decomposicao (raiz -> rotulo persistido).
SECOES_BP = (
    ("1.01", "ativo_circulante"),
    ("1.02", "ativo_nao_circulante"),
    ("2.01", "passivo_circulante"),
    ("2.02", "passivo_nao_circulante"),
    ("2.03", "patrimonio_liquido"),
)

# Identidades da DRE nao-financeira: alvo = soma dos codigos-fonte (VL_CONTA
# assinado, como divulgado). So verificadas quando todos os codigos existem.
IDENTIDADES_DRE = (
    ("lucro_bruto = receita_liquida + cpv", "3.03", ("3.01", "3.02")),
    ("ebit = lucro_bruto + despesas/receitas operacionais", "3.05", ("3.03", "3.04")),
    ("ebt = ebit + resultado financeiro", "3.07", ("3.05", "3.06")),
    ("resultado continuado = ebt + ir/csll", "3.09", ("3.07", "3.08")),
    ("lucro liquido = continuadas + descontinuadas", "3.11", ("3.09", "3.10")),
)

META_RESIDUAL_PCT = 0.05
DEMONSTRATIVOS_REMAP = ("dre", "bp", "dfc", "dva")


def resolver_raiz(raiz_projeto: Path | None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    return RAIZ_PROJETO if raiz_projeto is None else Path(raiz_projeto)


def _tolerancia(referencia: float) -> float:
    """Tolerancia de amarracao: R$ 1 mil absoluto ou 1e-4 relativo."""
    return max(1.0, 1e-4 * abs(referencia))


def _carregar_bruto(ticker: str, raiz: Path, demonstrativo: str) -> list[dict]:
    """Le um JSON bruto da CVM; lista vazia quando o arquivo nao existe."""
    caminho = raiz / "data" / "raw" / "cvm" / f"{ticker}_{demonstrativo}.json"
    if not caminho.exists():
        logger.warning("Base historica ausente para auditoria: %s", caminho)
        return []
    conteudo = carregar_json(caminho)
    return conteudo if isinstance(conteudo, list) else []


def listar_exercicios_anuais(linhas: list[dict], maximo: int = 5) -> list[str]:
    """Ultimos exercicios ANUAIS (31/12) presentes na base, mais recente por ultimo."""
    exercicios = sorted(
        {
            str(linha.get("DT_FIM_EXERC"))
            for linha in linhas
            if str(linha.get("DT_FIM_EXERC", "")).endswith("12-31")
        }
    )
    return exercicios[-maximo:]


def montar_snapshot(linhas: list[dict], exercicio: str) -> dict[str, dict]:
    """Retrato {CD_CONTA: linha} de um exercicio anual como divulgado.

    Convencao identica a ``serie_anual_por_ano``: ORDEM_EXERC = ULTIMO (valor
    originalmente divulgado, nao o comparativo reapresentado) e, havendo
    reapresentacoes, o maior ``ano_arquivo``. Duplicatas do mesmo CD_CONTA com
    valores divergentes viram aviso no log (fica a primeira).
    """
    selecao = [
        linha
        for linha in linhas
        if str(linha.get("DT_FIM_EXERC")) == exercicio
        and normalizar_texto(linha.get("ORDEM_EXERC")) == "ultimo"
    ]
    if not selecao:
        return {}
    maior_arquivo = max((linha.get("ano_arquivo") or 0) for linha in selecao)
    selecao = [
        linha for linha in selecao if (linha.get("ano_arquivo") or 0) == maior_arquivo
    ]
    snapshot: dict[str, dict] = {}
    for linha in selecao:
        codigo = str(linha.get("CD_CONTA"))
        if codigo in snapshot:
            atual = snapshot[codigo].get("VL_CONTA")
            novo = linha.get("VL_CONTA")
            if atual is not None and novo is not None and float(atual) != float(novo):
                logger.warning(
                    "Snapshot %s: CD_CONTA %s duplicada com valores divergentes "
                    "(%s vs %s); mantida a primeira.",
                    exercicio,
                    codigo,
                    atual,
                    novo,
                )
            continue
        snapshot[codigo] = linha
    return snapshot


def _valor(snapshot: dict[str, dict], codigo: str) -> float | None:
    """VL_CONTA de um codigo no snapshot (None quando a conta nao existe)."""
    linha = snapshot.get(codigo)
    if linha is None or linha.get("VL_CONTA") is None:
        return None
    return float(linha["VL_CONTA"])


def _filhos_diretos(snapshot: dict[str, dict]) -> dict[str, list[str]]:
    """Indice pai -> filhos diretos pela hierarquia dos CD_CONTA."""
    filhos: dict[str, list[str]] = defaultdict(list)
    for codigo in snapshot:
        partes = codigo.split(".")
        if len(partes) > 1:
            filhos[".".join(partes[:-1])].append(codigo)
    return {pai: sorted(lista) for pai, lista in filhos.items()}


def decompor_secao(
    snapshot: dict[str, dict],
    filhos: dict[str, list[str]],
    raiz_secao: str,
) -> dict[str, Any]:
    """Atribui cada R$ da secao a um nome proprio ou ao residual explicito.

    Caminhada em profundidade a partir da raiz da secao:
    - folha com nome PROPRIO -> soma em ``nomeadas[nome]``;
    - folha generica/sem nome -> entra no ``residual`` (linha a linha);
    - no com filhos: o resto ``valor do pai - soma dos filhos`` fica com o
      NOME DO PAI quando ele e proprio (filhos zerados sao refinamento da
      CVM), ou vai ao residual quando o pai e um balde generico.
    Cada R$ e atribuido exatamente uma vez (sem dupla contagem).
    """
    nomeadas: dict[str, float] = defaultdict(float)
    residual: list[dict[str, Any]] = []

    def caminhar(codigo: str) -> None:
        valor = _valor(snapshot, codigo) or 0.0
        nome = snapshot[codigo].get("nome_padronizado")
        generico = nome is None or nome in NOMES_GENERICOS
        descendentes = filhos.get(codigo, [])
        if not descendentes:
            if valor == 0.0:
                return
            if generico:
                residual.append(
                    {
                        "codigo": codigo,
                        "conta_cvm": snapshot[codigo].get("DS_CONTA"),
                        "valor": valor,
                    }
                )
            else:
                nomeadas[str(nome)] += valor
            return
        soma_filhos = sum(_valor(snapshot, filho) or 0.0 for filho in descendentes)
        resto = valor - soma_filhos
        if abs(resto) > _tolerancia(valor):
            if generico:
                residual.append(
                    {
                        "codigo": codigo,
                        "conta_cvm": f"[resto de] {snapshot[codigo].get('DS_CONTA')}",
                        "valor": resto,
                    }
                )
            else:
                nomeadas[str(nome)] += resto
        for filho in descendentes:
            caminhar(filho)

    if raiz_secao in snapshot:
        # A raiz da secao e um subtotal: decompoe apenas os filhos; o proprio
        # subtotal e conferido na verificacao de subtotais, nao aqui.
        for filho in filhos.get(raiz_secao, []):
            caminhar(filho)

    return {
        "total_cvm": _valor(snapshot, raiz_secao),
        "nomeadas": dict(sorted(nomeadas.items())),
        "residual": sorted(residual, key=lambda item: -abs(item["valor"])),
        "residual_total": sum(item["valor"] for item in residual),
    }


def _item(
    categoria: str,
    exercicio: str,
    descricao: str,
    status: str,
    detalhes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta um item OK/AVISO/ERRO do relatorio de auditoria."""
    resultado = {
        "categoria": categoria,
        "exercicio": exercicio,
        "descricao": descricao,
        "status": status,
    }
    if detalhes:
        resultado["detalhes"] = detalhes
    return resultado


def _conferir_soma(
    categoria: str,
    exercicio: str,
    descricao: str,
    alvo: float | None,
    parcelas: list[float | None],
) -> dict[str, Any] | None:
    """Item OK/ERRO comparando um alvo com a soma das parcelas presentes."""
    if alvo is None:
        return None
    soma = sum(parcela for parcela in parcelas if parcela is not None)
    diferenca = alvo - soma
    status = "OK" if abs(diferenca) <= _tolerancia(alvo) else "ERRO"
    return _item(
        categoria,
        exercicio,
        descricao,
        status,
        {"alvo": alvo, "soma": soma, "diferenca": diferenca},
    )


def verificar_balanco(snapshot: dict[str, dict], exercicio: str) -> list[dict]:
    """Checagem 1: Ativo Total = Passivo Total (conta 2 da CVM inclui o PL)."""
    itens: list[dict] = []
    ativo = _valor(snapshot, "1")
    passivo = _valor(snapshot, "2")
    if ativo is None or passivo is None:
        itens.append(
            _item(
                "balanco_fecha",
                exercicio,
                "Totais oficiais (contas 1 e 2) presentes",
                "AVISO",
                {"ativo_total": ativo, "passivo_total": passivo},
            )
        )
        return itens
    diferenca = ativo - passivo
    itens.append(
        _item(
            "balanco_fecha",
            exercicio,
            "Ativo Total = Passivo Total + PL (contas oficiais 1 e 2)",
            "OK" if abs(diferenca) <= _tolerancia(ativo) else "ERRO",
            {
                "ativo_total": ativo,
                "passivo_total_com_pl": passivo,
                "diferenca": diferenca,
            },
        )
    )
    for item in (
        _conferir_soma(
            "balanco_fecha",
            exercicio,
            "Ativo Total = AC + ANC",
            ativo,
            [_valor(snapshot, "1.01"), _valor(snapshot, "1.02")],
        ),
        _conferir_soma(
            "balanco_fecha",
            exercicio,
            "Passivo Total = PC + PNC + PL",
            passivo,
            [
                _valor(snapshot, "2.01"),
                _valor(snapshot, "2.02"),
                _valor(snapshot, "2.03"),
            ],
        ),
    ):
        if item is not None:
            itens.append(item)
    return itens


def verificar_subtotais_bp(
    snapshot: dict[str, dict],
    filhos: dict[str, list[str]],
    exercicio: str,
) -> list[dict]:
    """Checagem 2a: cada subtotal do BP = soma das contas de nivel 3."""
    itens: list[dict] = []
    for raiz_secao, rotulo in SECOES_BP:
        alvo = _valor(snapshot, raiz_secao)
        descendentes = filhos.get(raiz_secao, [])
        if alvo is None or not descendentes:
            continue
        item = _conferir_soma(
            "subtotais",
            exercicio,
            f"{rotulo} = soma das contas de nivel 3",
            alvo,
            [_valor(snapshot, filho) for filho in descendentes],
        )
        if item is not None:
            itens.append(item)
    return itens


def verificar_identidades_dre(snapshot: dict[str, dict], exercicio: str) -> list[dict]:
    """Checagem 2b: identidades da DRE nao-financeira (VL_CONTA assinado).

    Quando a identidade so fecha INVERTENDO o sinal de uma das parcelas, o
    item vira AVISO explicado em vez de ERRO: e o padrao de arquivo da CVM
    com sinal fora da convencao (ex.: VALE 2022 divulga o CPV positivo) — o
    problema e do dado divulgado e fica exposto, sem inventar numero.
    """
    itens: list[dict] = []
    for descricao, codigo_alvo, codigos_fonte in IDENTIDADES_DRE:
        alvo = _valor(snapshot, codigo_alvo)
        parcelas = [_valor(snapshot, codigo) for codigo in codigos_fonte]
        if alvo is None or all(parcela is None for parcela in parcelas):
            continue
        item = _conferir_soma("subtotais", exercicio, descricao, alvo, parcelas)
        if item is None:
            continue
        if item["status"] == "ERRO":
            for indice, codigo in enumerate(codigos_fonte):
                if parcelas[indice] is None:
                    continue
                invertidas = list(parcelas)
                invertidas[indice] = -invertidas[indice]
                soma = sum(p for p in invertidas if p is not None)
                if abs(alvo - soma) <= _tolerancia(alvo):
                    item["status"] = "AVISO"
                    item["detalhes"]["sinal_divulgado_fora_da_convencao"] = codigo
                    item["descricao"] += (
                        f" [fecha invertendo o sinal da conta {codigo} — sinal "
                        "divulgado fora da convencao CVM]"
                    )
                    break
        itens.append(item)
    return itens


def verificar_dfc(
    snapshot_dfc: dict[str, dict],
    snapshot_bp: dict[str, dict],
    exercicio: str,
) -> list[dict]:
    """Checagem 3: DFC amarra internamente e ao caixa do BP."""
    itens: list[dict] = []
    variacao = _valor(snapshot_dfc, "6.05")
    item = _conferir_soma(
        "dfc_amarra",
        exercicio,
        "FCO + FCI + FCF + variacao cambial = variacao de caixa",
        variacao,
        [
            _valor(snapshot_dfc, "6.01"),
            _valor(snapshot_dfc, "6.02"),
            _valor(snapshot_dfc, "6.03"),
            _valor(snapshot_dfc, "6.04"),
        ],
    )
    if item is not None:
        itens.append(item)

    caixa_final = _valor(snapshot_dfc, "6.05.02")
    item = _conferir_soma(
        "dfc_amarra",
        exercicio,
        "Caixa final DFC = caixa inicial + variacao",
        caixa_final,
        [_valor(snapshot_dfc, "6.05.01"), variacao],
    )
    if item is not None:
        itens.append(item)

    # Amarra cruzada DFC -> BP: o conceito de caixa do DFC pode incluir
    # aplicacoes de curtissimo prazo; o fallback reporta AVISO, nao ERRO.
    caixa_bp = _valor(snapshot_bp, "1.01.01")
    if caixa_final is not None and caixa_bp is not None:
        diferenca = caixa_final - caixa_bp
        if abs(diferenca) <= _tolerancia(caixa_final):
            itens.append(
                _item(
                    "dfc_amarra",
                    exercicio,
                    "Caixa final DFC = caixa e equivalentes do BP",
                    "OK",
                    {"caixa_dfc": caixa_final, "caixa_bp": caixa_bp},
                )
            )
        else:
            aplicacoes = _valor(snapshot_bp, "1.01.02") or 0.0
            diferenca_ampliada = caixa_final - (caixa_bp + aplicacoes)
            if abs(diferenca_ampliada) <= _tolerancia(caixa_final):
                itens.append(
                    _item(
                        "dfc_amarra",
                        exercicio,
                        "Caixa final DFC = caixa + aplicacoes do BP "
                        "(conceito ampliado de caixa)",
                        "AVISO",
                        {
                            "caixa_dfc": caixa_final,
                            "caixa_bp": caixa_bp,
                            "aplicacoes_bp": aplicacoes,
                        },
                    )
                )
            else:
                itens.append(
                    _item(
                        "dfc_amarra",
                        exercicio,
                        "Caixa final DFC nao amarra ao caixa do BP",
                        "ERRO",
                        {
                            "caixa_dfc": caixa_final,
                            "caixa_bp": caixa_bp,
                            "diferenca": diferenca,
                            "diferenca_com_aplicacoes": diferenca_ampliada,
                        },
                    )
                )
    return itens


def verificar_cobertura(
    snapshot: dict[str, dict],
    filhos: dict[str, list[str]],
    exercicio: str,
) -> tuple[list[dict], dict[str, Any]]:
    """Checagem 4: residual (sem nome proprio) < 5% do Ativo/Passivo total."""
    decomposicao = {
        rotulo: decompor_secao(snapshot, filhos, raiz_secao)
        for raiz_secao, rotulo in SECOES_BP
    }
    ativo_total = _valor(snapshot, "1")
    passivo_total = _valor(snapshot, "2")
    residual_ativo = sum(
        decomposicao[rotulo]["residual_total"]
        for rotulo in ("ativo_circulante", "ativo_nao_circulante")
    )
    residual_passivo = sum(
        decomposicao[rotulo]["residual_total"]
        for rotulo in (
            "passivo_circulante",
            "passivo_nao_circulante",
            "patrimonio_liquido",
        )
    )

    itens: list[dict] = []
    resumo: dict[str, Any] = {"exercicio": exercicio, "decomposicao": decomposicao}
    for lado, residual, total in (
        ("ativo", residual_ativo, ativo_total),
        ("passivo", residual_passivo, passivo_total),
    ):
        if not total:
            continue
        pct = abs(residual) / abs(total)
        resumo[f"residual_{lado}"] = residual
        resumo[f"residual_{lado}_pct"] = pct
        status = "OK" if pct < META_RESIDUAL_PCT else "AVISO"
        detalhes: dict[str, Any] = {
            "residual": residual,
            "total": total,
            "pct": pct,
            "meta": META_RESIDUAL_PCT,
        }
        if status == "AVISO":
            maiores: list[dict] = []
            for secao in decomposicao.values():
                maiores.extend(secao["residual"])
            detalhes["maiores_residuais"] = sorted(
                maiores, key=lambda item: -abs(item["valor"])
            )[:5]
            detalhes["dica"] = (
                "Mapear as maiores contas em config/mapeamento_cvm.json; ver "
                "tambem logs/contas_cvm_nao_mapeadas.log"
            )
        itens.append(
            _item(
                "cobertura",
                exercicio,
                f"Residual do {lado} sem nome proprio < 5% do total",
                status,
                detalhes,
            )
        )
    return itens, resumo


def verificar_escala_sinais(
    snapshots: dict[str, dict[str, dict]],
    exercicio: str,
) -> list[dict]:
    """Checagem 5: escala/moeda uniformes e sinais como divulgados."""
    itens: list[dict] = []
    escalas = {
        str(linha.get("ESCALA_MOEDA"))
        for snapshot in snapshots.values()
        for linha in snapshot.values()
        if linha.get("ESCALA_MOEDA") is not None
    }
    itens.append(
        _item(
            "escala_sinais",
            exercicio,
            "ESCALA_MOEDA uniforme nos 3 demonstrativos",
            "OK" if len(escalas) <= 1 else "ERRO",
            {"escalas": sorted(escalas)},
        )
    )

    # Sinais: na DRE divulgada, contas de despesa (sinal_esperado negativo no
    # catalogo) devem vir com VL_CONTA <= 0; subtotais do BP devem ser >= 0.
    violacoes: list[dict[str, Any]] = []
    for linha in snapshots.get("dre", {}).values():
        if (
            linha.get("sinal_esperado") == "negativo"
            and linha.get("VL_CONTA") is not None
            and float(linha["VL_CONTA"]) > 0
        ):
            violacoes.append(
                {
                    "codigo": str(linha.get("CD_CONTA")),
                    "conta_cvm": linha.get("DS_CONTA"),
                    "valor": float(linha["VL_CONTA"]),
                }
            )
    snapshot_bp = snapshots.get("bp", {})
    for codigo in ("1", "1.01", "1.02", "2", "2.01", "2.02"):
        valor = _valor(snapshot_bp, codigo)
        if valor is not None and valor < 0:
            violacoes.append(
                {
                    "codigo": codigo,
                    "conta_cvm": snapshot_bp[codigo].get("DS_CONTA"),
                    "valor": valor,
                }
            )
    itens.append(
        _item(
            "escala_sinais",
            exercicio,
            "Sinais como divulgados (despesas DRE <= 0; subtotais BP >= 0)",
            "OK" if not violacoes else "AVISO",
            {"violacoes": violacoes[:10]} if violacoes else None,
        )
    )
    return itens


def auditar_empresa(
    ticker: str,
    raiz_projeto: Path | None = None,
    maximo_exercicios: int = 5,
    estrito: bool = False,
    persistir: bool = True,
) -> dict[str, Any]:
    """Roda as 5 checagens nos ultimos exercicios anuais e persiste o laudo."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = ticker.strip().upper()
    brutos = {
        nome: _carregar_bruto(ticker_normalizado, raiz, nome)
        for nome in ("bp", "dre", "dfc")
    }
    if not brutos["bp"]:
        raise RuntimeError(
            f"Sem BP bruto para {ticker_normalizado} em data/raw/cvm/ — "
            "rode a coleta antes do auditor."
        )

    exercicios = listar_exercicios_anuais(brutos["bp"], maximo_exercicios)
    itens: list[dict] = []
    cobertura_por_exercicio: list[dict] = []
    bp_aberto: dict[str, Any] = {}

    for exercicio in exercicios:
        snapshots = {
            nome: montar_snapshot(linhas, exercicio) for nome, linhas in brutos.items()
        }
        snapshot_bp = snapshots["bp"]
        if not snapshot_bp:
            itens.append(
                _item(
                    "balanco_fecha",
                    exercicio,
                    "Sem retrato anual do BP para o exercicio",
                    "AVISO",
                )
            )
            continue
        filhos = _filhos_diretos(snapshot_bp)
        itens.extend(verificar_balanco(snapshot_bp, exercicio))
        itens.extend(verificar_subtotais_bp(snapshot_bp, filhos, exercicio))
        itens.extend(verificar_identidades_dre(snapshots["dre"], exercicio))
        itens.extend(verificar_dfc(snapshots["dfc"], snapshot_bp, exercicio))
        itens_cobertura, resumo = verificar_cobertura(snapshot_bp, filhos, exercicio)
        itens.extend(itens_cobertura)
        bp_aberto[exercicio] = resumo.pop("decomposicao")
        cobertura_por_exercicio.append(resumo)
        itens.extend(verificar_escala_sinais(snapshots, exercicio))

    contagem = {
        status: sum(1 for item in itens if item["status"] == status)
        for status in ("OK", "AVISO", "ERRO")
    }
    status_geral = (
        "ERRO" if contagem["ERRO"] else ("AVISO" if contagem["AVISO"] else "OK")
    )
    laudo = {
        "ticker": ticker_normalizado,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "exercicios_auditados": exercicios,
        "status_geral": status_geral,
        "contagem": contagem,
        "itens": itens,
        "cobertura": cobertura_por_exercicio,
        "bp_aberto": bp_aberto,
    }

    if persistir:
        caminho = (
            raiz / "data" / "raw" / "cvm" / f"{ticker_normalizado}_auditoria_cvm.json"
        )
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as arquivo:
            json.dump(laudo, arquivo, ensure_ascii=False, indent=2)
        logger.info("Auditoria persistida em %s", caminho)

    if estrito and contagem["ERRO"]:
        primeiro = next(item for item in itens if item["status"] == "ERRO")
        raise RuntimeError(
            f"Auditoria ESTRITA de {ticker_normalizado} falhou: "
            f"{primeiro['descricao']} ({primeiro['exercicio']}) — "
            f"detalhes: {primeiro.get('detalhes')}"
        )
    return laudo


def remapear_empresa(ticker: str, raiz_projeto: Path | None = None) -> dict[str, int]:
    """Reaplica a cascata de mapeamento ATUAL aos JSONs brutos persistidos.

    Recoleta OFFLINE: depois de expandir ``config/mapeamento_cvm.json``, os
    ``nome_padronizado`` gravados na coleta original ficam defasados. Este
    passo re-mapeia cada demonstrativo (sem rede), re-persiste os JSONs e
    atualiza o Parquet limpo. Devolve {demonstrativo: linhas_remapeadas}.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = ticker.strip().upper()
    pasta = raiz / "data" / "raw" / "cvm"
    meta_caminho = pasta / f"{ticker_normalizado}_meta.json"
    tipo = "nao_financeira"
    if meta_caminho.exists():
        tipo = str(carregar_json(meta_caminho).get("tipo", tipo))
    mapeamento = carregar_mapeamento(raiz)
    caminho_log = raiz / "logs" / "contas_cvm_nao_mapeadas.log"

    resultado: dict[str, int] = {}
    for demonstrativo in DEMONSTRATIVOS_REMAP:
        caminho = pasta / f"{ticker_normalizado}_{demonstrativo}.json"
        if not caminho.exists():
            continue
        dados = pd.DataFrame(carregar_json(caminho))
        if dados.empty:
            continue
        # O arquivo bp junta bp_ativo e bp_passivo: re-mapeia grupo a grupo
        # pela demonstracao padronizada gravada na coleta original.
        grupos = []
        for demonstracao, grupo in dados.groupby("demonstracao_padronizada"):
            grupos.append(
                mapear_demonstracao(
                    grupo.drop(
                        columns=[
                            "nome_padronizado",
                            "sinal_esperado",
                            "valor_padronizado",
                            "mapeado_por",
                        ],
                        errors="ignore",
                    ),
                    demonstracao=str(demonstracao),
                    tipo_empresa=tipo,
                    mapeamento=mapeamento,
                    ticker=ticker_normalizado,
                    cd_cvm=(
                        carregar_json(meta_caminho).get("codigo_cvm", "")
                        if meta_caminho.exists()
                        else ""
                    ),
                    caminho_log=caminho_log,
                    raiz_projeto=raiz,
                )
            )
        remapeado = pd.concat(grupos, ignore_index=True)
        registros = remapeado.where(pd.notna(remapeado), None).to_dict(orient="records")
        with caminho.open("w", encoding="utf-8") as arquivo:
            json.dump(registros, arquivo, ensure_ascii=False)
        resultado[demonstrativo] = len(registros)
        logger.info(
            "%s: %s remapeado (%d linhas)",
            ticker_normalizado,
            demonstrativo,
            len(registros),
        )

    # Parquet limpo nasce dos JSONs brutos: atualiza apos o remapeamento.
    try:
        from src.processamento.limpeza import limpar_empresa

        limpar_empresa(ticker_normalizado, raiz)
    except Exception as erro:  # noqa: BLE001 - limpeza e melhoria, nao gate
        logger.warning(
            "Falha ao atualizar o Parquet limpo de %s apos remapear: %s",
            ticker_normalizado,
            erro,
        )
    return resultado


def imprimir_laudo(laudo: dict[str, Any]) -> None:
    """Resumo ASCII do laudo para a linha de comando."""
    largura = 72
    print("=" * largura)
    print(
        f"AUDITORIA CVM — {laudo['ticker']} | status geral: {laudo['status_geral']}"
        f" | exercicios: {', '.join(laudo['exercicios_auditados'])}"
    )
    print("=" * largura)
    contagem = laudo["contagem"]
    print(
        f"OK: {contagem['OK']} | AVISO: {contagem['AVISO']} | ERRO: {contagem['ERRO']}"
    )
    for resumo in laudo["cobertura"]:
        pct_ativo = resumo.get("residual_ativo_pct")
        pct_passivo = resumo.get("residual_passivo_pct")
        print(
            f"  {resumo['exercicio']}: residual ativo "
            f"{pct_ativo:.2%} | residual passivo {pct_passivo:.2%}"
            if pct_ativo is not None and pct_passivo is not None
            else f"  {resumo['exercicio']}: cobertura indisponivel"
        )
    for item in laudo["itens"]:
        if item["status"] != "OK":
            print(f"  [{item['status']}] {item['exercicio']} — {item['descricao']}")


def main(argumentos: list[str] | None = None) -> int:
    """CLI: ``python -m src.coleta.auditor_cvm --ticker DIRR3 [--estrito]``."""
    parser = argparse.ArgumentParser(
        description=(
            "Auditor de amarracao historica contra a CVM (sem rede): balanco "
            "fecha, subtotais batem, DFC amarra, cobertura de mapeamento e "
            "escala/sinais. Persiste <TICKER>_auditoria_cvm.json."
        )
    )
    parser.add_argument("--ticker", required=True, help="Ticker da B3 (ex.: DIRR3)")
    parser.add_argument(
        "--estrito",
        action="store_true",
        help="Levanta erro no primeiro ERRO (uso em CI).",
    )
    parser.add_argument(
        "--remapear",
        action="store_true",
        help=(
            "Antes de auditar, reaplica o mapeamento ATUAL aos JSONs brutos "
            "persistidos (recoleta offline apos expandir o mapeamento)."
        ),
    )
    parser.add_argument(
        "--exercicios",
        type=int,
        default=5,
        help="Quantos exercicios anuais auditar (default 5).",
    )
    opcoes = parser.parse_args(argumentos)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    if opcoes.remapear:
        remapear_empresa(opcoes.ticker)
    try:
        laudo = auditar_empresa(
            opcoes.ticker,
            maximo_exercicios=opcoes.exercicios,
            estrito=opcoes.estrito,
        )
    except RuntimeError as erro:
        print(f"ERRO: {erro}")
        return 1
    imprimir_laudo(laudo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
