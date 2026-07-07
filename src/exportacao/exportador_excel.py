"""Exportador Excel de 7 abas (secao 5.10 do ROTEIRO — padrao WSP).

Gera ``outputs/excel/<TICKER>_dcf.xlsx`` com openpyxl a partir dos resultados
JA PERSISTIDOS pelo motor (``data/processed/<TICKER>_projecao.json`` e
companhia). O exportador e um CONSUMIDOR puro: nenhum numero nasce aqui —
quando uma celula recebe formula nativa do Excel, o valor que a formula
produziria e recalculado em Python e conferido contra o valor do motor;
se divergirem (ex.: salvaguarda do delta NWC do ano 1), a celula recebe o
VALOR do motor, preservando a fonte unica de verdade.

Convencao de cores de banco/WSP (ROTEIRO, Etapa 5):
- fonte AZUL   = premissa/input editavel (hard-coded);
- fonte PRETA  = formula na propria aba (ou valor do motor);
- fonte VERDE  = link para outra aba.

Abas: Capa, Premissas, Modelo Integrado, Schedules, Valuation,
Sensibilidades e Output. Cabecalhos navy, numeros com separador de milhar
e 2 casas, percentuais com 1 casa, numeros em fonte monoespacada.
"""

from __future__ import annotations

import logging
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ImagemExcel
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.worksheet import Worksheet

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

try:
    from src.metricas.metricas_historicas import montar_series_anuais
    from src.projecao.projetor_dre import (
        ALIQUOTA_IR_CSLL_GERAL,
        ALIQUOTA_RET_RECEITA,
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.visualizacao.apoio_cenarios import (
        carregar_metricas,
        carregar_projecao,
        recalcular_cenario,
    )
    from src.visualizacao.tema_institucional import (
        formatar_moeda_brl,
        formatar_percentual_br,
    )
except ModuleNotFoundError as erro:
    if erro.name != "src":
        raise
    from src.metricas.metricas_historicas import montar_series_anuais
    from src.projecao.projetor_dre import (
        ALIQUOTA_IR_CSLL_GERAL,
        ALIQUOTA_RET_RECEITA,
        HORIZONTE_PROJECAO,
        carregar_json,
        carregar_metadados,
        empresa_usa_ret,
        normalizar_texto,
        normalizar_ticker,
        resolver_raiz,
    )
    from src.visualizacao.apoio_cenarios import (
        carregar_metricas,
        carregar_projecao,
        recalcular_cenario,
    )
    from src.visualizacao.tema_institucional import (
        formatar_moeda_brl,
        formatar_percentual_br,
    )

# Nomes e ordem das 7 abas (secao 5.10). Fonte unica usada tanto na geracao
# do .xlsx quanto no preview do app, para que os dois nunca divirjam.
NOMES_ABAS = (
    "Capa",
    "Premissas",
    "Modelo Integrado",
    "Schedules",
    "Valuation",
    "Sensibilidades",
    "Output",
)

logger = logging.getLogger(__name__)

# Paleta institucional (mesma do tema Plotly, em ARGB para openpyxl).
COR_NAVY = "FF0A1628"
COR_AZUL_ANCORA = "FF1B4F8C"
COR_SUPERFICIE = "FF0F1E33"
COR_BRANCO = "FFFFFFFF"
COR_VERDE_FUNDO = "FF16A34A"
COR_VERMELHO_FUNDO = "FFDC2626"
COR_AMARELO_FUNDO = "FFB45309"
COR_DOURADO = "FFC9A227"
COR_CINZA_ND = "FF8FA3BC"

# Convencao WSP de fontes.
COR_FONTE_INPUT = "FF0B5394"  # azul: premissa hard-coded
COR_FONTE_FORMULA = "FF000000"  # preto: formula na propria aba
COR_FONTE_LINK = "FF1E7A34"  # verde: link para outra aba

FONTE_TEXTO = "Calibri"
FONTE_NUMERO = "Consolas"

# Formatos numericos padrao (milhar + 2 casas; percentual com 1 casa).
FORMATO_MILHAR = "#,##0.00"
FORMATO_PERCENTUAL = "0.0%"
FORMATO_PERCENTUAL_2 = "0.00%"
FORMATO_PRECO = '"R$" #,##0.00'
FORMATO_MULTIPLO = '0.00"x"'
FORMATO_DIAS = "#,##0"

# Limiares de recomendacao do motor (calculador_ev): COMPRA > +20%,
# VENDA < -5%. Usados na formatacao condicional das sensibilidades.
LIMITE_COMPRA = 0.20
LIMITE_VENDA = -0.05

ANOS_HISTORICOS_MODELO = 3

_LADO_FINO = Side(style="thin", color="FFB8C4D4")
BORDA_FINA = Border(
    left=_LADO_FINO,
    right=_LADO_FINO,
    top=_LADO_FINO,
    bottom=_LADO_FINO,
)
_LADO_OURO = Side(style="medium", color=COR_DOURADO)
BORDA_CASO_BASE = Border(
    left=_LADO_OURO,
    right=_LADO_OURO,
    top=_LADO_OURO,
    bottom=_LADO_OURO,
)


def caminho_excel(ticker: str, raiz: Path) -> Path:
    """Caminho padrao do arquivo Excel gerado para o ticker."""
    pasta = raiz / "outputs" / "excel"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{ticker}_dcf.xlsx"


def _celula(coluna: int, linha: int) -> str:
    """Endereco A1 a partir de indices numericos (coluna 1 = A)."""
    return f"{get_column_letter(coluna)}{linha}"


def _valores_proximos(valor_a: Any, valor_b: Any) -> bool:
    """Compara o valor recalculado em Python com o valor do motor."""
    if not isinstance(valor_a, (int, float)) or not isinstance(valor_b, (int, float)):
        return False
    return math.isclose(float(valor_a), float(valor_b), rel_tol=1e-6, abs_tol=1e-4)


def escrever_titulo(ws: Worksheet, linha: int, texto: str, ate_coluna: int) -> None:
    """Escreve uma faixa de titulo navy ocupando as colunas do bloco."""
    for coluna in range(1, ate_coluna + 1):
        celula = ws.cell(row=linha, column=coluna)
        celula.fill = PatternFill("solid", start_color=COR_NAVY)
    celula = ws.cell(row=linha, column=1, value=texto)
    celula.font = Font(name=FONTE_TEXTO, bold=True, size=12, color=COR_BRANCO)


def escrever_cabecalho_colunas(
    ws: Worksheet,
    linha: int,
    coluna_inicial: int,
    rotulos: list[str],
) -> None:
    """Escreve cabecalhos de coluna com fundo azul ancora e texto branco."""
    for indice, rotulo in enumerate(rotulos):
        celula = ws.cell(row=linha, column=coluna_inicial + indice, value=rotulo)
        celula.fill = PatternFill("solid", start_color=COR_AZUL_ANCORA)
        celula.font = Font(name=FONTE_TEXTO, bold=True, size=10, color=COR_BRANCO)
        celula.alignment = Alignment(horizontal="center")


def escrever_rotulo(
    ws: Worksheet,
    linha: int,
    texto: str,
    negrito: bool = False,
    recuo: int = 0,
) -> None:
    """Escreve o rotulo de uma linha na coluna A."""
    celula = ws.cell(row=linha, column=1, value=texto)
    celula.font = Font(name=FONTE_TEXTO, bold=negrito, size=10)
    if recuo:
        celula.alignment = Alignment(indent=recuo)


def escrever_numero(
    ws: Worksheet,
    linha: int,
    coluna: int,
    valor: Any,
    formato: str = FORMATO_MILHAR,
    cor_fonte: str = COR_FONTE_FORMULA,
    negrito: bool = False,
) -> None:
    """Escreve um valor numerico com fonte monoespacada e formato padrao.

    ``None`` e valores nao numericos viram "n/d" em cinza (dados historicos
    da CVM podem faltar sem derrubar a exportacao — robustez de dados).
    """
    celula = ws.cell(row=linha, column=coluna)
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        celula.value = float(valor)
        celula.number_format = formato
        celula.font = Font(name=FONTE_NUMERO, size=10, color=cor_fonte, bold=negrito)
    else:
        celula.value = "n/d"
        celula.font = Font(name=FONTE_NUMERO, size=10, color=COR_CINZA_ND)
        celula.alignment = Alignment(horizontal="right")


def escrever_calculo(
    ws: Worksheet,
    linha: int,
    coluna: int,
    formula: str,
    valor_python: Any,
    valor_motor: Any,
    formato: str = FORMATO_MILHAR,
    cor_fonte: str = COR_FONTE_FORMULA,
    negrito: bool = False,
) -> None:
    """Escreve formula nativa SE ela reproduz o valor do motor.

    ``valor_python`` e o resultado da formula recalculado em Python com os
    mesmos operandos que a formula referencia. Se nao bater com o valor
    persistido pelo motor (ex.: salvaguardas e pisos), a celula recebe o
    VALOR do motor — o Excel nunca mostra um numero diferente do pipeline.
    """
    if _valores_proximos(valor_python, valor_motor):
        celula = ws.cell(row=linha, column=coluna, value=formula)
        celula.number_format = formato
        celula.font = Font(name=FONTE_NUMERO, size=10, color=cor_fonte, bold=negrito)
    else:
        escrever_numero(ws, linha, coluna, valor_motor, formato, negrito=negrito)


def _serie_anual(projecao: dict[str, Any], bloco: str, campo: str) -> list[Any]:
    """Serie ano1..ano8 de um campo em um bloco da projecao persistida."""
    dados = projecao.get(bloco, {})
    serie: list[Any] = []
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        linha = dados.get(f"ano{ano}", {})
        serie.append(linha.get(campo))
    return serie


def _ultimos_anos_historicos(
    series: dict[str, dict[int, float]],
    quantidade: int = ANOS_HISTORICOS_MODELO,
) -> list[int]:
    """Ultimos exercicios anuais disponiveis na receita historica da CVM."""
    anos = sorted(series.get("receita_liquida", {}))
    return anos[-quantidade:] if anos else []


def _valor_historico(
    series: dict[str, dict[int, float]],
    campo: str,
    ano: int,
) -> float | None:
    """Valor historico de uma conta padronizada em um exercicio."""
    return series.get(campo, {}).get(ano)


def montar_contexto(ticker: str, raiz_projeto: Path | None = None) -> dict[str, Any]:
    """Carrega tudo que o exportador consome (motor, premissas, historico)."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    projecao = carregar_projecao(ticker_normalizado, raiz)
    caminho_premissas = (
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )
    premissas = carregar_json(caminho_premissas)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    metricas = carregar_metricas(ticker_normalizado, raiz)
    series_historicas = montar_series_anuais(ticker_normalizado, raiz)
    return {
        "ticker": ticker_normalizado,
        "raiz": raiz,
        "projecao": projecao,
        "premissas": premissas,
        "metadados": metadados,
        "metricas": metricas,
        "series_historicas": series_historicas,
        "anos_historicos": _ultimos_anos_historicos(series_historicas),
        "usa_ret": empresa_usa_ret(premissas, metadados),
        "referencias": {},
    }


def _inserir_png(
    ws: Worksheet,
    raiz: Path,
    ticker: str,
    nome: str,
    ancora: str,
    largura: int = 840,
    altura: int = 473,
) -> None:
    """Embute um PNG de ``outputs/graficos`` na aba; avisa se nao existir."""
    caminho = raiz / "outputs" / "graficos" / f"{ticker}_{nome}.png"
    if not caminho.exists():
        celula = ws[ancora]
        celula.value = f"[PNG nao encontrado: {caminho.name} — rode os graficos]"
        celula.font = Font(name=FONTE_TEXTO, italic=True, color=COR_CINZA_ND)
        logger.warning("PNG ausente para o Excel: %s", caminho)
        return
    imagem = ImagemExcel(str(caminho))
    imagem.width = largura
    imagem.height = altura
    ws.add_image(imagem, ancora)


# ---------------------------------------------------------------------------
# Aba 1 — Capa
# ---------------------------------------------------------------------------


def _aba_capa(wb: Workbook, ctx: dict[str, Any]) -> None:
    """Capa com identidade do modelo e os dados-chave da decisao."""
    ws = wb.active
    ws.title = "Capa"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 26

    projecao = ctx["projecao"]
    metadados = ctx["metadados"]
    ev_equity = projecao["ev_equity"]
    valor_terminal = projecao["valor_terminal"]

    # Faixa navy de abertura.
    for linha in range(1, 7):
        for coluna in range(1, 8):
            ws.cell(row=linha, column=coluna).fill = PatternFill(
                "solid", start_color=COR_NAVY
            )
    titulo = ws.cell(row=2, column=2, value=f"{ctx['ticker']} — Valuation por DCF")
    titulo.font = Font(name=FONTE_TEXTO, bold=True, size=22, color=COR_BRANCO)
    subtitulo = ws.cell(
        row=4,
        column=2,
        value=str(metadados.get("razao_social", "n/d")),
    )
    subtitulo.font = Font(name=FONTE_TEXTO, size=13, color="FF8FA3BC")
    marca = ws.cell(row=5, column=2, value="DCF Automatizado — v1.0")
    marca.font = Font(name=FONTE_TEXTO, size=10, color="FF8FA3BC")

    identidade = (
        ("Setor (CVM)", str(metadados.get("setor", "n/d")), None),
        ("Tipo detectado", str(metadados.get("tipo", "n/d")), None),
        (
            "Data-base (Ano 0)",
            str(projecao.get("ano0", {}).get("data_exercicio", "n/d")),
            None,
        ),
        ("Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M"), None),
        ("Escala dos valores", "R$ mil (escala CVM)", None),
    )
    decisao = (
        ("Preco atual", ev_equity.get("preco_atual"), FORMATO_PRECO),
        ("Target Price", ev_equity.get("target_price"), FORMATO_PRECO),
        ("Upside", ev_equity.get("upside"), FORMATO_PERCENTUAL),
        ("Recomendacao", str(ev_equity.get("recomendacao", "n/d")), None),
        ("WACC", projecao.get("wacc", {}).get("wacc"), FORMATO_PERCENTUAL_2),
        ("g (perpetuidade)", valor_terminal.get("g"), FORMATO_PERCENTUAL_2),
        ("EV", ev_equity.get("ev"), FORMATO_MILHAR),
        ("Equity Value", ev_equity.get("equity_value"), FORMATO_MILHAR),
        (
            "% do EV na perpetuidade",
            valor_terminal.get("pct_ev_perpetuidade"),
            FORMATO_PERCENTUAL,
        ),
    )

    linha = 8
    escrever_titulo(ws, linha, "IDENTIFICACAO", 7)
    linha += 1
    for rotulo, valor, formato in identidade:
        ws.cell(row=linha, column=2, value=rotulo).font = Font(
            name=FONTE_TEXTO, size=10
        )
        celula = ws.cell(row=linha, column=3, value=valor)
        celula.font = Font(name=FONTE_NUMERO, size=10)
        linha += 1

    linha += 1
    escrever_titulo(ws, linha, "DECISAO DE INVESTIMENTO", 7)
    linha += 1
    for rotulo, valor, formato in decisao:
        ws.cell(row=linha, column=2, value=rotulo).font = Font(
            name=FONTE_TEXTO, size=10
        )
        if formato is None:
            celula = ws.cell(row=linha, column=3, value=valor)
            cor = (
                COR_VERDE_FUNDO
                if valor == "COMPRA"
                else COR_VERMELHO_FUNDO if valor == "VENDA" else COR_FONTE_FORMULA
            )
            celula.font = Font(name=FONTE_NUMERO, size=11, bold=True, color=cor)
        else:
            escrever_numero(ws, linha, 3, valor, formato, negrito=True)
        linha += 1

    linha += 1
    convencao = ws.cell(
        row=linha,
        column=2,
        value=(
            "Convencao de cores: AZUL = premissa editavel | PRETO = formula | "
            "VERDE = link entre abas."
        ),
    )
    convencao.font = Font(name=FONTE_TEXTO, italic=True, size=9)
    linha += 1
    aviso = ws.cell(
        row=linha,
        column=2,
        value=(
            "Gerado automaticamente pelo motor Python; formulas nativas conferidas "
            "contra o pipeline. Nao e recomendacao de investimento."
        ),
    )
    aviso.font = Font(name=FONTE_TEXTO, italic=True, size=9, color="FF6B7A90")


# ---------------------------------------------------------------------------
# Aba 2 — Premissas
# ---------------------------------------------------------------------------


def _texto_historico_vetor(campo: str, agregados: dict[str, Any]) -> str:
    """Ancora historica exibida ao lado de cada vetor de premissas."""

    def _pct(valor: Any) -> str:
        return f"{float(valor) * 100:.1f}%" if valor is not None else "n/d"

    if campo == "crescimento_receita":
        return (
            f"CAGR 3a {_pct(agregados.get('cagr_receita_3a'))} | "
            f"CAGR 5a {_pct(agregados.get('cagr_receita_5a'))}"
        )
    if campo == "margem_ebitda":
        return (
            f"media 3a {_pct(agregados.get('margem_ebitda_media_3a'))} | "
            f"maxima {_pct(agregados.get('margem_ebitda_maxima'))}"
        )
    return f"media 3a {_pct(agregados.get('capex_receita_media_3a'))} da receita"


def _aba_premissas(wb: Workbook, ctx: dict[str, Any]) -> None:
    """Premissas: 8 valores individuais por vetor + historico ao lado."""
    ws = wb.create_sheet("Premissas")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 30
    for coluna in range(3, 11):
        ws.column_dimensions[get_column_letter(coluna)].width = 10
    ws.column_dimensions["B"].width = 2
    ws.column_dimensions["L"].width = 46

    premissas = ctx["premissas"]
    agregados = ctx["metricas"].get("agregados", {})
    referencias: dict[str, str] = {}

    escrever_titulo(ws, 1, "PREMISSAS DO ANALISTA — unico input humano do modelo", 12)
    nota = ws.cell(
        row=2,
        column=1,
        value=(
            "8 valores individuais por vetor (nunca uma taxa unica replicada). "
            "Fonte AZUL = input editavel; historico CVM ao lado como ancora."
        ),
    )
    nota.font = Font(name=FONTE_TEXTO, italic=True, size=9)

    linha = 4
    escrever_cabecalho_colunas(
        ws,
        linha,
        3,
        [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)],
    )
    ws.cell(row=linha, column=12, value="Historico CVM (ancora)").font = Font(
        name=FONTE_TEXTO, bold=True, size=10, color=COR_BRANCO
    )
    ws.cell(row=linha, column=12).fill = PatternFill(
        "solid", start_color=COR_AZUL_ANCORA
    )

    vetores = (
        ("crescimento_receita", "Crescimento da receita"),
        ("margem_ebitda", "Margem EBITDA"),
        ("capex_receita", "CAPEX / Receita (negativo = saida)"),
    )
    linha += 1
    for campo, rotulo in vetores:
        escrever_rotulo(ws, linha, rotulo, negrito=True)
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            escrever_numero(
                ws,
                linha,
                2 + ano,
                premissas.get(f"{campo}_ano{ano}"),
                FORMATO_PERCENTUAL,
                cor_fonte=COR_FONTE_INPUT,
            )
            referencias[f"{campo}_ano{ano}"] = _celula(2 + ano, linha)
        historico = ws.cell(
            row=linha, column=12, value=_texto_historico_vetor(campo, agregados)
        )
        historico.font = Font(name=FONTE_TEXTO, size=9, color="FF6B7A90")
        linha += 1

    linha += 1
    escrever_titulo(ws, linha, "CAPITAL DE GIRO E CUSTO DE CAPITAL", 12)
    linha += 1

    def _hist(chave: str, formato: str = "{:.0f}") -> str:
        valor = agregados.get(chave)
        if valor is None:
            return "sem historico"
        return f"hist. 3a: {formato.format(float(valor))}"

    escalares = (
        (
            "dso",
            "DSO — prazo de recebimento (dias)",
            FORMATO_DIAS,
            _hist("dso_media_3a"),
        ),
        ("dio", "DIO — prazo de estoque (dias)", FORMATO_DIAS, _hist("dio_media_3a")),
        ("dpo", "DPO — prazo de pagamento (dias)", FORMATO_DIAS, _hist("dpo_media_3a")),
        (
            "beta",
            "Beta desalavancado",
            "0.00",
            _hist("beta_desalavancado", "{:.2f}"),
        ),
        (
            "custo_divida_kd",
            "Kd — custo da divida",
            FORMATO_PERCENTUAL_2,
            (
                "hist.: "
                f"{(ctx['projecao']['wacc'].get('kd_historico') or 0) * 100:.1f}%"
            ),
        ),
        (
            "crescimento_perpetuidade_g",
            "g — crescimento na perpetuidade",
            FORMATO_PERCENTUAL_2,
            "teto de sanidade: 5,0% nominal BRL",
        ),
        ("erp", "ERP — premio de risco EUA", FORMATO_PERCENTUAL_2, ""),
        ("crp", "CRP — risco-pais Brasil", FORMATO_PERCENTUAL_2, ""),
    )
    for campo, rotulo, formato, historico in escalares:
        escrever_rotulo(ws, linha, rotulo)
        escrever_numero(
            ws,
            linha,
            3,
            premissas.get(campo),
            formato,
            cor_fonte=COR_FONTE_INPUT,
        )
        referencias[campo] = _celula(3, linha)
        ws.cell(row=linha, column=12, value=historico).font = Font(
            name=FONTE_TEXTO, size=9, color="FF6B7A90"
        )
        linha += 1

    estrutura = premissas.get("estrutura_capital_alvo", {})
    for campo, rotulo in (
        ("percentual_divida", "Estrutura alvo — % divida"),
        ("percentual_equity", "Estrutura alvo — % equity"),
    ):
        escrever_rotulo(ws, linha, rotulo)
        escrever_numero(
            ws,
            linha,
            3,
            estrutura.get(campo),
            FORMATO_PERCENTUAL,
            cor_fonte=COR_FONTE_INPUT,
        )
        linha += 1

    ctx["referencias"]["premissas"] = referencias


# ---------------------------------------------------------------------------
# Aba 3 — Modelo Integrado (DRE + BP + DFC, historico + projetado)
# ---------------------------------------------------------------------------

COL_MODELO_HIST = 2  # colunas B..D = 3 exercicios historicos
COL_MODELO_PROJ = COL_MODELO_HIST + ANOS_HISTORICOS_MODELO  # E..L = ano1..ano8
COL_MODELO_CS = COL_MODELO_PROJ + HORIZONTE_PROJECAO + 1  # common-size ao lado


def _cabecalho_modelo(
    ws: Worksheet,
    linha: int,
    anos_historicos: list[int],
    titulo_cs: str,
) -> None:
    """Cabecalho de anos: 3 historicos + ano1..ano8 + bloco common-size."""
    rotulos_hist = [str(ano) for ano in anos_historicos]
    while len(rotulos_hist) < ANOS_HISTORICOS_MODELO:
        rotulos_hist.insert(0, "hist n/d")
    rotulos_proj = [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)]
    escrever_cabecalho_colunas(ws, linha, COL_MODELO_HIST, rotulos_hist + rotulos_proj)
    escrever_cabecalho_colunas(
        ws,
        linha,
        COL_MODELO_CS,
        [f"{rotulo} %" for rotulo in rotulos_hist + rotulos_proj],
    )
    ws.cell(row=linha - 1, column=COL_MODELO_CS, value=titulo_cs).font = Font(
        name=FONTE_TEXTO, bold=True, size=9, color="FF6B7A90"
    )


def _common_size(
    ws: Worksheet,
    linha_origem: int,
    linha_base: int,
    colunas: int = ANOS_HISTORICOS_MODELO + HORIZONTE_PROJECAO,
) -> None:
    """Escreve o bloco common-size (linha / linha-base) ao lado do modelo."""
    for indice in range(colunas):
        coluna_origem = COL_MODELO_HIST + indice
        coluna_destino = COL_MODELO_CS + indice
        origem = ws.cell(row=linha_origem, column=coluna_origem)
        base = ws.cell(row=linha_base, column=coluna_origem)
        celula = ws.cell(row=linha_origem, column=coluna_destino)
        origem_numerica = isinstance(origem.value, (int, float)) or (
            isinstance(origem.value, str) and origem.value.startswith("=")
        )
        base_numerica = isinstance(base.value, (int, float)) or (
            isinstance(base.value, str) and base.value.startswith("=")
        )
        if origem_numerica and base_numerica:
            referencia_origem = _celula(coluna_origem, linha_origem)
            referencia_base = _celula(coluna_origem, linha_base)
            celula.value = f"={referencia_origem}/{referencia_base}"
            celula.number_format = FORMATO_PERCENTUAL
            celula.font = Font(name=FONTE_NUMERO, size=9, color=COR_FONTE_FORMULA)
        else:
            celula.value = "n/d"
            celula.font = Font(name=FONTE_NUMERO, size=9, color=COR_CINZA_ND)


def _aba_modelo_integrado(wb: Workbook, ctx: dict[str, Any]) -> None:
    """DRE + BP + DFC com 3 anos historicos e 8 projetados lado a lado."""
    ws = wb.create_sheet("Modelo Integrado")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B3"
    ws.column_dimensions["A"].width = 36
    total_colunas = ANOS_HISTORICOS_MODELO + HORIZONTE_PROJECAO
    for indice in range(total_colunas):
        ws.column_dimensions[get_column_letter(COL_MODELO_HIST + indice)].width = 13
        ws.column_dimensions[get_column_letter(COL_MODELO_CS + indice)].width = 9

    projecao = ctx["projecao"]
    premissas_ref = ctx["referencias"]["premissas"]
    series = ctx["series_historicas"]
    anos_hist = ctx["anos_historicos"]
    metricas_ano = ctx["metricas"].get("metricas_por_ano", {})
    usa_ret = ctx["usa_ret"]
    referencias: dict[str, int] = {}

    escrever_titulo(
        ws,
        1,
        "MODELO INTEGRADO — DRE + BP + DFC (R$ mil) | historico CVM + 8 anos "
        "projetados | common-size ao lado",
        COL_MODELO_CS + total_colunas - 1,
    )

    def _colunas_hist(campo: str) -> list[float | None]:
        valores: list[float | None] = [
            _valor_historico(series, campo, ano) for ano in anos_hist
        ]
        while len(valores) < ANOS_HISTORICOS_MODELO:
            valores.insert(0, None)
        return valores

    def _hist_metricas(campo: str) -> list[float | None]:
        valores: list[float | None] = [
            metricas_ano.get(str(ano), {}).get(campo) for ano in anos_hist
        ]
        while len(valores) < ANOS_HISTORICOS_MODELO:
            valores.insert(0, None)
        return valores

    def _escrever_linha_historica(linha: int, valores: list[float | None]) -> None:
        for indice, valor in enumerate(valores):
            escrever_numero(ws, linha, COL_MODELO_HIST + indice, valor)

    # ----------------------------- DRE ------------------------------------
    linha = 3
    escrever_titulo(ws, linha, "DRE", COL_MODELO_CS + total_colunas - 1)
    linha += 1
    _cabecalho_modelo(ws, linha, anos_hist, "Common-size (% da receita)")
    linha += 1

    linha_receita = linha
    referencias["receita"] = linha_receita
    escrever_rotulo(ws, linha, "Receita liquida", negrito=True)
    _escrever_linha_historica(linha, _colunas_hist("receita_liquida"))
    receita_hist_final = (
        _valor_historico(series, "receita_liquida", anos_hist[-1])
        if anos_hist
        else None
    )
    receita_serie = _serie_anual(projecao, "dre", "receita_liquida")
    crescimento_serie = _serie_anual(projecao, "dre", "taxa_crescimento_receita")
    receita_anterior = receita_hist_final
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        anterior = _celula(coluna - 1, linha)
        taxa_ref = premissas_ref[f"crescimento_receita_ano{ano}"]
        valor_python = None
        if receita_anterior is not None and crescimento_serie[ano - 1] is not None:
            valor_python = float(receita_anterior) * (
                1 + float(crescimento_serie[ano - 1])
            )
        escrever_calculo(
            ws,
            linha,
            coluna,
            f"={anterior}*(1+Premissas!{taxa_ref})",
            valor_python,
            receita_serie[ano - 1],
            cor_fonte=COR_FONTE_LINK,
            negrito=True,
        )
        receita_anterior = receita_serie[ano - 1]
    linha += 1

    escrever_rotulo(ws, linha, "Crescimento da receita (%)", recuo=1)
    yoy_hist = _hist_metricas("crescimento_receita_yoy")
    for indice, valor in enumerate(yoy_hist):
        escrever_numero(ws, linha, COL_MODELO_HIST + indice, valor, FORMATO_PERCENTUAL)
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        atual = _celula(coluna, linha_receita)
        anterior = _celula(coluna - 1, linha_receita)
        celula = ws.cell(row=linha, column=coluna, value=f"={atual}/{anterior}-1")
        celula.number_format = FORMATO_PERCENTUAL
        celula.font = Font(name=FONTE_NUMERO, size=10, color=COR_FONTE_FORMULA)
    linha += 1

    linha_ebitda = linha
    referencias["ebitda"] = linha_ebitda
    escrever_rotulo(ws, linha, "EBITDA")
    _escrever_linha_historica(linha, _hist_metricas("ebitda"))
    ebitda_serie = _serie_anual(projecao, "dre", "ebitda")
    margem_serie = _serie_anual(projecao, "dre", "margem_ebitda")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        margem_ref = premissas_ref[f"margem_ebitda_ano{ano}"]
        receita_ref = _celula(coluna, linha_receita)
        valor_python = None
        if receita_serie[ano - 1] is not None and margem_serie[ano - 1] is not None:
            valor_python = float(receita_serie[ano - 1]) * float(margem_serie[ano - 1])
        escrever_calculo(
            ws,
            linha,
            coluna,
            f"={receita_ref}*Premissas!{margem_ref}",
            valor_python,
            ebitda_serie[ano - 1],
            cor_fonte=COR_FONTE_LINK,
        )
    linha += 1

    escrever_rotulo(ws, linha, "Margem EBITDA (%)", recuo=1)
    for indice, valor in enumerate(_hist_metricas("margem_ebitda")):
        escrever_numero(ws, linha, COL_MODELO_HIST + indice, valor, FORMATO_PERCENTUAL)
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        formula = f"={_celula(coluna, linha_ebitda)}/{_celula(coluna, linha_receita)}"
        celula = ws.cell(row=linha, column=coluna, value=formula)
        celula.number_format = FORMATO_PERCENTUAL
        celula.font = Font(name=FONTE_NUMERO, size=10, color=COR_FONTE_FORMULA)
    linha += 1

    # D&A vem do schedule de PP&E (aba Schedules) de volta para a DRE.
    linha_da = linha
    referencias["da"] = linha_da
    escrever_rotulo(ws, linha, "(-) D&A (schedule PP&E)")
    _escrever_linha_historica(linha, _colunas_hist("depreciacao_amortizacao"))
    da_serie = _serie_anual(projecao, "dre", "depreciacao_amortizacao")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        ref_schedule = f"Schedules!{_celula(2 + ano, LINHA_PPE_DA)}"
        escrever_calculo(
            ws,
            linha,
            coluna,
            f"={ref_schedule}",
            da_serie[ano - 1],
            da_serie[ano - 1],
            cor_fonte=COR_FONTE_LINK,
        )
    linha += 1

    linha_ebit = linha
    referencias["ebit"] = linha_ebit
    escrever_rotulo(ws, linha, "EBIT", negrito=True)
    _escrever_linha_historica(linha, _colunas_hist("ebit"))
    ebit_serie = _serie_anual(projecao, "dre", "ebit")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        # Formula: EBIT = EBITDA - D&A.
        formula = f"={_celula(coluna, linha_ebitda)}-{_celula(coluna, linha_da)}"
        valor_python = None
        if ebitda_serie[ano - 1] is not None and da_serie[ano - 1] is not None:
            valor_python = float(ebitda_serie[ano - 1]) - float(da_serie[ano - 1])
        escrever_calculo(
            ws,
            linha,
            coluna,
            formula,
            valor_python,
            ebit_serie[ano - 1],
            negrito=True,
        )
    linha += 1

    linha_rf = linha
    escrever_rotulo(ws, linha, "Resultado financeiro (schedule divida)")
    _escrever_linha_historica(linha, _colunas_hist("resultado_financeiro"))
    rf_serie = _serie_anual(projecao, "dre", "resultado_financeiro")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        ref_schedule = f"Schedules!{_celula(2 + ano, LINHA_DIV_RF)}"
        escrever_calculo(
            ws,
            linha,
            coluna,
            f"={ref_schedule}",
            rf_serie[ano - 1],
            rf_serie[ano - 1],
            cor_fonte=COR_FONTE_LINK,
        )
    linha += 1

    linha_ebt = linha
    escrever_rotulo(ws, linha, "EBT")
    _escrever_linha_historica(linha, _colunas_hist("ebt"))
    ebt_serie = _serie_anual(projecao, "dre", "ebt")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        formula = f"={_celula(coluna, linha_ebit)}+{_celula(coluna, linha_rf)}"
        valor_python = None
        if ebit_serie[ano - 1] is not None and rf_serie[ano - 1] is not None:
            valor_python = float(ebit_serie[ano - 1]) + float(rf_serie[ano - 1])
        escrever_calculo(ws, linha, coluna, formula, valor_python, ebt_serie[ano - 1])
    linha += 1

    linha_ir = linha
    rotulo_ir = "(-) IR/CSLL (RET 4% receita)" if usa_ret else "(-) IR/CSLL (34% EBT)"
    escrever_rotulo(ws, linha, rotulo_ir)
    _escrever_linha_historica(linha, _colunas_hist("ir_csll"))
    ir_serie = _serie_anual(projecao, "dre", "ir_csll")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        if usa_ret:
            # Formula: IR/CSLL RET = -4% x receita (proxy da receita bruta).
            formula = f"=-{ALIQUOTA_RET_RECEITA}*{_celula(coluna, linha_receita)}"
            valor_python = (
                -ALIQUOTA_RET_RECEITA * float(receita_serie[ano - 1])
                if receita_serie[ano - 1] is not None
                else None
            )
        else:
            # Formula: IR/CSLL geral = -34% x EBT positivo (0 se prejuizo).
            referencia_ebt = _celula(coluna, linha_ebt)
            formula = (
                f"=IF({referencia_ebt}>0,"
                f"-{ALIQUOTA_IR_CSLL_GERAL}*{referencia_ebt},0)"
            )
            valor_python = None
            if ebt_serie[ano - 1] is not None:
                ebt_valor = float(ebt_serie[ano - 1])
                valor_python = (
                    -ALIQUOTA_IR_CSLL_GERAL * ebt_valor if ebt_valor > 0 else 0.0
                )
        escrever_calculo(ws, linha, coluna, formula, valor_python, ir_serie[ano - 1])
    linha += 1

    linha_ll = linha
    referencias["ll"] = linha_ll
    escrever_rotulo(ws, linha, "Lucro liquido", negrito=True)
    _escrever_linha_historica(linha, _colunas_hist("lucro_liquido"))
    ll_serie = _serie_anual(projecao, "dre", "lucro_liquido")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        formula = f"={_celula(coluna, linha_ebt)}+{_celula(coluna, linha_ir)}"
        valor_python = None
        if ebt_serie[ano - 1] is not None and ir_serie[ano - 1] is not None:
            valor_python = float(ebt_serie[ano - 1]) + float(ir_serie[ano - 1])
        escrever_calculo(
            ws,
            linha,
            coluna,
            formula,
            valor_python,
            ll_serie[ano - 1],
            negrito=True,
        )
    linha += 1

    # Common-size da DRE: % da receita do proprio ano.
    for linha_cs in (
        linha_receita,
        linha_ebitda,
        linha_da,
        linha_ebit,
        linha_rf,
        linha_ebt,
        linha_ir,
        linha_ll,
    ):
        _common_size(ws, linha_cs, linha_receita)

    # ----------------------------- BP -------------------------------------
    linha += 1
    escrever_titulo(ws, linha, "BALANCO PATRIMONIAL", COL_MODELO_CS + total_colunas - 1)
    linha += 1
    _cabecalho_modelo(ws, linha, anos_hist, "Common-size (% do ativo total)")
    linha += 1

    ativos = (
        ("caixa_equivalentes", "Caixa e equivalentes (plug)", None),
        ("aplicacoes_financeiras", "Aplicacoes financeiras", None),
        ("contas_receber", "Contas a receber", LINHA_WK_CR),
        ("estoques", "Estoques", LINHA_WK_EST),
        ("imobilizado", "Imobilizado (PP&E)", LINHA_PPE_IMOB),
        ("outros_ativos", "Outros ativos", None),
    )
    linhas_ativos: list[int] = []
    balanco_series = {
        campo: _serie_anual(projecao, "balanco", campo) for campo, _, _ in ativos
    }
    linha_caixa = linha
    for campo, rotulo, linha_schedule in ativos:
        escrever_rotulo(ws, linha, rotulo)
        if campo in ("outros_ativos",):
            _escrever_linha_historica(linha, [None] * ANOS_HISTORICOS_MODELO)
        else:
            _escrever_linha_historica(linha, _colunas_hist(campo))
        serie = balanco_series[campo]
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            coluna = COL_MODELO_PROJ + ano - 1
            if linha_schedule is not None:
                ref = f"Schedules!{_celula(2 + ano, linha_schedule)}"
                escrever_calculo(
                    ws,
                    linha,
                    coluna,
                    f"={ref}",
                    serie[ano - 1],
                    serie[ano - 1],
                    cor_fonte=COR_FONTE_LINK,
                )
            else:
                escrever_numero(ws, linha, coluna, serie[ano - 1])
        linhas_ativos.append(linha)
        linha += 1

    linha_ativo_total = linha
    escrever_rotulo(ws, linha, "Ativo total (soma das contas)", negrito=True)
    for indice in range(total_colunas):
        coluna = COL_MODELO_HIST + indice
        primeira = _celula(coluna, linhas_ativos[0])
        ultima = _celula(coluna, linhas_ativos[-1])
        celula = ws.cell(row=linha, column=coluna, value=f"=SUM({primeira}:{ultima})")
        celula.number_format = FORMATO_MILHAR
        celula.font = Font(name=FONTE_NUMERO, size=10, bold=True)
    linha += 1

    passivos = (
        ("fornecedores", "Fornecedores", LINHA_WK_FORN),
        ("divida_curto_prazo", "Divida de curto prazo", LINHA_DIV_CP),
        ("divida_longo_prazo", "Divida de longo prazo", LINHA_DIV_LP),
        ("outros_passivos", "Outros passivos", None),
    )
    linhas_passivos: list[int] = []
    for campo, rotulo, linha_schedule in passivos:
        escrever_rotulo(ws, linha, rotulo)
        if campo == "outros_passivos":
            _escrever_linha_historica(linha, [None] * ANOS_HISTORICOS_MODELO)
        elif campo == "fornecedores":
            historico = [
                abs(valor) if valor is not None else None
                for valor in _colunas_hist(campo)
            ]
            _escrever_linha_historica(linha, historico)
        else:
            _escrever_linha_historica(linha, _colunas_hist(campo))
        serie = _serie_anual(projecao, "balanco", campo)
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            coluna = COL_MODELO_PROJ + ano - 1
            if linha_schedule is None:
                escrever_numero(ws, linha, coluna, serie[ano - 1])
                continue
            ref = f"Schedules!{_celula(2 + ano, linha_schedule)}"
            if campo == "fornecedores":
                # No BP fornecedores entra como magnitude positiva; o schedule
                # WK preserva o sinal negativo de passivo para calcular o NWC.
                valor_schedule = _serie_anual(projecao, "wk", campo)[ano - 1]
                valor_python = (
                    -float(valor_schedule) if valor_schedule is not None else None
                )
                escrever_calculo(
                    ws,
                    linha,
                    coluna,
                    f"=-{ref}",
                    valor_python,
                    serie[ano - 1],
                    cor_fonte=COR_FONTE_LINK,
                )
            else:
                escrever_calculo(
                    ws,
                    linha,
                    coluna,
                    f"={ref}",
                    serie[ano - 1],
                    serie[ano - 1],
                    cor_fonte=COR_FONTE_LINK,
                )
        linhas_passivos.append(linha)
        linha += 1

    linha_passivo_total = linha
    escrever_rotulo(ws, linha, "Passivo total (soma das contas)", negrito=True)
    for indice in range(total_colunas):
        coluna = COL_MODELO_HIST + indice
        primeira = _celula(coluna, linhas_passivos[0])
        ultima = _celula(coluna, linhas_passivos[-1])
        celula = ws.cell(row=linha, column=coluna, value=f"=SUM({primeira}:{ultima})")
        celula.number_format = FORMATO_MILHAR
        celula.font = Font(name=FONTE_NUMERO, size=10, bold=True)
    linha += 1

    linha_pl = linha
    escrever_rotulo(ws, linha, "Patrimonio liquido", negrito=True)
    _escrever_linha_historica(linha, _colunas_hist("patrimonio_liquido"))
    pl_serie = _serie_anual(projecao, "balanco", "patrimonio_liquido")
    pl_hist_final = (
        _valor_historico(series, "patrimonio_liquido", anos_hist[-1])
        if anos_hist
        else None
    )
    pl_anterior = pl_hist_final
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        anterior = _celula(coluna - 1, linha)
        # Formula: PL_t = PL_(t-1) + LL_t (payout de dividendos = 0 na v1).
        formula = f"={anterior}+{_celula(coluna, linha_ll)}"
        valor_python = None
        if pl_anterior is not None and ll_serie[ano - 1] is not None:
            valor_python = float(pl_anterior) + float(ll_serie[ano - 1])
        escrever_calculo(
            ws,
            linha,
            coluna,
            formula,
            valor_python,
            pl_serie[ano - 1],
            negrito=True,
        )
        pl_anterior = pl_serie[ano - 1]
    linha += 1

    # O caixa projetado e o plug de fechamento do balanco (decisao v1):
    # caixa = Passivo total + PL - demais ativos. Reescreve a linha do caixa
    # com a formula do plug agora que os totais existem.
    caixa_serie = balanco_series["caixa_equivalentes"]
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        demais_ini = _celula(coluna, linhas_ativos[1])
        demais_fim = _celula(coluna, linhas_ativos[-1])
        formula = (
            f"={_celula(coluna, linha_passivo_total)}"
            f"+{_celula(coluna, linha_pl)}"
            f"-SUM({demais_ini}:{demais_fim})"
        )
        soma_demais = 0.0
        completa = True
        for campo, _, _ in ativos[1:]:
            valor = balanco_series[campo][ano - 1]
            if valor is None:
                completa = False
                break
            soma_demais += float(valor)
        passivo_total = _serie_anual(projecao, "balanco", "passivo_total")[ano - 1]
        valor_python = None
        if completa and passivo_total is not None and pl_serie[ano - 1] is not None:
            valor_python = float(passivo_total) + float(pl_serie[ano - 1]) - soma_demais
        escrever_calculo(
            ws,
            linha_caixa,
            coluna,
            formula,
            valor_python,
            caixa_serie[ano - 1],
        )

    escrever_rotulo(ws, linha, "Verificacao: Ativo - (Passivo + PL)")
    for indice in range(ANOS_HISTORICOS_MODELO):
        celula = ws.cell(row=linha, column=COL_MODELO_HIST + indice, value="—")
        celula.font = Font(name=FONTE_NUMERO, size=10, color=COR_CINZA_ND)
        celula.alignment = Alignment(horizontal="right")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        formula = (
            f"={_celula(coluna, linha_ativo_total)}"
            f"-{_celula(coluna, linha_passivo_total)}"
            f"-{_celula(coluna, linha_pl)}"
        )
        celula = ws.cell(row=linha, column=coluna, value=formula)
        celula.number_format = FORMATO_MILHAR
        celula.font = Font(name=FONTE_NUMERO, size=10, color="FF6B7A90")
    linha += 1

    for linha_cs in (
        linhas_ativos
        + [linha_ativo_total]
        + linhas_passivos
        + [linha_passivo_total, linha_pl]
    ):
        _common_size(ws, linha_cs, linha_ativo_total)

    # ----------------------------- DFC ------------------------------------
    linha += 1
    escrever_titulo(
        ws,
        linha,
        "DFC SIMPLIFICADO (projecao)",
        COL_MODELO_CS + total_colunas - 1,
    )
    linha += 1
    _cabecalho_modelo(ws, linha, anos_hist, "")
    linha += 1

    dfc_linhas = (
        ("lucro_liquido", "Lucro liquido", linha_ll, 1.0),
        ("depreciacao_amortizacao", "(+) D&A", linha_da, 1.0),
        ("delta_nwc", "(-) Delta NWC (consumo)", None, 1.0),
        ("capex_saida_caixa", "(-) CAPEX (saida de caixa)", None, 1.0),
        ("delta_divida", "(+) Delta divida", None, 1.0),
    )
    linhas_dfc: dict[str, int] = {}
    for campo, rotulo, linha_ref, _ in dfc_linhas:
        escrever_rotulo(ws, linha, rotulo)
        if campo == "depreciacao_amortizacao":
            _escrever_linha_historica(linha, _colunas_hist("depreciacao_amortizacao"))
        else:
            _escrever_linha_historica(linha, [None] * ANOS_HISTORICOS_MODELO)
        serie = _serie_anual(projecao, "dfc", campo)
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            coluna = COL_MODELO_PROJ + ano - 1
            if linha_ref is not None:
                escrever_calculo(
                    ws,
                    linha,
                    coluna,
                    f"={_celula(coluna, linha_ref)}",
                    serie[ano - 1],
                    serie[ano - 1],
                )
            elif campo == "delta_nwc":
                ref = f"Schedules!{_celula(2 + ano, LINHA_WK_DNWC)}"
                escrever_calculo(
                    ws,
                    linha,
                    coluna,
                    f"={ref}",
                    serie[ano - 1],
                    serie[ano - 1],
                    cor_fonte=COR_FONTE_LINK,
                )
            elif campo == "capex_saida_caixa":
                # O DFC subtrai a magnitude do CAPEX; o schedule PP&E salva o
                # CAPEX assinado (negativo = saida), por isso o sinal invertido.
                ref = f"Schedules!{_celula(2 + ano, LINHA_PPE_CAPEX)}"
                capex_assinado = _serie_anual(projecao, "ppe", "capex")[ano - 1]
                valor_python = (
                    abs(float(capex_assinado)) if capex_assinado is not None else None
                )
                escrever_calculo(
                    ws,
                    linha,
                    coluna,
                    f"=-{ref}",
                    valor_python,
                    serie[ano - 1],
                    cor_fonte=COR_FONTE_LINK,
                )
            else:
                escrever_numero(ws, linha, coluna, serie[ano - 1])
        linhas_dfc[campo] = linha
        linha += 1

    escrever_rotulo(ws, linha, "Fluxo de caixa livre", negrito=True)
    fcl_serie = _serie_anual(projecao, "dfc", "fluxo_caixa_livre")
    for indice in range(ANOS_HISTORICOS_MODELO):
        celula = ws.cell(row=linha, column=COL_MODELO_HIST + indice, value="n/d")
        celula.font = Font(name=FONTE_NUMERO, size=10, color=COR_CINZA_ND)
        celula.alignment = Alignment(horizontal="right")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = COL_MODELO_PROJ + ano - 1
        # Formula: FCL = LL + D&A - Delta NWC - CAPEX + Delta divida.
        formula = (
            f"={_celula(coluna, linhas_dfc['lucro_liquido'])}"
            f"+{_celula(coluna, linhas_dfc['depreciacao_amortizacao'])}"
            f"-{_celula(coluna, linhas_dfc['delta_nwc'])}"
            f"-{_celula(coluna, linhas_dfc['capex_saida_caixa'])}"
            f"+{_celula(coluna, linhas_dfc['delta_divida'])}"
        )
        componentes = [
            _serie_anual(projecao, "dfc", campo)[ano - 1]
            for campo in (
                "lucro_liquido",
                "depreciacao_amortizacao",
                "delta_nwc",
                "capex_saida_caixa",
                "delta_divida",
            )
        ]
        valor_python = None
        if all(valor is not None for valor in componentes):
            ll_v, da_v, dnwc_v, capex_v, ddiv_v = (float(v) for v in componentes)
            valor_python = ll_v + da_v - dnwc_v - capex_v + ddiv_v
        escrever_calculo(
            ws,
            linha,
            coluna,
            formula,
            valor_python,
            fcl_serie[ano - 1],
            negrito=True,
        )

    ctx["referencias"]["modelo"] = referencias


# ---------------------------------------------------------------------------
# Aba 4 — Schedules (WK, PP&E e Divida em blocos verticais)
# ---------------------------------------------------------------------------

# Layout fixo da aba Schedules: colunas B = Ano 0, C..J = ano1..ano8.
# As constantes existem porque Modelo Integrado e Valuation referenciam
# celulas desta aba por formula ANTES de ela ser construida.
LINHA_WK_TITULO = 3
LINHA_WK_CR = 5
LINHA_WK_EST = 6
LINHA_WK_FORN = 7
LINHA_WK_NWC = 8
LINHA_WK_DNWC = 9
LINHA_WK_MODO = 10

LINHA_PPE_TITULO = 12
LINHA_PPE_TAXA = 14
LINHA_PPE_CAPEX_PCT = 15
LINHA_PPE_CAPEX = 16
LINHA_PPE_DA = 17
LINHA_PPE_IMOB = 18

LINHA_DIV_TITULO = 20
LINHA_DIV_KD = 22
LINHA_DIV_CP = 23
LINHA_DIV_LP = 24
LINHA_DIV_BRUTA = 25
LINHA_DIV_SALDO_MEDIO = 26
LINHA_DIV_JUROS = 27
LINHA_DIV_RF = 28
LINHA_DIV_DELTA = 29


def _aba_schedules(wb: Workbook, ctx: dict[str, Any]) -> None:
    """Schedules de WK, PP&E e Divida em blocos verticais com Ano 0."""
    ws = wb.create_sheet("Schedules")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 38
    for coluna in range(2, 11):
        ws.column_dimensions[get_column_letter(coluna)].width = 13

    projecao = ctx["projecao"]
    premissas_ref = ctx["referencias"]["premissas"]
    ano0 = projecao.get("ano0", {})
    parametros = carregar_json(ctx["raiz"] / "config" / "parametros.json")
    vida_util = float(parametros.get("vida_util_ppe_anos", 10))
    taxa_depreciacao = 1.0 / vida_util if vida_util > 0 else 0.0

    escrever_titulo(ws, 1, "SCHEDULES OPERACIONAIS (R$ mil)", 10)
    rotulos = ["Ano 0"] + [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)]

    # ------------------------ Capital de giro ------------------------------
    escrever_titulo(ws, LINHA_WK_TITULO, "CAPITAL DE GIRO (WK)", 10)
    escrever_cabecalho_colunas(ws, LINHA_WK_TITULO + 1, 2, rotulos)

    wk_ano0 = ano0.get("wk", {})
    wk_campos = (
        (LINHA_WK_CR, "contas_receber", "Contas a receber"),
        (LINHA_WK_EST, "estoques", "Estoques"),
        (LINHA_WK_FORN, "fornecedores", "Fornecedores (passivo, negativo)"),
    )
    for linha, campo, rotulo in wk_campos:
        escrever_rotulo(ws, linha, rotulo)
        escrever_numero(ws, linha, 2, wk_ano0.get(campo))
        serie = _serie_anual(projecao, "wk", campo)
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            escrever_numero(ws, linha, 2 + ano, serie[ano - 1])

    escrever_rotulo(ws, LINHA_WK_NWC, "NWC (CR + Estoques + Fornecedores)", True)
    nwc_serie = _serie_anual(projecao, "wk", "nwc")
    escrever_numero(ws, LINHA_WK_NWC, 2, wk_ano0.get("nwc"), negrito=True)
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        formula = (
            f"=SUM({_celula(coluna, LINHA_WK_CR)}:{_celula(coluna, LINHA_WK_FORN)})"
        )
        componentes = [
            _serie_anual(projecao, "wk", campo)[ano - 1]
            for campo in ("contas_receber", "estoques", "fornecedores")
        ]
        valor_python = (
            sum(float(v) for v in componentes)
            if all(v is not None for v in componentes)
            else None
        )
        escrever_calculo(
            ws,
            LINHA_WK_NWC,
            coluna,
            formula,
            valor_python,
            nwc_serie[ano - 1],
            negrito=True,
        )

    escrever_rotulo(ws, LINHA_WK_DNWC, "Delta NWC (positivo = consumo de caixa)")
    dnwc_serie = _serie_anual(projecao, "wk", "delta_nwc")
    nwc_ano0 = wk_ano0.get("nwc")
    nwc_anterior = nwc_ano0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        # Formula: Delta NWC_t = NWC_t - NWC_(t-1). No ano 1 a salvaguarda do
        # motor pode truncar o salto; nesse caso a celula recebe o VALOR.
        formula = (
            f"={_celula(coluna, LINHA_WK_NWC)}-{_celula(coluna - 1, LINHA_WK_NWC)}"
        )
        valor_python = None
        if nwc_anterior is not None and nwc_serie[ano - 1] is not None:
            valor_python = float(nwc_serie[ano - 1]) - float(nwc_anterior)
        escrever_calculo(
            ws,
            LINHA_WK_DNWC,
            coluna,
            formula,
            valor_python,
            dnwc_serie[ano - 1],
        )
        nwc_anterior = nwc_serie[ano - 1]

    escrever_rotulo(ws, LINHA_WK_MODO, "Modo de capital de giro")
    modo_serie = _serie_anual(projecao, "wk", "modo_capital_giro")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        celula = ws.cell(row=LINHA_WK_MODO, column=2 + ano, value=modo_serie[ano - 1])
        celula.font = Font(name=FONTE_TEXTO, size=8, color="FF6B7A90")
        celula.alignment = Alignment(horizontal="center")

    # ----------------------------- PP&E ------------------------------------
    escrever_titulo(ws, LINHA_PPE_TITULO, "PP&E (IMOBILIZADO)", 10)
    escrever_cabecalho_colunas(ws, LINHA_PPE_TITULO + 1, 2, rotulos)

    escrever_rotulo(ws, LINHA_PPE_TAXA, "Taxa de depreciacao (1/vida util)")
    escrever_numero(
        ws,
        LINHA_PPE_TAXA,
        2,
        taxa_depreciacao,
        FORMATO_PERCENTUAL,
        cor_fonte=COR_FONTE_INPUT,
    )

    escrever_rotulo(ws, LINHA_PPE_CAPEX_PCT, "CAPEX / Receita (premissa)")
    capex_pct_serie = _serie_anual(projecao, "ppe", "capex_receita")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        ref_premissa = premissas_ref[f"capex_receita_ano{ano}"]
        escrever_calculo(
            ws,
            LINHA_PPE_CAPEX_PCT,
            2 + ano,
            f"=Premissas!{ref_premissa}",
            capex_pct_serie[ano - 1],
            capex_pct_serie[ano - 1],
            FORMATO_PERCENTUAL,
            cor_fonte=COR_FONTE_LINK,
        )

    escrever_rotulo(ws, LINHA_PPE_CAPEX, "CAPEX (assinado; negativo = saida)")
    capex_serie = _serie_anual(projecao, "ppe", "capex")
    receita_serie = _serie_anual(projecao, "dre", "receita_liquida")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        ref_receita = (
            f"'Modelo Integrado'!"
            f"{_celula(COL_MODELO_PROJ + ano - 1, LINHA_MODELO_RECEITA)}"
        )
        # Formula: CAPEX_t = (CAPEX/Receita)_t x Receita_t.
        formula = f"={_celula(coluna, LINHA_PPE_CAPEX_PCT)}*{ref_receita}"
        valor_python = None
        if capex_pct_serie[ano - 1] is not None and receita_serie[ano - 1] is not None:
            valor_python = float(capex_pct_serie[ano - 1]) * float(
                receita_serie[ano - 1]
            )
        escrever_calculo(
            ws,
            LINHA_PPE_CAPEX,
            coluna,
            formula,
            valor_python,
            capex_serie[ano - 1],
            cor_fonte=COR_FONTE_LINK,
        )

    escrever_rotulo(ws, LINHA_PPE_DA, "D&A do periodo")
    da_serie = _serie_anual(projecao, "ppe", "depreciacao_amortizacao")
    imob_serie = _serie_anual(projecao, "ppe", "imobilizado")
    imob_ano0 = ano0.get("ppe", {}).get("imobilizado")
    escrever_numero(ws, LINHA_PPE_IMOB, 2, imob_ano0)
    imob_anterior = imob_ano0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        ref_taxa = f"$B${LINHA_PPE_TAXA}"
        ref_imob_ant = _celula(coluna - 1, LINHA_PPE_IMOB)
        ref_capex = _celula(coluna, LINHA_PPE_CAPEX)
        # Formula: D&A_t = min(taxa x PP&E_(t-1), max(PP&E_(t-1)+CAPEX_t, 0)).
        formula = f"=MIN({ref_taxa}*{ref_imob_ant},MAX({ref_imob_ant}+{ref_capex},0))"
        valor_python = None
        if imob_anterior is not None and capex_serie[ano - 1] is not None:
            base = max(float(imob_anterior) + float(capex_serie[ano - 1]), 0.0)
            valor_python = max(min(taxa_depreciacao * float(imob_anterior), base), 0.0)
        escrever_calculo(
            ws,
            LINHA_PPE_DA,
            coluna,
            formula,
            valor_python,
            da_serie[ano - 1],
        )
        imob_anterior = imob_serie[ano - 1]

    escrever_rotulo(ws, LINHA_PPE_IMOB, "PP&E final", negrito=True)
    imob_anterior = imob_ano0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        ref_imob_ant = _celula(coluna - 1, LINHA_PPE_IMOB)
        ref_capex = _celula(coluna, LINHA_PPE_CAPEX)
        ref_da = _celula(coluna, LINHA_PPE_DA)
        # Formula: PP&E_t = max(PP&E_(t-1) + CAPEX_t - D&A_t, 0).
        formula = f"=MAX({ref_imob_ant}+{ref_capex}-{ref_da},0)"
        valor_python = None
        if (
            imob_anterior is not None
            and capex_serie[ano - 1] is not None
            and da_serie[ano - 1] is not None
        ):
            valor_python = max(
                float(imob_anterior)
                + float(capex_serie[ano - 1])
                - float(da_serie[ano - 1]),
                0.0,
            )
        escrever_calculo(
            ws,
            LINHA_PPE_IMOB,
            coluna,
            formula,
            valor_python,
            imob_serie[ano - 1],
            negrito=True,
        )
        imob_anterior = imob_serie[ano - 1]

    # ----------------------------- Divida -----------------------------------
    escrever_titulo(
        ws,
        LINHA_DIV_TITULO,
        "DIVIDA (politica v1: divida bruta constante, sem amortizacao)",
        10,
    )
    escrever_cabecalho_colunas(ws, LINHA_DIV_TITULO + 1, 2, rotulos)

    escrever_rotulo(ws, LINHA_DIV_KD, "Kd — custo da divida (premissa)")
    kd_premissa = ctx["premissas"].get("custo_divida_kd")
    escrever_calculo(
        ws,
        LINHA_DIV_KD,
        2,
        f"=Premissas!{premissas_ref['custo_divida_kd']}",
        kd_premissa,
        kd_premissa,
        FORMATO_PERCENTUAL_2,
        cor_fonte=COR_FONTE_LINK,
    )

    divida_ano0 = ano0.get("divida", {})
    div_campos = (
        (LINHA_DIV_CP, "divida_curto_prazo", "Divida de curto prazo"),
        (LINHA_DIV_LP, "divida_longo_prazo", "Divida de longo prazo"),
    )
    for linha, campo, rotulo in div_campos:
        escrever_rotulo(ws, linha, rotulo)
        escrever_numero(ws, linha, 2, divida_ano0.get(campo))
        serie = _serie_anual(projecao, "divida", campo)
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            escrever_numero(ws, linha, 2 + ano, serie[ano - 1])

    escrever_rotulo(ws, LINHA_DIV_BRUTA, "Divida bruta", negrito=True)
    bruta_serie = _serie_anual(projecao, "divida", "divida_bruta")
    escrever_numero(
        ws, LINHA_DIV_BRUTA, 2, divida_ano0.get("divida_bruta"), negrito=True
    )
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        formula = f"={_celula(coluna, LINHA_DIV_CP)}+{_celula(coluna, LINHA_DIV_LP)}"
        componentes = [
            _serie_anual(projecao, "divida", campo)[ano - 1]
            for campo in ("divida_curto_prazo", "divida_longo_prazo")
        ]
        valor_python = (
            sum(float(v) for v in componentes)
            if all(v is not None for v in componentes)
            else None
        )
        escrever_calculo(
            ws,
            LINHA_DIV_BRUTA,
            coluna,
            formula,
            valor_python,
            bruta_serie[ano - 1],
            negrito=True,
        )

    escrever_rotulo(ws, LINHA_DIV_SALDO_MEDIO, "Saldo medio da divida")
    saldo_serie = _serie_anual(projecao, "divida", "saldo_medio_divida")
    bruta_anterior = divida_ano0.get("divida_bruta")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        # Formula: saldo medio = (divida bruta_t + divida bruta_(t-1)) / 2.
        formula = (
            f"=({_celula(coluna, LINHA_DIV_BRUTA)}"
            f"+{_celula(coluna - 1, LINHA_DIV_BRUTA)})/2"
        )
        valor_python = None
        if bruta_anterior is not None and bruta_serie[ano - 1] is not None:
            valor_python = (float(bruta_serie[ano - 1]) + float(bruta_anterior)) / 2
        escrever_calculo(
            ws,
            LINHA_DIV_SALDO_MEDIO,
            coluna,
            formula,
            valor_python,
            saldo_serie[ano - 1],
        )
        bruta_anterior = bruta_serie[ano - 1]

    escrever_rotulo(ws, LINHA_DIV_JUROS, "Juros (Kd x saldo medio)")
    juros_serie = _serie_anual(projecao, "divida", "juros")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        formula = f"=$B${LINHA_DIV_KD}*{_celula(coluna, LINHA_DIV_SALDO_MEDIO)}"
        valor_python = None
        if kd_premissa is not None and saldo_serie[ano - 1] is not None:
            valor_python = float(kd_premissa) * float(saldo_serie[ano - 1])
        escrever_calculo(
            ws,
            LINHA_DIV_JUROS,
            coluna,
            formula,
            valor_python,
            juros_serie[ano - 1],
        )

    escrever_rotulo(ws, LINHA_DIV_RF, "Resultado financeiro (= -juros)")
    rf_serie = _serie_anual(projecao, "divida", "resultado_financeiro")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 2 + ano
        formula = f"=-{_celula(coluna, LINHA_DIV_JUROS)}"
        valor_python = (
            -float(juros_serie[ano - 1]) if juros_serie[ano - 1] is not None else None
        )
        escrever_calculo(
            ws,
            LINHA_DIV_RF,
            coluna,
            formula,
            valor_python,
            rf_serie[ano - 1],
        )

    escrever_rotulo(ws, LINHA_DIV_DELTA, "Delta divida (politica v1 = 0)")
    delta_serie = _serie_anual(projecao, "divida", "delta_divida")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        escrever_numero(ws, LINHA_DIV_DELTA, 2 + ano, delta_serie[ano - 1])


# Linha da receita na aba Modelo Integrado (layout fixo: titulo 1, DRE em 3,
# cabecalho 4, receita 5). Usada pelos schedules que referenciam a receita.
LINHA_MODELO_RECEITA = 5


# ---------------------------------------------------------------------------
# Aba 5 — Valuation (FCFF, WACC, VT, bridge, ROIC/ROIIC + PNGs)
# ---------------------------------------------------------------------------


def _aba_valuation(wb: Workbook, ctx: dict[str, Any]) -> None:
    """FCFF 8 anos, ROIC/ROIIC, decomposicao do WACC, VT e bridge."""
    ws = wb.create_sheet("Valuation")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 34
    for coluna in range(2, 11):
        ws.column_dimensions[get_column_letter(coluna)].width = 13
    ws.column_dimensions["D"].width = 30
    ws.column_dimensions["G"].width = 34

    projecao = ctx["projecao"]
    ticker = ctx["ticker"]
    wacc = projecao["wacc"]
    valor_terminal = projecao["valor_terminal"]
    ev_equity = projecao["ev_equity"]

    escrever_titulo(ws, 1, "VALUATION — FCFF, WACC, VALOR TERMINAL E BRIDGE", 12)

    # ------------------------- Bloco FCFF ----------------------------------
    linha = 3
    escrever_titulo(ws, linha, "FCFF PROJETADO (R$ mil)", 12)
    linha += 1
    escrever_cabecalho_colunas(
        ws, linha, 2, [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)]
    )
    linha += 1

    linha_ebit = linha
    escrever_rotulo(ws, linha, "EBIT (Modelo Integrado)")
    ebit_serie = _serie_anual(projecao, "dre", "ebit")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        ref = (
            f"'Modelo Integrado'!"
            f"{_celula(COL_MODELO_PROJ + ano - 1, LINHA_MODELO_EBIT)}"
        )
        escrever_calculo(
            ws,
            linha,
            1 + ano,
            f"={ref}",
            ebit_serie[ano - 1],
            ebit_serie[ano - 1],
            cor_fonte=COR_FONTE_LINK,
        )
    linha += 1

    linha_aliquota = linha
    escrever_rotulo(ws, linha, "Aliquota do NOPAT")
    aliquota_serie = _serie_anual(projecao, "fcff", "aliquota_ir_nopat")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        escrever_numero(ws, linha, 1 + ano, aliquota_serie[ano - 1], FORMATO_PERCENTUAL)
    linha += 1

    linha_nopat = linha
    escrever_rotulo(ws, linha, "NOPAT = EBIT x (1 - t)", negrito=True)
    nopat_serie = _serie_anual(projecao, "fcff", "nopat")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 1 + ano
        formula = (
            f"={_celula(coluna, linha_ebit)}*(1-{_celula(coluna, linha_aliquota)})"
        )
        valor_python = None
        if ebit_serie[ano - 1] is not None and aliquota_serie[ano - 1] is not None:
            valor_python = float(ebit_serie[ano - 1]) * (
                1 - float(aliquota_serie[ano - 1])
            )
        escrever_calculo(
            ws,
            linha,
            coluna,
            formula,
            valor_python,
            nopat_serie[ano - 1],
            negrito=True,
        )
    linha += 1

    componentes_fcff = (
        ("depreciacao_amortizacao", "(+) D&A", LINHA_PPE_DA, 1.0),
        ("delta_nwc", "(-) Delta NWC", LINHA_WK_DNWC, 1.0),
        ("capex_saida_caixa", "(-) CAPEX (saida)", LINHA_PPE_CAPEX, -1.0),
    )
    linhas_componentes: dict[str, int] = {}
    for campo, rotulo, linha_schedule, sinal in componentes_fcff:
        escrever_rotulo(ws, linha, rotulo)
        serie = _serie_anual(projecao, "fcff", campo)
        for ano in range(1, HORIZONTE_PROJECAO + 1):
            ref = f"Schedules!{_celula(2 + ano, linha_schedule)}"
            formula = f"={ref}" if sinal > 0 else f"=-{ref}"
            valor_base = (
                _serie_anual(projecao, "ppe", "capex")[ano - 1]
                if campo == "capex_saida_caixa"
                else serie[ano - 1]
            )
            valor_python = None
            if valor_base is not None:
                valor_python = sinal * float(valor_base)
                if campo != "capex_saida_caixa":
                    valor_python = float(valor_base)
            escrever_calculo(
                ws,
                linha,
                1 + ano,
                formula,
                valor_python,
                serie[ano - 1],
                cor_fonte=COR_FONTE_LINK,
            )
        linhas_componentes[campo] = linha
        linha += 1

    linha_fcff = linha
    escrever_rotulo(ws, linha, "FCFF = NOPAT + D&A - dNWC - CAPEX", negrito=True)
    fcff_serie = _serie_anual(projecao, "fcff", "fcff")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 1 + ano
        formula = (
            f"={_celula(coluna, linha_nopat)}"
            f"+{_celula(coluna, linhas_componentes['depreciacao_amortizacao'])}"
            f"-{_celula(coluna, linhas_componentes['delta_nwc'])}"
            f"-{_celula(coluna, linhas_componentes['capex_saida_caixa'])}"
        )
        componentes = [
            nopat_serie[ano - 1],
            _serie_anual(projecao, "fcff", "depreciacao_amortizacao")[ano - 1],
            _serie_anual(projecao, "fcff", "delta_nwc")[ano - 1],
            _serie_anual(projecao, "fcff", "capex_saida_caixa")[ano - 1],
        ]
        valor_python = None
        if all(valor is not None for valor in componentes):
            nopat_v, da_v, dnwc_v, capex_v = (float(v) for v in componentes)
            valor_python = nopat_v + da_v - dnwc_v - capex_v
        escrever_calculo(
            ws,
            linha,
            coluna,
            formula,
            valor_python,
            fcff_serie[ano - 1],
            negrito=True,
        )
    linha += 1

    linha_fator = linha
    escrever_rotulo(ws, linha, "Fator de desconto 1/(1+WACC)^t")
    wacc_valor = wacc.get("wacc")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 1 + ano
        formula = f"=1/(1+WACC)^{ano}"
        valor_python = (
            1.0 / (1.0 + float(wacc_valor)) ** ano if wacc_valor is not None else None
        )
        escrever_calculo(
            ws,
            linha,
            coluna,
            formula,
            valor_python,
            valor_python,
            "0.0000",
        )
    linha += 1

    linha_vp = linha
    escrever_rotulo(ws, linha, "VP(FCFF)")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        coluna = 1 + ano
        formula = f"={_celula(coluna, linha_fcff)}*{_celula(coluna, linha_fator)}"
        valor_python = None
        if fcff_serie[ano - 1] is not None and wacc_valor is not None:
            valor_python = float(fcff_serie[ano - 1]) / (
                (1.0 + float(wacc_valor)) ** ano
            )
        escrever_calculo(ws, linha, coluna, formula, valor_python, valor_python)
    linha += 1

    escrever_rotulo(ws, linha, "ROIC (NOPAT / Capital investido)")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        escrever_numero(
            ws,
            linha,
            1 + ano,
            _serie_anual(projecao, "fcff", "roic")[ano - 1],
            FORMATO_PERCENTUAL,
        )
    linha += 1

    escrever_rotulo(ws, linha, "ROIIC (dNOPAT_t / dIC_(t-1))")
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        valor = _serie_anual(projecao, "fcff", "roiic")[ano - 1]
        escrever_numero(ws, linha, 1 + ano, valor, FORMATO_PERCENTUAL)
    linha += 2

    # ---------------- Decomposicao do WACC + VT + bridge --------------------
    linha_blocos = linha
    escrever_titulo(ws, linha_blocos, "DECOMPOSICAO DO WACC", 2)
    escrever_titulo_bloco(ws, linha_blocos, 4, 5, "VALOR TERMINAL (GORDON)")
    escrever_titulo_bloco(ws, linha_blocos, 7, 8, "BRIDGE EV -> EQUITY -> TARGET")

    componentes_wacc: tuple[tuple[str, str, str, Any], ...] = (
        ("rf_usd", "Rf USD (^TNX)", FORMATO_PERCENTUAL_2, None),
        ("beta_desalavancado", "Beta desalavancado", "0.0000", None),
        ("divida_sobre_equity", "D/E medio (anos 1-8)", "0.0000", None),
        ("beta_realavancado", "Beta re-alavancado (Hamada)", "0.0000", "hamada"),
        ("erp_eua", "ERP EUA", FORMATO_PERCENTUAL_2, None),
        ("crp_brasil", "CRP Brasil", FORMATO_PERCENTUAL_2, None),
        ("ke_usd", "Ke USD", FORMATO_PERCENTUAL_2, "ke_usd"),
        ("ipca", "IPCA longo prazo", FORMATO_PERCENTUAL_2, None),
        ("cpi_eua", "CPI EUA longo prazo", FORMATO_PERCENTUAL_2, None),
        ("ke_brl", "Ke BRL", FORMATO_PERCENTUAL_2, "ke_brl"),
        ("kd_historico", "Kd historico", FORMATO_PERCENTUAL_2, None),
        ("aliquota_ir", "Aliquota IR (escudo fiscal)", FORMATO_PERCENTUAL_2, None),
        ("kd_liquido", "Kd liquido", FORMATO_PERCENTUAL_2, "kd_liquido"),
        ("peso_equity", "Peso Equity (E/V)", FORMATO_PERCENTUAL_2, None),
        ("peso_divida", "Peso Divida (D/V)", FORMATO_PERCENTUAL_2, None),
        ("wacc", "WACC", FORMATO_PERCENTUAL_2, "wacc"),
    )
    # Mapa de linhas pre-computado: formulas como Hamada referenciam
    # componentes que aparecem DEPOIS na tabela (ex.: aliquota do IR).
    linhas_wacc: dict[str, int] = {
        campo: linha_blocos + 1 + indice
        for indice, (campo, _, _, _) in enumerate(componentes_wacc)
    }
    linha = linha_blocos + 1
    for campo, rotulo, formato, tipo_formula in componentes_wacc:
        escrever_rotulo(ws, linha, rotulo, negrito=campo == "wacc")
        valor_motor = wacc.get(campo)
        cor = COR_FONTE_INPUT if tipo_formula is None else COR_FONTE_FORMULA
        if tipo_formula is None:
            escrever_numero(ws, linha, 2, valor_motor, formato, cor_fonte=cor)
        else:
            formula, valor_python = _formula_wacc(tipo_formula, linhas_wacc, wacc)
            escrever_calculo(
                ws,
                linha,
                2,
                formula,
                valor_python,
                valor_motor,
                formato,
                negrito=campo == "wacc",
            )
        linhas_wacc[campo] = linha
        linha += 1

    # Nomes definidos para WACC e g: permitem Data Tables nativas no Excel.
    referencia_wacc = f"Valuation!$B${linhas_wacc['wacc']}"
    wb.defined_names["WACC"] = DefinedName("WACC", attr_text=referencia_wacc)

    linha_vt_ini = linha_blocos + 1
    vt_linhas: tuple[tuple[str, str, str], ...] = (
        ("g", "g — crescimento na perpetuidade", FORMATO_PERCENTUAL_2),
        ("fcff_ano8", "FCFF ano 8", FORMATO_MILHAR),
        ("nopat_ano8", "NOPAT ano 8 (base alternativa)", FORMATO_MILHAR),
        ("base_vt", "Base utilizada no VT", ""),
        ("vt_bruto", "VT bruto = base x (1+g)/(WACC-g)", FORMATO_MILHAR),
        ("vp_vt", "VP(VT) = VT/(1+WACC)^8", FORMATO_MILHAR),
        ("pct_ev_perpetuidade", "% do EV na perpetuidade", FORMATO_PERCENTUAL),
        ("multiplo_saida_implicito", "Multiplo de saida implicito", FORMATO_MULTIPLO),
    )
    linhas_vt: dict[str, int] = {}
    linha_atual = linha_vt_ini
    for campo, rotulo, formato in vt_linhas:
        celula_rotulo = ws.cell(row=linha_atual, column=4, value=rotulo)
        celula_rotulo.font = Font(name=FONTE_TEXTO, size=10)
        valor_motor = valor_terminal.get(campo)
        if campo == "base_vt":
            celula = ws.cell(row=linha_atual, column=5, value=str(valor_motor))
            celula.font = Font(name=FONTE_NUMERO, size=10)
        elif campo == "g":
            escrever_numero(
                ws,
                linha_atual,
                5,
                valor_motor,
                formato,
                cor_fonte=COR_FONTE_INPUT,
            )
        elif campo == "vt_bruto":
            ref_base = f"E{linhas_vt['fcff_ano8']}"
            if valor_terminal.get("base_vt") == "nopat_normalizado_ano8":
                ref_base = f"E{linhas_vt['nopat_ano8']}"
            ref_g = f"E{linhas_vt['g']}"
            formula = f"={ref_base}*(1+{ref_g})/(WACC-{ref_g})"
            base = valor_terminal.get("base_utilizada")
            g_valor = valor_terminal.get("g")
            valor_python = None
            if None not in (base, g_valor, wacc_valor):
                valor_python = (
                    float(base)
                    * (1 + float(g_valor))
                    / (float(wacc_valor) - float(g_valor))
                )
            escrever_calculo(
                ws, linha_atual, 5, formula, valor_python, valor_motor, formato
            )
        elif campo == "vp_vt":
            formula = f"=E{linhas_vt['vt_bruto']}/(1+WACC)^{HORIZONTE_PROJECAO}"
            vt_bruto = valor_terminal.get("vt_bruto")
            valor_python = None
            if vt_bruto is not None and wacc_valor is not None:
                valor_python = float(vt_bruto) / (
                    (1 + float(wacc_valor)) ** HORIZONTE_PROJECAO
                )
            escrever_calculo(
                ws, linha_atual, 5, formula, valor_python, valor_motor, formato
            )
        elif campo == "fcff_ano8":
            formula = f"={_celula(1 + HORIZONTE_PROJECAO, linha_fcff)}"
            escrever_calculo(
                ws, linha_atual, 5, formula, valor_motor, valor_motor, formato
            )
        else:
            escrever_numero(ws, linha_atual, 5, valor_motor, formato)
        linhas_vt[campo] = linha_atual
        linha_atual += 1

    wb.defined_names["g_perpetuidade"] = DefinedName(
        "g_perpetuidade", attr_text=f"Valuation!$E${linhas_vt['g']}"
    )

    # Bridge: EV -> Equity -> Target Price, com ajustes assinados.
    ajustes = ev_equity.get("ajustes_bridge", {})
    linha_atual = linha_vt_ini
    linhas_bridge: dict[str, int] = {}

    def _linha_bridge(
        chave: str,
        rotulo: str,
        valor: Any,
        formato: str = FORMATO_MILHAR,
        formula: str | None = None,
        valor_python: Any = None,
        negrito: bool = False,
    ) -> None:
        nonlocal linha_atual
        celula_rotulo = ws.cell(row=linha_atual, column=7, value=rotulo)
        celula_rotulo.font = Font(name=FONTE_TEXTO, size=10, bold=negrito)
        if formula is None:
            escrever_numero(ws, linha_atual, 8, valor, formato, negrito=negrito)
        else:
            escrever_calculo(
                ws,
                linha_atual,
                8,
                formula,
                valor_python,
                valor,
                formato,
                negrito=negrito,
            )
        linhas_bridge[chave] = linha_atual
        linha_atual += 1

    soma_vp = ev_equity.get("soma_vp_fcff")
    _linha_bridge(
        "soma_vp",
        "Soma VP(FCFF anos 1-8)",
        soma_vp,
        formula=f"=SUM({_celula(2, linha_vp)}:{_celula(9, linha_vp)})",
        valor_python=soma_vp,
    )
    _linha_bridge(
        "vp_vt",
        "(+) VP(Valor Terminal)",
        ev_equity.get("vp_vt"),
        formula=f"=E{linhas_vt['vp_vt']}",
        valor_python=ev_equity.get("vp_vt"),
    )
    ev_valor = ev_equity.get("ev")
    valor_python_ev = None
    if soma_vp is not None and ev_equity.get("vp_vt") is not None:
        valor_python_ev = float(soma_vp) + float(ev_equity["vp_vt"])
    _linha_bridge(
        "ev",
        "= Enterprise Value (EV)",
        ev_valor,
        formula=(f"=H{linhas_bridge['soma_vp']}+H{linhas_bridge['vp_vt']}"),
        valor_python=valor_python_ev,
        negrito=True,
    )
    ajustes_bridge = (
        ("divida_bruta", "(-) Divida bruta", -1.0),
        ("caixa_equivalentes", "(+) Caixa e equivalentes", 1.0),
        ("aplicacoes_financeiras", "(+) Aplicacoes financeiras", 1.0),
        ("participacoes_minoritarias", "(-) Minoritarios", -1.0),
        ("investimentos_coligadas", "(+) Coligadas", 1.0),
        ("ativos_nao_operacionais", "(+) Ativos nao operacionais", 1.0),
    )
    for campo, rotulo, sinal in ajustes_bridge:
        bruto = ajustes.get(campo)
        assinado = sinal * float(bruto) if bruto is not None else None
        _linha_bridge(campo, rotulo, assinado)

    equity = ev_equity.get("equity_value")
    valor_python_eq = None
    if ev_valor is not None and all(
        ajustes.get(campo) is not None for campo, _, _ in ajustes_bridge
    ):
        valor_python_eq = float(ev_valor) + sum(
            sinal * float(ajustes[campo]) for campo, _, sinal in ajustes_bridge
        )
    primeiro_ajuste = linhas_bridge["divida_bruta"]
    ultimo_ajuste = linhas_bridge["ativos_nao_operacionais"]
    _linha_bridge(
        "equity",
        "= Equity Value",
        equity,
        formula=(f"=H{linhas_bridge['ev']}+SUM(H{primeiro_ajuste}:H{ultimo_ajuste})"),
        valor_python=valor_python_eq,
        negrito=True,
    )
    _linha_bridge(
        "fator_escala",
        "Fator de escala da moeda (CVM em mil)",
        ev_equity.get("fator_escala_moeda"),
        formato="#,##0",
    )
    _linha_bridge(
        "acoes",
        "Acoes fully diluted",
        ev_equity.get("acoes_fully_diluted"),
        formato="#,##0",
    )
    target = ev_equity.get("target_price")
    valor_python_target = None
    if (
        equity is not None
        and ev_equity.get("fator_escala_moeda") is not None
        and ev_equity.get("acoes_fully_diluted")
    ):
        valor_python_target = (
            float(equity)
            * float(ev_equity["fator_escala_moeda"])
            / float(ev_equity["acoes_fully_diluted"])
        )
    _linha_bridge(
        "target",
        "TARGET PRICE (R$/acao)",
        target,
        formato=FORMATO_PRECO,
        formula=(
            f"=H{linhas_bridge['equity']}*H{linhas_bridge['fator_escala']}"
            f"/H{linhas_bridge['acoes']}"
        ),
        valor_python=valor_python_target,
        negrito=True,
    )
    preco = ev_equity.get("preco_atual")
    _linha_bridge("preco", "Preco atual", preco, formato=FORMATO_PRECO)
    upside = ev_equity.get("upside")
    valor_python_upside = None
    if target is not None and preco:
        valor_python_upside = float(target) / float(preco) - 1
    _linha_bridge(
        "upside",
        "Upside",
        upside,
        formato=FORMATO_PERCENTUAL,
        formula=(f"=H{linhas_bridge['target']}/H{linhas_bridge['preco']}-1"),
        valor_python=valor_python_upside,
        negrito=True,
    )
    recomendacao = str(ev_equity.get("recomendacao", "n/d"))
    celula_rotulo = ws.cell(row=linha_atual, column=7, value="Recomendacao")
    celula_rotulo.font = Font(name=FONTE_TEXTO, size=10, bold=True)
    celula_rec = ws.cell(row=linha_atual, column=8, value=recomendacao)
    cor_rec = (
        COR_VERDE_FUNDO
        if recomendacao == "COMPRA"
        else COR_VERMELHO_FUNDO if recomendacao == "VENDA" else COR_AMARELO_FUNDO
    )
    celula_rec.font = Font(name=FONTE_NUMERO, size=11, bold=True, color=cor_rec)
    linha_atual += 1

    # Graficos institucionais embutidos como PNG (Etapa 5 do ROTEIRO).
    linha_imagens = max(linha_atual, linhas_wacc["wacc"] + 2) + 2
    ws.cell(
        row=linha_imagens - 1,
        column=1,
        value="Football Field e Waterfall (PNG gerados pelo motor):",
    ).font = Font(name=FONTE_TEXTO, italic=True, size=9)
    _inserir_png(ws, ctx["raiz"], ticker, "football_field", f"A{linha_imagens}")
    _inserir_png(ws, ctx["raiz"], ticker, "waterfall_ev", f"A{linha_imagens + 25}")


def escrever_titulo_bloco(
    ws: Worksheet,
    linha: int,
    coluna_inicial: int,
    coluna_final: int,
    texto: str,
) -> None:
    """Titulo navy de um bloco que nao comeca na coluna A."""
    for coluna in range(coluna_inicial, coluna_final + 1):
        ws.cell(row=linha, column=coluna).fill = PatternFill(
            "solid", start_color=COR_NAVY
        )
    celula = ws.cell(row=linha, column=coluna_inicial, value=texto)
    celula.font = Font(name=FONTE_TEXTO, bold=True, size=11, color=COR_BRANCO)


def _formula_wacc(
    tipo: str,
    linhas: dict[str, int],
    wacc: dict[str, Any],
) -> tuple[str, float | None]:
    """Formula nativa e valor recalculado de um componente do WACC."""

    def _b(campo: str) -> str:
        return f"B{linhas[campo]}"

    def _v(campo: str) -> float | None:
        valor = wacc.get(campo)
        return float(valor) if valor is not None else None

    if tipo == "hamada":
        # Formula: beta_L = beta_U x (1 + (1 - t) x D/E).
        formula = (
            f"={_b('beta_desalavancado')}*(1+(1-{_b('aliquota_ir')})"
            f"*{_b('divida_sobre_equity')})"
        )
        beta_u = _v("beta_desalavancado")
        aliquota = _v("aliquota_ir")
        de = _v("divida_sobre_equity")
        valor = None
        if None not in (beta_u, aliquota, de):
            valor = beta_u * (1 + (1 - aliquota) * de)
        return formula, valor
    if tipo == "ke_usd":
        # Formula: Ke_USD = Rf + beta_L x (ERP + CRP).
        formula = (
            f"={_b('rf_usd')}+{_b('beta_realavancado')}"
            f"*({_b('erp_eua')}+{_b('crp_brasil')})"
        )
        rf = _v("rf_usd")
        beta_l = _v("beta_realavancado")
        erp = _v("erp_eua")
        crp = _v("crp_brasil")
        valor = None
        if None not in (rf, beta_l, erp, crp):
            valor = rf + beta_l * (erp + crp)
        return formula, valor
    if tipo == "ke_brl":
        # Formula: Ke_BRL = (1 + Ke_USD) x (1 + IPCA) / (1 + CPI_EUA) - 1.
        formula = f"=(1+{_b('ke_usd')})*(1+{_b('ipca')})/(1+{_b('cpi_eua')})-1"
        ke_usd = _v("ke_usd")
        ipca = _v("ipca")
        cpi = _v("cpi_eua")
        valor = None
        if None not in (ke_usd, ipca, cpi):
            valor = (1 + ke_usd) * (1 + ipca) / (1 + cpi) - 1
        return formula, valor
    if tipo == "kd_liquido":
        # Formula: Kd liquido = Kd x (1 - t).
        formula = f"={_b('kd_historico')}*(1-{_b('aliquota_ir')})"
        kd = _v("kd_historico")
        aliquota = _v("aliquota_ir")
        valor = None
        if None not in (kd, aliquota):
            valor = kd * (1 - aliquota)
        return formula, valor
    # Formula: WACC = E/V x Ke_BRL + D/V x Kd x (1 - t).
    formula = (
        f"={_b('peso_equity')}*{_b('ke_brl')}"
        f"+{_b('peso_divida')}*{_b('kd_liquido')}"
    )
    peso_e = _v("peso_equity")
    ke_brl = _v("ke_brl")
    peso_d = _v("peso_divida")
    kd_liquido = _v("kd_liquido")
    valor = None
    if None not in (peso_e, ke_brl, peso_d, kd_liquido):
        valor = peso_e * ke_brl + peso_d * kd_liquido
    return formula, valor


# Linha do EBIT na aba Modelo Integrado (layout: receita 5, crescimento 6,
# ebitda 7, margem 8, d&a 9, ebit 10).
LINHA_MODELO_EBIT = 10


# ---------------------------------------------------------------------------
# Aba 6 — Sensibilidades (3 tabelas com formatacao condicional)
# ---------------------------------------------------------------------------


def _grade_cenarios(
    projecao: dict[str, Any],
    valores_linha: list[float],
    valores_coluna: list[float],
    calcular: Callable[[float, float], dict[str, Any] | None],
) -> list[list[float | None]]:
    """Varre a grade de cenarios devolvendo a matriz de target price."""
    matriz: list[list[float | None]] = []
    for valor_linha in valores_linha:
        linha_atual: list[float | None] = []
        for valor_coluna in valores_coluna:
            cenario = calcular(valor_linha, valor_coluna)
            linha_atual.append(cenario["target_price"] if cenario is not None else None)
        matriz.append(linha_atual)
    return matriz


def _escrever_tabela_sensibilidade(
    ws: Worksheet,
    linha_inicial: int,
    titulo: str,
    rotulo_eixo_linha: str,
    rotulos_linha: list[str],
    rotulos_coluna: list[str],
    matriz: list[list[float | None]],
    preco_atual: float,
    indice_base: tuple[int, int] | None,
) -> int:
    """Escreve uma tabela de sensibilidade com formatacao condicional.

    Verde/vermelho seguem os MESMOS limiares de recomendacao do motor
    (COMPRA > +20%, VENDA < -5%); o caso base recebe borda dourada.
    Devolve a linha seguinte ao fim da tabela.
    """
    total_colunas = len(rotulos_coluna) + 1
    escrever_titulo(ws, linha_inicial, titulo, total_colunas)
    linha_cabecalho = linha_inicial + 1
    ws.cell(row=linha_cabecalho, column=1, value=rotulo_eixo_linha).font = Font(
        name=FONTE_TEXTO, bold=True, size=9, color=COR_BRANCO
    )
    ws.cell(row=linha_cabecalho, column=1).fill = PatternFill(
        "solid", start_color=COR_AZUL_ANCORA
    )
    escrever_cabecalho_colunas(ws, linha_cabecalho, 2, rotulos_coluna)

    for indice_linha, rotulo in enumerate(rotulos_linha):
        linha = linha_cabecalho + 1 + indice_linha
        celula_rotulo = ws.cell(row=linha, column=1, value=rotulo)
        celula_rotulo.font = Font(name=FONTE_NUMERO, size=10, bold=True)
        celula_rotulo.alignment = Alignment(horizontal="center")
        for indice_coluna in range(len(rotulos_coluna)):
            valor = matriz[indice_linha][indice_coluna]
            celula = ws.cell(row=linha, column=2 + indice_coluna)
            celula.border = BORDA_FINA
            if valor is None:
                # Celula bloqueada pelo Gordon (g >= WACC).
                celula.value = "n/d"
                celula.font = Font(name=FONTE_NUMERO, size=10, color=COR_CINZA_ND)
                celula.alignment = Alignment(horizontal="center")
            else:
                celula.value = float(valor)
                celula.number_format = FORMATO_PRECO
                celula.font = Font(name=FONTE_NUMERO, size=10)
            if indice_base is not None and (
                (indice_linha, indice_coluna) == indice_base
            ):
                celula.border = BORDA_CASO_BASE
                celula.font = Font(name=FONTE_NUMERO, size=10, bold=True)

    # Formatacao condicional pelos limiares de recomendacao do motor.
    # Nos estilos diferenciais do Excel o preenchimento solido usa start E
    # end color; sem o end_color a regra existe mas pinta de branco.
    def _fill_condicional(cor: str) -> PatternFill:
        return PatternFill(start_color=cor, end_color=cor, fill_type="solid")

    faixa = (
        f"{_celula(2, linha_cabecalho + 1)}:"
        f"{_celula(1 + len(rotulos_coluna), linha_cabecalho + len(rotulos_linha))}"
    )
    limite_compra = preco_atual * (1 + LIMITE_COMPRA)
    limite_venda = preco_atual * (1 + LIMITE_VENDA)
    ws.conditional_formatting.add(
        faixa,
        CellIsRule(
            operator="greaterThan",
            formula=[f"{limite_compra}"],
            fill=_fill_condicional("FFCDEFD8"),
        ),
    )
    ws.conditional_formatting.add(
        faixa,
        CellIsRule(
            operator="lessThan",
            formula=[f"{limite_venda}"],
            fill=_fill_condicional("FFF5D2D2"),
        ),
    )
    ws.conditional_formatting.add(
        faixa,
        CellIsRule(
            operator="between",
            formula=[f"{limite_venda}", f"{limite_compra}"],
            fill=_fill_condicional("FFFBEED2"),
        ),
    )
    return linha_cabecalho + len(rotulos_linha) + 2


def _rotulo_pp(passo: float) -> str:
    """Rotulo de delta em pontos percentuais (base quando zero)."""
    return "base" if passo == 0 else f"{passo * 100:+.1f}pp"


def _rotulo_fator(fator: float) -> str:
    """Rotulo de fator multiplicativo de intensidade (base quando 1)."""
    return "base" if fator == 1.0 else f"{fator:.2f}x"


def _aba_sensibilidades(wb: Workbook, ctx: dict[str, Any]) -> None:
    """As 3 tabelas de sensibilidade com caso base destacado."""
    ws = wb.create_sheet("Sensibilidades")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 16
    for coluna in range(2, 10):
        ws.column_dimensions[get_column_letter(coluna)].width = 13

    projecao = ctx["projecao"]
    parametros = carregar_json(ctx["raiz"] / "config" / "parametros.json")
    sensibilidade = parametros.get("sensibilidade", {})
    passos_wacc = [float(p) for p in sensibilidade.get("wacc_passos_pp", [])]
    passos_g = [float(p) for p in sensibilidade.get("g_passos_pp", [])]
    passos_crescimento = [
        float(p) for p in sensibilidade.get("crescimento_passos_pp", [])
    ]
    passos_margem = [float(p) for p in sensibilidade.get("margem_passos_pp", [])]
    fatores = [float(f) for f in sensibilidade.get("fatores_intensidade", [])]

    wacc_base = float(projecao["wacc"]["wacc"])
    g_base = float(projecao["valor_terminal"]["g"])
    preco_atual = float(projecao["ev_equity"].get("preco_atual", 0.0))
    target_base = float(projecao["ev_equity"]["target_price"])

    legenda = (
        f"Caso base: WACC {wacc_base * 100:.2f}% | g {g_base * 100:.2f}% | "
        f"target R$ {target_base:.2f}. Verde = COMPRA (upside > +20%), "
        "amarelo = NEUTRO, vermelho = VENDA (downside < -5%); "
        "caso base com borda dourada; n/d = celula bloqueada (g >= WACC)."
    )
    ws.cell(row=1, column=1, value=legenda).font = Font(
        name=FONTE_TEXTO, italic=True, size=9
    )

    # Tabela 1 — WACC x g.
    matriz_wacc_g = _grade_cenarios(
        projecao,
        passos_g,
        passos_wacc,
        lambda passo_g, passo_wacc: recalcular_cenario(
            projecao, delta_wacc=passo_wacc, delta_g=passo_g
        ),
    )
    indice_base = None
    if 0.0 in passos_g and 0.0 in passos_wacc:
        indice_base = (passos_g.index(0.0), passos_wacc.index(0.0))
    linha = _escrever_tabela_sensibilidade(
        ws,
        3,
        "TABELA 1 — TARGET PRICE: WACC x g (perpetuidade)",
        "g \\ WACC",
        [f"{(g_base + passo) * 100:.2f}%" for passo in passos_g],
        [f"{(wacc_base + passo) * 100:.2f}%" for passo in passos_wacc],
        matriz_wacc_g,
        preco_atual,
        indice_base,
    )

    # Tabela 2 — Delta crescimento x Delta margem (pp, aplicados aos 8 anos).
    matriz_receita_margem = _grade_cenarios(
        projecao,
        passos_margem,
        passos_crescimento,
        lambda passo_margem, passo_crescimento: recalcular_cenario(
            projecao,
            delta_crescimento_pp=passo_crescimento,
            delta_margem_pp=passo_margem,
        ),
    )
    indice_base = None
    if 0.0 in passos_margem and 0.0 in passos_crescimento:
        indice_base = (passos_margem.index(0.0), passos_crescimento.index(0.0))
    linha = _escrever_tabela_sensibilidade(
        ws,
        linha + 1,
        "TABELA 2 — TARGET PRICE: crescimento da receita x margem EBITDA",
        "margem \\ cresc.",
        [_rotulo_pp(passo) for passo in passos_margem],
        [_rotulo_pp(passo) for passo in passos_crescimento],
        matriz_receita_margem,
        preco_atual,
        indice_base,
    )

    # Tabela 3 — setorial: construcao usa NWC (proxy inverso de VSO);
    # varejo e demais setores usam intensidade de CAPEX.
    setor = normalizar_texto(projecao.get("setor"))
    eh_construcao = "construcao" in setor
    if eh_construcao:
        titulo_setor = (
            "TABELA 3 — SETORIAL (construcao): margem EBITDA x intensidade "
            "de capital de giro (proxy inverso de VSO)"
        )

        def _cenario_setor(fator: float, passo_margem: float):
            return recalcular_cenario(
                projecao, delta_margem_pp=passo_margem, fator_nwc=fator
            )

    else:
        titulo_setor = (
            "TABELA 3 — SETORIAL (varejo): margem EBITDA x intensidade de CAPEX"
        )

        def _cenario_setor(fator: float, passo_margem: float):
            return recalcular_cenario(
                projecao, delta_margem_pp=passo_margem, fator_capex=fator
            )

    matriz_setor = _grade_cenarios(projecao, fatores, passos_margem, _cenario_setor)
    indice_base = None
    if 1.0 in fatores and 0.0 in passos_margem:
        indice_base = (fatores.index(1.0), passos_margem.index(0.0))
    _escrever_tabela_sensibilidade(
        ws,
        linha + 1,
        titulo_setor,
        "intens. \\ margem",
        [_rotulo_fator(fator) for fator in fatores],
        [_rotulo_pp(passo) for passo in passos_margem],
        matriz_setor,
        preco_atual,
        indice_base,
    )


# ---------------------------------------------------------------------------
# Aba 7 — Output (dashboard + checklist + ROIC/ROIIC)
# ---------------------------------------------------------------------------


def _aba_output(wb: Workbook, ctx: dict[str, Any]) -> None:
    """Dashboard de decisao, checklist de consistencia e graficos finais."""
    ws = wb.create_sheet("Output")
    ws.sheet_view.showGridLines = False
    # Coluna A larga o bastante para os KPIs numericos em fonte 14
    # (Target Price e WACC vivem nela; estreita demais vira "#####").
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 44
    ws.column_dimensions["E"].width = 30
    ws.column_dimensions["G"].width = 16

    projecao = ctx["projecao"]
    ev_equity = projecao["ev_equity"]
    valor_terminal = projecao["valor_terminal"]
    checklist = projecao.get("checklist", {})

    escrever_titulo(ws, 1, "OUTPUT — DASHBOARD DE DECISAO E CHECKLIST", 6)

    kpis = (
        ("Target Price", ev_equity.get("target_price"), FORMATO_PRECO),
        ("Preco atual", ev_equity.get("preco_atual"), FORMATO_PRECO),
        ("Upside", ev_equity.get("upside"), FORMATO_PERCENTUAL),
        ("Recomendacao", str(ev_equity.get("recomendacao", "n/d")), None),
        ("WACC", projecao["wacc"].get("wacc"), FORMATO_PERCENTUAL_2),
        ("g (perpetuidade)", valor_terminal.get("g"), FORMATO_PERCENTUAL_2),
        (
            "% EV na perpetuidade",
            valor_terminal.get("pct_ev_perpetuidade"),
            FORMATO_PERCENTUAL,
        ),
        (
            "Checklist",
            "APROVADO" if checklist.get("aprovado") is True else "REPROVADO",
            None,
        ),
    )
    linha = 3
    for indice, (rotulo, valor, formato) in enumerate(kpis):
        coluna = 1 + (indice % 4) * 2
        linha_kpi = linha + (indice // 4) * 3
        celula_rotulo = ws.cell(row=linha_kpi, column=coluna, value=rotulo)
        celula_rotulo.font = Font(name=FONTE_TEXTO, size=9, color="FF6B7A90")
        celula_valor = ws.cell(row=linha_kpi + 1, column=coluna)
        if formato is None:
            celula_valor.value = valor
            cor = (
                COR_VERDE_FUNDO
                if valor in ("COMPRA", "APROVADO")
                else (
                    COR_VERMELHO_FUNDO
                    if valor in ("VENDA", "REPROVADO")
                    else COR_AMARELO_FUNDO
                )
            )
            celula_valor.font = Font(name=FONTE_NUMERO, size=14, bold=True, color=cor)
        else:
            if isinstance(valor, (int, float)):
                celula_valor.value = float(valor)
                celula_valor.number_format = formato
            else:
                celula_valor.value = "n/d"
            celula_valor.font = Font(name=FONTE_NUMERO, size=14, bold=True)
    linha += 7

    escrever_titulo(ws, linha, "CHECKLIST DE CONSISTENCIA", 6)
    linha += 1
    escrever_cabecalho_colunas(
        ws, linha, 1, ["ID", "Verificacao", "Status", "Valor", "Limite"]
    )
    linha += 1
    for item in checklist.get("itens", []):
        ws.cell(row=linha, column=1, value=str(item.get("id", ""))).font = Font(
            name=FONTE_NUMERO, size=10, bold=True
        )
        ws.cell(row=linha, column=2, value=str(item.get("descricao", ""))).font = Font(
            name=FONTE_TEXTO, size=10
        )
        status = str(item.get("status", ""))
        celula_status = ws.cell(row=linha, column=3, value=status)
        cor_status = (
            COR_VERDE_FUNDO
            if status == "OK"
            else COR_VERMELHO_FUNDO if status == "ERRO" else COR_AMARELO_FUNDO
        )
        celula_status.font = Font(
            name=FONTE_NUMERO, size=10, bold=True, color=cor_status
        )
        ws.cell(row=linha, column=4, value=str(item.get("valor", ""))).font = Font(
            name=FONTE_NUMERO, size=9
        )
        ws.cell(row=linha, column=5, value=str(item.get("limite", ""))).font = Font(
            name=FONTE_TEXTO, size=9, color="FF6B7A90"
        )
        linha += 1

    linha += 2
    ws.cell(
        row=linha - 1,
        column=1,
        value="Dashboard executivo e ROIC x ROIIC (PNG gerados pelo motor):",
    ).font = Font(name=FONTE_TEXTO, italic=True, size=9)
    _inserir_png(ws, ctx["raiz"], ctx["ticker"], "dashboard_final", f"A{linha}")
    _inserir_png(ws, ctx["raiz"], ctx["ticker"], "roic_roiic", f"A{linha + 25}")


# ---------------------------------------------------------------------------
# Preview das 7 abas para o app (Streamlit) — valores, nao formulas
# ---------------------------------------------------------------------------
#
# O .xlsx guarda FORMULAS nativas; sem o Excel para recalcular, elas nao teriam
# valor no preview. Por isso o preview e montado do MESMO ``montar_contexto``
# que alimenta a exportacao (fonte unica de verdade), devolvendo tabelas de
# VALORES ja formatados no padrao brasileiro. O download entrega o .xlsx real
# com as formulas; o preview mostra os numeros que essas formulas produzem.


def _fmt_moeda_preview(valor: Any, casas: int = 2) -> str:
    """Formata em R$ (padrao BR) ou 'n/d' quando nao numerico."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return formatar_moeda_brl(float(valor), casas)
    return "n/d"


def _fmt_num_preview(valor: Any, casas: int = 2) -> str:
    """Formata numero com separador de milhar (ponto) e virgula decimal."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        texto = f"{float(valor):,.{casas}f}"
        return texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return "n/d"


def _fmt_pct_preview(valor: Any, casas: int = 1) -> str:
    """Formata decimal como percentual BR ou 'n/d'."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return formatar_percentual_br(float(valor), casas)
    return "n/d"


def _df_series(
    linhas: list[tuple[str, list[str]]],
    colunas: list[str],
) -> pd.DataFrame:
    """Monta DataFrame com uma coluna 'Linha' e as colunas de anos."""
    registros = []
    for rotulo, valores in linhas:
        registro: dict[str, str] = {"Linha": rotulo}
        for coluna, valor in zip(colunas, valores):
            registro[coluna] = valor
        registros.append(registro)
    return pd.DataFrame(registros)


def _df_chave_valor(pares: list[tuple[str, str]]) -> pd.DataFrame:
    """Monta DataFrame de duas colunas (Item, Valor)."""
    return pd.DataFrame([{"Item": rotulo, "Valor": valor} for rotulo, valor in pares])


def _hist_series_preview(ctx: dict[str, Any], campo: str) -> list[float | None]:
    """Serie historica (contas da CVM) alinhada aos 3 anos do modelo."""
    series = ctx["series_historicas"]
    valores: list[float | None] = [
        series.get(campo, {}).get(ano) for ano in ctx["anos_historicos"]
    ]
    while len(valores) < ANOS_HISTORICOS_MODELO:
        valores.insert(0, None)
    return valores


def _hist_metricas_preview(ctx: dict[str, Any], campo: str) -> list[float | None]:
    """Serie historica das metricas anuais alinhada aos 3 anos do modelo."""
    por_ano = ctx["metricas"].get("metricas_por_ano", {})
    valores: list[float | None] = [
        por_ano.get(str(ano), {}).get(campo) for ano in ctx["anos_historicos"]
    ]
    while len(valores) < ANOS_HISTORICOS_MODELO:
        valores.insert(0, None)
    return valores


def _rotulos_anos_historicos(ctx: dict[str, Any]) -> list[str]:
    """Rotulos dos exercicios historicos, preenchendo lacunas com 'hist n/d'."""
    rotulos = [str(ano) for ano in ctx["anos_historicos"]]
    while len(rotulos) < ANOS_HISTORICOS_MODELO:
        rotulos.insert(0, "hist n/d")
    return rotulos


def _preview_capa(ctx: dict[str, Any]) -> list[tuple[str, pd.DataFrame]]:
    """Capa: identificacao do modelo + dados-chave da decisao."""
    projecao = ctx["projecao"]
    metadados = ctx["metadados"]
    ev = projecao["ev_equity"]
    vt = projecao["valor_terminal"]
    data_base = str(projecao.get("ano0", {}).get("data_exercicio", "n/d"))
    pares = [
        ("Empresa", str(metadados.get("razao_social", "n/d"))),
        ("Ticker", ctx["ticker"]),
        ("Setor (CVM)", str(metadados.get("setor", "n/d"))),
        ("Tipo detectado", str(metadados.get("tipo", "n/d"))),
        ("Data-base (Ano 0)", data_base),
        ("Escala dos valores", "R$ mil (escala CVM)"),
        ("Preco atual", _fmt_moeda_preview(ev.get("preco_atual"))),
        ("Target Price", _fmt_moeda_preview(ev.get("target_price"))),
        ("Upside", _fmt_pct_preview(ev.get("upside"))),
        ("Recomendacao", str(ev.get("recomendacao", "n/d"))),
        ("WACC", _fmt_pct_preview(projecao.get("wacc", {}).get("wacc"), 2)),
        ("g (perpetuidade)", _fmt_pct_preview(vt.get("g"), 2)),
        ("EV", _fmt_num_preview(ev.get("ev"))),
        ("Equity Value", _fmt_num_preview(ev.get("equity_value"))),
        ("% do EV na perpetuidade", _fmt_pct_preview(vt.get("pct_ev_perpetuidade"))),
    ]
    return [("Identificacao e decisao de investimento", _df_chave_valor(pares))]


def _preview_premissas(ctx: dict[str, Any]) -> list[tuple[str, pd.DataFrame]]:
    """Premissas: os 8 valores individuais por vetor + historico ao lado."""
    premissas = ctx["premissas"]
    agregados = ctx["metricas"].get("agregados", {})
    colunas = [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)]
    vetores = (
        ("crescimento_receita", "Crescimento da receita"),
        ("margem_ebitda", "Margem EBITDA"),
        ("capex_receita", "CAPEX / Receita"),
    )
    linhas = []
    for campo, rotulo in vetores:
        valores = [
            _fmt_pct_preview(premissas.get(f"{campo}_ano{ano}"))
            for ano in range(1, HORIZONTE_PROJECAO + 1)
        ]
        linhas.append((rotulo, valores))
    df_vetores = _df_series(linhas, colunas)
    df_vetores["Historico CVM"] = [
        _texto_historico_vetor(campo, agregados) for campo, _ in vetores
    ]

    estrutura = premissas.get("estrutura_capital_alvo", {})
    pares = [
        ("DSO — recebimento (dias)", _fmt_num_preview(premissas.get("dso"), 0)),
        ("DIO — estoque (dias)", _fmt_num_preview(premissas.get("dio"), 0)),
        ("DPO — pagamento (dias)", _fmt_num_preview(premissas.get("dpo"), 0)),
        ("Beta desalavancado", _fmt_num_preview(premissas.get("beta"), 2)),
        ("Kd — custo da divida", _fmt_pct_preview(premissas.get("custo_divida_kd"), 2)),
        (
            "g — perpetuidade",
            _fmt_pct_preview(premissas.get("crescimento_perpetuidade_g"), 2),
        ),
        ("ERP — premio de risco EUA", _fmt_pct_preview(premissas.get("erp"), 2)),
        ("CRP — risco-pais Brasil", _fmt_pct_preview(premissas.get("crp"), 2)),
        ("Estrutura alvo — % divida", _fmt_pct_preview(estrutura.get("percentual_divida"))),
        ("Estrutura alvo — % equity", _fmt_pct_preview(estrutura.get("percentual_equity"))),
    ]
    return [
        ("Vetores anuais (8 valores individuais + historico)", df_vetores),
        ("Capital de giro e custo de capital", _df_chave_valor(pares)),
    ]


def _preview_modelo_integrado(
    ctx: dict[str, Any],
) -> list[tuple[str, pd.DataFrame]]:
    """Modelo Integrado: DRE, BP e DFC (3 anos historicos + 8 projetados)."""
    projecao = ctx["projecao"]
    colunas = _rotulos_anos_historicos(ctx) + [
        f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)
    ]

    def _linha(rotulo: str, hist: list[float | None], proj_campo_bloco: tuple[str, str]):
        bloco, campo = proj_campo_bloco
        proj = _serie_anual(projecao, bloco, campo)
        valores = [_fmt_num_preview(valor) for valor in hist + proj]
        return (rotulo, valores)

    dre = [
        _linha("Receita liquida", _hist_series_preview(ctx, "receita_liquida"), ("dre", "receita_liquida")),
        _linha("EBITDA", _hist_metricas_preview(ctx, "ebitda"), ("dre", "ebitda")),
        _linha("(-) D&A", _hist_series_preview(ctx, "depreciacao_amortizacao"), ("dre", "depreciacao_amortizacao")),
        _linha("EBIT", _hist_series_preview(ctx, "ebit"), ("dre", "ebit")),
        _linha("Resultado financeiro", _hist_series_preview(ctx, "resultado_financeiro"), ("dre", "resultado_financeiro")),
        _linha("EBT", _hist_series_preview(ctx, "ebt"), ("dre", "ebt")),
        _linha("(-) IR/CSLL", _hist_series_preview(ctx, "ir_csll"), ("dre", "ir_csll")),
        _linha("Lucro liquido", _hist_series_preview(ctx, "lucro_liquido"), ("dre", "lucro_liquido")),
    ]

    fornecedores_hist = [
        abs(valor) if valor is not None else None
        for valor in _hist_series_preview(ctx, "fornecedores")
    ]
    bp = [
        _linha("Caixa e equivalentes", _hist_series_preview(ctx, "caixa_equivalentes"), ("balanco", "caixa_equivalentes")),
        _linha("Aplicacoes financeiras", _hist_series_preview(ctx, "aplicacoes_financeiras"), ("balanco", "aplicacoes_financeiras")),
        _linha("Contas a receber", _hist_series_preview(ctx, "contas_receber"), ("balanco", "contas_receber")),
        _linha("Estoques", _hist_series_preview(ctx, "estoques"), ("balanco", "estoques")),
        _linha("Imobilizado (PP&E)", _hist_series_preview(ctx, "imobilizado"), ("balanco", "imobilizado")),
        _linha("Ativo total", [None] * ANOS_HISTORICOS_MODELO, ("balanco", "ativo_total")),
        _linha("Fornecedores", fornecedores_hist, ("balanco", "fornecedores")),
        _linha("Divida de curto prazo", _hist_series_preview(ctx, "divida_curto_prazo"), ("balanco", "divida_curto_prazo")),
        _linha("Divida de longo prazo", _hist_series_preview(ctx, "divida_longo_prazo"), ("balanco", "divida_longo_prazo")),
        _linha("Passivo total", [None] * ANOS_HISTORICOS_MODELO, ("balanco", "passivo_total")),
        _linha("Patrimonio liquido", _hist_series_preview(ctx, "patrimonio_liquido"), ("balanco", "patrimonio_liquido")),
    ]

    sem_hist = [None] * ANOS_HISTORICOS_MODELO
    dfc = [
        _linha("Lucro liquido", sem_hist, ("dfc", "lucro_liquido")),
        _linha("(+) D&A", _hist_series_preview(ctx, "depreciacao_amortizacao"), ("dfc", "depreciacao_amortizacao")),
        _linha("(-) Delta NWC", sem_hist, ("dfc", "delta_nwc")),
        _linha("(-) CAPEX (saida)", sem_hist, ("dfc", "capex_saida_caixa")),
        _linha("(+) Delta divida", sem_hist, ("dfc", "delta_divida")),
        _linha("Fluxo de caixa livre", sem_hist, ("dfc", "fluxo_caixa_livre")),
    ]
    return [
        ("DRE (R$ mil)", _df_series(dre, colunas)),
        ("Balanco patrimonial (R$ mil)", _df_series(bp, colunas)),
        ("DFC simplificado (R$ mil)", _df_series(dfc, colunas)),
    ]


def _preview_schedules(ctx: dict[str, Any]) -> list[tuple[str, pd.DataFrame]]:
    """Schedules de WK, PP&E e Divida com a coluna Ano 0."""
    projecao = ctx["projecao"]
    ano0 = projecao.get("ano0", {})
    colunas = ["Ano 0"] + [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)]

    def _com_ano0(valor_ano0, proj, formatar=_fmt_num_preview) -> list[str]:
        return [formatar(valor_ano0)] + [formatar(valor) for valor in proj]

    wk0 = ano0.get("wk", {})
    wk = [
        ("Contas a receber", _com_ano0(wk0.get("contas_receber"), _serie_anual(projecao, "wk", "contas_receber"))),
        ("Estoques", _com_ano0(wk0.get("estoques"), _serie_anual(projecao, "wk", "estoques"))),
        ("Fornecedores (passivo)", _com_ano0(wk0.get("fornecedores"), _serie_anual(projecao, "wk", "fornecedores"))),
        ("NWC", _com_ano0(wk0.get("nwc"), _serie_anual(projecao, "wk", "nwc"))),
        ("Delta NWC", _com_ano0(None, _serie_anual(projecao, "wk", "delta_nwc"))),
    ]

    ppe0 = ano0.get("ppe", {})
    ppe = [
        ("CAPEX / Receita", _com_ano0(None, _serie_anual(projecao, "ppe", "capex_receita"), _fmt_pct_preview)),
        ("CAPEX", _com_ano0(None, _serie_anual(projecao, "ppe", "capex"))),
        ("D&A do periodo", _com_ano0(None, _serie_anual(projecao, "ppe", "depreciacao_amortizacao"))),
        ("PP&E final", _com_ano0(ppe0.get("imobilizado"), _serie_anual(projecao, "ppe", "imobilizado"))),
    ]

    div0 = ano0.get("divida", {})
    divida = [
        ("Kd — custo da divida", _com_ano0(None, _serie_anual(projecao, "divida", "custo_divida_kd"), _fmt_pct_preview)),
        ("Divida de curto prazo", _com_ano0(div0.get("divida_curto_prazo"), _serie_anual(projecao, "divida", "divida_curto_prazo"))),
        ("Divida de longo prazo", _com_ano0(div0.get("divida_longo_prazo"), _serie_anual(projecao, "divida", "divida_longo_prazo"))),
        ("Divida bruta", _com_ano0(div0.get("divida_bruta"), _serie_anual(projecao, "divida", "divida_bruta"))),
        ("Saldo medio da divida", _com_ano0(None, _serie_anual(projecao, "divida", "saldo_medio_divida"))),
        ("Juros", _com_ano0(None, _serie_anual(projecao, "divida", "juros"))),
        ("Resultado financeiro", _com_ano0(None, _serie_anual(projecao, "divida", "resultado_financeiro"))),
    ]
    return [
        ("Capital de giro (WK)", _df_series(wk, colunas)),
        ("PP&E (imobilizado)", _df_series(ppe, colunas)),
        ("Divida (politica v1: bruta constante)", _df_series(divida, colunas)),
    ]


def _preview_valuation(ctx: dict[str, Any]) -> list[tuple[str, pd.DataFrame]]:
    """Valuation: FCFF anual, decomposicao do WACC, valor terminal e bridge."""
    projecao = ctx["projecao"]
    wacc = projecao["wacc"]
    vt = projecao["valor_terminal"]
    ev = projecao["ev_equity"]
    colunas = [f"Ano {ano}" for ano in range(1, HORIZONTE_PROJECAO + 1)]

    def _serie_fmt(bloco: str, campo: str, formatar=_fmt_num_preview) -> list[str]:
        return [formatar(valor) for valor in _serie_anual(projecao, bloco, campo)]

    fcff = [
        ("EBIT", _serie_fmt("dre", "ebit")),
        ("Aliquota do NOPAT", _serie_fmt("fcff", "aliquota_ir_nopat", _fmt_pct_preview)),
        ("NOPAT", _serie_fmt("fcff", "nopat")),
        ("(+) D&A", _serie_fmt("fcff", "depreciacao_amortizacao")),
        ("(-) Delta NWC", _serie_fmt("fcff", "delta_nwc")),
        ("(-) CAPEX (saida)", _serie_fmt("fcff", "capex_saida_caixa")),
        ("FCFF", _serie_fmt("fcff", "fcff")),
        ("ROIC", _serie_fmt("fcff", "roic", _fmt_pct_preview)),
        ("ROIIC", _serie_fmt("fcff", "roiic", _fmt_pct_preview)),
    ]

    decomposicao_wacc = [
        ("Rf USD (^TNX)", _fmt_pct_preview(wacc.get("rf_usd"), 2)),
        ("Beta desalavancado", _fmt_num_preview(wacc.get("beta_desalavancado"), 4)),
        ("D/E medio (anos 1-8)", _fmt_num_preview(wacc.get("divida_sobre_equity"), 4)),
        ("Beta re-alavancado (Hamada)", _fmt_num_preview(wacc.get("beta_realavancado"), 4)),
        ("ERP EUA", _fmt_pct_preview(wacc.get("erp_eua"), 2)),
        ("CRP Brasil", _fmt_pct_preview(wacc.get("crp_brasil"), 2)),
        ("Ke USD", _fmt_pct_preview(wacc.get("ke_usd"), 2)),
        ("Ke BRL", _fmt_pct_preview(wacc.get("ke_brl"), 2)),
        ("Kd historico", _fmt_pct_preview(wacc.get("kd_historico"), 2)),
        ("Kd liquido", _fmt_pct_preview(wacc.get("kd_liquido"), 2)),
        ("Peso Equity (E/V)", _fmt_pct_preview(wacc.get("peso_equity"), 2)),
        ("Peso Divida (D/V)", _fmt_pct_preview(wacc.get("peso_divida"), 2)),
        ("WACC", _fmt_pct_preview(wacc.get("wacc"), 2)),
    ]

    valor_terminal = [
        ("g — perpetuidade", _fmt_pct_preview(vt.get("g"), 2)),
        ("FCFF ano 8", _fmt_num_preview(vt.get("fcff_ano8"))),
        ("NOPAT ano 8 (base alternativa)", _fmt_num_preview(vt.get("nopat_ano8"))),
        ("Base utilizada no VT", str(vt.get("base_vt", "n/d"))),
        ("VT bruto", _fmt_num_preview(vt.get("vt_bruto"))),
        ("VP(VT)", _fmt_num_preview(vt.get("vp_vt"))),
        ("% do EV na perpetuidade", _fmt_pct_preview(vt.get("pct_ev_perpetuidade"))),
        (
            "Multiplo de saida implicito",
            _fmt_num_preview(vt.get("multiplo_saida_implicito"), 2) + "x"
            if isinstance(vt.get("multiplo_saida_implicito"), (int, float))
            else "n/d",
        ),
    ]

    ajustes = ev.get("ajustes_bridge", {})
    bridge = [
        ("Soma VP(FCFF anos 1-8)", _fmt_num_preview(ev.get("soma_vp_fcff"))),
        ("(+) VP(Valor Terminal)", _fmt_num_preview(ev.get("vp_vt"))),
        ("= Enterprise Value (EV)", _fmt_num_preview(ev.get("ev"))),
        ("(-) Divida bruta", _fmt_num_preview(ajustes.get("divida_bruta"))),
        ("(+) Caixa e equivalentes", _fmt_num_preview(ajustes.get("caixa_equivalentes"))),
        ("(+) Aplicacoes financeiras", _fmt_num_preview(ajustes.get("aplicacoes_financeiras"))),
        ("= Equity Value", _fmt_num_preview(ev.get("equity_value"))),
        ("Acoes fully diluted", _fmt_num_preview(ev.get("acoes_fully_diluted"), 0)),
        ("Target Price", _fmt_moeda_preview(ev.get("target_price"))),
        ("Preco atual", _fmt_moeda_preview(ev.get("preco_atual"))),
        ("Upside", _fmt_pct_preview(ev.get("upside"))),
        ("Recomendacao", str(ev.get("recomendacao", "n/d"))),
    ]
    return [
        ("FCFF projetado (R$ mil)", _df_series(fcff, colunas)),
        ("Decomposicao do WACC", _df_chave_valor(decomposicao_wacc)),
        ("Valor terminal (Gordon)", _df_chave_valor(valor_terminal)),
        ("Bridge EV -> Equity -> Target", _df_chave_valor(bridge)),
    ]


def _df_matriz(
    rotulo_canto: str,
    rotulos_linha: list[str],
    rotulos_coluna: list[str],
    matriz: list[list[float | None]],
) -> pd.DataFrame:
    """Converte uma matriz de target price em DataFrame formatado."""
    registros = []
    for rotulo_linha, linha in zip(rotulos_linha, matriz):
        registro: dict[str, str] = {rotulo_canto: rotulo_linha}
        for rotulo_coluna, valor in zip(rotulos_coluna, linha):
            registro[rotulo_coluna] = (
                _fmt_moeda_preview(valor) if valor is not None else "n/d"
            )
        registros.append(registro)
    return pd.DataFrame(registros)


def _preview_sensibilidades(
    ctx: dict[str, Any],
) -> list[tuple[str, pd.DataFrame]]:
    """As 3 tabelas de sensibilidade (mesmos cenarios do .xlsx)."""
    projecao = ctx["projecao"]
    parametros = carregar_json(ctx["raiz"] / "config" / "parametros.json")
    sensibilidade = parametros.get("sensibilidade", {})
    passos_wacc = [float(p) for p in sensibilidade.get("wacc_passos_pp", [])]
    passos_g = [float(p) for p in sensibilidade.get("g_passos_pp", [])]
    passos_crescimento = [
        float(p) for p in sensibilidade.get("crescimento_passos_pp", [])
    ]
    passos_margem = [float(p) for p in sensibilidade.get("margem_passos_pp", [])]
    fatores = [float(f) for f in sensibilidade.get("fatores_intensidade", [])]

    wacc_base = float(projecao["wacc"]["wacc"])
    g_base = float(projecao["valor_terminal"]["g"])

    matriz_wacc_g = _grade_cenarios(
        projecao,
        passos_g,
        passos_wacc,
        lambda passo_g, passo_wacc: recalcular_cenario(
            projecao, delta_wacc=passo_wacc, delta_g=passo_g
        ),
    )
    tabela1 = _df_matriz(
        "g \\ WACC",
        [f"{(g_base + passo) * 100:.2f}%" for passo in passos_g],
        [f"{(wacc_base + passo) * 100:.2f}%" for passo in passos_wacc],
        matriz_wacc_g,
    )

    matriz_receita_margem = _grade_cenarios(
        projecao,
        passos_margem,
        passos_crescimento,
        lambda passo_margem, passo_crescimento: recalcular_cenario(
            projecao,
            delta_crescimento_pp=passo_crescimento,
            delta_margem_pp=passo_margem,
        ),
    )
    tabela2 = _df_matriz(
        "margem \\ cresc.",
        [_rotulo_pp(passo) for passo in passos_margem],
        [_rotulo_pp(passo) for passo in passos_crescimento],
        matriz_receita_margem,
    )

    setor = normalizar_texto(projecao.get("setor"))
    eh_construcao = "construcao" in setor
    if eh_construcao:
        titulo3 = "Setorial (construcao): margem EBITDA x intensidade de WK"

        def _cenario_setor(fator: float, passo_margem: float):
            return recalcular_cenario(
                projecao, delta_margem_pp=passo_margem, fator_nwc=fator
            )

    else:
        titulo3 = "Setorial (varejo): margem EBITDA x intensidade de CAPEX"

        def _cenario_setor(fator: float, passo_margem: float):
            return recalcular_cenario(
                projecao, delta_margem_pp=passo_margem, fator_capex=fator
            )

    matriz_setor = _grade_cenarios(projecao, fatores, passos_margem, _cenario_setor)
    tabela3 = _df_matriz(
        "intens. \\ margem",
        [_rotulo_fator(fator) for fator in fatores],
        [_rotulo_pp(passo) for passo in passos_margem],
        matriz_setor,
    )
    return [
        ("Tabela 1 — Target Price: WACC x g", tabela1),
        ("Tabela 2 — Target Price: crescimento x margem", tabela2),
        (f"Tabela 3 — {titulo3}", tabela3),
    ]


def _preview_output(ctx: dict[str, Any]) -> list[tuple[str, pd.DataFrame]]:
    """Output: dashboard de KPIs + checklist de consistencia."""
    projecao = ctx["projecao"]
    ev = projecao["ev_equity"]
    vt = projecao["valor_terminal"]
    checklist = projecao.get("checklist", {})
    aprovado = checklist.get("aprovado") is True

    kpis = [
        ("Target Price", _fmt_moeda_preview(ev.get("target_price"))),
        ("Preco atual", _fmt_moeda_preview(ev.get("preco_atual"))),
        ("Upside", _fmt_pct_preview(ev.get("upside"))),
        ("Recomendacao", str(ev.get("recomendacao", "n/d"))),
        ("WACC", _fmt_pct_preview(projecao.get("wacc", {}).get("wacc"), 2)),
        ("g (perpetuidade)", _fmt_pct_preview(vt.get("g"), 2)),
        ("% EV na perpetuidade", _fmt_pct_preview(vt.get("pct_ev_perpetuidade"))),
        ("Checklist", "APROVADO" if aprovado else "REPROVADO"),
    ]
    itens = checklist.get("itens", [])
    df_checklist = pd.DataFrame(
        [
            {
                "ID": str(item.get("id", "")),
                "Verificacao": str(item.get("descricao", "")),
                "Status": str(item.get("status", "")),
                "Valor": str(item.get("valor", "")),
                "Limite": str(item.get("limite", "")),
            }
            for item in itens
        ]
    )
    return [
        ("Dashboard de decisao", _df_chave_valor(kpis)),
        ("Checklist de consistencia", df_checklist),
    ]


def montar_preview_por_aba(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, list[tuple[str, pd.DataFrame]]]:
    """Monta as 7 abas do Excel como DataFrames de VALORES para o app.

    Cada aba vira uma lista de secoes ``(subtitulo, DataFrame)``. Consome o
    mesmo ``montar_contexto`` do exportador, entao preview e .xlsx nunca
    divergem. O app renderiza estas tabelas e oferece o download do .xlsx.
    """
    ctx = montar_contexto(ticker, raiz_projeto)
    return {
        "Capa": _preview_capa(ctx),
        "Premissas": _preview_premissas(ctx),
        "Modelo Integrado": _preview_modelo_integrado(ctx),
        "Schedules": _preview_schedules(ctx),
        "Valuation": _preview_valuation(ctx),
        "Sensibilidades": _preview_sensibilidades(ctx),
        "Output": _preview_output(ctx),
    }


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------


def exportar_excel(ticker: str, raiz_projeto: Path | None = None) -> Path:
    """Gera o Excel institucional de 7 abas para o ticker.

    Le exclusivamente os resultados persistidos pelo motor; devolve o
    caminho do arquivo salvo em ``outputs/excel/<TICKER>_dcf.xlsx``.
    """
    ctx = montar_contexto(ticker, raiz_projeto)
    wb = Workbook()

    # Modelo Integrado referencia a aba Schedules por layout fixo (constantes
    # LINHA_*), por isso pode ser construida antes dela sem quebrar formulas.
    _aba_capa(wb, ctx)
    _aba_premissas(wb, ctx)
    _aba_modelo_integrado(wb, ctx)
    _aba_schedules(wb, ctx)
    _aba_valuation(wb, ctx)
    _aba_sensibilidades(wb, ctx)
    _aba_output(wb, ctx)

    caminho = caminho_excel(ctx["ticker"], ctx["raiz"])
    wb.save(caminho)
    logger.info("Excel gerado: %s", caminho)
    return caminho


def main() -> None:
    """Gera o Excel de 7 abas para DIRR3 e MGLU3 (escopo v1.0)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for ticker in ("DIRR3", "MGLU3"):
        caminho = exportar_excel(ticker)
        print(f"{ticker}: {caminho}")


if __name__ == "__main__":
    main()
