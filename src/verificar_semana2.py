"""Verificacao operacional da Semana 2 para DIRR3 e MGLU3."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.projecao.projetor_dre import (  # noqa: E402
    HORIZONTE_PROJECAO,
    carregar_json,
    formatar_numero,
    formatar_percentual,
    projetar_dre,
    selecionar_ultimo_exercicio,
)
from src.projecao.schedule_divida import projetar_divida  # noqa: E402
from src.projecao.schedule_leasing import projetar_leasing  # noqa: E402
from src.projecao.schedule_ppe import projetar_ppe  # noqa: E402
from src.projecao.schedule_wk import projetar_wk  # noqa: E402


def obter_valor_ano0(ticker: str, demonstrativo: str, campo: str) -> float:
    """Le uma conta padronizada do ultimo exercicio historico disponivel."""
    caminho = RAIZ_PROJETO / "data" / "raw" / "cvm" / f"{ticker}_{demonstrativo}.json"
    dados = pd.DataFrame(carregar_json(caminho))
    linha = selecionar_ultimo_exercicio(dados, campo)
    return float(linha["valor_padronizado"])


def imprimir_premissas(ticker: str) -> None:
    """Imprime as oito premissas anuais exigidas pela Semana 2."""
    caminho = RAIZ_PROJETO / "data" / "premissas" / f"{ticker}_premissas.json"
    premissas = carregar_json(caminho)
    crescimentos = [
        float(premissas[f"crescimento_receita_ano{ano}"])
        for ano in range(1, HORIZONTE_PROJECAO + 1)
    ]
    margens = [
        float(premissas[f"margem_ebitda_ano{ano}"])
        for ano in range(1, HORIZONTE_PROJECAO + 1)
    ]

    print(
        "Crescimento receita: "
        + ", ".join(formatar_percentual(valor) for valor in crescimentos)
    )
    print(
        "Margem EBITDA: " + ", ".join(formatar_percentual(valor) for valor in margens)
    )


def verificar_ticker(ticker: str) -> bool:
    """Roda DRE -> WK -> PP&E -> divida e imprime diagnostico anual."""
    print("\n" + "=" * 120)
    print(f"Verificacao Semana 2 - {ticker}")

    receita_ano0 = obter_valor_ano0(ticker, "dre", "receita_liquida")
    lucro_ano0 = obter_valor_ano0(ticker, "dre", "lucro_liquido")
    print(
        "Ano 0: "
        f"receita_liquida={formatar_numero(receita_ano0)} | "
        f"lucro_liquido={formatar_numero(lucro_ano0)}"
    )
    imprimir_premissas(ticker)

    projetar_dre(ticker)
    projetar_wk(ticker)
    projetar_ppe(ticker)
    projetar_leasing(ticker)
    resultado = projetar_divida(ticker)

    anos_com_desvio = []
    cabecalho = (
        f"{'Ano':<6} {'Receita':>18} {'EBITDA':>18} " f"{'LL':>18} {'Dif. balanco':>18}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        linha_dre = resultado["dre"][chave_ano]
        linha_balanco = resultado["balanco"][chave_ano]
        diferenca = float(linha_balanco["diferenca_balanco"])
        if abs(diferenca) > 1e-6:
            anos_com_desvio.append(chave_ano)

        print(
            f"{chave_ano:<6} "
            f"{formatar_numero(float(linha_dre['receita_liquida'])):>18} "
            f"{formatar_numero(float(linha_dre['ebitda'])):>18} "
            f"{formatar_numero(float(linha_dre['lucro_liquido'])):>18} "
            f"{formatar_numero(diferenca):>18}"
        )

    if anos_com_desvio:
        print(f"SEMANA 2 COM DESVIOS EM {ticker}: {', '.join(anos_com_desvio)}")
        return False

    print(f"SEMANA 2 OK - {ticker}")
    return True


def main() -> None:
    """Executa a verificacao para os dois tickers da v1.0."""
    resultados = [verificar_ticker(ticker) for ticker in ("DIRR3", "MGLU3")]
    if not all(resultados):
        raise SystemExit(1)

    print("\nSEMANA 2 OK")


if __name__ == "__main__":
    main()
