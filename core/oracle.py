"""Catálogo de oracles externos (held-out test set) — D5 do sprint.

`OracleEntry` é um registro **metadata-only** de uma refatoração identificada
por uma fonte externa (PyRef, Sourcery, ActRef, etc.). NÃO contém código
before/after; serve como índice para:

  - extração posterior do código via nosso pipeline (Dia 3 do sprint —
    "adjacent mining"), produzindo `RefactoringPair` com `source="adjacent_oracle"`;
  - avaliação do modelo treinado contra um conjunto cuja origem é
    verificável e separada do treino.

Mantemos `OracleEntry` em arquivo distinto de `RefactoringPair` porque os
campos obrigatórios divergem: o `RefactoringPair` exige `before_code` /
`after_code` (par real), enquanto o catálogo só tem ponteiros (`repo`,
`commit_hash`) + metadados da fonte.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .smells import SmellType

OracleSource = Literal["pyref", "sourcery", "actref", "swe_refactor", "marv"]
Validation = Literal["TP", "FP", "CTP", "unknown"]


class OracleEntry(BaseModel):
    """Entrada do catálogo de oracles externos — ponteiro para uma refatoração.

    Fields mínimos para localizar a refatoração + mapeamento opcional para os
    códigos R1..R5 do TP. Quando a refatoração do oracle não tem correspondente
    direto entre os 5 smells (ex.: "Rename Method"), `smell_type` fica `None`
    e o registro serve só como referência bibliográfica.
    """

    # --- origem ---
    source_dataset: OracleSource              # PyRef, Sourcery, ActRef, ...
    external_refactoring_type: str            # tipo na taxonomia da fonte
    validation: Validation = "unknown"        # TP/FP conforme a fonte

    # --- localização ---
    repo: str                                  # URL ou owner/repo
    commit_hash: Optional[str] = None
    file: Optional[str] = None
    function_name: Optional[str] = None

    # --- mapeamento para o TP ---
    smell_type: Optional[SmellType] = None    # R1..R5 (None se não mapeia)

    # --- contexto ---
    description: Optional[str] = None
    tool: Optional[str] = None                 # ferramenta de detecção original
    notes: Optional[str] = None
    extra: dict = Field(default_factory=dict)
