"""Projetor da DRE para empresas nao financeiras."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parents[2]
HORIZONTE_PROJECAO = 8
ALIQUOTA_IR_CSLL_GERAL = 0.34
ALIQUOTA_RET_RECEITA = 0.04

CAMPOS_DRE_PROJETADA = (
    "ano_projecao",
    "taxa_crescimento_receita",
    "receita_liquida",
    "margem_ebitda",
    "ebitda",
    "depreciacao_amortizacao",
    "ebit",
    "resultado_financeiro",
    "ebt",
    "ir_csll",
    "lucro_liquido",
)

# Campos adicionais persistidos SOMENTE no modo completo (Padrao Smartfit,
# Prompt 8.1). Todos ja registrados em config/mapeamento_cvm.json.
CAMPOS_DRE_COMPLETA = (
    "receita_bruta",
    "deducoes",
    "cpv_cmv",
    "lucro_bruto",
    "margem_bruta",
    "sgna",
    "sgna_pct_receita",
    "outras_receitas_despesas",
    "equivalencia_patrimonial",
    "aliquota_efetiva_usada",
    "da_direito_uso",
    "da_imobilizado",
    "da_intangivel",
)

MODO_DRE_LEGADO = "legado"
MODO_DRE_COMPLETO = "completo"
MODO_ALIQUOTA_MARGINAL = "marginal"
MODO_ALIQUOTA_EFETIVA = "efetiva_historica"


def resolver_raiz(raiz_projeto: Path | None = None) -> Path:
    """Devolve a raiz do projeto, permitindo override em testes."""
    if raiz_projeto is None:
        return RAIZ_PROJETO
    return Path(raiz_projeto)


def normalizar_texto(valor: Any) -> str:
    """Normaliza texto para comparacoes defensivas sem depender de acentos."""
    texto = "" if valor is None else str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


def carregar_json(caminho: Path) -> Any:
    """Carrega um JSON e apresenta erro claro quando o arquivo for invalido."""
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except FileNotFoundError as erro:
        raise RuntimeError(f"Arquivo obrigatorio nao encontrado: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise RuntimeError(f"JSON invalido em {caminho}: {erro}") from erro


def salvar_json(caminho: Path, conteudo: Any) -> None:
    """Salva conteudo JSON com UTF-8 e indentacao estavel."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)


def normalizar_valor_json(valor: Any) -> Any:
    """Converte escalares pandas/numpy para tipos nativos serializaveis em JSON."""
    if valor is None:
        return None
    if isinstance(valor, pd.Timestamp):
        if pd.isna(valor):
            return None
        return valor.strftime("%Y-%m-%d")
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def validar_nomes_mapeados(raiz_projeto: Path) -> None:
    """Garante que as colunas da DRE projetada existem no mapeamento oficial."""
    caminho = raiz_projeto / "config" / "mapeamento_cvm.json"
    mapeamento = carregar_json(caminho)
    campos_mapeados = set(mapeamento.get("campos", {}))
    faltantes = sorted(set(CAMPOS_DRE_PROJETADA) - campos_mapeados)
    if faltantes:
        raise RuntimeError(
            "Campos de projecao ausentes em config/mapeamento_cvm.json: "
            + ", ".join(faltantes)
        )


def normalizar_ticker(ticker: str) -> str:
    """Normaliza ticker B3 removendo sufixo de bolsa e padronizando caixa."""
    return ticker.upper().replace(".SA", "").strip()


def valor_numerico_obrigatorio(premissas: dict[str, Any], campo: str) -> float:
    """Le uma premissa numerica obrigatoria e falha se ela estiver ausente."""
    if campo not in premissas or premissas[campo] is None:
        raise ValueError(f"Premissa obrigatoria ausente ou nula: {campo}")

    valor = premissas[campo]
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Premissa obrigatoria precisa ser numerica: {campo}")
    return float(valor)


def carregar_premissas_dre(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[dict[str, Any], dict[int, float], dict[int, float]]:
    """Carrega as premissas anuais de crescimento e margem EBITDA."""
    caminho = raiz_projeto / "data" / "premissas" / f"{ticker}_premissas.json"
    premissas = carregar_json(caminho)
    taxas_crescimento = {}
    margens_ebitda = {}

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        campo_crescimento = f"crescimento_receita_ano{ano}"
        campo_margem = f"margem_ebitda_ano{ano}"
        taxas_crescimento[ano] = valor_numerico_obrigatorio(
            premissas,
            campo_crescimento,
        )
        margens_ebitda[ano] = valor_numerico_obrigatorio(
            premissas,
            campo_margem,
        )

    return premissas, taxas_crescimento, margens_ebitda


def carregar_metadados(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega os metadados da empresa produzidos pela coleta CVM."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_meta.json"
    return carregar_json(caminho)


def empresa_usa_ret(premissas: dict[str, Any], metadados: dict[str, Any]) -> bool:
    """Detecta se a empresa deve usar o RET de construtoras."""
    setores = [
        normalizar_texto(premissas.get("setor")),
        normalizar_texto(metadados.get("setor")),
    ]
    return any(setor == "construcao" or "construcao" in setor for setor in setores)


def selecionar_ultimo_exercicio(
    dados: pd.DataFrame,
    nome_padronizado: str,
) -> pd.Series:
    """Seleciona a linha do ultimo exercicio para uma conta padronizada."""
    if dados.empty:
        raise RuntimeError("Base historica vazia para selecionar Ano 0.")
    if "nome_padronizado" not in dados.columns:
        raise RuntimeError("Base historica sem coluna nome_padronizado.")
    if "valor_padronizado" not in dados.columns:
        raise RuntimeError("Base historica sem coluna valor_padronizado.")

    selecionado = dados[dados["nome_padronizado"] == nome_padronizado].copy()
    selecionado = selecionado[selecionado["valor_padronizado"].notna()]
    if "ORDEM_EXERC" in selecionado.columns:
        ordem_normalizada = selecionado["ORDEM_EXERC"].map(normalizar_texto)
        selecionado = selecionado[ordem_normalizada == "ultimo"]
    if selecionado.empty:
        raise RuntimeError(f"Conta {nome_padronizado} nao encontrada no Ano 0.")

    # O Ano 0 precisa ser um exercicio ANUAL (DFP, 31/12): um ITR trimestral
    # como base faria a projecao partir de 1/4 da receita real enquanto o
    # bridge subtrai a divida bruta inteira. Se nao houver fechamento anual
    # (fixtures sinteticas), mantem o comportamento antigo como fallback.
    if "DT_FIM_EXERC" in selecionado.columns:
        datas_exercicio = pd.to_datetime(
            selecionado["DT_FIM_EXERC"],
            errors="coerce",
        )
        anuais = selecionado[
            (datas_exercicio.dt.month == 12) & (datas_exercicio.dt.day == 31)
        ]
        if not anuais.empty:
            selecionado = anuais.copy()

    if "ano_arquivo" in selecionado.columns:
        selecionado["_ano_arquivo_num"] = pd.to_numeric(
            selecionado["ano_arquivo"],
            errors="coerce",
        )
        maior_ano_arquivo = selecionado["_ano_arquivo_num"].max()
        selecionado = selecionado[selecionado["_ano_arquivo_num"] == maior_ano_arquivo]

    if "DT_FIM_EXERC" in selecionado.columns:
        selecionado["_data_exercicio"] = pd.to_datetime(
            selecionado["DT_FIM_EXERC"],
            errors="coerce",
        )
        maior_data = selecionado["_data_exercicio"].max()
        selecionado = selecionado[selecionado["_data_exercicio"] == maior_data]

    if "CD_CONTA" in selecionado.columns:
        selecionado["_prioridade_conta"] = selecionado["CD_CONTA"].astype(str).str.len()
        selecionado = selecionado.sort_values("_prioridade_conta")

    return selecionado.iloc[0]


def extrair_receita_linha(linha: pd.Series, fonte: str) -> dict[str, Any]:
    """Extrai a receita liquida e metadados da linha historica selecionada."""
    return {
        "fonte": fonte,
        "ano_arquivo": normalizar_valor_json(linha.get("ano_arquivo")),
        "data_exercicio": normalizar_valor_json(linha.get("DT_FIM_EXERC")),
        "ordem_exercicio": normalizar_valor_json(linha.get("ORDEM_EXERC")),
        "receita_liquida": float(linha["valor_padronizado"]),
    }


def carregar_receita_ano0_de_parquet(
    ticker: str,
    raiz_projeto: Path,
    caminhos: list[Path],
) -> dict[str, Any]:
    """Carrega a receita Ano 0 de Parquets processados quando eles existirem."""
    quadros = []
    for caminho in caminhos:
        quadro = pd.read_parquet(caminho)
        quadro["_fonte_parquet"] = str(caminho)
        quadros.append(quadro)
    dados = pd.concat(quadros, ignore_index=True)
    linha = selecionar_ultimo_exercicio(dados, "receita_liquida")
    return extrair_receita_linha(linha, f"data/processed/{ticker}*.parquet")


def carregar_receita_ano0_de_json(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega a receita Ano 0 diretamente do JSON bruto da CVM."""
    caminho = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_dre.json"
    registros = carregar_json(caminho)
    dados = pd.DataFrame(registros)
    linha = selecionar_ultimo_exercicio(dados, "receita_liquida")
    return extrair_receita_linha(linha, str(caminho.relative_to(raiz_projeto)))


def carregar_receita_ano0(ticker: str, raiz_projeto: Path) -> dict[str, Any]:
    """Carrega a receita liquida do Ano 0 preferindo Parquet processado."""
    pasta_processados = raiz_projeto / "data" / "processed"
    caminhos_parquet = sorted(pasta_processados.glob(f"{ticker}*.parquet"))
    if caminhos_parquet:
        return carregar_receita_ano0_de_parquet(
            ticker,
            raiz_projeto,
            caminhos_parquet,
        )
    return carregar_receita_ano0_de_json(ticker, raiz_projeto)


def calcular_ir_csll(
    ebt: float,
    receita_liquida: float,
    usa_ret: bool,
    razao_receita_bruta: float | None = None,
) -> float:
    """Calcula IR/CSLL mantendo despesas tributarias com sinal negativo.

    Aliquota efetiva vs. marginal: o motor usa a MARGINAL (34% IR/CSLL) por
    conservadorismo; a aliquota efetiva historica (que embute diferidos e
    beneficios) fica disponivel nas metricas para o analista ajustar.
    """
    if usa_ret:
        # Formula: IR/CSLL RET = -4% x receita BRUTA.
        # Quando a DVA (7.01.01) fornece a razao RB/RL do Ano 0, a base e
        # RL_t x razao; sem DVA, a receita liquida segue como proxy avisado.
        razao = razao_receita_bruta if razao_receita_bruta is not None else 1.0
        return -(receita_liquida * razao * ALIQUOTA_RET_RECEITA)

    if ebt <= 0:
        # Formula: IR/CSLL geral = 0 quando EBT <= 0 (sem credito automatico).
        return 0.0

    # Formula: IR/CSLL geral = -34% x EBT positivo (aliquota marginal).
    return -(ebt * ALIQUOTA_IR_CSLL_GERAL)


def carregar_razao_receita_bruta(
    ticker: str,
    raiz_projeto: Path,
) -> tuple[float | None, str]:
    """Razao Receita Bruta / Receita Liquida do Ano 0 via DVA (7.01.01).

    Devolve ``(razao, fonte)``; sem DVA ou sem linha de receita bruta, a
    razao e None e a fonte explica o fallback (proxy pela receita liquida).
    """
    caminho_dva = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_dva.json"
    if not caminho_dva.exists():
        return None, "proxy_receita_liquida (DVA nao coletada)"
    registros = carregar_json(caminho_dva)
    if not registros:
        return None, "proxy_receita_liquida (DVA vazia)"
    dva = pd.DataFrame(registros)
    try:
        linha_bruta = selecionar_ultimo_exercicio(dva, "receita_bruta")
    except RuntimeError:
        return None, "proxy_receita_liquida (DVA sem linha 7.01.01)"

    caminho_dre = raiz_projeto / "data" / "raw" / "cvm" / f"{ticker}_dre.json"
    dre = pd.DataFrame(carregar_json(caminho_dre))
    try:
        linha_liquida = selecionar_ultimo_exercicio(dre, "receita_liquida")
    except RuntimeError:
        return None, "proxy_receita_liquida (DRE sem receita liquida)"

    receita_bruta = float(linha_bruta["valor_padronizado"])
    receita_liquida = float(linha_liquida["valor_padronizado"])
    if receita_liquida <= 0 or receita_bruta <= 0:
        return None, "proxy_receita_liquida (bases nao positivas)"
    # Formula: razao RB/RL do Ano 0, aplicada as receitas projetadas.
    return receita_bruta / receita_liquida, "dva_7_01_01"


def projetar_receita(
    receita_ano0: float,
    taxas_crescimento: dict[int, float],
    premissas: dict[str, Any] | None = None,
) -> dict[int, float]:
    """Projeta a serie de RECEITA LIQUIDA de ano1..ano8 (funcao plugavel).

    PONTO DE ENCAIXE do unit economics (v3.0). Hoje implementa apenas o
    crescimento percentual sobre o ano anterior
    (``Receita_t = Receita_(t-1) x (1 + crescimento_receita_t)``). A v3.0
    plugara AQUI o build-up setorial (academias x ticket, VGV x POC, ARPU x
    base etc.) devolvendo a mesma serie de 8 anos, sem tocar no resto da DRE.
    O parametro ``premissas`` fica disponivel para esse build-up futuro; hoje
    nao e usado (o crescimento vem de ``taxas_crescimento``).
    """
    serie: dict[int, float] = {}
    receita_anterior = receita_ano0
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        # Formula: Receita_t = Receita_(t-1) x (1 + crescimento_receita_t).
        receita_liquida = receita_anterior * (1 + taxas_crescimento[ano])
        serie[ano] = receita_liquida
        receita_anterior = receita_liquida
    return serie


def projetar_linhas_dre(
    receita_ano0: float,
    taxas_crescimento: dict[int, float],
    margens_ebitda: dict[int, float],
    usa_ret: bool,
    razao_receita_bruta: float | None = None,
) -> dict[str, dict[str, float | str]]:
    """Projeta as linhas da DRE (modo LEGADO) para ano1..ano8."""
    linhas = {}
    serie_receita = projetar_receita(receita_ano0, taxas_crescimento)

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        taxa_crescimento = taxas_crescimento[ano]
        margem_ebitda = margens_ebitda[ano]

        # Formula: Receita_t = Receita_(t-1) x (1 + crescimento_receita_t).
        receita_liquida = serie_receita[ano]

        # Formula: EBITDA_t = Receita_t x margem_ebitda_t.
        ebitda = receita_liquida * margem_ebitda

        # Formula: EBIT = EBITDA - D&A. D&A entra como 0 nesta versao inicial
        # e sera sobrescrita pelo schedule PP&E mantendo o campo explicito.
        depreciacao_amortizacao = 0.0
        ebit = ebitda + depreciacao_amortizacao

        # Formula: EBT = EBIT + resultado financeiro. O schedule de divida
        # substituira este placeholder quando estiver implementado.
        resultado_financeiro = 0.0
        ebt = ebit + resultado_financeiro

        ir_csll = calcular_ir_csll(
            ebt,
            receita_liquida,
            usa_ret,
            razao_receita_bruta=razao_receita_bruta,
        )

        # Formula: Lucro liquido = EBT - IR. Como IR/CSLL e despesa negativa
        # no padrao de sinais do projeto, somamos o campo ir_csll.
        lucro_liquido = ebt + ir_csll

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "taxa_crescimento_receita": taxa_crescimento,
            "receita_liquida": receita_liquida,
            "margem_ebitda": margem_ebitda,
            "ebitda": ebitda,
            "depreciacao_amortizacao": depreciacao_amortizacao,
            "ebit": ebit,
            "resultado_financeiro": resultado_financeiro,
            "ebt": ebt,
            "ir_csll": ir_csll,
            "lucro_liquido": lucro_liquido,
        }
        if razao_receita_bruta is not None:
            # Formula: Receita Bruta_t = RL_t x razao RB/RL do Ano 0 (DVA).
            linhas[chave_ano]["receita_bruta"] = receita_liquida * razao_receita_bruta

    return linhas


def validar_nomes_mapeados_completa(raiz_projeto: Path) -> None:
    """Garante que as colunas EXTRAS da DRE completa existem no mapeamento."""
    caminho = raiz_projeto / "config" / "mapeamento_cvm.json"
    mapeamento = carregar_json(caminho)
    campos_mapeados = set(mapeamento.get("campos", {}))
    faltantes = sorted(set(CAMPOS_DRE_COMPLETA) - campos_mapeados)
    if faltantes:
        raise RuntimeError(
            "Campos da DRE completa ausentes em config/mapeamento_cvm.json: "
            + ", ".join(faltantes)
        )


def premissas_tem_dre_completa(premissas: dict[str, Any]) -> bool:
    """Detecta o modo COMPLETO pela presenca das duas premissas definidoras.

    A DRE completa (Padrao Smartfit, Prompt 8.1) so liga quando ha
    ``margem_bruta_ano1`` E ``sgna_pct_receita_ano1`` (os dois vetores que a
    definem). Arquivos v2 (so ``margem_ebitda_ano1..8``) rodam no modo LEGADO
    byte a byte — retrocompatibilidade do Principio 13.
    """

    def _tem(campo: str) -> bool:
        valor = premissas.get(campo)
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)

    return _tem("margem_bruta_ano1") and _tem("sgna_pct_receita_ano1")


def carregar_parametros_dre_completa(raiz_projeto: Path) -> dict[str, Any]:
    """Le clamps/defaults do bloco ``dre_completa`` de config/parametros.json."""
    caminho = raiz_projeto / "config" / "parametros.json"
    parametros = carregar_json(caminho)
    bloco = parametros.get("dre_completa", {})
    return {
        "modo_aliquota_padrao": bloco.get(
            "modo_aliquota_padrao", MODO_ALIQUOTA_MARGINAL
        ),
        "aliquota_marginal": float(
            bloco.get("aliquota_marginal", ALIQUOTA_IR_CSLL_GERAL)
        ),
        "aliquota_efetiva_min": float(bloco.get("aliquota_efetiva_min", 0.15)),
        "aliquota_efetiva_max": float(bloco.get("aliquota_efetiva_max", 0.45)),
        "deducoes_padrao": float(bloco.get("deducoes_pct_receita_bruta_padrao", 0.0)),
        "outras_padrao": float(bloco.get("outras_despesas_pct_receita_padrao", 0.0)),
        "equivalencia_padrao": float(bloco.get("equivalencia_pct_receita_padrao", 0.0)),
    }


def _escalar_premissa(premissas: dict[str, Any], campo: str, padrao: float) -> float:
    """Le uma premissa escalar opcional; ausente/invalida usa o padrao."""
    valor = premissas.get(campo)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return padrao
    return float(valor)


def _vetor_premissa_8(
    premissas: dict[str, Any],
    prefixo: str,
    fallback: float,
) -> dict[int, float]:
    """Le um vetor opcional de 8 valores; anos ausentes herdam o mais antigo.

    Preserva a regra dos 8 valores INDIVIDUAIS quando o arquivo os traz; para
    um ano faltante usa o primeiro valor presente (ou ``fallback`` se nenhum),
    nunca uma taxa unica silenciosa que apague a intencao do analista.
    """
    presentes: dict[int, float] = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        valor = premissas.get(f"{prefixo}_ano{ano}")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            presentes[ano] = float(valor)
    base = presentes[min(presentes)] if presentes else fallback
    return {ano: presentes.get(ano, base) for ano in range(1, HORIZONTE_PROJECAO + 1)}


def carregar_aliquota_efetiva_historica(
    ticker: str,
    raiz_projeto: Path,
) -> float | None:
    """Aliquota efetiva historica media (agregado das metricas), se existir."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_metricas.json"
    if not caminho.exists():
        return None
    metricas = carregar_json(caminho)
    valor = metricas.get("agregados", {}).get("aliquota_efetiva_media_3a")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def resolver_aliquota_efetiva(
    ticker: str,
    premissas: dict[str, Any],
    raiz_projeto: Path,
    parametros_completa: dict[str, Any],
) -> float | None:
    """Aliquota efetiva a aplicar: premissa > historico, com clamp de sanidade.

    Devolve None quando nao ha base historica nem premissa (o motor cai no
    modo marginal). Clamp em [min, max] do bloco ``dre_completa`` (default
    [15%, 45%]) — padrao Smartfit ``Model !N65``.
    """
    bruta = premissas.get("aliquota_efetiva")
    if isinstance(bruta, bool) or not isinstance(bruta, (int, float)):
        bruta = carregar_aliquota_efetiva_historica(ticker, raiz_projeto)
    if bruta is None:
        return None
    minimo = parametros_completa["aliquota_efetiva_min"]
    maximo = parametros_completa["aliquota_efetiva_max"]
    return max(minimo, min(maximo, float(bruta)))


def calcular_ir_csll_completo(
    ebt: float,
    receita_bruta: float,
    usa_ret: bool,
    modo_aliquota: str,
    aliquota_efetiva: float | None,
    aliquota_marginal: float,
) -> tuple[float, float | None]:
    """IR/CSLL da DRE completa; devolve (ir_csll, aliquota_efetiva_usada).

    - RET (construtoras): -4% sobre a Receita BRUTA projetada (base gross).
    - ``efetiva_historica``: -aliquota_efetiva x EBT positivo (clamp aplicado
      antes). ``marginal`` (default): -34% x EBT positivo. EBT <= 0 => IR = 0.
    """
    if usa_ret:
        # Formula: IR/CSLL RET = -4% x Receita Bruta projetada.
        return -(receita_bruta * ALIQUOTA_RET_RECEITA), None

    if modo_aliquota == MODO_ALIQUOTA_EFETIVA and aliquota_efetiva is not None:
        aliquota = aliquota_efetiva
    else:
        aliquota = aliquota_marginal

    if ebt <= 0:
        # Formula: IR/CSLL = 0 quando EBT <= 0 (sem credito automatico).
        return 0.0, aliquota
    # Formula: IR/CSLL = -aliquota x EBT positivo.
    return -(ebt * aliquota), aliquota


def projetar_linhas_dre_completa(
    receita_ano0: float,
    taxas_crescimento: dict[int, float],
    premissas: dict[str, Any],
    usa_ret: bool,
    aliquota_efetiva: float | None,
    parametros_completa: dict[str, Any],
) -> dict[str, dict[str, float | str]]:
    """Projeta a DRE COMPLETA (Padrao Smartfit) de ano1..ano8.

    Ordem (Smartfit ``Model `` L19-L81): Receita Bruta -> (-)Deducoes ->
    Receita Liquida -> (-)CPV -> Lucro Bruto -> (-)SG&A -> (+/-)Outras ->
    (+/-)Equivalencia -> EBIT -> Resultado financeiro (placeholder) -> EBT ->
    IR/CSLL -> LL. Memo: D&A aberta (direito de uso/imobilizado/intangivel,
    zeradas aqui; o schedule PP&E preenche a do imobilizado) e EBITDA = EBIT +
    D&A total. CPV e SG&A ja embutem a D&A (como no Smartfit L68-69), por isso
    o EBIT sai direto das margens e o EBITDA a reconstroi somando a D&A.
    """
    serie_receita = projetar_receita(receita_ano0, taxas_crescimento, premissas)
    margens_bruta = _vetor_premissa_8(premissas, "margem_bruta", 0.30)
    sgna_pct = _vetor_premissa_8(premissas, "sgna_pct_receita", 0.15)
    deducoes_pct = _vetor_premissa_8(
        premissas,
        "deducoes_pct_receita_bruta",
        parametros_completa["deducoes_padrao"],
    )
    outras_pct = _escalar_premissa(
        premissas,
        "outras_despesas_pct_receita",
        parametros_completa["outras_padrao"],
    )
    equivalencia_pct = _escalar_premissa(
        premissas,
        "equivalencia_pct_receita",
        parametros_completa["equivalencia_padrao"],
    )
    modo_aliquota = (
        premissas.get("modo_aliquota") or parametros_completa["modo_aliquota_padrao"]
    )
    aliquota_marginal = parametros_completa["aliquota_marginal"]

    linhas: dict[str, dict[str, float | str]] = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        receita_liquida = serie_receita[ano]

        # Deducoes como % da RECEITA BRUTA: RB = RL / (1 - deducoes%).
        deducoes_pct_ano = min(max(deducoes_pct[ano], 0.0), 0.95)
        receita_bruta = receita_liquida / (1 - deducoes_pct_ano)
        # Deducoes = RL - RB (<= 0; despesa/reducao com sinal negativo).
        deducoes = receita_liquida - receita_bruta

        # CPV via margem bruta: Lucro Bruto = RL x margem_bruta_t.
        margem_bruta = margens_bruta[ano]
        cpv = -(receita_liquida * (1 - margem_bruta))
        lucro_bruto = receita_liquida + cpv

        # SG&A como % da receita liquida (despesa negativa).
        sgna_pct_ano = sgna_pct[ano]
        sgna = -(receita_liquida * sgna_pct_ano)
        outras_receitas_despesas = receita_liquida * outras_pct
        equivalencia_patrimonial = receita_liquida * equivalencia_pct

        # Formula: EBIT = Lucro Bruto + SG&A + Outras + Equivalencia.
        ebit = lucro_bruto + sgna + outras_receitas_despesas + equivalencia_patrimonial

        # D&A aberta (memo): imobilizado vem do schedule PP&E; direito de uso
        # e intangivel nascem zerados (o Prompt 8.2 os preenche).
        da_direito_uso = 0.0
        da_imobilizado = 0.0
        da_intangivel = 0.0
        depreciacao_amortizacao = da_direito_uso + da_imobilizado + da_intangivel

        # Formula: EBITDA = EBIT + D&A total (D&A embutida em CPV/SG&A).
        ebitda = ebit + depreciacao_amortizacao

        # Resultado financeiro entra pelo schedule de divida (placeholder 0).
        resultado_financeiro = 0.0
        ebt = ebit + resultado_financeiro

        ir_csll, aliquota_usada = calcular_ir_csll_completo(
            ebt=ebt,
            receita_bruta=receita_bruta,
            usa_ret=usa_ret,
            modo_aliquota=str(modo_aliquota),
            aliquota_efetiva=aliquota_efetiva,
            aliquota_marginal=aliquota_marginal,
        )
        lucro_liquido = ebt + ir_csll

        linhas[chave_ano] = {
            "ano_projecao": chave_ano,
            "taxa_crescimento_receita": taxas_crescimento[ano],
            "receita_bruta": receita_bruta,
            "deducoes": deducoes,
            "receita_liquida": receita_liquida,
            "margem_bruta": margem_bruta,
            "cpv_cmv": cpv,
            "lucro_bruto": lucro_bruto,
            "sgna_pct_receita": sgna_pct_ano,
            "sgna": sgna,
            "outras_receitas_despesas": outras_receitas_despesas,
            "equivalencia_patrimonial": equivalencia_patrimonial,
            "ebit": ebit,
            "da_direito_uso": da_direito_uso,
            "da_imobilizado": da_imobilizado,
            "da_intangivel": da_intangivel,
            "depreciacao_amortizacao": depreciacao_amortizacao,
            # margem EBITDA derivada e PERSISTIDA (compat com consumidores v2).
            "margem_ebitda": (ebitda / receita_liquida if receita_liquida else 0.0),
            "ebitda": ebitda,
            "resultado_financeiro": resultado_financeiro,
            "ebt": ebt,
            "modo_aliquota": str(modo_aliquota),
            "aliquota_efetiva_usada": aliquota_usada,
            "ir_csll": ir_csll,
            "lucro_liquido": lucro_liquido,
        }

    return linhas


def atualizar_projecao(
    ticker: str,
    raiz_projeto: Path,
    premissas: dict[str, Any],
    metadados: dict[str, Any],
    ano0: dict[str, Any],
    dre: dict[str, dict[str, float | str]],
    politicas_ret: dict[str, Any] | None = None,
    modo_dre: str = MODO_DRE_LEGADO,
    politicas_dre: dict[str, Any] | None = None,
) -> Path:
    """Grava ou atualiza a estrutura unica de projecao do ticker."""
    caminho = raiz_projeto / "data" / "processed" / f"{ticker}_projecao.json"
    if caminho.exists():
        conteudo = carregar_json(caminho)
    else:
        conteudo = {}

    conteudo["ticker"] = ticker
    conteudo["tipo"] = premissas.get("tipo") or metadados.get("tipo")
    conteudo["setor"] = premissas.get("setor") or metadados.get("setor")
    conteudo["modo_dre"] = modo_dre
    conteudo["ano0"] = ano0
    conteudo["dre"] = dre
    if politicas_ret is not None or politicas_dre is not None:
        politicas = conteudo.get("politicas_projecao")
        if not isinstance(politicas, dict):
            politicas = {}
        if politicas_ret is not None:
            politicas["ret"] = politicas_ret
        if politicas_dre is not None:
            politicas["dre"] = politicas_dre
        conteudo["politicas_projecao"] = politicas
    salvar_json(caminho, conteudo)
    return caminho


def _carregar_taxas_crescimento(premissas: dict[str, Any]) -> dict[int, float]:
    """Le os 8 campos individuais de crescimento (obrigatorios nos dois modos)."""
    taxas = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        taxas[ano] = valor_numerico_obrigatorio(
            premissas,
            f"crescimento_receita_ano{ano}",
        )
    return taxas


def _projetar_dre_completa(
    ticker: str,
    raiz: Path,
    premissas: dict[str, Any],
    metadados: dict[str, Any],
    ano0: dict[str, Any],
    taxas_crescimento: dict[int, float],
    usa_ret: bool,
) -> dict[str, Any]:
    """Ramo COMPLETO (Padrao Smartfit): DRE bruta->liquida com CPV/SG&A/D&A."""
    validar_nomes_mapeados_completa(raiz)
    parametros_completa = carregar_parametros_dre_completa(raiz)
    aliquota_efetiva = resolver_aliquota_efetiva(
        ticker,
        premissas,
        raiz,
        parametros_completa,
    )
    modo_aliquota = str(
        premissas.get("modo_aliquota") or parametros_completa["modo_aliquota_padrao"]
    )

    dre = projetar_linhas_dre_completa(
        receita_ano0=ano0["receita_liquida"],
        taxas_crescimento=taxas_crescimento,
        premissas=premissas,
        usa_ret=usa_ret,
        aliquota_efetiva=aliquota_efetiva,
        parametros_completa=parametros_completa,
    )

    politicas_dre = {
        "modo_dre": MODO_DRE_COMPLETO,
        "modo_aliquota": modo_aliquota,
        "aliquota_efetiva_disponivel": aliquota_efetiva,
        "aliquota_marginal": parametros_completa["aliquota_marginal"],
        "base_ret": "receita_bruta_projetada" if usa_ret else "n/a",
        "fonte_receita": (
            "projetar_receita:crescimento_percentual "
            "(encaixe do unit economics reservado para a v3.0)"
        ),
    }
    # No modo completo o RET incide sobre a Receita BRUTA PROJETADA ano a ano
    # (linha receita_bruta da DRE), nao mais sobre a razao fixa RB/RL da DVA.
    politicas_ret = (
        {
            "usa_ret": True,
            "razao_receita_bruta": None,
            "fonte_base_ret": "receita_bruta_projetada_da_dre_completa",
        }
        if usa_ret
        else None
    )

    caminho_saida = atualizar_projecao(
        ticker=ticker,
        raiz_projeto=raiz,
        premissas=premissas,
        metadados=metadados,
        ano0=ano0,
        dre=dre,
        politicas_ret=politicas_ret,
        modo_dre=MODO_DRE_COMPLETO,
        politicas_dre=politicas_dre,
    )
    return {
        "ticker": ticker,
        "modo_dre": MODO_DRE_COMPLETO,
        "usa_ret": usa_ret,
        "razao_receita_bruta": None,
        "aliquota_efetiva": aliquota_efetiva,
        "ano0": ano0,
        "dre": dre,
        "caminho_saida": caminho_saida,
    }


def projetar_dre(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa a projecao da DRE para um ticker e persiste o resultado.

    Detecta o modo pela presenca das premissas definidoras (Principio 13):
    ``margem_bruta`` + ``sgna_pct_receita`` => DRE COMPLETA (Padrao Smartfit);
    caso contrario, modo LEGADO (margem EBITDA direta) byte a byte.
    """
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    validar_nomes_mapeados(raiz)
    caminho_premissas = (
        raiz / "data" / "premissas" / f"{ticker_normalizado}_premissas.json"
    )
    premissas = carregar_json(caminho_premissas)
    taxas_crescimento = _carregar_taxas_crescimento(premissas)
    metadados = carregar_metadados(ticker_normalizado, raiz)
    ano0 = carregar_receita_ano0(ticker_normalizado, raiz)
    usa_ret = empresa_usa_ret(premissas, metadados)

    if premissas_tem_dre_completa(premissas):
        return _projetar_dre_completa(
            ticker=ticker_normalizado,
            raiz=raiz,
            premissas=premissas,
            metadados=metadados,
            ano0=ano0,
            taxas_crescimento=taxas_crescimento,
            usa_ret=usa_ret,
        )

    # --- Modo LEGADO (v2): receita liquida x margem EBITDA (intocado) ---
    margens_ebitda = {}
    for ano in range(1, HORIZONTE_PROJECAO + 1):
        margens_ebitda[ano] = valor_numerico_obrigatorio(
            premissas,
            f"margem_ebitda_ano{ano}",
        )

    razao_receita_bruta: float | None = None
    politicas_ret: dict[str, Any] | None = None
    if usa_ret:
        razao_receita_bruta, fonte_razao = carregar_razao_receita_bruta(
            ticker_normalizado,
            raiz,
        )
        politicas_ret = {
            "usa_ret": True,
            "razao_receita_bruta": razao_receita_bruta,
            "fonte_base_ret": fonte_razao,
        }
        if razao_receita_bruta is None:
            # Campo CVM ausente vai para aviso explicito, nunca quebra.
            print(
                f"    AVISO RET: {fonte_razao} — usando receita liquida "
                "como base do RET."
            )

    dre = projetar_linhas_dre(
        receita_ano0=ano0["receita_liquida"],
        taxas_crescimento=taxas_crescimento,
        margens_ebitda=margens_ebitda,
        usa_ret=usa_ret,
        razao_receita_bruta=razao_receita_bruta,
    )
    caminho_saida = atualizar_projecao(
        ticker=ticker_normalizado,
        raiz_projeto=raiz,
        premissas=premissas,
        metadados=metadados,
        ano0=ano0,
        dre=dre,
        politicas_ret=politicas_ret,
        modo_dre=MODO_DRE_LEGADO,
    )
    return {
        "ticker": ticker_normalizado,
        "modo_dre": MODO_DRE_LEGADO,
        "usa_ret": usa_ret,
        "razao_receita_bruta": razao_receita_bruta,
        "ano0": ano0,
        "dre": dre,
        "caminho_saida": caminho_saida,
    }


def formatar_percentual(valor: float) -> str:
    """Formata numero decimal como percentual legivel no terminal."""
    return f"{valor * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero(valor: float) -> str:
    """Formata numero com separador de milhar no padrao brasileiro."""
    return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def imprimir_tabela_dre(resultado: dict[str, Any]) -> None:
    """Imprime a tabela de DRE projetada para validacao visual."""
    ticker = resultado["ticker"]
    ano0 = resultado["ano0"]
    dre = resultado["dre"]
    print("\n" + "=" * 120)
    print(f"DRE projetada - {ticker}")
    print(
        "Ano 0: "
        f"receita_liquida={formatar_numero(ano0['receita_liquida'])} | "
        f"data={ano0.get('data_exercicio')} | fonte={ano0.get('fonte')}"
    )
    print(
        "Campos de crescimento lidos individualmente: "
        + ", ".join(f"crescimento_receita_ano{ano}" for ano in range(1, 9))
    )
    print(
        "Campos de margem lidos individualmente: "
        + ", ".join(f"margem_ebitda_ano{ano}" for ano in range(1, 9))
    )

    cabecalho = (
        f"{'Ano':<6} {'Crescimento':>13} {'Receita':>18} "
        f"{'Margem EBITDA':>15} {'EBITDA':>18} {'EBIT':>18} "
        f"{'EBT':>18} {'IR/CSLL':>18} {'LL':>18}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for chave_ano, linha in dre.items():
        print(
            f"{chave_ano:<6} "
            f"{formatar_percentual(float(linha['taxa_crescimento_receita'])):>13} "
            f"{formatar_numero(float(linha['receita_liquida'])):>18} "
            f"{formatar_percentual(float(linha['margem_ebitda'])):>15} "
            f"{formatar_numero(float(linha['ebitda'])):>18} "
            f"{formatar_numero(float(linha['ebit'])):>18} "
            f"{formatar_numero(float(linha['ebt'])):>18} "
            f"{formatar_numero(float(linha['ir_csll'])):>18} "
            f"{formatar_numero(float(linha['lucro_liquido'])):>18}"
        )


def executar_validacao_padrao() -> None:
    """Executa a projecao padrao para DIRR3 e MGLU3 ao rodar o arquivo direto."""
    houve_falha = False
    for ticker in ("DIRR3", "MGLU3"):
        try:
            resultado = projetar_dre(ticker)
            imprimir_tabela_dre(resultado)
        except Exception as erro:
            houve_falha = True
            print(f"\nFalha ao projetar {ticker}: {erro}")

    if houve_falha:
        raise SystemExit(1)


if __name__ == "__main__":
    executar_validacao_padrao()
