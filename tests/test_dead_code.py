"""Testes do detector de dead code — `detectores/dead_code.py` (F6).

`_find_unreachable` assumia que `node.body`/`orelse`/`finalbody` eram sempre
listas de statements; em `IfExp` (ternário) e `Lambda` são um nó de expressão
único → `TypeError: 'Call' object is not iterable`, que derrubava `mine()`.
"""
import pytest

from core.ast_types import FunctionInfo
from detectores.dead_code import _find_unreachable, _find_unused_vars, detect


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


# --------------------------------------------------------------------------
# `_find_unused_vars` — investigação F-R5.
#
# A versão anterior rodava `vulture <tmpfile> --min-confidence 80` sobre a
# função isolada. Empiricamente (vulture 2.16): locais não usados saem a 60%
# de confiança e parâmetros não usados a 100%. Com o corte em 80% o detector
# ficava INVERTIDO — descartava todo local morto (sound) e disparava só em
# parâmetros (unsound: param de interface não é dead code). A versão `ast`
# corrige a inversão: reporta locais, nunca parâmetros.
# --------------------------------------------------------------------------

# (descrição, fonte, nº esperado de achados unused_var)
_UNUSED_VAR_CASES = [
    ("local morto", "def f(a):\n    x = 1\n    return a + 2\n", 1),
    ("dois locais mortos",
     "def p(a, b):\n    result = 0\n    junk = 99\n    return a + b\n", 2),
    ("local usado", "def g(a):\n    x = a + 1\n    return x\n", 0),
    # parâmetros de interface: NUNCA reportados (correção da inversão)
    ("params de interface",
     "def on_event(sender, event, context):\n    return 1\n", 0),
    ("**kwargs", "def h(data, **kwargs):\n    return data\n", 0),
    ("*args", "def v(first, *args):\n    return first\n", 0),
    ("param usado só em closure",
     "def outer(factor):\n    def inner(v):\n        return v * factor\n"
     "    return inner\n", 0),
    # idiomas intencionais: não reportar
    ("var de loop não usada",
     "def f(it):\n    for i in it:\n        print(1)\n    return 0\n", 0),
    ("desempacotamento parcial de tupla",
     "def f(p):\n    a, b = p\n    return a\n", 0),
    ("augassign", "def f(a):\n    s = 0\n    s += a\n    return 1\n", 0),
    ("walrus em comprehension",
     "def f(xs):\n    return [y for x in xs if (y := x * 2) > 0]\n", 0),
    ("global", "def f():\n    global G\n    G = 5\n", 0),
    ("underscore descartado", "def f(p):\n    _ = p\n    return 1\n", 0),
    ("del referencia o binding", "def f():\n    t = 1\n    del t\n", 0),
    # método: `source` de um método é o `def` sozinho — `self` é só um param
    ("método com self e local morto",
     "def m(self, x):\n    y = 1\n    return x\n", 1),
    # with-as não usado: tratado como local morto (igual ao vulture)
    ("with-as não usado",
     "def f():\n    with open('x') as fh:\n        return 1\n", 1),
    ("except-as",
     "def f():\n    try:\n        pass\n    except Exception as e:\n"
     "        return 0\n", 0),
    # except-as unused (`e` nunca lido): `ExceptHandler.name` é uma string,
    # não um `Name(Store)` — então não entra em `assigned`. Comportamento
    # travado: 0 (igual a parâmetro de interface — sem semântica de módulo
    # não dá pra dizer se é dead ou contrato).
    ("except-as não lido",
     "def f():\n    try:\n        pass\n    except Exception as e:\n"
     "        pass\n", 0),
    # I1 (revisão PR #16): alvo de comprehension não usado é idioma — não
    # reportar. Comprehensions têm escopo próprio em Python 3.
    ("I1: alvo de comprehension não usado",
     "def f(items):\n    return [1 for x in items]\n", 0),
    # I2 (revisão PR #16): walrus em if-test sem leitura subsequente — o
    # valor é consumido pelo `if`, não é dead.
    ("I2: walrus em if-test (sem leitura subsequente)",
     "def f(xs):\n    if (n := compute(xs)):\n        return 0\n"
     "    return 1\n", 0),
    # C1 (revisão PR #16): função aninhada reusa um nome local; o local
    # externo é DEAD e DEVE ser reportado. `ast.walk` flatten antigo
    # mascarava esse caso pelo Load do binding interno subir para o externo.
    ("C1: inner func reusa nome — outer local fica morto",
     "def outer():\n    total = 100\n"
     "    def helper():\n        total = 0\n        return total + 1\n"
     "    return helper()\n", 1),
    # Caso simétrico de C1: outer usado por closure LEGÍTIMA (sem rebinding
    # interno) — NÃO reportar. A free var do inner deve subir para o externo.
    ("C1 simétrico: outer usado por closure (sem reuso) — não reporta",
     "def outer():\n    total = 100\n"
     "    def helper():\n        return total\n"
     "    return helper()\n", 0),
]


@pytest.mark.parametrize(
    "desc,src,esperado", _UNUSED_VAR_CASES, ids=[c[0] for c in _UNUSED_VAR_CASES]
)
def test_find_unused_vars(desc, src, esperado):
    achados = _find_unused_vars(src)
    assert len(achados) == esperado, f"{desc}: {achados}"
    for a in achados:
        assert a["type"] == "unused_var"
        assert isinstance(a["lineno"], int)


def test_find_unused_vars_nao_dispara_em_param_de_interface():
    """Regressão F-R5: param não usado no corpo NÃO é dead code (contrato)."""
    src = "def callback(request, response, *, retries):\n    return response\n"
    assert _find_unused_vars(src) == []


def test_find_unused_vars_ainda_pega_local_genuinamente_morto():
    """Regressão F-R5: local morto deve continuar sendo detectado (true positive)."""
    achados = _find_unused_vars("def f(a):\n    morto = a * 999\n    return a\n")
    assert len(achados) == 1 and achados[0]["lineno"] == 2


def test_detect_dispara_em_local_morto():
    """`detect` completo: local morto -> detected=True (antes era missado)."""
    res = detect(_fn("def f(a):\n    sobra = 1\n    return a\n"))
    assert res.detected is True
    assert {"type": "unused_var", "lineno": 2} in res.evidence["dead_code"]


def test_detect_nao_dispara_em_param_de_interface():
    """`detect` completo: param de interface -> detected=False (antes era FP)."""
    res = detect(_fn("def hook(self, ctx, event):\n    return ctx\n"))
    assert res.detected is False


# --------------------------------------------------------------------------
# Regressões da revisão do PR #16 — bugs achados na própria reescrita AST.
# --------------------------------------------------------------------------

def test_c1_inner_reusa_nome_nao_mascara_outer_dead():
    """C1 — bug headline: inner func que reusa um identificador comum
    (`total`, `result`, `tmp`) NÃO pode mascarar o local externo morto."""
    src = ("def outer():\n"
           "    total = 100\n"
           "    def helper():\n"
           "        total = 0\n"
           "        return total + 1\n"
           "    return helper()\n")
    achados = _find_unused_vars(src)
    assert {"type": "unused_var", "lineno": 2} in achados


def test_c1_closure_legitima_continua_suprimindo_report():
    """Inverso de C1: closure que lê o nome do externo (sem rebinding
    interno) é uso legítimo — externo NÃO deve ser reportado."""
    src = ("def outer():\n"
           "    total = 100\n"
           "    def helper():\n"
           "        return total\n"
           "    return helper()\n")
    assert _find_unused_vars(src) == []


def test_i1_alvo_de_comprehension_nao_usado_nao_dispara():
    """I1 — alvo de comprehension não usado é idioma comum (`[1 for x in ...]`)."""
    assert _find_unused_vars("def f(items):\n    return [1 for x in items]\n") == []


def test_i2_walrus_target_nao_eh_reportado():
    """I2 — walrus em if-test: valor consumido pela expressão, não é dead."""
    src = ("def f(xs):\n"
           "    if (n := compute(xs)):\n"
           "        return 0\n"
           "    return 1\n")
    assert _find_unused_vars(src) == []
