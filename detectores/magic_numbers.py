"""Detector R3 — Magic Numbers (números mágicos).

Um número mágico é um literal numérico (int/float) embutido diretamente no
código sem ser atribuído a um nome significativo.

Strings NÃO são tratadas aqui; detecção de magic strings, se necessária, seria
um detector separado.

Regras de exemption (NÃO são magic numbers):
  1. Valores triviais: {0, 1, 2}  — convencionalmente aceitáveis.
  2. RHS direto de atribuição a nome:
       TIMEOUT = 30        (ast.Assign)
       TIMEOUT: int = 30   (ast.AnnAssign)
     Só quando o valor da atribuição é exatamente o literal (ou `-literal`).
     Literais aninhados em expressões NÃO são isentos: `x = 86400 * 2`.
  3. Valor padrão de parâmetro de função:
       def f(timeout=30): ...
       def f(*, retries=3): ...
"""

import ast
from .data_structs import FunctionInfo
from .base import DetectionResult

NUMERIC_WHITELIST: frozenset = frozenset({0, 1, 2})


def _collect_exempt_ids(tree: ast.AST) -> set:
    """Retorna o conjunto de id() dos nós Constant numéricos que são isentos."""
    exempt = set()

    for node in ast.walk(tree):

        # --- Atribuição simples: NOME = literal  ou  NOME = -literal ---
        if isinstance(node, ast.Assign):
            val = node.value
            # desembrulha -literal
            if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub):
                val = val.operand
            if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)):
                exempt.add(id(val))

        # --- Atribuição anotada: NOME: tipo = literal  ou  = -literal ---
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                val = node.value
                if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub):
                    val = val.operand
                if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)):
                    exempt.add(id(val))

        # --- Defaults de parâmetros posicionais e keyword-only ---
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults:
                d = default
                if isinstance(d, ast.UnaryOp) and isinstance(d.op, ast.USub):
                    d = d.operand
                if isinstance(d, ast.Constant) and isinstance(d.value, (int, float)):
                    exempt.add(id(d))
            for default in node.args.kw_defaults:
                if default is None:
                    continue
                d = default
                if isinstance(d, ast.UnaryOp) and isinstance(d.op, ast.USub):
                    d = d.operand
                if isinstance(d, ast.Constant) and isinstance(d.value, (int, float)):
                    exempt.add(id(d))

    return exempt


def detect(fn: FunctionInfo) -> DetectionResult:
    try:
        tree = ast.parse(fn.source)
    except SyntaxError:
        return DetectionResult(smell="magic_numbers", detected=False,
                               confidence=1.0, evidence={})

    exempt_ids = _collect_exempt_ids(tree)

    magic_numbers = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))):
            continue
        if node.value in NUMERIC_WHITELIST:
            continue
        if id(node) in exempt_ids:
            continue
        magic_numbers.append({"value": node.value, "lineno": node.lineno})

    return DetectionResult(
        smell="magic_numbers",
        detected=len(magic_numbers) > 0,
        confidence=1.0,
        evidence={"magic_numbers": magic_numbers},
    )
