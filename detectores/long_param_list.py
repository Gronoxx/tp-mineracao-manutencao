from .data_structs import FunctionInfo
from .base import DetectionResult

DEFAULT_THRESHOLD = 5  # >5 parâmetros = smell

def detect(fn: FunctionInfo, threshold = DEFAULT_THRESHOLD) -> DetectionResult:
    
    count = len(fn.params)
    
    return DetectionResult(
        smell="long_param_list",
        detected=count > threshold,
        confidence=1.0,
        evidence={"params": fn.params, "count": count, "threshold": threshold},
    )