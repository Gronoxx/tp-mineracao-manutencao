import ast
import subprocess
import tempfile
import os
from .data_structs import FunctionInfo
from .base import DetectionResult

def _find_unreachable(fn_source: str) -> list[dict]:
    
    """Encontra statements após return/raise no mesmo bloco."""
    
    try:
        tree = ast.parse(fn_source)
    except SyntaxError:
        return []

    dead = []
    for node in ast.walk(tree):
        # itera sobre listas de statements (body, orelse, handlers, etc.)
        
        for stmts in [getattr(node, "body", []),
                      getattr(node, "orelse", []),
                      getattr(node, "finalbody", [])]:
            
            terminal_seen = False
            
            for stmt in stmts:
                if terminal_seen:
                    dead.append({"type": "unreachable", "lineno": stmt.lineno})
                    
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    terminal_seen = True
                    
    return dead

def _find_unused_vars(fn_source: str) -> list[dict]:
    
    """Usa vulture para detectar variáveis atribuídas mas não usadas."""
    
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(fn_source)
        tmp = f.name
        
    try:
        
        out = subprocess.run(
            ["vulture", tmp, "--min-confidence", "80"],
            capture_output=True, text=True
        )
        unused = []
        
        for line in out.stdout.splitlines():
            
            if "unused variable" in line:
                # formato: "file.py:10: unused variable 'x' (80% confidence)"
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        unused.append({"type": "unused_var", "lineno": int(parts[1])})
                    except ValueError:
                        pass
        return unused
    
    finally:
        os.unlink(tmp)

def detect(fn: FunctionInfo) -> DetectionResult:
    
    dead = _find_unreachable(fn.source) + _find_unused_vars(fn.source)
    
    return DetectionResult(
        smell="dead_code",
        detected=len(dead) > 0,
        confidence=1.0,
        evidence={"dead_code": dead},
    )