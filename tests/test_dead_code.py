"""Testes do detector de dead code — `detectores/dead_code.py` (F6).

`_find_unreachable` assumia que `node.body`/`orelse`/`finalbody` eram sempre
listas de statements; em `IfExp` (ternário) e `Lambda` são um nó de expressão
único → `TypeError: 'Call' object is not iterable`, que derrubava `mine()`.
"""
from core.ast_types import FunctionInfo
from detectores.dead_code import _find_unreachable, detect


def _fn(source: str) -> FunctionInfo:
    return FunctionInfo(name="f", lineno=1, end_lineno=1, source=source, params=[])


def test_find_unreachable_nao_quebra_com_ternario():
    """F6 — `IfExp.body` é um nó único (aqui um Call), não uma lista."""
    src = "def f(x):\n    y = g() if x else h()\n    return y\n"
    assert _find_unreachable(src) == []


def test_find_unreachable_nao_quebra_com_lambda():
    """F6 — `Lambda.body` também é um nó de expressão único."""
    src = "def f():\n    cb = lambda a: a + 1\n    return cb(2)\n"
    assert _find_unreachable(src) == []


def test_find_unreachable_detecta_codigo_apos_return():
    dead = _find_unreachable("def f():\n    return 1\n    x = 2\n")
    assert len(dead) == 1 and dead[0]["type"] == "unreachable"


def test_find_unreachable_codigo_vivo_sem_dead_code():
    src = "def f(x):\n    if x:\n        return 1\n    return 2\n"
    assert _find_unreachable(src) == []


def test_detect_sobrevive_a_ternario():
    """O detector completo não pode quebrar num par com ternário (regressão F6)."""
    res = detect(_fn("def f(x):\n    return 1 if x else 2\n"))
    assert res.smell == "dead_code" and res.detected is False
