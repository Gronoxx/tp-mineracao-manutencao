"""Shim de compatibilidade — o schema foi unificado em `core/schema.py`
(D-DEV-18, contrato A↔B). Mantido como re-export; será removido num ciclo
futuro. Quem importa `schema` continua funcionando sem alteração."""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.schema import RefactoringPair, ReviewBlock, SmellType  # noqa: E402,F401
