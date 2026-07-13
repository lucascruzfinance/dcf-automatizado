"""Checklist de consistencia do valuation persistido.

O modulo consome os blocos ja calculados do JSON de projecao. Ele nao chama os
calculadores de valuation: apenas valida limites de sanidade e persiste o
resultado em ``checklist``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        formatar_percentual,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        formatar_numero,
        formatar_percentual,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )

STATUS_OK = "OK"
STATUS_ALERTA = "ALERTA"
STATUS_ERRO = "ERRO"

LIMITE_G_BRL = 0.05
LIMITE_VT_EV = 0.85
LIMITE_BALANCO_ABS = 1.0
LIMITE_ROIIC = 0.50
LIMITE_FCO_EBITDA = 0.70
LIMITE_DIVIDA_LIQUIDA_EBITDA = 4.0
ALIQUOTA_IR_GERAL = 0.34
EPSILON = 1e-12

BLOCOS_OBRIGATORIOS = (
    "fcff",
    "wacc",
    "valor_terminal",
    "ev_equity",
    "balanco",
    "dre",
    "ppe",
    "divida",
    "ano0",
)
BLOCOS_ANUAIS = ("fcff", "balanco", "dre", "ppe", "divida")

# Trilha financeira (FCFE/Ke): blocos proprios, sem balanco/ppe/divida.
BLOCOS_OBRIGATORIOS_FINANCEIRA = (
    "dre",
    "fcfe",
    "ke",
    "capital_regulatorio",
    "valor_terminal",
    "ev_equity",
)
BLOCOS_ANUAIS_FINANCEIRA = ("dre", "fcfe", "capital_regulatorio")
LIMITE_INDICE_CAPITAL = 0.105
LIMITE_PAYOUT_IMPLICITO = (0.0, 1.0)


def carregar_premissas_checklist(
    ticker: str,
    raiz_projeto: Path,
) -> dict[str, Any]:
    """Carrega premissas quando existirem; fixtures podem usar apenas meta."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    if not caminho.exists():
        return {}
    return carregar_json(caminho)


def carregar_projecao_checklist(
    ticker: str,
    raiz_projeto: Path,
    financeira: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Carrega a projecao integrada e valida os blocos do TIPO da empresa."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)

    obrigatorios = BLOCOS_OBRIGATORIOS_FINANCEIRA if financeira else BLOCOS_OBRIGATORIOS
    anuais = BLOCOS_ANUAIS_FINANCEIRA if financeira else BLOCOS_ANUAIS

    for bloco in obrigatorios:
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(f"Bloco obrigatorio ausente em {caminho}: {bloco}")

    for bloco in anuais:
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            chave_ano = f"ano{ano}"
            if not isinstance(conteudo[bloco].get(chave_ano), dict):
                raise RuntimeError(f"Bloco {bloco} sem {chave_ano} em {caminho}")

    return caminho, conteudo


def criar_item(
    identificador: str,
    descricao: str,
    status: str,
    valor: float | str,
    limite: str,
) -> dict[str, float | str]:
    """Monta um item de checklist no contrato publico do modulo."""
    if status not in {STATUS_OK, STATUS_ALERTA, STATUS_ERRO}:
        raise ValueError(f"Status invalido no checklist: {status}")
    return {
        "id": identificador,
        "descricao": descricao,
        "status": status,
        "valor": valor,
        "limite": limite,
    }


def _numero_opcional(dados: dict[str, Any], campo: str) -> float | None:
    """Le numero opcional sem aceitar booleano como numerico."""
    valor = dados.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    valor_float = float(valor)
    if not math.isfinite(valor_float):
        return None
    return valor_float


def _item_campo_invalido(
    identificador: str,
    descricao: str,
    campo: str,
    limite: str,
) -> dict[str, float | str]:
    """Cria erro padrao quando um campo necessario esta ausente ou invalido."""
    return criar_item(
        identificador,
        descricao,
        STATUS_ERRO,
        f"{campo} ausente ou invalido",
        limite,
    )


def _formatar_percentuais(**valores: float) -> str:
    """Formata pares nome=percentual para a coluna valor."""
    partes = [f"{nome}={formatar_percentual(valor)}" for nome, valor in valores.items()]
    return "; ".join(partes)


def verificar_u1(valor_terminal: dict[str, Any]) -> dict[str, float | str]:
    """U1: g precisa ser menor que WACC."""
    descricao = "g menor que WACC"
    limite = "g < WACC"
    g = _numero_opcional(valor_terminal, "g")
    wacc = _numero_opcional(valor_terminal, "wacc")
    if g is None or wacc is None:
        return _item_campo_invalido("U1", descricao, "g/wacc", limite)

    status = STATUS_ERRO if g >= wacc else STATUS_OK
    return criar_item(
        "U1",
        descricao,
        status,
        _formatar_percentuais(g=g, WACC=wacc),
        limite,
    )


def verificar_u2(valor_terminal: dict[str, Any]) -> dict[str, float | str]:
    """U2: g nominal em BRL acima de 5% exige alerta."""
    descricao = "g ate 5% nominal BRL"
    limite = "<= 5,00%"
    g = _numero_opcional(valor_terminal, "g")
    if g is None:
        return _item_campo_invalido("U2", descricao, "g", limite)

    status = STATUS_ALERTA if g > LIMITE_G_BRL else STATUS_OK
    return criar_item("U2", descricao, status, g, limite)


def verificar_u3(valor_terminal: dict[str, Any]) -> dict[str, float | str]:
    """U3: taxa de reinvestimento precisa ficar entre 0 e 1 se existir."""
    descricao = "taxa de reinvestimento em 0-100%"
    limite = "0 <= taxa <= 1"
    if "taxa_reinvestimento" not in valor_terminal:
        return criar_item("U3", descricao, STATUS_OK, "n/d", limite)

    taxa = _numero_opcional(valor_terminal, "taxa_reinvestimento")
    if taxa is None:
        return _item_campo_invalido(
            "U3",
            descricao,
            "taxa_reinvestimento",
            limite,
        )

    status = STATUS_ERRO if taxa < 0 or taxa > 1 else STATUS_OK
    return criar_item("U3", descricao, status, taxa, limite)


def verificar_u4(valor_terminal: dict[str, Any]) -> dict[str, float | str]:
    """U4: VP do valor terminal deve ser menor que 85% do EV."""
    descricao = "VP(VT) abaixo de 85% do EV"
    limite = "< 85,00%"
    pct_ev = _numero_opcional(valor_terminal, "pct_ev_perpetuidade")

    if pct_ev is None:
        vp_vt = _numero_opcional(valor_terminal, "vp_vt")
        soma_vp_fcff = _numero_opcional(valor_terminal, "soma_vp_fcff")
        if vp_vt is None or soma_vp_fcff is None:
            return _item_campo_invalido(
                "U4",
                descricao,
                "vp_vt/soma_vp_fcff",
                limite,
            )
        ev = soma_vp_fcff + vp_vt
        if abs(ev) < EPSILON:
            return criar_item("U4", descricao, STATUS_ERRO, "EV zero", limite)
        pct_ev = vp_vt / ev

    status = STATUS_ALERTA if pct_ev >= LIMITE_VT_EV else STATUS_OK
    return criar_item("U4", descricao, status, pct_ev, limite)


def verificar_u5(ev_equity: dict[str, Any]) -> dict[str, float | str]:
    """U5: acoes fully diluted precisam estar presentes e positivas."""
    descricao = "acoes fully diluted positivas"
    limite = "> 0"
    acoes = _numero_opcional(ev_equity, "acoes_fully_diluted")
    if acoes is None or acoes <= 0:
        valor: float | str = "ausente" if acoes is None else acoes
        return criar_item("U5", descricao, STATUS_ERRO, valor, limite)
    return criar_item("U5", descricao, STATUS_OK, acoes, limite)


def _valor_anual(
    conteudo: dict[str, Any],
    bloco: str,
    chave_ano: str,
    campo: str,
) -> float | None:
    """Le um campo numerico anual de bloco ja validado."""
    return _numero_opcional(conteudo[bloco][chave_ano], campo)


def verificar_nf1(conteudo: dict[str, Any]) -> dict[str, float | str]:
    """NF1: balanco precisa fechar nos 8 anos."""
    descricao = "balanco fecha nos 8 anos"
    limite = "abs(diferenca_balanco) < 1,0"
    violacoes = []
    maior_diferenca = 0.0

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        diferenca = _valor_anual(conteudo, "balanco", chave_ano, "diferenca_balanco")
        if diferenca is None:
            violacoes.append(f"{chave_ano}=invalido")
            continue
        maior_diferenca = max(maior_diferenca, abs(diferenca))
        if abs(diferenca) >= LIMITE_BALANCO_ABS:
            violacoes.append(f"{chave_ano}={formatar_numero(diferenca)}")

    status = STATUS_ERRO if violacoes else STATUS_OK
    valor: float | str = "; ".join(violacoes) if violacoes else maior_diferenca
    return criar_item("NF1", descricao, status, valor, limite)


def verificar_nf2(conteudo: dict[str, Any]) -> dict[str, float | str]:
    """NF2: ROIIC implicito dos anos 7 e 8 deve ficar abaixo de 50%."""
    descricao = "ROIIC menor que 50% nos anos 7 e 8"
    limite = "< 50,00%"
    valores = []
    violacoes = []
    erros = []

    for ano in (7, 8):
        chave_ano = f"ano{ano}"
        roiic = _valor_anual(conteudo, "fcff", chave_ano, "roiic")
        if roiic is None:
            erros.append(f"{chave_ano}=roiic invalido")
            continue

        valores.append(f"{chave_ano}={formatar_percentual(roiic)}")
        if roiic >= LIMITE_ROIIC:
            violacoes.append(f"{chave_ano}={formatar_percentual(roiic)}")

    if erros:
        return criar_item("NF2", descricao, STATUS_ERRO, "; ".join(erros), limite)
    status = STATUS_ALERTA if violacoes else STATUS_OK
    valor = "; ".join(valores) if valores else "n/d"
    return criar_item("NF2", descricao, status, valor, limite)


def verificar_nf3(conteudo: dict[str, Any]) -> dict[str, float | str]:
    """NF3: CAPEX de perpetuidade precisa cobrir D&A no ano 8."""
    descricao = "CAPEX maior ou igual a D&A na perpetuidade"
    limite = "abs(CAPEX ano8) >= D&A ano8"
    capex = _valor_anual(conteudo, "ppe", "ano8", "capex")
    depreciacao = _valor_anual(
        conteudo,
        "ppe",
        "ano8",
        "depreciacao_amortizacao",
    )
    if capex is None or depreciacao is None:
        return _item_campo_invalido("NF3", descricao, "capex/D&A", limite)

    capex_magnitude = abs(capex)
    status = STATUS_ALERTA if capex_magnitude < depreciacao else STATUS_OK
    valor = (
        f"CAPEX={formatar_numero(capex_magnitude)}; "
        f"D&A={formatar_numero(depreciacao)}"
    )
    return criar_item("NF3", descricao, status, valor, limite)


def verificar_nf4(
    conteudo: dict[str, Any],
    usa_ret: bool,
) -> dict[str, float | str]:
    """NF4: FCO aproximado precisa superar 0,7x EBITDA em todos os anos."""
    descricao = "FCO/EBITDA acima de 0,7x nos 8 anos"
    limite = "> 0,7x"
    aliquota = 0.0 if usa_ret else ALIQUOTA_IR_GERAL
    fator_ir = aliquota / (1 - aliquota) if aliquota < 1 else 0.0
    valores = []
    violacoes = []
    erros = []

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        ebitda = _valor_anual(conteudo, "dre", chave_ano, "ebitda")
        delta_nwc = _valor_anual(conteudo, "fcff", chave_ano, "delta_nwc")
        nopat = _valor_anual(conteudo, "fcff", chave_ano, "nopat")
        if ebitda is None or delta_nwc is None or nopat is None:
            erros.append(f"{chave_ano}=campos invalidos")
            continue
        if abs(ebitda) < EPSILON:
            violacoes.append(f"{chave_ano}=EBITDA zero")
            continue

        # Formula: FCO ~= EBITDA - Delta NWC - IR pago.
        ir_pago = nopat * fator_ir
        fco = ebitda - delta_nwc - ir_pago
        razao = fco / ebitda
        valores.append(f"{chave_ano}={razao:.2f}x")
        if razao <= LIMITE_FCO_EBITDA:
            violacoes.append(f"{chave_ano}={razao:.2f}x")

    if erros:
        return criar_item("NF4", descricao, STATUS_ERRO, "; ".join(erros), limite)
    status = STATUS_ALERTA if violacoes else STATUS_OK
    valor = "; ".join(violacoes if violacoes else valores)
    return criar_item("NF4", descricao, status, valor, limite)


def verificar_nf5(conteudo: dict[str, Any]) -> dict[str, float | str]:
    """NF5: Divida liquida / EBITDA do ano 8 deve ficar abaixo de 4x."""
    descricao = "Divida liquida / EBITDA ano8 abaixo de 4x"
    limite = "< 4,0x"
    divida_bruta = _valor_anual(conteudo, "divida", "ano8", "divida_bruta")
    caixa = _valor_anual(conteudo, "balanco", "ano8", "caixa_equivalentes")
    aplicacoes = _valor_anual(
        conteudo,
        "balanco",
        "ano8",
        "aplicacoes_financeiras",
    )
    ebitda = _valor_anual(conteudo, "dre", "ano8", "ebitda")
    if divida_bruta is None or caixa is None or aplicacoes is None or ebitda is None:
        return _item_campo_invalido(
            "NF5",
            descricao,
            "divida/caixa/aplicacoes/EBITDA",
            limite,
        )
    if abs(ebitda) < EPSILON:
        return criar_item("NF5", descricao, STATUS_ALERTA, "EBITDA zero", limite)

    # Formula: Divida Liquida = Divida Bruta - Caixa - Aplicacoes.
    divida_liquida = divida_bruta - caixa - aplicacoes
    razao = divida_liquida / ebitda
    status = STATUS_ALERTA if razao >= LIMITE_DIVIDA_LIQUIDA_EBITDA else STATUS_OK
    return criar_item("NF5", descricao, status, razao, limite)


def verificar_f1(conteudo: dict[str, Any]) -> dict[str, float | str]:
    """F1: indice de capital alvo precisa respeitar Basileia (>= 10,5%)."""
    descricao = "indice de capital alvo acima de Basileia"
    limite = ">= 10,50%"
    capital = conteudo.get("capital_regulatorio", {}).get("ano1", {})
    indice = _numero_opcional(capital, "indice_capital_alvo")
    if indice is None:
        return _item_campo_invalido("F1", descricao, "indice_capital_alvo", limite)
    status = STATUS_ERRO if indice < LIMITE_INDICE_CAPITAL else STATUS_OK
    return criar_item("F1", descricao, status, indice, limite)


def verificar_f2(conteudo: dict[str, Any]) -> dict[str, float | str]:
    """F2: ROE projetado medio deve superar o Ke (criacao de valor)."""
    descricao = "ROE projetado medio acima do Ke"
    limite = "ROE medio > Ke"
    ke = _numero_opcional(conteudo.get("ke", {}), "ke_brl")
    if ke is None:
        return _item_campo_invalido("F2", descricao, "ke_brl", limite)

    roes = []
    capital = conteudo.get("capital_regulatorio", {})
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        roe = _numero_opcional(capital.get(f"ano{ano}", {}), "roe_projetado")
        if roe is not None:
            roes.append(roe)
    if not roes:
        return _item_campo_invalido("F2", descricao, "roe_projetado", limite)

    roe_medio = sum(roes) / len(roes)
    status = STATUS_ALERTA if roe_medio <= ke else STATUS_OK
    return criar_item(
        "F2",
        descricao,
        status,
        _formatar_percentuais(ROE=roe_medio, Ke=ke),
        limite,
    )


def verificar_f3(conteudo: dict[str, Any]) -> dict[str, float | str]:
    """F3: payout implicito (FCFE/LL) medio precisa ficar entre 0 e 100%."""
    descricao = "payout implicito medio em 0-100%"
    limite = "0 <= FCFE/LL <= 1"
    payouts = []
    fcfe = conteudo.get("fcfe", {})
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        payout = _numero_opcional(fcfe.get(f"ano{ano}", {}), "payout_implicito")
        if payout is not None:
            payouts.append(payout)
    if not payouts:
        return criar_item("F3", descricao, STATUS_ALERTA, "n/d (LL <= 0)", limite)

    payout_medio = sum(payouts) / len(payouts)
    fora = (
        payout_medio < LIMITE_PAYOUT_IMPLICITO[0]
        or payout_medio > LIMITE_PAYOUT_IMPLICITO[1]
    )
    status = STATUS_ALERTA if fora else STATUS_OK
    return criar_item("F3", descricao, status, payout_medio, limite)


def _empresa_nao_financeira(
    conteudo: dict[str, Any],
    premissas: dict[str, Any],
    metadados: dict[str, Any],
) -> bool:
    """Detecta trilha nao-financeira usando metadados, premissas e projecao."""
    for fonte in (premissas, metadados, conteudo):
        tipo = normalizar_texto(fonte.get("tipo"))
        tipo = tipo.replace("-", "_").replace(" ", "_")
        if tipo in {"nao_financeira", "naofinanceira"}:
            return True
    return False


def _empresa_financeira(
    conteudo: dict[str, Any],
    premissas: dict[str, Any],
    metadados: dict[str, Any],
) -> bool:
    """Detecta trilha financeira EXPLICITA (sem tipo declarado nao entra)."""
    for fonte in (premissas, metadados, conteudo):
        if normalizar_texto(fonte.get("tipo")) == "financeira":
            return True
    return False


def montar_itens_checklist(
    conteudo: dict[str, Any],
    premissas: dict[str, Any],
    metadados: dict[str, Any],
) -> list[dict[str, float | str]]:
    """Monta todos os itens aplicaveis ao tipo de empresa."""
    valor_terminal = conteudo["valor_terminal"]
    ev_equity = conteudo["ev_equity"]
    itens = [
        verificar_u1(valor_terminal),
        verificar_u2(valor_terminal),
        verificar_u3(valor_terminal),
        verificar_u4(valor_terminal),
        verificar_u5(ev_equity),
    ]

    if _empresa_nao_financeira(conteudo, premissas, metadados):
        usa_ret = empresa_usa_ret(premissas, metadados)
        itens.extend(
            [
                verificar_nf1(conteudo),
                verificar_nf2(conteudo),
                verificar_nf3(conteudo),
                verificar_nf4(conteudo, usa_ret=usa_ret),
                verificar_nf5(conteudo),
            ]
        )
    elif _empresa_financeira(conteudo, premissas, metadados):
        # Trilha financeira (Onda 2): Basileia, ROE vs Ke e payout implicito.
        itens.extend(
            [
                verificar_f1(conteudo),
                verificar_f2(conteudo),
                verificar_f3(conteudo),
            ]
        )

    return itens


def executar_checklist(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa o checklist de consistencia e persiste no JSON de projecao."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    premissas = carregar_premissas_checklist(ticker_normalizado, raiz)
    financeira = _empresa_financeira({}, premissas, metadados)
    caminho, conteudo = carregar_projecao_checklist(
        ticker_normalizado,
        raiz,
        financeira=financeira,
    )

    itens = montar_itens_checklist(conteudo, premissas, metadados)
    aprovado = not any(item["status"] == STATUS_ERRO for item in itens)
    resultado = {
        "ticker": ticker_normalizado,
        "itens": itens,
        "aprovado": aprovado,
    }

    conteudo["checklist"] = resultado
    salvar_json(caminho, conteudo)
    return resultado


def _formatar_valor_tabela(valor: float | str) -> str:
    """Formata valores para a tabela ASCII do checklist."""
    if isinstance(valor, float):
        return formatar_numero(valor)
    return str(valor)


def imprimir_checklist(resultado: dict[str, Any]) -> None:
    """Imprime o checklist em tabela ASCII."""
    print("\n" + "=" * 120)
    print(f"Checklist de consistencia - {resultado['ticker']}")
    print("-" * 120)
    cabecalho = (
        f"{'ID':<5} {'Descricao':<45} {'Marcador':<8} " f"{'Valor':<38} {'Limite':<20}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for item in resultado["itens"]:
        valor = _formatar_valor_tabela(item["valor"])
        print(
            f"{item['id']:<5} "
            f"{item['descricao']:<45} "
            f"{item['status']:<8} "
            f"{valor:<38.38} "
            f"{item['limite']:<20}"
        )
    print("-" * len(cabecalho))
    print(f"Aprovado: {resultado['aprovado']}")


def main() -> None:
    """Executa o checklist padrao para DIRR3."""
    imprimir_checklist(executar_checklist("DIRR3"))


if __name__ == "__main__":
    main()
