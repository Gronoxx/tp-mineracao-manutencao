"""Resiliência do `verify_pair` — um detector que crashe não pode derrubar
a corrida de produção. Plano 3.

Um detector pode crashar num input incomum (ex.: F6 era exatamente isso —
ternário em IfExp.body quebrava o `dead_code` antes do PR #14). Numa corrida
overnight, isso não pode jogar fora horas de mineração. `verify_pair` agora
captura exceções por-detector: o smell que crashou é pulado, os outros 4
continuam.
"""
from extracao.mineracao import minerador


class _FakeRes:
    def __init__(self, detected: bool):
        self.detected = detected
        self.evidence = {}


class _FakeFn:
    def __init__(self, source: str):
        self.source = source


def _candidate():
    return {
        "function_name": "f",
        "before_fn": _FakeFn("def f():\n    pass\n"),
        "after_fn": _FakeFn("def f():\n    return 1\n"),
        "helper_sources": [],
    }


def _verify(cand, **kwargs):
    return minerador.verify_pair(
        cand, repo="r", commit_hash="c", parent_commit=None,
        commit_msg="m", msg_keywords=[], filename="f.py", **kwargs,
    )


def _bom(fn):
    """Detector que sempre dispara no before e nunca no after — gera 1 par."""
    return _FakeRes(True) if "pass" in fn.source else _FakeRes(False)


def _explode(fn):
    """Detector que crasha em qualquer input — simula bug latente."""
    raise RuntimeError("detector com bug latente")


def test_verify_pair_sobrevive_a_detector_que_crasha(monkeypatch, capsys):
    """Um detector que levanta exceção é pulado; os outros continuam."""
    monkeypatch.setattr(minerador, "DETECTORS",
                        {"deep_nesting": _bom, "magic_numbers": _explode})
    records = _verify(_candidate())
    # `deep_nesting` (R4) produz 1 par; `magic_numbers` (R3) crashou e foi pulado.
    assert len(records) == 1 and records[0].smell_type == "R4"
    # E ainda loga a falha (visível pra debugging).
    out = capsys.readouterr().out
    assert "magic_numbers" in out and "RuntimeError" in out


def test_verify_pair_dois_detectores_crasham_nao_perdem_o_terceiro(monkeypatch):
    """Múltiplas falhas: nenhuma derruba os bons."""
    monkeypatch.setattr(minerador, "DETECTORS", {
        "long_method": _explode,        # R1
        "long_param_list": _explode,    # R2
        "deep_nesting": _bom,           # R4 -> emite
    })
    records = _verify(_candidate())
    assert len(records) == 1 and records[0].smell_type == "R4"


def test_verify_pair_todos_crasham_retorna_vazio(monkeypatch):
    """Caso degenerado: todo detector crasha -> records vazio, sem exceção."""
    monkeypatch.setattr(minerador, "DETECTORS", {
        "deep_nesting": _explode, "magic_numbers": _explode,
    })
    assert _verify(_candidate()) == []
