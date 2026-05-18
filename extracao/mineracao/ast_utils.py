import ast

from .data_structs import ClassInfo, FunctionInfo

def _extract_source(lines: list[str], node) -> str:
    # ast fornece lineno e end_lineno (1-indexed)
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])

def _extract_bases(node: ast.ClassDef) -> list[str]:
    # Serializa cada base como string — cobre ast.Name, ast.Attribute (module.Bar),
    # ast.Subscript (Generic[T]) e qualquer outra forma sem perda silenciosa
    return [ast.unparse(base) for base in node.bases]

def _extract_params(node) -> list[str]:
    # Coleta o conjunto completo de parâmetros, excluindo self/cls
    args = node.args
    params = (
        [a.arg for a in args.args]                      # posicionais normais
        + [a.arg for a in args.kwonlyargs]              # keyword-only (após *)
        + ([args.vararg.arg] if args.vararg else [])    # *args
        + ([args.kwarg.arg] if args.kwarg else [])      # **kwargs
    )
    return [p for p in params if p not in ("self", "cls")]

def extract_nodes(tree, lines) -> dict:
    
    functions = []
    classes = []
    
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # função top-level
            fi = FunctionInfo(
                name=node.name,
                lineno=node.lineno,
                end_lineno=node.end_lineno,
                source=_extract_source(lines, node),
                params=_extract_params(node),
            )
            functions.append(fi)
        
        elif isinstance(node, ast.ClassDef):
            # classe: extrair métodos com ast.iter_child_nodes(node)
            methods = []
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mi = FunctionInfo(
                        name=child.name,
                        lineno=child.lineno,
                        end_lineno=child.end_lineno,
                        source=_extract_source(lines, child),
                        params=_extract_params(child),
                        owner_class=node.name,
                    )
                    methods.append(mi)
            
            ci = ClassInfo(
                name=node.name,
                lineno=node.lineno,
                end_lineno=node.end_lineno,
                source=_extract_source(lines, node),
                methods=methods,
                bases=_extract_bases(node),
            )
            classes.append(ci)
    
    return {"functions": functions, "classes": classes}

def parse_file(filepath: str) -> dict:
    
    """
    Args: file's path
    Retorna:
    {
      "functions": [FunctionInfo, ...],   # functions
      "classes": [ClassInfo, ...],        # classes and methods
    }
    """
    
    with open(filepath, encoding="utf-8") as f:
        source_code = f.read()
    
        lines = source_code.splitlines()
        tree = ast.parse(source_code, filename=filepath)
        
        return extract_nodes(tree, lines)
    
def parse_file_from_string(source: str, filename: str = "<string>") -> dict:
    
    """
    Args: code string
    Retorna:
    {
      "functions": [FunctionInfo, ...],   # functions
      "classes": [ClassInfo, ...],        # classes and methods
    }
    """
    
    lines = source.splitlines()
    tree = ast.parse(source, filename=filename)
    
    return extract_nodes(tree, lines)