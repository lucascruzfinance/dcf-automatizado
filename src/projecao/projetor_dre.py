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


def projetar_linhas_dre(
    receita_ano0: float,
    taxas_crescimento: dict[int, float],
    margens_ebitda: dict[int, float],
    usa_ret: bool,
    razao_receita_bruta: float | None = None,
) -> dict[str, dict[str, float | str]]:
    """Projeta as linhas da DRE para ano1..ano8."""
    linhas = {}
    receita_anterior = receita_ano0

    for ano in range(1, HORIZONTE_PROJECAO + 1):
        chave_ano = f"ano{ano}"
        taxa_crescimento = taxas_crescimento[ano]
        margem_ebitda = margens_ebitda[ano]

        # Formula: Receita_t = Receita_(t-1) x (1 + crescimento_receita_t).
        receita_liquida = receita_anterior * (1 + taxa_crescimento)

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
        receita_anterior = receita_liquida

    return linhas


def atualizar_projecao(
    ticker: str,
    raiz_projeto: Path,
    premissas: dict[str, Any],
    metadados: dict[str, Any],
    ano0: dict[str, Any],
    dre: dict[str, dict[str, float | str]],
    politicas_ret: dict[str, Any] | None = None,
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
    conteudo["ano0"] = ano0
    conteudo["dre"] = dre
    if politicas_ret is not None:
        politicas = conteudo.get("politicas_projecao")
        if not isinstance(politicas, dict):
            politicas = {}
        politicas["ret"] = politicas_ret
        conteudo["politicas_projecao"] = politicas
    salvar_json(caminho, conteudo)
    return caminho


def projetar_dre(
    ticker: str,
    raiz_projeto: Path | None = None,
) -> dict[str, Any]:
    """Executa a projecao da DRE para um ticker e persiste o resultado."""
    raiz = resolver_raiz(raiz_projeto)
    ticker_normalizado = normalizar_ticker(ticker)
    validar_nomes_mapeados(raiz)
    premissas, taxas_crescimento, margens_ebitda = carregar_premissas_dre(
        ticker_normalizado,
        raiz,
    )
    metadados = carregar_metadados(ticker_normalizado, raiz)
    ano0 = carregar_receita_ano0(ticker_normalizado, raiz)
    usa_ret = empresa_usa_ret(premissas, metadados)

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
    )
    return {
        "ticker": ticker_normalizado,
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
