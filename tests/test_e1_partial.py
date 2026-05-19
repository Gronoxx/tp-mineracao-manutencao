"""Testes da verificação permissiva (E1) — `partial_threshold` em `verify_pair`.

Modo estrito (default): só aceita pares cujo detector dispara no `before` e
NÃO dispara no `after`. Modo permissivo (`partial_threshold=0.5`): também
aceita pares em que o detector ainda dispara no `after` mas com magnitude
reduzida em pelo menos 50% — marcados `partial=True`.
"""
import pytest

from core.schema import RefactoringPair
from extracao.mineracao import minerador


# ── _magnitude — extração da magnitude por smell ────────────────────────────

class _Res:
    def __init__(self, detected: bool, evidence: dict):
        self.detected, self.evidence = detected, evidence


def test_magnitude_long_method_usa_lines_of_code():
    assert minerador._magnitude(_Res(True, {"lines_of_code": 80}), "long_method") == 80.0


def test_magnitude_long_method_cai_para_lines_fallback():
    assert minerador._magnitude(_Res(True, {"lines_fallback": 45}), "long_method") == 45.0


def test_magnitude_long_param_list_usa_count():
    assert minerador._magnitude(_Res(True, {"count": 7}), "long_param_list") == 7.0


def test_magnitude_magic_numbers_conta_a_lista():
    res = _Res(True, {"magic_numbers": [{"value": 86400}, {"value": 24}, {"value": 100}]})
    assert minerador._magnitude(res, "magic_numbers") == 3.0


def test_magnitude_deep_nesting_usa_max_depth():
    assert minerador._magnitude(_Res(True, {"max_depth": 5}), "deep_nesting") == 5.0


def test_magnitude_dead_code_conta_a_lista():
    res = _Res(True, {"dead_code": [{"type": "unused_var", "lineno": 3}]})
    assert minerador._magnitude(res, "dead_code") == 1.0


def test_magnitude_evidencia_vazia_eh_zero():
    assert minerador._magnitude(_Res(True, {}), "magic_numbers") == 0.0


# ── verify_pair em modo estrito vs permissivo ───────────────────────────────

class _FakeFn:
    def __init__(self, source: str):
        self.source = source


def _candidate(before="def f(x): return x * 86400 * 24 * 7\n",
               after="def f(x): return x * 86400\n", helpers=None):
    return {
        "function_name": "f",
        "before_fn": _FakeFn(before),
        "after_fn": _FakeFn(after),
        "helper_sources": helpers or [],
    }


def _verify(cand, **kwargs):
    return minerador.verify_pair(
        cand, repo="r", commit_hash="c", parent_commit=None,
        commit_msg="refactor: named constant", msg_keywords=["refactor"],
        filename="m.py", **kwargs,
    )


def _fake_detector_magic(mag_before: int, mag_after: int):
    """Detector falso que vê N magic numbers no before e M no after.
    Usa o número de `*` na fonte como proxy — o teste controla N via fonte."""
    def detector(fn):
        n = fn.source.count("*")
        return _Res(detected=(n > 0),
                    evidence={"magic_numbers": [{}] * n})
    return detector


def test_modo_estrito_rejeita_par_partial(monkeypatch):
    """Sem `partial_threshold`, refactor parcial (4 → 1 magic) é descartado."""
    det = _fake_detector_magic(4, 1)
    monkeypatch.setattr(minerador, "DETECTORS", {"magic_numbers": det})
    # before = 4 magic, after = 1 magic — ambos disparam
    cand = _candidate(before="def f(): return 1*2*3*4\n",
                      after="def f(): return X*1\n")
    assert _verify(cand) == []   # estrito: descarta


def test_modo_permissivo_aceita_reducao_de_75_por_cento(monkeypatch):
    """4 → 1 magic = 75% de redução; aceita com threshold 0.5."""
    det = _fake_detector_magic(4, 1)
    monkeypatch.setattr(minerador, "DETECTORS", {"magic_numbers": det})
    cand = _candidate(before="def f(): return 1*2*3*4\n",
                      after="def f(): return X*1\n")
    records = _verify(cand, partial_threshold=0.5)
    assert len(records) == 1
    assert records[0].smell_type == "R3" and records[0].partial is True


def test_modo_permissivo_rejeita_reducao_insuficiente(monkeypatch):
    """4 → 3 magic = 25% de redução; rejeitado com threshold 0.5."""
    det = _fake_detector_magic(4, 3)
    monkeypatch.setattr(minerador, "DETECTORS", {"magic_numbers": det})
    cand = _candidate(before="def f(): return 1*2*3*4\n",
                      after="def f(): return 1*2*3\n")
    assert _verify(cand, partial_threshold=0.5) == []


def test_modo_permissivo_par_estrito_marca_partial_false(monkeypatch):
    """Quando o after não dispara (estrito), `partial=False` mesmo no modo permissivo."""
    det = _fake_detector_magic(4, 0)
    monkeypatch.setattr(minerador, "DETECTORS", {"magic_numbers": det})
    cand = _candidate(before="def f(): return 1*2*3*4\n",
                      after="def f(): return X\n")
    records = _verify(cand, partial_threshold=0.5)
    assert len(records) == 1 and records[0].partial is False


def test_modo_permissivo_threshold_zero_aceita_qualquer_reducao(monkeypatch):
    """`threshold=0.0` (limite extremo): aceita qualquer redução > 0."""
    det = _fake_detector_magic(4, 3)
    monkeypatch.setattr(minerador, "DETECTORS", {"magic_numbers": det})
    cand = _candidate(before="def f(): return 1*2*3*4\n",
                      after="def f(): return 1*2*3\n")
    # 4 → 3: mag_a (3) <= mag_b * (1 - 0.0) = 4? Sim. Mas mag_a > mag_b * 1 = 4 é
    # falso; 3 <= 4 é verdadeiro. Aceita.
    records = _verify(cand, partial_threshold=0.0)
    assert len(records) == 1 and records[0].partial is True


# ── R1 helper-check (F3) continua valendo no modo permissivo ────────────────

def test_r1_partial_ainda_exige_helper_extraido(monkeypatch):
    """Mesmo em modo permissivo, R1 sem helper não é Extract Method."""
    # detector long_method que devolve magnitude reduzida (80 → 30 LOC)
    def long(fn):
        loc = fn.source.count("\n") + 1
        return _Res(detected=(loc > 30),
                    evidence={"lines_of_code": loc})
    monkeypatch.setattr(minerador, "DETECTORS", {"long_method": long})
    cand = _candidate(
        before="def f():\n" + "    x = 1\n" * 80 + "    return x\n",
        after="def f():\n" + "    y = 2\n" * 35 + "    return y\n",
        helpers=[],   # sem helper extraído
    )
    # 81 → 36 LOC (≈55% de redução): aceita como partial — mas R1 sem helper rejeita
    assert _verify(cand, partial_threshold=0.5) == []


# ── Schema: o campo `partial` round-trips ───────────────────────────────────

def test_schema_partial_default_false():
    p = RefactoringPair(before_code="def f(): pass", after_code="def f(): return 1",
                        smell_type="R3", repo="r", commit_hash="c")
    assert p.partial is False


def test_schema_partial_explicito_true():
    p = RefactoringPair(before_code="def f(): pass", after_code="def f(): return 1",
                        smell_type="R3", repo="r", commit_hash="c", partial=True)
    assert p.partial is True
