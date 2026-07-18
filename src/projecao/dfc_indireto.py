"""DFC INDIRETO completo reconciliando o BP projetado (Prompt 9.0.2.5).

Pos-processador da cadeia de projecao (roda DEPOIS do schedule de divida):
abre o DFC no padrao Direcional (``Modelo`` L123-L139), com UMA linha de
variacao por conta do capital de giro:

    LL + D&A - Delta WK (linha a linha)            = FCO
    - CAPEX (imobilizado; intangivel constante)    = FCI
    - Dividendos + Delta Emprestimos (capt - amort) = FCFin
    Caixa BoP + (FCO + FCI + FCFin)                = Caixa EoP = caixa do BP

A aritmetica e IDENTICA a do bloco ``dfc`` gravado pelo schedule de divida
(mesmo LL, D&A, Delta NWC total, capex, captacoes, amortizacoes e
dividendos) — este modulo apenas ABRE as linhas e VERIFICA as amarracoes:
soma das variacoes por conta = -Delta NWC; caixa EoP = caixa do balanco
(dif < 1e-6). O bloco legado e preservado em ``dfc_simplificado`` ate o
Excel do 9.0.5 migrar os consumidores (contrato do prompt); o bloco ``dfc``
vira um SUPERSET (campos legados + linhas abertas) para nao quebrar
consumidores atuais (checklist, exportador).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )

# Contas do WK abertas no DFC (ordem de exibicao do padrao Direcional).
# Passivos sao persistidos NEGATIVOS no WK; a contribuicao ao caixa de
# qualquer conta e -Delta(saldo assinado), o que unifica os dois lados.
CONTAS_WK_DFC = (
    "contas_receber",
    "estoques",
    "tributos_a_recuperar",
    "fornecedores",
    "obrigacoes_sociais_trabalhistas",
    "adiantamento_clientes",
)
TOLERANCIA_DFC = 1e-6


def _contas_presentes(wk: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    """Contas do WK realmente projetadas (multi-driver traz as expandidas)."""
    linha = wk.get("ano1", {})
    return tuple(conta for conta in CONTAS_WK_DFC if conta in linha)


def _saldo(linha: dict[str, Any], conta: str) -> float:
    """Saldo assinado de uma conta do WK (ausente = 0.0)."""
    valor = linha.get(conta)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return 0.0
    return float(valor)


def montar_dfc_indireto(
    conteudo: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    """Abre o DFC por conta do WK e verifica as amarracoes com o BP.

    Devolve ``(dfc_superset, verificacao_por_ano, avisos)``. Nao recalcula
    nenhum fluxo: FCO/FCI/FCF, captacoes, amortizacoes e caixa final sao os
    ja persistidos pelo schedule de divida (fonte unica); as linhas novas
    sao a ABERTURA do Delta WK e a verificacao e aritmetica.
    """
    dfc = conteudo.get("dfc")
    wk = conteudo.get("wk")
    balanco = conteudo.get("balanco")
    ano0 = conteudo.get("ano0", {})
    if not isinstance(dfc, dict) or not isinstance(wk, dict):
        raise RuntimeError("Blocos dfc/wk ausentes — rode o schedule de divida antes.")
    if not isinstance(balanco, dict):
        raise RuntimeError("Bloco balanco ausente — rode o schedule de divida antes.")
    ano0_wk = ano0.get("wk", {})
    ano0_balanco = ano0.get("balanco", {})

    contas = _contas_presentes(wk)
    avisos: list[str] = []
    superset: dict[str, dict[str, Any]] = {}
    verificacao: dict[str, dict[str, Any]] = {}

    caixa_anterior = float(ano0_balanco.get("caixa_equivalentes") or 0.0)
    saldos_anteriores = {conta: _saldo(ano0_wk, conta) for conta in contas}

    for indice_ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{indice_ano}"
        linha_dfc = dict(dfc[chave_ano])
        linha_wk = wk[chave_ano]
        linha_balanco = balanco[chave_ano]

        # Abertura do Delta WK: contribuicao ao caixa = -Delta(saldo
        # assinado) — ativo crescendo consome caixa; passivo (negativo)
        # crescendo em magnitude libera caixa.
        soma_variacoes = 0.0
        for conta in contas:
            saldo_atual = _saldo(linha_wk, conta)
            variacao = -(saldo_atual - saldos_anteriores[conta])
            linha_dfc[f"variacao_{conta}"] = variacao
            soma_variacoes += variacao
            saldos_anteriores[conta] = saldo_atual

        delta_nwc = float(linha_dfc["delta_nwc"])
        # Identidade: soma das variacoes por conta = -Delta NWC total.
        diferenca_wk = soma_variacoes - (-delta_nwc)
        if abs(diferenca_wk) > max(TOLERANCIA_DFC, 1e-9 * abs(delta_nwc)):
            avisos.append(
                f"{chave_ano}: abertura do WK nao soma ao Delta NWC "
                f"(diferenca {diferenca_wk:.6f})."
            )

        # Formula (Direcional L123-L139): FCO = LL + D&A - Delta WK;
        # FCI = -CAPEX; FCFin = captacao - amortizacao - dividendos;
        # Caixa BoP + (FCO + FCI + FCFin) = Caixa EoP (= caixa do BP).
        linha_dfc["caixa_inicial"] = caixa_anterior
        linha_dfc["delta_emprestimos"] = float(linha_dfc["captacao"]) - float(
            linha_dfc["amortizacao"]
        )
        linha_dfc["fcfin"] = float(linha_dfc["fcf"])

        caixa_final_dfc = float(linha_dfc["caixa_final"])
        caixa_bp = float(linha_balanco["caixa_equivalentes"])
        diferenca_caixa = caixa_final_dfc - caixa_bp
        variacao_caixa = float(linha_dfc["variacao_caixa"])
        diferenca_variacao = (caixa_final_dfc - caixa_anterior) - variacao_caixa

        fecha = (
            abs(diferenca_caixa) <= TOLERANCIA_DFC
            and abs(diferenca_variacao) <= TOLERANCIA_DFC
        )
        if not fecha:
            avisos.append(
                f"{chave_ano}: DFC indireto nao amarra ao caixa do BP "
                f"(dif caixa {diferenca_caixa:.6f}; dif variacao "
                f"{diferenca_variacao:.6f})."
            )
        verificacao[chave_ano] = {
            "caixa_final_dfc": caixa_final_dfc,
            "caixa_bp": caixa_bp,
            "diferenca_caixa": diferenca_caixa,
            "diferenca_abertura_wk": diferenca_wk,
            "fecha": fecha,
        }

        superset[chave_ano] = linha_dfc
        caixa_anterior = caixa_final_dfc

    return superset, verificacao, avisos


def projetar_dfc_indireto(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Abre o DFC indireto do ticker e persiste na estrutura de projecao.

    Persiste: ``dfc`` (superset com as linhas abertas), ``dfc_simplificado``
    (copia do bloco legado, contrato do 9.0.2 ate o Excel migrar) e
    ``verificacao_dfc`` (amarracao caixa DFC = caixa BP por ano).
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    caminho = raiz / "data" / "processed" / f"{ticker_normalizado}_projecao.json"
    conteudo = carregar_json(caminho)

    dfc_legado = conteudo.get("dfc")
    if not isinstance(dfc_legado, dict):
        raise RuntimeError(f"Bloco dfc ausente em {caminho} — rode a divida antes.")
    superset, verificacao, avisos = montar_dfc_indireto(conteudo)

    # dfc_simplificado preserva o formato LEGADO puro (sem as linhas novas).
    conteudo["dfc_simplificado"] = {
        chave: {
            campo: valor
            for campo, valor in linha.items()
            if not campo.startswith("variacao_")
            and campo not in ("caixa_inicial", "delta_emprestimos", "fcfin")
        }
        for chave, linha in dfc_legado.items()
    }
    conteudo["dfc"] = superset
    conteudo["verificacao_dfc"] = verificacao
    salvar_json(caminho, conteudo)

    tudo_fecha = all(item["fecha"] for item in verificacao.values())
    return {
        "ticker": ticker_normalizado,
        "contas_abertas": list(_contas_presentes(conteudo.get("wk", {}))),
        "fecha": tudo_fecha,
        "verificacao_dfc": verificacao,
        "avisos": avisos,
        "caminho_saida": caminho,
    }


def executar_validacao_padrao() -> None:
    """Roda o DFC indireto para DIRR3 e MGLU3 ao executar o arquivo direto."""
    houve_falha = False
    for ticker in ("DIRR3", "MGLU3"):
        try:
            resultado = projetar_dfc_indireto(ticker)
            status = "FECHA" if resultado["fecha"] else "NAO FECHA"
            print(
                f"{ticker}: DFC indireto {status} | contas abertas: "
                f"{', '.join(resultado['contas_abertas'])}"
            )
            for aviso in resultado["avisos"]:
                print(f"  AVISO: {aviso}")
        except Exception as erro:  # noqa: BLE001 - validacao manual
            houve_falha = True
            print(f"Falha no DFC indireto de {ticker}: {erro}")
    if houve_falha:
        raise SystemExit(1)


if __name__ == "__main__":
    executar_validacao_padrao()
