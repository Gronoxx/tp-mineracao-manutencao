import lizard
from .data_structs import FunctionInfo
from .base import DetectionResult

LINE_THRESHOLD = 30       # linhas lógicas
STMT_THRESHOLD = 15       # statements (Pylint R0915 usa 50, mas 15 é mais restrito)
CCN_THRESHOLD  = 10       # complexidade ciclomática (McCabe)

def detect(fn: FunctionInfo) -> DetectionResult:
    
    # Lizard analisa a string de source diretamente
    
    result = lizard.analyze_file.analyze_source_code(
        fn.name + ".py", fn.source
    )

    if not result.function_list:
        # fallback: contar linhas brutas
        loc = fn.end_lineno - fn.lineno + 1
        
        return DetectionResult(
            smell="long_method",
            detected=loc > LINE_THRESHOLD,
            confidence=1.0,
            evidence={"lines_fallback": loc, "threshold": LINE_THRESHOLD},
        )

    func = result.function_list[0]
    detected = (
        func.nloc > LINE_THRESHOLD or
        func.cyclomatic_complexity > CCN_THRESHOLD
    )
    
    return DetectionResult(
        smell="long_method",
        detected=detected,
        confidence=1.0,
        evidence={
            "lines_of_code": func.nloc,
            "complexidade_ciclomatica": func.cyclomatic_complexity,
            "line_threshold": LINE_THRESHOLD,
            "complexidade_threshold": CCN_THRESHOLD,
        },
    )