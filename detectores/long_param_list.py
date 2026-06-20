from .data_structs import FunctionInfo
from .base import DetectionResult

DEFAULT_PARAMS = {
    "max_params": 5,  # >5 parâmetros = smell
}

def detect(fn: FunctionInfo, params: dict | None = None) -> DetectionResult:
    p = {**DEFAULT_PARAMS, **(params or {})}

    count = len(fn.params)

    return DetectionResult(
        smell="long_param_list",
        detected=count > p["max_params"],
        confidence=1.0,
        evidence={"params": fn.params, "count": count, "threshold": p["max_params"]},
    )
