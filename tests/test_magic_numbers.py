"""Testes do detector R3 — Magic Numbers (F7).

Cobre as regras de exemption e os casos de falso-positivo que causavam
over-fire (F7): constantes nomeadas e strings (incluindo docstrings) eram
incorretamente sinalizadas.
"""
import pytest
from core.ast_types import FunctionInfo
from detectores.magic_numbers import detect


def _fn(source: str) -> FunctionInfo:
    return FunctionInfo(name="f", lineno=1, end_lineno=1, source=source, params=[])


# ---------------------------------------------------------------------------
# Casos que DEVEM ser detectados
# ---------------------------------------------------------------------------

def test_numero_inline_detectado():
    """Literal numérico em expressão aritmética → magic number."""
    src = "def f(x):\n    return x * 86400\n"
    result = detect(_fn(src))
    assert result.detected is True
    values = [e["value"] for e in result.evidence["magic_numbers"]]
    assert 86400 in values


def test_literal_em_expressao_binaria_detectado():
    """x = 86400 * 2 — 86400 é magic (não é o RHS inteiro)."""
    src = "def f():\n    x = 86400 * 2\n    return x\n"
    result = detect(_fn(src))
    assert result.detected is True
    values = [e["value"] for e in result.evidence["magic_numbers"]]
    assert 86400 in values


def test_negativo_5_detectado():
    """-5 em expressão de retorno deve ser detectado."""
    src = "def f():\n    return -5\n"
    result = detect(_fn(src))
    assert result.detected is True
    values = [e["value"] for e in result.evidence["magic_numbers"]]
    assert 5 in values  # ast.walk vê Constant(5), não -5


# ---------------------------------------------------------------------------
# Casos que NÃO devem ser detectados
# ---------------------------------------------------------------------------

def test_constante_nomeada_nao_detectada():
    """TIMEOUT = 30 é uma constante nomeada — deve ser isenta."""
    src = "def f():\n    TIMEOUT = 30\n    return TIMEOUT\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_constante_nomeada_annotated_nao_detectada():
    """TIMEOUT: int = 30 (AnnAssign) também deve ser isenta."""
    src = "def f():\n    TIMEOUT: int = 30\n    return TIMEOUT\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_default_parametro_nao_detectado():
    """Valor padrão de parâmetro posicional não é magic number."""
    src = "def f(timeout=30):\n    return timeout\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_default_kwonly_nao_detectado():
    """Valor padrão de parâmetro keyword-only não é magic number."""
    src = "def f(*, retries=3):\n    return retries\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_whitelist_0_1_2_nao_detectados():
    """0, 1 e 2 são triviais — não devem ser reportados."""
    src = "def f(n):\n    return n + 1\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_negativo_1_nao_detectado():
    """-1 em expressão: o operando 1 está na whitelist."""
    src = "def f(n):\n    return n - 1\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_negativo_2_nao_detectado():
    """-2 em expressão: o operando 2 está na whitelist."""
    src = "def f(n):\n    return n - 2\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_strings_nao_detectadas():
    """Strings comuns não devem ser reportadas (branch removida em F7)."""
    src = 'def f():\n    msg = "hello world"\n    return msg\n'
    result = detect(_fn(src))
    assert result.detected is False


def test_docstring_nao_detectada():
    """Docstring não deve acionar o detector (strings removidas em F7)."""
    src = 'def f():\n    """Função que faz alguma coisa."""\n    return 42\n'
    result = detect(_fn(src))
    # 42 não é whitelisted — deve detectar o número, mas não a string
    assert result.detected is True
    types_found = [e.get("value") for e in result.evidence["magic_numbers"]]
    # nenhum item deve ser a docstring
    assert all(isinstance(v, (int, float)) for v in types_found)


def test_funcao_so_docstring_nao_detectada():
    """Função cujo único conteúdo é uma docstring → sem magic numbers."""
    src = 'def f():\n    """Apenas documentação."""\n    pass\n'
    result = detect(_fn(src))
    assert result.detected is False


def test_constante_nomeada_negativa_nao_detectada():
    """OFFSET = -86400 (UnaryOp/USub sobre Constant) é constante nomeada."""
    src = "def f():\n    OFFSET = -86400\n    return OFFSET\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_default_negativo_nao_detectado():
    """def f(delta=-30) — default negativo também é isento."""
    src = "def f(delta=-30):\n    return delta\n"
    result = detect(_fn(src))
    assert result.detected is False


def test_evidence_key_e_magic_numbers():
    """A chave de evidência deve ser 'magic_numbers' (não 'number'/'string')."""
    src = "def f():\n    return 99\n"
    result = detect(_fn(src))
    assert "magic_numbers" in result.evidence
    assert result.evidence["magic_numbers"][0]["value"] == 99
