"""Calculador do Valor Terminal (perpetuidade de Gordon) do DCF.

VT = FCFF_8 x (1 + g) / (WACC - g), com salvaguardas:
    - bloqueia g >= WACC (modelo explode);
    - alerta g > 5% BRL;
    - valida taxa de reinvestimento em [0, 1];
    - se FCFF_8 < 0, usa NOPAT_8 normalizado como base.
Calcula VP(VT), % do EV na perpetuidade e multiplo de saida implicito.
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from typing import Any

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        formatar_numero,
        formatar_percentual,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.valuation.calculador_wacc import ler_premissa_numerica
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.projecao.projetor_dre import (
        HORIZONTE_PROJECAO,
        carregar_json,
        formatar_numero,
        formatar_percentual,
        normalizar_ticker,
        resolver_raiz,
        salvar_json,
    )
    from src.projecao.schedule_divida import obter_float_obrigatorio
    from src.valuation.calculador_wacc import ler_premissa_numerica

LIMITE_G_BRL = 0.05
TAXA_REINVESTIMENTO_PADRAO = 0.0

logger = logging.getLogger(__name__)


def carregar_premissas_vt(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega o arquivo de premissas do ticker."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    return carregar_json(caminho)


def carregar_projecao_vt(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[Path, dict[str, Any]]:
    """Carrega a projecao integrada e valida os blocos usados pelo VT."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    conteudo = carregar_json(caminho)
    for bloco in ("dre", "fcff", "wacc"):
        if not isinstance(conteudo.get(bloco), dict):
            raise RuntimeError(f"Bloco obrigatorio ausente em {caminho}: {bloco}")
    return caminho, conteudo


def calcular_soma_vp_fcff(conteudo: dict[str, Any], wacc: float) -> float:
    """Soma os FCFF dos anos 1-8 descontados ao WACC (calculo interno)."""
    fcff = conteudo["fcff"]
    soma = 0.0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        fluxo = obter_float_obrigatorio(fcff[chave_ano], "fcff", chave_ano)
        # Formula: VP(FCFF_t) = FCFF_t / (1 + WACC)^t.
        soma += fluxo / (1 + wacc) ** ano
    return soma


def calcular_valor_terminal(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Calcula o valor terminal e persiste o bloco valor_terminal na projecao."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    premissas = carregar_premissas_vt(ticker_normalizado, raiz)
    caminho, conteudo = carregar_projecao_vt(ticker_normalizado, raiz)

    g = ler_premissa_numerica(
        premissas,
        ("crescimento_perpetuidade", "crescimento_perpetuidade_g"),
    )
    wacc = obter_float_obrigatorio(conteudo["wacc"], "wacc", "wacc")
    fcff_ano8 = obter_float_obrigatorio(conteudo["fcff"]["ano8"], "fcff", "ano8")
    nopat_ano8 = obter_float_obrigatorio(conteudo["fcff"]["ano8"], "nopat", "ano8")
    ebitda_ano8 = obter_float_obrigatorio(conteudo["dre"]["ano8"], "ebitda", "ano8")

    # Validacao (a): g >= WACC faz a perpetuidade de Gordon explodir.
    if g >= wacc:
        raise ValueError(
            f"g ({g:.2%}) >= WACC ({wacc:.2%}): modelo Gordon explode. "
            "Reduza g ou aumente o WACC."
        )

    # Validacao (b): g acima de 5% BRL exige justificativa macro.
    if g > LIMITE_G_BRL:
        warnings.warn(
            f"ALERTA: g={g:.2%} acima de 5% BRL. Justifique com crescimento "
            "nominal de longo prazo da economia.",
            stacklevel=2,
        )

    # Validacao (c): taxa de reinvestimento precisa estar em [0, 1].
    taxa_reinvestimento = ler_premissa_numerica(
        premissas,
        ("taxa_reinvestimento_perpetuidade", "taxa_reinvestimento"),
        padrao=TAXA_REINVESTIMENTO_PADRAO,
    )
    if not 0.0 <= taxa_reinvestimento <= 1.0:
        raise ValueError(
            f"Taxa de reinvestimento na perpetuidade fora de [0, 1]: "
            f"{taxa_reinvestimento:.2%}."
        )

    # Tratamento de FCFF_8 negativo: usa NOPAT_8 normalizado como base.
    if fcff_ano8 < 0:
        base = nopat_ano8
        base_vt = "nopat_normalizado"
        logger.warning(
            "FCFF do ano 8 negativo (%.1f); usando NOPAT_8 normalizado (%.1f) "
            "como base do valor terminal.",
            fcff_ano8,
            nopat_ano8,
        )
    else:
        base = fcff_ano8
        base_vt = "fcff_ano8"

    # Formula: VT_bruto = base x (1 + g) / (WACC - g).
    vt_bruto = base * (1 + g) / (wacc - g)

    # Formula: VP(VT) = VT_bruto / (1 + WACC)^8.
    vp_vt = vt_bruto / (1 + wacc) ** HORIZONTE_PROJECAO

    # Sanity check: multiplo de saida implicito EV/EBITDA na perpetuidade.
    if ebitda_ano8 == 0:
        multiplo_saida = float("nan")
    else:
        multiplo_saida = vt_bruto / ebitda_ano8

    soma_vp_fcff = calcular_soma_vp_fcff(conteudo, wacc)
    ev_total = soma_vp_fcff + vp_vt
    if ev_total == 0:
        pct_ev_perpetuidade = float("nan")
    else:
        pct_ev_perpetuidade = vp_vt / ev_total

    resultado = {
        "ticker": ticker_normalizado,
        "g": g,
        "wacc": wacc,
        "fcff_ano8": fcff_ano8,
        "nopat_ano8": nopat_ano8,
        "ebitda_ano8": ebitda_ano8,
        "taxa_reinvestimento": taxa_reinvestimento,
        "base_vt": base_vt,
        "base_utilizada": base,
        "vt_bruto": vt_bruto,
        "vp_vt": vp_vt,
        "multiplo_saida_implicito": multiplo_saida,
        "soma_vp_fcff": soma_vp_fcff,
        "pct_ev_perpetuidade": pct_ev_perpetuidade,
    }

    conteudo["valor_terminal"] = resultado
    salvar_json(caminho, conteudo)
    resultado["caminho_saida"] = caminho
    return resultado


def imprimir_valor_terminal(resultado: dict[str, Any]) -> None:
    """Imprime a decomposicao do valor terminal para validacao visual."""
    print("\n" + "=" * 72)
    print(f"Valor Terminal - {resultado['ticker']}")
    print("-" * 72)
    print(f"{'g (perpetuidade)':<28} {formatar_percentual(resultado['g']):>18}")
    print(f"{'WACC':<28} {formatar_percentual(resultado['wacc']):>18}")
    print(f"{'FCFF ano 8':<28} R$ {formatar_numero(resultado['fcff_ano8']):>15}")
    print(f"{'NOPAT ano 8':<28} R$ {formatar_numero(resultado['nopat_ano8']):>15}")
    print(
        f"{'Base do VT':<28} {resultado['base_vt']:>18}  "
        f"(R$ {formatar_numero(resultado['base_utilizada'])})"
    )
    print(f"{'VT bruto':<28} R$ {formatar_numero(resultado['vt_bruto']):>15}")
    print(f"{'VP(VT)':<28} R$ {formatar_numero(resultado['vp_vt']):>15}")
    print(
        f"{'Soma VP(FCFF) 1-8':<28} "
        f"R$ {formatar_numero(resultado['soma_vp_fcff']):>15}"
    )
    print(
        f"{'Multiplo saida (VT/EBITDA8)':<28} "
        f"{resultado['multiplo_saida_implicito']:>16.2f}x"
    )
    print(
        f"{'% EV na perpetuidade':<28} "
        f"{formatar_percentual(resultado['pct_ev_perpetuidade']):>18}"
    )


def main() -> None:
    """Executa o calculo padrao para DIRR3."""
    imprimir_valor_terminal(calcular_valor_terminal("DIRR3"))


if __name__ == "__main__":
    main()
