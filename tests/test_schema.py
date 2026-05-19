"""Testes do schema unificado — `core/schema.py`.

Foco: o `id` gerado por `_fill_id()` (F4 — o hash deve incluir `smell_type`).
"""
from core.schema import RefactoringPair

# Núcleo de par idêntico, reutilizado entre os casos.
_BASE = dict(
    before_code="def f():\n    x = 1\n    return x\n",
    after_code="def f():\n    return 1\n",
    repo="https://github.com/exemplo/repo",
    commit_hash="abc123",
    file="modulo.py",
    function_name="f",
)


def test_id_estavel_para_entradas_iguais():
    a = RefactoringPair(smell_type="R1", **_BASE)
    b = RefactoringPair(smell_type="R1", **_BASE)
    assert a.id == b.id and a.id is not None


def test_id_difere_quando_so_o_smell_type_muda():
    """F4 — o mesmo trecho before/after verificado para 2 smells distintos
    precisa de ids distintos, senão um par sobrescreve o outro na dedup."""
    r1 = RefactoringPair(smell_type="R1", **_BASE)
    r4 = RefactoringPair(smell_type="R4", **_BASE)
    assert r1.id != r4.id


def test_id_difere_quando_o_codigo_muda():
    a = RefactoringPair(smell_type="R1", **_BASE)
    variante = dict(_BASE, after_code="def f():\n    return 2\n")
    b = RefactoringPair(smell_type="R1", **variante)
    assert a.id != b.id


def test_id_explicito_e_preservado():
    p = RefactoringPair(smell_type="R1", id="id-fixo-123", **_BASE)
    assert p.id == "id-fixo-123"
