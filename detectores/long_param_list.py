from .data_structs import FunctionInfo
from .base import DetectionResult

THRESHOLD = 5  # >5 parâmetros = smell

def detect(fn: FunctionInfo) -> DetectionResult:
    
    count = len(fn.params)
    
    return DetectionResult(
        smell="long_param_list",
        detected=count > THRESHOLD,
        confidence=1.0,
        evidence={"params": fn.params, "count": count, "threshold": THRESHOLD},
    )