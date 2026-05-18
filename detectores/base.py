from dataclasses import dataclass, field

@dataclass
class DetectionResult:
    smell: str
    detected: bool
    confidence: float        # 0.0–1.0 (regras = 1.0 sempre)
    evidence: dict           # métricas que justificam a detecção
    # exemplos de evidence:
    # {"lines": 47, "threshold": 30}
    # {"params": 6, "threshold": 5}
    # {"literals": [{"value": 42, "lineno": 7}, ...]}
    # {"max_depth": 5, "threshold": 3}
    # {"dead": [{"type": "unreachable", "lineno": 12}, ...]}