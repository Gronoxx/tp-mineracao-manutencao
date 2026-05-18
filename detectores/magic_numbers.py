import ast
from .data_structs import FunctionInfo
from .base import DetectionResult

# Valores que NÃO são magic numbers — não reportar
NUMERIC_WHITELIST = {0, 1, -1, 2, 100, 1000}
STRING_WHITELIST  = {"", " ", "\n", "\t", "utf-8", "utf8", "ascii"}

# Strings que são podem ser códigos de protocolo — não reportar
HTTP_CODES = {str(c) for c in range(100, 600)}

def detect(fn: FunctionInfo) -> DetectionResult:
    try:
        tree = ast.parse(fn.source)
    except SyntaxError:
        return DetectionResult(smell="magic_numbers", detected=False,
                               confidence=1.0, evidence={})

    magic_constants = []
    for node in ast.walk(tree):
        
        # Números
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if node.value not in NUMERIC_WHITELIST:
                magic_constants.append({"type": "number", "value": node.value,
                                  "lineno": node.lineno})
                
        # Strings (ignora docstrings — primeiro statement de função/classe)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            
            if (node.value not in STRING_WHITELIST and
                    node.value not in HTTP_CODES and
                    len(node.value) > 1):  # ignora chars únicos
                
                magic_constants.append({"type": "string", "value": repr(node.value)[:40],
                                  "lineno": node.lineno})

    return DetectionResult(
        smell="magic_numbers",
        detected=len(magic_constants) > 0,
        confidence=1.0,
        evidence={"magic_numbers": magic_constants},
    )