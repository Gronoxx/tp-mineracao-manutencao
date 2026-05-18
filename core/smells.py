"""Vocabulário canônico dos code smells do TP.

Decisão D-DEV-18 / decisão do trio nº 1: o código `R1..R5` é o canônico no
schema; o nome (`long_method`...) — usado pelos detectores — é alias.

Substitui as tabelas antes espalhadas: `MAP_SMELLS`/`SMELL_KEYWORDS` no
minerador, `SmellType` em `schema.py` e `instruction_templates.py`.
"""
from typing import Literal

# Os 5 smells com LoRA de refatoração (R1–R5) — os únicos que o minerador serve.
SMELL_CODES = ["R1", "R2", "R3", "R4", "R5"]
SmellType = Literal["R1", "R2", "R3", "R4", "R5"]

# código canônico -> nome do smell (chave usada pelos detectores em `detectores/`)
CODE_TO_NAME = {
    "R1": "long_method",
    "R2": "long_param_list",
    "R3": "magic_numbers",
    "R4": "deep_nesting",
    "R5": "dead_code",
}
NAME_TO_CODE = {nome: codigo for codigo, nome in CODE_TO_NAME.items()}

# código -> refatoração que o LoRA correspondente aplica
REFACTORING = {
    "R1": "Extract Method",
    "R2": "Introduce Parameter Object",
    "R3": "Replace with Named Constant",
    "R4": "Guard Clauses",
    "R5": "Remove Dead Code",
}

# Smells detectados (regra estática) mas SEM LoRA — detecção apenas.
# O minerador os ignora; ficam aqui para detectores e visualização.
DETECTION_ONLY = ["refused_bequest", "duplicate_code", "long_message_chain", "middle_man"]


def to_code(smell: str) -> str:
    """Aceita `'R1'` ou `'long_method'` e devolve o código canônico (`'R1'`)."""
    if smell in CODE_TO_NAME:
        return smell
    if smell in NAME_TO_CODE:
        return NAME_TO_CODE[smell]
    raise ValueError(f"Smell desconhecido: {smell!r}. Esperado um de "
                     f"{SMELL_CODES} ou {list(NAME_TO_CODE)}")


def to_name(smell: str) -> str:
    """Aceita `'R1'` ou `'long_method'` e devolve o nome do smell."""
    return CODE_TO_NAME[to_code(smell)]
