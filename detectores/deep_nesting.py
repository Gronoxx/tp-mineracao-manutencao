import ast
from .data_structs import FunctionInfo
from .base import DetectionResult

THRESHOLD = 3  # profundidade > 3 = smell

NESTING_NODES = (ast.If, ast.For, ast.While, ast.With, ast.Try,
                 ast.AsyncFor, ast.AsyncWith)

def _max_depth(node, current=0) -> int:
    
    if isinstance(node, NESTING_NODES):
        current += 1
        
    max_d = current
    
    for child in ast.iter_child_nodes(node):
        max_d = max(max_d, _max_depth(child, current))
        
    return max_d

def detect(fn: FunctionInfo) -> DetectionResult:
    
    try:
        tree = ast.parse(fn.source)
    except SyntaxError:
        return DetectionResult(smell="deep_nesting", detected=False, confidence=1.0, evidence={})

    # pega a FunctionDef dentro do parse (o source é só a função)
    func_node = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
        tree
    )
    depth = _max_depth(func_node)

    return DetectionResult(
        smell="deep_nesting",
        detected=depth > THRESHOLD,
        confidence=1.0,
        evidence={"max_depth": depth, "threshold": THRESHOLD},
    )