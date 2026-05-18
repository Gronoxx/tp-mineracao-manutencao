"""Shim de compatibilidade — os tipos foram unificados em `core/ast_types.py`
(D-DEV-18). Mantido como re-export; será removido num ciclo futuro."""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.ast_types import ClassInfo, FunctionInfo  # noqa: E402,F401
