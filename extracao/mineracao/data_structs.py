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
    name: str                                                   # nome
    lineno: int                                                 # linha inicio
    end_lineno: int                                             # linha de fim
    source: str                                                 # codigo fonte
    methods: list[FunctionInfo] = field(default_factory=list)   # metodos filhos
    bases: list[str] = field(default_factory=list)              # classes pai como string (para Refused Bequest depois)