"""Pacote `core/` — contrato compartilhado entre as trilhas A e B (D-DEV-18).

Reúne, num único lugar, o que antes estava duplicado ou divergente:
- `smells`     : vocabulário canônico dos smells/refatorações (R1–R5).
- `ast_types`  : `FunctionInfo`/`ClassInfo` (antes duplicados em
                 `extracao/mineracao/data_structs.py` e `detectores/data_structs.py`).
- `schema`     : `RefactoringPair` — o registro que cruza a fronteira A↔B.
"""
from .smells import (  # noqa: F401
    SMELL_CODES,
    SmellType,
    CODE_TO_NAME,
    NAME_TO_CODE,
    REFACTORING,
    DETECTION_ONLY,
    to_code,
)
from .ast_types import ClassInfo, FunctionInfo  # noqa: F401
from .schema import RefactoringPair, ReviewBlock  # noqa: F401
