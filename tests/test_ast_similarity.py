"""Testes de `ast_similarity` (C5c.2 — Dia 6-7 do sprint).

Cobre: `shape_hash`, `shape_distance`, `ast_similarity`, `find_cross_file_candidates`.
"""
import pytest

from extracao.mineracao.ast_similarity import (
    ShapeHash,
    ast_similarity,
    find_cross_file_candidates,
    shape_distance,
    shape_hash,
)


# --- shape_hash ---

def test_shape_hash_funcao_simples():
    sh = shape_hash(
        "def f(a, b, c):\n"
        "    if a:\n"
        "        return b\n"
        "    return c\n"
    )
    assert sh == ShapeHash(n_stmts=2, n_params=3, depth=sh.depth, n_returns=2)
    assert sh.depth >= 3  # FunctionDef -> If -> Return aninhado


def test_shape_hash_conta_args_vargs_kwargs():
    """*args e **kwargs contam como parâmetros."""
    sh = shape_hash("def f(a, *args, **kwargs):\n    return 1\n")
    assert sh.n_params == 3   # a + args + kwargs


def test_shape_hash_codigo_invalido_retorna_none():
    assert shape_hash("not python code at all !!!") is None


def test_shape_hash_sem_funcao_retorna_none():
    """String válida mas sem função top-level."""
    assert shape_hash("x = 1\ny = 2\n") is None


# --- shape_distance ---

def test_shape_distance_identicos_e_zero():
    sh = shape_hash("def f(a, b):\n    return a + b\n")
    assert shape_distance(sh, sh) == 0.0


def test_shape_distance_difere_quando_n_stmts_muda():
    sh1 = shape_hash("def f():\n    return 1\n")
    sh2 = shape_hash("def f():\n    x = 1\n    y = 2\n    return x + y\n")
    assert shape_distance(sh1, sh2) > 0


def test_shape_distance_zero_a_um():
    """Sempre em [0, 1] — cada componente é normalizado e a média mantém range."""
    sh1 = shape_hash("def f(a):\n    return a\n")
    sh2 = shape_hash("def g(a, b, c, d, e, f, g, h, i, j):\n"
                    "    if a:\n        if b:\n            if c:\n"
                    "                return d\n    return None\n")
    d = shape_distance(sh1, sh2)
    assert 0.0 <= d <= 1.0


# --- ast_similarity ---

def test_ast_similarity_identicas_e_um():
    src = "def f(a, b):\n    return a + b\n"
    assert ast_similarity(src, src) == 1.0


def test_ast_similarity_rename_vars_quase_um():
    """Mesma estrutura, nomes de variáveis diferentes — similaridade ~1
    porque comparamos só TIPOS de nó AST, ignorando nomes."""
    a = "def f(a, b):\n    return a + b\n"
    b = "def g(x, y):\n    return x + y\n"
    sim = ast_similarity(a, b)
    assert sim is not None and sim == 1.0   # estrutura idêntica


def test_ast_similarity_estruturas_diferentes_baixa():
    a = "def f(a):\n    return a\n"
    b = ("def g(a, b, c, d):\n"
         "    if a:\n        return b\n"
         "    elif c:\n        return d\n"
         "    return None\n")
    sim = ast_similarity(a, b)
    assert sim is not None and sim < 0.7


def test_ast_similarity_codigo_invalido_retorna_none():
    assert ast_similarity("def f():\n    return 1\n", "lixo !!! ") is None


def test_ast_similarity_param_object_alta_mas_nao_um():
    """Parameter Object: assinatura encolheu drasticamente mas o corpo tem
    estrutura parecida (return de soma vs return de atributo de objeto)."""
    a = ("def f(a, b, c, d, e, f, g, h):\n"
         "    return a + b + c + d + e + f + g + h\n")
    b = "def f(cfg):\n    return cfg.total\n"
    sim = ast_similarity(a, b)
    assert sim is not None
    # Não exigimos exatamente quanto — só que esteja em um regime razoável
    # (alguma similaridade pelo Return em ambos, mas <1.0).
    assert 0.0 < sim < 1.0


# --- find_cross_file_candidates ---

def test_find_cross_file_funcao_movida_simples():
    """`foo` desaparece de `utils.py` e aparece em `models.py` quase idêntica."""
    before = {
        "utils.py": "def helper():\n    return 1\n\ndef foo(a, b):\n    return a + b\n",
        "models.py": "class M:\n    pass\n",
    }
    after = {
        "utils.py": "def helper():\n    return 1\n",
        "models.py": "class M:\n    pass\n\ndef foo(a, b):\n    return a + b\n",
    }
    cands = find_cross_file_candidates(before, after, similarity_threshold=0.7)
    assert len(cands) == 1
    c = cands[0]
    assert c["function_name_before"] == "foo"
    assert c["function_name_after"] == "foo"
    assert c["file_before"] == "utils.py"
    assert c["file_after"] == "models.py"
    assert c["similarity"] == 1.0


def test_find_cross_file_funcao_renomeada_similar():
    """Função renomeada (foo → bar) mas estrutura idêntica → casada."""
    before = {
        "a.py": "def helper():\n    return 1\n\ndef foo(a, b):\n    return a + b\n",
    }
    after = {
        "b.py": "def helper2():\n    return 2\n\ndef bar(x, y):\n    return x + y\n",
    }
    cands = find_cross_file_candidates(before, after, similarity_threshold=0.9)
    # foo↔bar tem estrutura idêntica; helper↔helper2 também. Pareamento por
    # best-similarity escolhe os pares de maior similaridade.
    names = sorted((c["function_name_before"], c["function_name_after"]) for c in cands)
    assert ("foo", "bar") in names or ("foo", "helper2") in names
    # Pelo menos um candidato deve existir.
    assert len(cands) >= 1


def test_find_cross_file_mesmo_arquivo_ignorado():
    """Funções `gone` e `fresh` no MESMO arquivo NÃO devem virar candidatos —
    o caminho per-file (extract_candidates) cobre esse caso."""
    before = {
        "x.py": "def old_name():\n    return 1\n",
    }
    after = {
        # `old_name` removida, `new_name` adicionada — mas tudo no mesmo file.
        "x.py": "def new_name():\n    return 1\n",
    }
    cands = find_cross_file_candidates(before, after, similarity_threshold=0.5)
    assert cands == []


def test_find_cross_file_pre_filtro_shape_descarta_obvios():
    """Função de 50 linhas vs função de 1 linha — `shape_distance` alto,
    descartada antes do APTED (não invade o O(n²))."""
    long_body = "\n    ".join(f"x{i} = {i}" for i in range(50))
    before = {"x.py": f"def big():\n    {long_body}\n    return x49\n"}
    after = {"y.py": "def big():\n    return 1\n"}
    cands = find_cross_file_candidates(
        before, after,
        shape_threshold=0.3,        # razoavelmente apertado
        similarity_threshold=0.5,
    )
    assert cands == []


def test_find_cross_file_arquivo_sem_python_valido():
    """Arquivo que não parseia é ignorado — sem crash."""
    before = {"bad.py": "this is not python ((("}
    after = {"good.py": "def f():\n    return 1\n"}
    # Não deve crashar; nenhuma função "gone" identificada → vazio.
    cands = find_cross_file_candidates(before, after)
    assert cands == []
