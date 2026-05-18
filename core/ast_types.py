"""Tipos de parsing AST compartilhados (D-DEV-18).

Antes duplicados, idênticos, em `extracao/mineracao/data_structs.py` e
`detectores/data_structs.py` — agora unificados aqui. Aqueles dois arquivos
passam a re-exportar deste módulo.

São objetos internos de parsing (não payload serializado) → `@dataclass`,
não Pydantic.
"""
from dataclasses import dataclass, field


@dataclass
class FunctionInfo:
    name: str                       # nome
    lineno: int                     # linha de início
    end_lineno: int                 # linha de fim
    source: str                     # código-fonte da função
    params: list[str]               # nomes dos parâmetros
    owner_class: str | None = None  # None se top-level


@dataclass
class ClassInfo:
    name: str                                                  # nome
    lineno: int                                                # linha de início
    end_lineno: int                                            # linha de fim
    source: str                                                # código-fonte
    methods: list[FunctionInfo] = field(default_factory=list)  # métodos filhos
    bases: list[str] = field(default_factory=list)             # classes-pai como string
