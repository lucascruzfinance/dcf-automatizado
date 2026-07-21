"""Mini-avaliador do subset de formulas geradas pelo exportador 9.0.5.

Suporta: refs (Aba!$A$1), numeros, strings, + - * / ^ %, comparacoes,
SUM/IF/ROUND/MIN/MAX/AVERAGE/IRR com ranges, nomes definidos.
"""

from __future__ import annotations

import re


class Avaliador:
    def __init__(self, wb, overrides=None):
        self.wb = wb
        self.cache: dict[tuple[str, str], object] = {}
        self.pilha: set[tuple[str, str]] = set()
        self.overrides = overrides or {}
        self.nomes = {}
        for nome in wb.defined_names:
            destino = wb.defined_names[nome].attr_text
            self.nomes[nome.upper()] = destino  # ex.: FCFF!$B$60

    def valor_celula(self, aba: str, coordenada: str):
        coordenada = coordenada.replace("$", "")
        chave = (aba, coordenada)
        if chave in self.overrides:
            return self.overrides[chave]
        if chave in self.cache:
            return self.cache[chave]
        if chave in self.pilha:
            raise RuntimeError(f"circularidade em {aba}!{coordenada}")
        self.pilha.add(chave)
        try:
            celula = self.wb[aba][coordenada]
            bruto = celula.value
            if isinstance(bruto, str) and bruto.startswith("="):
                resultado = self.avaliar(bruto[1:], aba)
            elif isinstance(bruto, str):
                resultado = bruto
            elif bruto is None:
                resultado = 0.0
            else:
                resultado = float(bruto)
        finally:
            self.pilha.discard(chave)
        self.cache[chave] = resultado
        return resultado

    # --- parser recursivo (REENTRANTE: avaliar celula referenciada nao pode
    # clobberar o estado do parser externo) ---
    def avaliar(self, expressao: str, aba_atual: str):
        estado = (
            getattr(self, "tokens", None),
            getattr(self, "pos", None),
            getattr(self, "aba_atual", None),
        )
        self.tokens = self._tokenizar(expressao)
        self.pos = 0
        self.aba_atual = aba_atual
        try:
            resultado = self._comparacao()
            if self.pos != len(self.tokens):
                raise RuntimeError(f"sobra de tokens em: {expressao}")
            return resultado
        finally:
            self.tokens, self.pos, self.aba_atual = estado

    TOKEN_RE = re.compile(
        r"\s*(?:"
        r"(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?)"
        r"|(?P<str>\"[^\"]*\")"
        r"|(?P<ref>(?:'[^']+'|[A-Za-z_][A-Za-z0-9_]*)?!?"
        r"\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)"
        r"|(?P<nome>[A-Za-z_][A-Za-z0-9_.]*)"
        r"|(?P<op><=|>=|<>|[-+*/^%(),=<>&])"
        r")"
    )

    def _tokenizar(self, texto: str):
        tokens, pos = [], 0
        while pos < len(texto):
            m = self.TOKEN_RE.match(texto, pos)
            if not m or m.end() == pos:
                raise RuntimeError(f"token invalido em: {texto[pos:pos+20]!r}")
            pos = m.end()
            if m.group("num") is not None:
                tokens.append(("num", float(m.group("num"))))
            elif m.group("str") is not None:
                tokens.append(("str", m.group("str")[1:-1]))
            elif m.group("ref") is not None:
                tokens.append(("ref", m.group("ref")))
            elif m.group("nome") is not None:
                tokens.append(("nome", m.group("nome")))
            else:
                tokens.append(("op", m.group("op")))
        return tokens

    def _ver(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def _comer(self):
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _comparacao(self):
        esquerda = self._aditivo()
        tipo, valor = self._ver()
        if tipo == "op" and valor in ("=", "<", ">", "<=", ">=", "<>"):
            self._comer()
            direita = self._aditivo()
            if valor == "=":
                if isinstance(esquerda, str) or isinstance(direita, str):
                    return esquerda == direita
                return abs(esquerda - direita) < 1e-9
            if valor == "<>":
                return esquerda != direita
            if valor == "<":
                return esquerda < direita
            if valor == ">":
                return esquerda > direita
            if valor == "<=":
                return esquerda <= direita
            return esquerda >= direita
        return esquerda

    def _aditivo(self):
        resultado = self._termo()
        while True:
            tipo, valor = self._ver()
            if tipo == "op" and valor in ("+", "-"):
                self._comer()
                direita = self._termo()
                resultado = resultado + direita if valor == "+" else resultado - direita
            else:
                return resultado

    def _termo(self):
        resultado = self._potencia()
        while True:
            tipo, valor = self._ver()
            if tipo == "op" and valor in ("*", "/"):
                self._comer()
                direita = self._potencia()
                resultado = resultado * direita if valor == "*" else resultado / direita
            else:
                return resultado

    def _potencia(self):
        base = self._unario()
        tipo, valor = self._ver()
        if tipo == "op" and valor == "^":
            self._comer()
            expoente = self._potencia()
            return base**expoente
        return base

    def _unario(self):
        tipo, valor = self._ver()
        if tipo == "op" and valor in ("+", "-"):
            self._comer()
            operando = self._unario()
            return operando if valor == "+" else -operando
        return self._primario()

    def _resolver_ref(self, ref: str):
        ref = ref.replace("$", "")
        if "!" in ref:
            aba, coordenada = ref.split("!", 1)
            aba = aba.strip("'")
        else:
            aba, coordenada = self.aba_atual, ref
        if ":" in coordenada:
            return self._valores_range(aba, coordenada)
        return self.valor_celula(aba, coordenada)

    def _valores_range(self, aba: str, faixa: str):
        inicio, fim = faixa.split(":")
        m1 = re.match(r"([A-Z]+)(\d+)", inicio)
        m2 = re.match(r"([A-Z]+)(\d+)", fim)
        from openpyxl.utils import column_index_from_string, get_column_letter

        c1, l1 = column_index_from_string(m1.group(1)), int(m1.group(2))
        c2, l2 = column_index_from_string(m2.group(1)), int(m2.group(2))
        valores = []
        for linha in range(min(l1, l2), max(l1, l2) + 1):
            for coluna in range(min(c1, c2), max(c1, c2) + 1):
                valores.append(
                    self.valor_celula(aba, f"{get_column_letter(coluna)}{linha}")
                )
        return valores

    def _primario(self):
        tipo, valor = self._comer()
        if tipo == "num":
            proximo = self._ver()
            if proximo == ("op", "%"):
                self._comer()
                return valor / 100.0
            return valor
        if tipo == "str":
            return valor
        if tipo == "ref":
            return self._resolver_ref(valor)
        if tipo == "nome":
            proximo = self._ver()
            if proximo == ("op", "("):
                return self._funcao(valor.upper())
            destino = self.nomes.get(valor.upper())
            if destino is None:
                raise RuntimeError(f"nome desconhecido: {valor}")
            return self._resolver_ref(destino)
        if tipo == "op" and valor == "(":
            resultado = self._comparacao()
            assert self._comer() == ("op", ")")
            return resultado
        raise RuntimeError(f"token inesperado: {tipo} {valor}")

    def _funcao(self, nome: str):
        assert self._comer() == ("op", "(")
        argumentos = []
        if self._ver() != ("op", ")"):
            argumentos.append(self._comparacao())
            while self._ver() == ("op", ","):
                self._comer()
                argumentos.append(self._comparacao())
        assert self._comer() == ("op", ")")

        def achatar(itens):
            achatados = []
            for item in itens:
                if isinstance(item, list):
                    achatados.extend(item)
                else:
                    achatados.append(item)
            return achatados

        if nome == "SUM":
            return sum(x for x in achatar(argumentos) if isinstance(x, (int, float)))
        if nome == "AVERAGE":
            numeros = [x for x in achatar(argumentos) if isinstance(x, (int, float))]
            return sum(numeros) / len(numeros)
        if nome == "IF":
            condicao = argumentos[0]
            return (
                argumentos[1]
                if condicao
                else (argumentos[2] if len(argumentos) > 2 else False)
            )
        if nome == "ROUND":
            return round(argumentos[0], int(argumentos[1]))
        if nome == "MIN":
            return min(achatar(argumentos))
        if nome == "MAX":
            return max(achatar(argumentos))
        if nome == "IRR":
            fluxos = achatar(argumentos)
            return _irr(fluxos)
        raise RuntimeError(f"funcao nao suportada: {nome}")


def _irr(fluxos):
    def npv(taxa):
        return sum(f / (1 + taxa) ** t for t, f in enumerate(fluxos))

    baixo, alto = -0.9999, 10.0
    fb, fa = npv(baixo), npv(alto)
    if fb * fa > 0:
        return float("nan")
    for _ in range(200):
        meio = (baixo + alto) / 2
        fm = npv(meio)
        if abs(fm) < 1e-9:
            return meio
        if fb * fm < 0:
            alto, fa = meio, fm
        else:
            baixo, fb = meio, fm
    return (baixo + alto) / 2
