import ast
import lizard
from .data_structs import FunctionInfo
from .base import DetectionResult

# Limiares default. Mantêm o comportamento histórico do detector:
# `stmt_threshold=None` desativa a checagem por número de statements, de modo
# que `detect(fn)` (sem params) é idêntico à versão pré-parametrização. Quem
# quiser varrer o limiar de statements (p.ex. o estudo de calibração) passa um
# inteiro explícito em `params`.
DEFAULT_PARAMS = {
    "line_threshold": 75,    # linhas lógicas (lizard nloc)
    "stmt_threshold": 35,    # statements (Pylint R0915 usa 50); None = desativado
    "ccn_threshold": 25,     # complexidade ciclomática (McCabe = 10)
}


def _count_statements(source: str) -> int:
    """Conta os statements do corpo da função (proxy do Pylint R0915).

    Lizard não expõe contagem de statements, então usamos o `ast`: contamos os
    nós-statement alcançáveis a partir da `FunctionDef` (inclui aninhados) e
    descontamos o próprio `def`. Retorna 0 se o source não parsear.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if fn is None:
        return 0
    return sum(1 for n in ast.walk(fn) if isinstance(n, ast.stmt)) - 1


def detect(fn: FunctionInfo, params: dict | None = None) -> DetectionResult:
    p = {**DEFAULT_PARAMS, **(params or {})}

    # Lizard analisa a string de source diretamente
    result = lizard.analyze_file.analyze_source_code(
        fn.name + ".py", fn.source
    )

    if not result.function_list:
        # fallback: contar linhas brutas
        loc = fn.end_lineno - fn.lineno + 1

        return DetectionResult(
            smell="long_method",
            detected=loc > p["line_threshold"],
            confidence=1.0,
            evidence={"lines_fallback": loc, "threshold": p["line_threshold"], "params": p},
        )

    func = result.function_list[0]
    n_stmts = _count_statements(fn.source)
    detected = (
        func.nloc > p["line_threshold"]
        or func.cyclomatic_complexity > p["ccn_threshold"]
        or (p["stmt_threshold"] is not None and n_stmts > p["stmt_threshold"])
    )

    return DetectionResult(
        smell="long_method",
        detected=detected,
        confidence=1.0,
        evidence={
            "lines_of_code": func.nloc,
            "complexidade_ciclomatica": func.cyclomatic_complexity,
            "n_statements": n_stmts,
            "line_threshold": p["line_threshold"],
            "stmt_threshold": p["stmt_threshold"],
            "complexidade_threshold": p["ccn_threshold"],
            "params": p,
        },
    )
