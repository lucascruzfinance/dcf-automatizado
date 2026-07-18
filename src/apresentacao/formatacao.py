"""Formatacao de numeros (padrao BR) e cores da paleta institucional.

Nucleo do projeto (Prompt 9.0.0). Estas funcoes vinham de
`src/visualizacao/tema_institucional.py`, que passou a ser suporte apenas do
exportador Excel legado (reescrito no 9.0.5). Para que o `app.py` enxuto NAO
importe de `src/visualizacao/`, os auxiliares de apresentacao usados pelo
nucleo vivem aqui, sem qualquer dependencia de Plotly.
"""

from __future__ import annotations

# Paleta institucional (navy) — mesma do ROTEIRO/Etapa 4. Usadas em rotulos.
COR_FUNDO = "#0A1628"
COR_SUPERFICIE = "#0F1E33"
COR_AZUL_ANCORA = "#1B4F8C"
COR_VERDE_UPSIDE = "#16A34A"
COR_VERMELHO_DOWNSIDE = "#DC2626"
COR_TEXTO = "#E6EDF5"
COR_TEXTO_SECUNDARIO = "#8FA3BC"
COR_GRADE = "#1E3350"


def formatar_moeda_brl(valor: float, casas: int = 2) -> str:
    """Formata valor em R$ no padrao brasileiro (ponto milhar, virgula decimal)."""
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_percentual_br(valor: float, casas: int = 1) -> str:
    """Formata decimal como percentual brasileiro."""
    texto = f"{valor * 100:,.{casas}f}".replace(",", "X")
    texto = texto.replace(".", ",").replace("X", ".")
    return f"{texto}%"


def formatar_compacto(valor: float) -> str:
    """Formata numero grande em notacao compacta (mil/mi/bi) para rotulos."""
    magnitude = abs(valor)
    if magnitude >= 1_000_000_000:
        return f"{valor / 1_000_000_000:,.1f} bi".replace(".", ",")
    if magnitude >= 1_000_000:
        return f"{valor / 1_000_000:,.1f} mi".replace(".", ",")
    if magnitude >= 1_000:
        return f"{valor / 1_000:,.1f} mil".replace(".", ",")
    return f"{valor:,.1f}".replace(".", ",")
