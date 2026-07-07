"""Verificacao operacional da Semana 3 para DIRR3 e MGLU3."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.projecao.projetor_dre import (  # noqa: E402
    HORIZONTE_PROJECAO,
    carregar_json,
    formatar_numero,
    formatar_percentual,
    normalizar_ticker,
    projetar_dre,
)
from src.projecao.schedule_divida import (  # noqa: E402
    obter_float_obrigatorio,
    projetar_divida,
)
from src.projecao.schedule_ppe import projetar_ppe  # noqa: E402
from src.projecao.schedule_wk import projetar_wk  # noqa: E402
from src.valuation.calculador_ev import calcular_ev  # noqa: E402
from src.valuation.calculador_fcff import calcular_fcff  # noqa: E402
from src.valuation.calculador_vt import calcular_valor_terminal  # noqa: E402
from src.valuation.calculador_wacc import calcular_wacc  # noqa: E402
from src.valuation.checklist import executar_checklist  # noqa: E402

STATUS_OK = "OK"
STATUS_ALERTA = "ALERTA"
STATUS_FALHA = "FALHA"

BLOCOS_SEMANA3 = ("fcff", "wacc", "valor_terminal", "ev_equity", "checklist")
RECOMENDACOES_VALIDAS = {"COMPRA", "NEUTRO", "VENDA"}


def caminho_projecao(ticker: str) -> Path:
    """Monta o caminho da projecao persistida do ticker."""
    return RAIZ_PROJETO / "data" / "processed" / f"{ticker}_projecao.json"


def item(
    identificador: str,
    descricao: str,
    status: str,
    detalhe: str,
    estrutural: bool,
) -> dict[str, Any]:
    """Monta um item de verificacao operacional."""
    return {
        "id": identificador,
        "descricao": descricao,
        "status": status,
        "detalhe": detalhe,
        "estrutural": estrutural,
    }


def numero_finito(dados: dict[str, Any], campo: str, contexto: str) -> float:
    """Le campo numerico e exige valor finito."""
    valor = obter_float_obrigatorio(dados, campo, contexto)
    if not math.isfinite(valor):
        raise ValueError(f"Campo numerico nao finito: {contexto}.{campo}")
    return valor


def formatar_valor(valor: float | None, prefixo: str = "") -> str:
    """Formata valor numerico para painel textual."""
    if valor is None or not math.isfinite(valor):
        return "n/d"
    return f"{prefixo}{formatar_numero(valor)}"


def formatar_pct(valor: float | None) -> str:
    """Formata percentual para painel textual."""
    if valor is None or not math.isfinite(valor):
        return "n/d"
    return formatar_percentual(valor)


def numero_opcional(dados: dict[str, Any], campo: str) -> float | None:
    """Le numero opcional; devolve None se ausente ou invalido."""
    valor = dados.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    valor_float = float(valor)
    if not math.isfinite(valor_float):
        return None
    return valor_float


def executar_cadeia(ticker: str) -> None:
    """Executa a cadeia completa da Semana 3 para um ticker."""
    projetar_dre(ticker)
    projetar_wk(ticker)
    projetar_ppe(ticker)
    projetar_divida(ticker)
    calcular_fcff(ticker)
    calcular_wacc(ticker)
    calcular_valor_terminal(ticker)
    calcular_ev(ticker)
    executar_checklist(ticker)


def verificar_e1(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E1: todos os blocos da Semana 3 devem existir."""
    faltantes = [
        bloco for bloco in BLOCOS_SEMANA3 if not isinstance(conteudo.get(bloco), dict)
    ]
    if faltantes:
        return item(
            "E1",
            "Blocos Semana 3 existem",
            STATUS_FALHA,
            "faltantes: " + ", ".join(faltantes),
            True,
        )
    return item("E1", "Blocos Semana 3 existem", STATUS_OK, "todos presentes", True)


def verificar_e2(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E2: FCFF deve existir de ano1 a ano8 e ser numerico."""
    fcff = conteudo.get("fcff")
    if not isinstance(fcff, dict):
        return item(
            "E2", "FCFF ano1..ano8 numerico", STATUS_FALHA, "fcff ausente", True
        )

    invalidos = []
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha = fcff.get(chave_ano)
        if not isinstance(linha, dict):
            invalidos.append(chave_ano)
            continue
        try:
            numero_finito(linha, "fcff", chave_ano)
        except ValueError:
            invalidos.append(chave_ano)

    if invalidos:
        return item(
            "E2",
            "FCFF ano1..ano8 numerico",
            STATUS_FALHA,
            "invalidos: " + ", ".join(invalidos),
            True,
        )
    return item("E2", "FCFF ano1..ano8 numerico", STATUS_OK, "negativo permitido", True)


def verificar_e3(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E3: balanco deve fechar nos 8 anos."""
    balanco = conteudo.get("balanco")
    if not isinstance(balanco, dict):
        return item("E3", "Balanco fecha", STATUS_FALHA, "balanco ausente", True)

    violacoes = []
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha = balanco.get(chave_ano)
        if not isinstance(linha, dict):
            violacoes.append(f"{chave_ano}=ausente")
            continue
        try:
            diferenca = numero_finito(linha, "diferenca_balanco", chave_ano)
        except ValueError:
            violacoes.append(f"{chave_ano}=invalido")
            continue
        if abs(diferenca) >= 1.0:
            violacoes.append(f"{chave_ano}={formatar_numero(diferenca)}")

    if violacoes:
        return item("E3", "Balanco fecha", STATUS_FALHA, "; ".join(violacoes), True)
    return item("E3", "Balanco fecha", STATUS_OK, "abs(diferenca) < 1,0", True)


def verificar_e4(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E4: WACC precisa ser positivo."""
    try:
        wacc = numero_finito(conteudo["wacc"], "wacc", "wacc")
    except (KeyError, TypeError, ValueError):
        return item("E4", "WACC positivo", STATUS_FALHA, "wacc invalido", True)
    if wacc <= 0:
        return item(
            "E4", "WACC positivo", STATUS_FALHA, formatar_percentual(wacc), True
        )
    return item("E4", "WACC positivo", STATUS_OK, formatar_percentual(wacc), True)


def verificar_e5(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E5: g precisa ser menor que WACC no Gordon."""
    vt = conteudo.get("valor_terminal")
    if not isinstance(vt, dict):
        return item("E5", "g menor que WACC", STATUS_FALHA, "VT ausente", True)
    try:
        g = numero_finito(vt, "g", "valor_terminal")
        wacc = numero_finito(vt, "wacc", "valor_terminal")
    except ValueError:
        return item("E5", "g menor que WACC", STATUS_FALHA, "g/wacc invalido", True)
    if g >= wacc:
        detalhe = f"g={formatar_percentual(g)}; WACC={formatar_percentual(wacc)}"
        return item("E5", "g menor que WACC", STATUS_FALHA, detalhe, True)
    return item("E5", "g menor que WACC", STATUS_OK, "Gordon valido", True)


def verificar_e6(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E6: acoes fully diluted e target price precisam ser positivos."""
    ev = conteudo.get("ev_equity")
    if not isinstance(ev, dict):
        return item("E6", "Acoes e target positivos", STATUS_FALHA, "EV ausente", True)
    try:
        acoes = numero_finito(ev, "acoes_fully_diluted", "ev_equity")
        target = numero_finito(ev, "target_price", "ev_equity")
    except ValueError:
        return item(
            "E6",
            "Acoes e target positivos",
            STATUS_FALHA,
            "acoes/target invalidos",
            True,
        )
    if acoes <= 0 or target <= 0:
        detalhe = f"acoes={formatar_numero(acoes)}; target={formatar_numero(target)}"
        return item("E6", "Acoes e target positivos", STATUS_FALHA, detalhe, True)
    return item("E6", "Acoes e target positivos", STATUS_OK, "ambos > 0", True)


def verificar_e7(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E7: recomendacao precisa estar no conjunto permitido."""
    ev = conteudo.get("ev_equity")
    recomendacao = ev.get("recomendacao") if isinstance(ev, dict) else None
    if recomendacao not in RECOMENDACOES_VALIDAS:
        return item(
            "E7",
            "Recomendacao valida",
            STATUS_FALHA,
            f"recebido={recomendacao}",
            True,
        )
    return item("E7", "Recomendacao valida", STATUS_OK, str(recomendacao), True)


def verificar_e8(conteudo: dict[str, Any]) -> dict[str, Any]:
    """E8: checklist precisa estar aprovado."""
    checklist = conteudo.get("checklist")
    if not isinstance(checklist, dict):
        return item("E8", "Checklist aprovado", STATUS_FALHA, "checklist ausente", True)
    if checklist.get("aprovado") is not True:
        erros = [
            str(item_check.get("id"))
            for item_check in checklist.get("itens", [])
            if isinstance(item_check, dict) and item_check.get("status") == "ERRO"
        ]
        detalhe = "itens ERRO: " + ", ".join(erros) if erros else "aprovado != True"
        return item("E8", "Checklist aprovado", STATUS_FALHA, detalhe, True)
    return item("E8", "Checklist aprovado", STATUS_OK, "sem itens ERRO", True)


def verificar_s1(conteudo: dict[str, Any]) -> dict[str, Any]:
    """S1: WACC deve ficar em faixa economica razoavel."""
    wacc = numero_opcional(conteudo.get("wacc", {}), "wacc")
    if wacc is None:
        return item("S1", "WACC em faixa", STATUS_ALERTA, "wacc n/d", False)
    if wacc < 0.05 or wacc > 0.30:
        return item(
            "S1", "WACC em faixa", STATUS_ALERTA, formatar_percentual(wacc), False
        )
    return item("S1", "WACC em faixa", STATUS_OK, formatar_percentual(wacc), False)


def verificar_s2(conteudo: dict[str, Any]) -> dict[str, Any]:
    """S2: perpetuidade nao deve dominar o EV."""
    vt = conteudo.get("valor_terminal", {})
    pct = numero_opcional(vt if isinstance(vt, dict) else {}, "pct_ev_perpetuidade")
    if pct is None:
        return item("S2", "% EV perpetuidade", STATUS_ALERTA, "pct n/d", False)
    if pct >= 0.85:
        return item(
            "S2",
            "% EV perpetuidade",
            STATUS_ALERTA,
            formatar_percentual(pct),
            False,
        )
    return item("S2", "% EV perpetuidade", STATUS_OK, formatar_percentual(pct), False)


def verificar_s3(conteudo: dict[str, Any]) -> dict[str, Any]:
    """S3: multiplo de saida implicito deve ficar em faixa de sanidade."""
    vt = conteudo.get("valor_terminal", {})
    multiplo = numero_opcional(
        vt if isinstance(vt, dict) else {},
        "multiplo_saida_implicito",
    )
    if multiplo is None:
        return item("S3", "Multiplo de saida", STATUS_ALERTA, "multiplo n/d", False)
    if multiplo < 3.0 or multiplo > 25.0:
        return item("S3", "Multiplo de saida", STATUS_ALERTA, f"{multiplo:.2f}x", False)
    return item("S3", "Multiplo de saida", STATUS_OK, f"{multiplo:.2f}x", False)


def verificar_s4(conteudo: dict[str, Any]) -> dict[str, Any]:
    """S4: FCFF ano1 nao deve destoar da media dos anos 2 a 8."""
    fcff = conteudo.get("fcff")
    if not isinstance(fcff, dict):
        return item("S4", "FCFF ano1 vs anos 2-8", STATUS_ALERTA, "fcff n/d", False)
    try:
        fcff_ano1 = numero_finito(fcff["ano1"], "fcff", "ano1")
        demais = [
            abs(numero_finito(fcff[f"ano{ano}"], "fcff", f"ano{ano}"))
            for ano in range(2, HORIZONTE_PROJECAO + 1)
        ]
    except (KeyError, TypeError, ValueError):
        return item(
            "S4", "FCFF ano1 vs anos 2-8", STATUS_ALERTA, "fcff invalido", False
        )

    media = sum(demais) / len(demais)
    if media == 0 and abs(fcff_ano1) > 0:
        return item("S4", "FCFF ano1 vs anos 2-8", STATUS_ALERTA, "media zero", False)
    if media > 0 and abs(fcff_ano1) > 3 * media:
        detalhe = (
            f"ano1={formatar_numero(fcff_ano1)}; "
            f"media_abs_2_8={formatar_numero(media)}"
        )
        return item("S4", "FCFF ano1 vs anos 2-8", STATUS_ALERTA, detalhe, False)
    detalhe = (
        f"ano1={formatar_numero(fcff_ano1)}; media_abs_2_8={formatar_numero(media)}"
    )
    return item("S4", "FCFF ano1 vs anos 2-8", STATUS_OK, detalhe, False)


def verificar_conteudo(conteudo: dict[str, Any]) -> list[dict[str, Any]]:
    """Executa verificacoes estruturais e de sanidade economica."""
    return [
        verificar_e1(conteudo),
        verificar_e2(conteudo),
        verificar_e3(conteudo),
        verificar_e4(conteudo),
        verificar_e5(conteudo),
        verificar_e6(conteudo),
        verificar_e7(conteudo),
        verificar_e8(conteudo),
        verificar_s1(conteudo),
        verificar_s2(conteudo),
        verificar_s3(conteudo),
        verificar_s4(conteudo),
    ]


def imprimir_tabela_fcff(conteudo: dict[str, Any]) -> None:
    """Imprime FCFF dos 8 anos projetados."""
    print("\nFCFF projetado")
    cabecalho = f"{'Ano':<6} {'FCFF':>18}"
    print(cabecalho)
    print("-" * len(cabecalho))
    fcff = conteudo.get("fcff", {})
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        valor = None
        if isinstance(fcff, dict) and isinstance(fcff.get(chave_ano), dict):
            valor = numero_opcional(fcff[chave_ano], "fcff")
        print(f"{chave_ano:<6} {formatar_valor(valor):>18}")


def imprimir_painel_resumo(conteudo: dict[str, Any]) -> None:
    """Imprime os principais resultados de valuation."""
    wacc = conteudo.get("wacc", {})
    vt = conteudo.get("valor_terminal", {})
    ev = conteudo.get("ev_equity", {})
    checklist = conteudo.get("checklist", {})
    if not isinstance(wacc, dict):
        wacc = {}
    if not isinstance(vt, dict):
        vt = {}
    if not isinstance(ev, dict):
        ev = {}
    if not isinstance(checklist, dict):
        checklist = {}

    linhas = [
        ("WACC", formatar_pct(numero_opcional(wacc, "wacc"))),
        ("g", formatar_pct(numero_opcional(vt, "g"))),
        ("EV", formatar_valor(numero_opcional(ev, "ev"), "R$ ")),
        ("Equity", formatar_valor(numero_opcional(ev, "equity_value"), "R$ ")),
        ("Target Price", formatar_valor(numero_opcional(ev, "target_price"), "R$ ")),
        ("Preco Atual", formatar_valor(numero_opcional(ev, "preco_atual"), "R$ ")),
        ("Upside", formatar_pct(numero_opcional(ev, "upside"))),
        ("Recomendacao", str(ev.get("recomendacao", "n/d"))),
        ("% EV perpetuidade", formatar_pct(numero_opcional(vt, "pct_ev_perpetuidade"))),
        ("Checklist", "APROVADO" if checklist.get("aprovado") is True else "REPROVADO"),
    ]

    print("\nResumo Semana 3")
    for rotulo, valor in linhas:
        print(f"{rotulo:<20} {valor:>18}")


def imprimir_verificacoes(itens: list[dict[str, Any]]) -> None:
    """Imprime status das verificacoes E1-E8 e S1-S4."""
    print("\nVerificacoes")
    cabecalho = f"{'ID':<4} {'Status':<8} {'Descricao':<30} {'Detalhe'}"
    print(cabecalho)
    print("-" * len(cabecalho))
    for item_verificacao in itens:
        print(
            f"{item_verificacao['id']:<4} "
            f"{item_verificacao['status']:<8} "
            f"{item_verificacao['descricao']:<30} "
            f"{item_verificacao['detalhe']}"
        )


def verificar_ticker(ticker: str) -> dict[str, Any]:
    """Executa a Semana 3 completa e valida o resultado persistido."""
    ticker_normalizado = normalizar_ticker(ticker)
    print("\n" + "=" * 120)
    print(f"Verificacao Semana 3 - {ticker_normalizado}")

    try:
        executar_cadeia(ticker_normalizado)
        conteudo = carregar_json(caminho_projecao(ticker_normalizado))
        itens = verificar_conteudo(conteudo)
        imprimir_tabela_fcff(conteudo)
        imprimir_painel_resumo(conteudo)
        imprimir_verificacoes(itens)
        falha_estrutural = any(
            linha["estrutural"] and linha["status"] == STATUS_FALHA for linha in itens
        )
        return {
            "ticker": ticker_normalizado,
            "falha_estrutural": falha_estrutural,
            "itens": itens,
            "erro_execucao": None,
        }
    except Exception as erro:  # noqa: BLE001 - verificador operacional deve seguir.
        print(f"FALHA ESTRUTURAL EM {ticker_normalizado}: {erro}")
        return {
            "ticker": ticker_normalizado,
            "falha_estrutural": True,
            "itens": [],
            "erro_execucao": str(erro),
        }


def imprimir_alertas(resultados: list[dict[str, Any]]) -> None:
    """Lista alertas de sanidade sem reprovar a Semana 3."""
    alertas = []
    for resultado in resultados:
        for item_verificacao in resultado["itens"]:
            if item_verificacao["status"] == STATUS_ALERTA:
                alertas.append(
                    f"{resultado['ticker']} {item_verificacao['id']}: "
                    f"{item_verificacao['detalhe']}"
                )

    if not alertas:
        return

    print("\nALERTAS DE SANIDADE")
    for alerta in alertas:
        print(f"- {alerta}")


def main() -> None:
    """Executa a verificacao operacional da Semana 3."""
    resultados = [verificar_ticker(ticker) for ticker in ("DIRR3", "MGLU3")]
    imprimir_alertas(resultados)

    if any(resultado["falha_estrutural"] for resultado in resultados):
        print("\nSEMANA 3 COM FALHAS")
        raise SystemExit(1)

    print("\nSEMANA 3 OK")


if __name__ == "__main__":
    main()
