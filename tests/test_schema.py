"""Testes do schema unificado — `core/schema.py`.

Foco: o `id` gerado por `_fill_id()` (F4 — o hash deve incluir `smell_type`)
e o campo `source` (D5 — proveniência do par para separar train/test).
"""
import pytest
from pydantic import ValidationError

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


# --- D5: campo `source` (proveniência do par) ---

def test_source_default_e_mined_commit():
    """Sem `source` explícito, o default é `mined_commit` — preserva
    compatibilidade com fixtures antigas e os 400 pares minerados antes
    do sprint."""
    p = RefactoringPair(smell_type="R1", **_BASE)
    assert p.source == "mined_commit"


def test_source_aceita_outros_valores():
    """Os 4 valores válidos correspondem aos Caminhos do sprint: commit
    individual, PR colapsado (C2), commit adjacente a oracle (C3),
    tradução Java→Python (C4)."""
    for value in ("mined_commit", "mined_pr", "adjacent_oracle", "translated_java"):
        p = RefactoringPair(smell_type="R1", source=value, **_BASE)
        assert p.source == value


def test_source_invalido_rejeitado():
    """Pydantic rejeita valores fora do Literal — guard contra typos
    silenciosos que poderiam misturar train e test."""
    with pytest.raises(ValidationError):
        RefactoringPair(smell_type="R1", source="foobar", **_BASE)
