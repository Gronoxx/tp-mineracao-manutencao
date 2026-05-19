"""Configuração do pytest — garante a raiz do repo em `sys.path`.

Os pacotes `core/` e `detectores/` e os namespace-packages `extracao/` e
`trilha_b/` são importáveis a partir da raiz do repositório. Este conftest
na raiz faz o pytest prependar a raiz em `sys.path` para toda a suíte.
"""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
