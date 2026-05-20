"""Testes de `behavioral_check` (C5c.4 — Dia 9 do sprint).

Cobertura: pares equivalentes (todos casam), pares divergentes (output
diferente), pares cuja assinatura difere, código que falha em parsear.
"""
from extracao.mineracao.behavioral_check import (
    BehavioralCheckResult,
    behavioral_check,
)


def test_pares_identicos_passam():
    src = "def f(x):\n    return x + 1\n"
    r = behavioral_check(src, src, n_samples=5)
    assert r.equivalent is True
    assert r.n_matching == r.n_samples > 0


def test_pares_divergentes_falham():
    """Funções que retornam valores diferentes para a mesma entrada."""
    a = "def f(x):\n    return x + 1\n"
    b = "def g(x):\n    return x + 2\n"
    r = behavioral_check(a, b, n_samples=10)
    assert r.equivalent is False
    # Pelo menos algumas amostras retornam (não levantam) → diferenças contadas
    assert r.n_different_output + r.n_matching > 0


def test_dead_code_removal_e_equivalente():
    """Remoção de variáveis mortas preserva semântica."""
    before = (
        "def f(x, y):\n"
        "    dead1 = x + y\n"
        "    dead2 = x * y\n"
        "    return x ** 2 + y ** 2\n"
    )
    after = "def f(x, y):\n    return x ** 2 + y ** 2\n"
    r = behavioral_check(before, after, n_samples=8)
    assert r.equivalent is True
    assert r.n_matching > 0


def test_funcao_sem_params_um_sample():
    """`f()` sem parâmetros — só um chamado faz sentido."""
    a = "def f():\n    return 42\n"
    b = "def g():\n    return 42\n"
    r = behavioral_check(a, b, n_samples=5)
    assert r.n_samples == 1
    assert r.equivalent is True


def test_uma_levanta_outra_nao_nao_e_equivalente():
    """Comportamento divergente sob exceção é flag de não-equivalência."""
    safe = "def f(x):\n    return x or 0\n"
    crashy = "def g(x):\n    return 1 / x\n"   # x=0 ou x=None → exception
    r = behavioral_check(safe, crashy, n_samples=15)
    assert r.equivalent is False
    # Esperamos pelo menos uma divergência por exceção (x=0, x=None).
    assert r.n_one_raised + r.n_different_output > 0


def test_codigo_invalido_retorna_erro():
    r = behavioral_check("def f(): return 1\n", "lixo ((( ", n_samples=3)
    assert r.equivalent is False
    assert r.n_samples == 0
    assert "failed to compile" in (r.error_msg or "")


def test_resultado_tem_estrutura_documentada():
    """Sanity: dataclass tem os campos esperados."""
    r = behavioral_check("def f(x): return x\n", "def g(x): return x\n", n_samples=3)
    assert isinstance(r, BehavioralCheckResult)
    assert hasattr(r, "equivalent")
    assert hasattr(r, "n_samples")
    assert hasattr(r, "n_matching")
    assert hasattr(r, "n_one_raised")
    assert hasattr(r, "n_different_output")
