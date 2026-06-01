import lizard
from .data_structs import FunctionInfo
from .base import DetectionResult

DEFAULT_THRESHOLDS = {
    "lines": 30,
    "stmt": 15,
    "ccn": 10
}

LINE_THRESHOLD = 30       # linhas lógicas
STMT_THRESHOLD = 15       # statements (Pylint R0915 usa 50, mas 15 é mais restrito)
CCN_THRESHOLD  = 10       # complexidade ciclomática (McCabe)

def detect(fn: FunctionInfo, thresholds = DEFAULT_THRESHOLDS) -> DetectionResult:
    
    # Lizard analisa a string de source diretamente
    
    result = lizard.analyze_file.analyze_source_code(
        fn.name + ".py", fn.source
    )

    if not result.function_list:
        # fallback: contar linhas brutas
        loc = fn.end_lineno - fn.lineno + 1
        
        return DetectionResult(
            smell="long_method",
            detected=loc > thresholds.get("lines"),
            confidence=1.0,
            evidence={"lines_fallback": loc, "threshold": thresholds.get("lines")},
        )

    func = result.function_list[0]
    detected = (
        func.nloc > thresholds.get("lines") or
        func.cyclomatic_complexity > thresholds.get("ccn")
    )
    
    return DetectionResult(
        smell="long_method",
        detected=detected,
        confidence=1.0,
        evidence={
            "lines_of_code": func.nloc,
            "complexidade_ciclomatica": func.cyclomatic_complexity,
            "line_threshold": thresholds.get("lines"),
            "complexidade_threshold": thresholds.get("cnn"),
        },
    )