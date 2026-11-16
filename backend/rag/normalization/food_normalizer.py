
"""Normalización lingüística y terminológica de alimentos."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReglaSinonimo:
    alias: str
    canonico: str


@dataclass(frozen=True, slots=True)
class ModificadorProducto:
    termino: str
    penalizacion: float


REGLAS_SINONIMOS: tuple[ReglaSinonimo, ...] = (
    ReglaSinonimo("banana", "platano"),
    ReglaSinonimo("bananas", "platano"),
    ReglaSinonimo("platanos", "platano"),
    ReglaSinonimo("yogur", "yogurt"),
    ReglaSinonimo("yogures", "yogurt"),
    ReglaSinonimo("leches", "leche"),
    ReglaSinonimo("huevos", "huevo"),
    ReglaSinonimo("patatas", "patata"),
    ReglaSinonimo("papas", "patata"),
    ReglaSinonimo("tomates", "tomate"),
    ReglaSinonimo("zanahorias", "zanahoria"),
    ReglaSinonimo("manzanas", "manzana"),
    ReglaSinonimo("naranjas", "naranja"),
    ReglaSinonimo("lentejas", "lenteja"),
    ReglaSinonimo("garbanzos", "garbanzo"),
    ReglaSinonimo("judias", "judia"),
)


MODIFICADORES_PRODUCTO: tuple[ModificadorProducto, ...] = (
    ModificadorProducto("helado", 24),
    ModificadorProducto("harina", 18),
    ModificadorProducto("polvo", 18),
    ModificadorProducto("galleta", 24),
    ModificadorProducto("galletas", 24),
    ModificadorProducto("bizcocho", 24),
    ModificadorProducto("croissant", 24),
    ModificadorProducto("granola", 20),
    ModificadorProducto("snack", 22),
    ModificadorProducto("chips", 22),
    ModificadorProducto("tarta", 24),
    ModificadorProducto("pastel", 24),
    ModificadorProducto("magdalena", 24),
    ModificadorProducto("muffin", 24),
    ModificadorProducto("cookie", 24),
    ModificadorProducto("cookies", 24),
    ModificadorProducto("salsa", 20),
    ModificadorProducto("sopa", 18),
    ModificadorProducto("caldo", 18),
    ModificadorProducto("ramen", 24),
    ModificadorProducto("hamburguesa", 22),
    ModificadorProducto("hamburguesas", 22),
    ModificadorProducto("croquetas", 24),
    ModificadorProducto("nuggets", 24),
    ModificadorProducto("zumo", 18),
    ModificadorProducto("jugo", 18),
    ModificadorProducto("bebida", 18),
    ModificadorProducto("conserva", 18),
    ModificadorProducto("enlatado", 18),
    ModificadorProducto("enlatada", 18),
    ModificadorProducto("relleno", 20),
    ModificadorProducto("rellena", 20),
    ModificadorProducto("rellenos", 20),
    ModificadorProducto("empanado", 20),
    ModificadorProducto("empanada", 20),
    ModificadorProducto("rebozado", 20),
    ModificadorProducto("pudding", 24),
    ModificadorProducto("smoothie", 20),
    ModificadorProducto("deshidratado", 12),
    ModificadorProducto("deshidratada", 12),
    ModificadorProducto("sabor", 15),
    ModificadorProducto("sabores", 15),
)


PALABRAS_VACIAS: frozenset[str] = frozenset({
    "de", "la", "el", "los", "las",
    "un", "una", "unos", "unas",
    "con", "en", "para", "por",
    "del", "al", "y",
})


RESTRICCIONES_CRITICAS: tuple[str, ...] = (
    "sin azucar",
    "sin lactosa",
    "sin gluten",
    "sin sal",
)


class NormalizadorAlimentos:
    """Proporciona operaciones comunes de normalización."""

    @staticmethod
    def normalizar_texto(texto: str) -> str:
        if not isinstance(texto, str) or not texto:
            return ""

        texto = unicodedata.normalize(
            "NFD",
            texto.lower().strip(),
        )

        texto = "".join(
            caracter
            for caracter in texto
            if unicodedata.category(caracter) != "Mn"
        )

        texto = re.sub(r"[^a-z0-9\s]", " ", texto)

        return " ".join(texto.split())

    @classmethod
    def normalizar_token(cls, token: str) -> str:
        token_normalizado = cls.normalizar_texto(token)

        for regla in REGLAS_SINONIMOS:
            if regla.alias == token_normalizado:
                return regla.canonico

        return token_normalizado

    @classmethod
    def obtener_tokens(cls, texto: str) -> tuple[str, ...]:
        tokens: list[str] = []

        for token in cls.normalizar_texto(texto).split():
            if token in PALABRAS_VACIAS or len(token) <= 1:
                continue

            token_normalizado = cls.normalizar_token(token)

            if token_normalizado:
                tokens.append(token_normalizado)

        return tuple(tokens)

    @classmethod
    def obtener_consultas_equivalentes(
        cls,
        query: str,
    ) -> tuple[str, ...]:
        consulta = cls.normalizar_texto(query)

        if not consulta:
            return ()

        consultas: list[str] = [consulta]
        tokens = consulta.split()

        for indice, token in enumerate(tokens):
            for regla in REGLAS_SINONIMOS:
                equivalente: str | None = None

                if token == regla.alias:
                    equivalente = regla.canonico
                elif token == regla.canonico:
                    equivalente = regla.alias

                if equivalente is None or equivalente == token:
                    continue

                tokens_alternativos = list(tokens)
                tokens_alternativos[indice] = equivalente

                alternativa = " ".join(tokens_alternativos)

                if alternativa not in consultas:
                    consultas.append(alternativa)

                break

        return tuple(consultas)

    @classmethod
    def obtener_penalizacion_modificador(
        cls,
        token: str,
    ) -> float:
        token_normalizado = cls.normalizar_texto(token)

        for modificador in MODIFICADORES_PRODUCTO:
            if modificador.termino == token_normalizado:
                return modificador.penalizacion

        return 0.0

    @classmethod
    def contiene_restricciones_criticas(
        cls,
        query: str,
        nombre: str,
    ) -> bool:
        consulta = cls.normalizar_texto(query)
        nombre_normalizado = cls.normalizar_texto(nombre)

        for restriccion in RESTRICCIONES_CRITICAS:
            if restriccion in consulta:
                if restriccion not in nombre_normalizado:
                    return False

        return True


normalizador_alimentos = NormalizadorAlimentos()
