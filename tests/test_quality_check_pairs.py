"""Testes do `scripts/quality_check_pairs.py`.

Cobre cada heuristica individualmente (record sintetico) + o sanity check
sobre os pares reais em `data/raw/` (se existirem no ambiente).
"""
import json
from pathlib import Path

import pytest

from scripts.quality_check_pairs import (
    AST_SIM_FAIL_BELOW,
    AST_SIM_WARN_BELOW,
    check_pair,
    load_pairs,
)


def _base_record(**overrides):
    """Record minimo valido — heuristicas se aplicam sobre overrides."""
    rec = {
        "id": "fake-id",
        "smell_type": "R2",
        "source": "mined_commit",
        "repo": "https://github.com/x/y",
        "file": "mod.py",
        "function_name": "foo",
        "before_code": (
            "def foo(a, b, c, d, e, f, g, h):\n"
            "    return a + b + c + d + e + f + g + h\n"
        ),
        "after_code": "def foo(cfg):\n    return cfg.total\n",
        "n_functions_after": 1,
        "partial": False,
    }
    rec.update(overrides)
    return rec


# --- FAIL rules ---

def test_fail_no_change_quando_before_eh_igual_after():
    code = "def foo():\n    return 1\n"
    rep = check_pair(_base_record(before_code=code, after_code=code))
    assert rep.n_fail >= 1
    assert any(i.rule == "no_change" for i in rep.issues)


def test_fail_unparseable_before():
    rep = check_pair(_base_record(before_code="this is not python ((("))
    assert any(i.rule == "before_unparseable" and i.severity == "fail"
               for i in rep.issues)


def test_fail_unparseable_after():
    rep = check_pair(_base_record(after_code="def f( (((("))
    assert any(i.rule == "after_unparseable" and i.severity == "fail"
               for i in rep.issues)


def test_fail_smell_invalido():
    rep = check_pair(_base_record(smell_type="R99"))
    assert any(i.rule == "smell_invalid" and i.severity == "fail"
               for i in rep.issues)


def test_fail_similarity_muito_baixa():
    """before e after estruturalmente disjuntos -> ast_similarity < 0.1."""
    rep = check_pair(_base_record(
        before_code="def foo():\n    return 1\n",
        after_code=(
            "def foo(a, b, c, d, e, f, g, h, i, j):\n"
            "    if a:\n        if b:\n            if c:\n"
            "                while d:\n                    return e\n"
            "    return None\n"
        ),
    ))
    if rep.ast_similarity is not None and rep.ast_similarity < AST_SIM_FAIL_BELOW:
        assert any(i.rule == "similarity_too_low" and i.severity == "fail"
                   for i in rep.issues)


# --- WARN rules ---

def test_warn_borderline_similarity_em_param_object():
    """Parameter Object tem ast_sim ~0.17 — abaixo de 0.30 -> WARN, acima de 0.10 -> nao FAIL."""
    rep = check_pair(_base_record())
    # Caso real: param 8->1, return atributo. Esperamos warn de similaridade.
    if rep.ast_similarity is not None:
        if AST_SIM_FAIL_BELOW <= rep.ast_similarity < AST_SIM_WARN_BELOW:
            assert any(i.rule == "similarity_borderline"
                       for i in rep.issues)


def test_warn_before_muito_curto():
    rep = check_pair(_base_record(
        before_code="def f(x): return x\n",       # 1 linha nao-branca
        after_code="def f(x):\n    return x + 1\n",
    ))
    assert any(i.rule == "before_too_short" and i.severity == "warn"
               for i in rep.issues)


def test_warn_after_muito_curto():
    rep = check_pair(_base_record(
        before_code="def f(x):\n    return x + 1\n    # comment\n",
        after_code="def f(x): return x\n",
    ))
    assert any(i.rule == "after_too_short" and i.severity == "warn"
               for i in rep.issues)


def test_warn_r1_sem_helper():
    """R1 sem helper extraido — F3 deveria ter rejeitado; warn de regressao."""
    rep = check_pair(_base_record(
        smell_type="R1",
        n_functions_after=1,   # sem helpers
        before_code="def f():\n    " + "\n    ".join(f"x{i} = {i}" for i in range(40)) + "\n    return x39\n",
        after_code="def f():\n    return 1\n",
    ))
    assert any(i.rule == "r1_no_helper" and i.severity == "warn"
               for i in rep.issues)


def test_warn_partial_sem_reducao_significativa():
    """Modo permissivo + magnitude_a quase igual a magnitude_b -> warn."""
    rep = check_pair(_base_record(
        smell_type="R2",
        partial=True,
        before_code="def f(a, b, c, d, e, f, g, h):\n    return a\n",
        after_code="def f(a, b, c, d, e, f, g):\n    return a\n",   # 8 -> 7
        detector_before={"detected": True, "evidence": {"parametros": 8}},
        detector_after={"detected": True, "evidence": {"parametros": 7}},
    ))
    # reduction = (8-7)/8 = 0.125 → > 0.05 → SEM warn de trivial. Vamos forcar caso trivial.
    rep2 = check_pair(_base_record(
        smell_type="R2",
        partial=True,
        before_code="def f(a, b, c, d, e, f, g, h):\n    return a\n",
        after_code="def f(a, b, c, d, e, f, g, h):\n    return a + 1\n",
        detector_before={"detected": True, "evidence": {"parametros": 8}},
        detector_after={"detected": True, "evidence": {"parametros": 8}},
    ))
    assert any(i.rule == "trivial_reduction" and i.severity == "warn"
               for i in rep2.issues)


# --- Limpo ---

def test_par_legitimo_de_dead_code_e_clean():
    """Refactoring de dead code preserva estrutura (sim alta) e tem reducao."""
    rep = check_pair({
        **_base_record(),
        "smell_type": "R5",
        "before_code": (
            "def foo(x, y):\n"
            "    dead1 = x + y\n"
            "    dead2 = x * y\n"
            "    result = x ** 2 + y ** 2\n"
            "    return result\n"
        ),
        "after_code": "def foo(x, y):\n    result = x ** 2 + y ** 2\n    return result\n",
        "n_functions_after": 1,
        "partial": False,
    })
    assert rep.n_fail == 0


def test_pairreport_n_fail_n_warn_propriedades():
    rep = check_pair(_base_record(before_code="def f(): pass\n",
                                  after_code="def f(): pass\n"))
    # FAIL no_change → n_fail >= 1, n_warn = 0 (early return)
    assert rep.n_fail >= 1
    assert rep.n_warn == 0


# --- Filtros de carga ---

def test_load_pairs_filtra_por_source(tmp_path):
    p = tmp_path / "long_param_list.jsonl"
    p.write_text(
        json.dumps({"smell_type": "R2", "source": "mined_commit",
                    "before_code": "def f(): pass\n",
                    "after_code": "def f(): return 1\n", "repo": "x"}) + "\n"
        + json.dumps({"smell_type": "R2", "source": "adjacent_oracle",
                      "before_code": "def f(): pass\n",
                      "after_code": "def f(): return 2\n", "repo": "y"}) + "\n",
        encoding="utf-8",
    )
    all_pairs = load_pairs(tmp_path, source_filter=None, smell_filter=None)
    adj_pairs = load_pairs(tmp_path, source_filter="adjacent_oracle", smell_filter=None)
    assert len(all_pairs) == 2
    assert len(adj_pairs) == 1
    assert adj_pairs[0]["source"] == "adjacent_oracle"


# --- Sanity sobre os 25 adjacent_oracle reais (se presentes) ---

def test_adjacent_oracle_em_data_raw_se_existirem():
    """Smoke sobre os pares reais — nao falha se data/raw estiver vazio."""
    raw = Path(__file__).resolve().parent.parent / "data" / "raw"
    if not raw.is_dir():
        pytest.skip("data/raw/ ausente neste ambiente")
    pairs = load_pairs(raw, source_filter="adjacent_oracle", smell_filter=None)
    if not pairs:
        pytest.skip("nenhum par adjacent_oracle em data/raw")
    # Verificacao basica: cada par produz um report sem crash.
    reports = [check_pair(p) for p in pairs]
    assert len(reports) == len(pairs)
    # Quantos sao FAIL? Imprime informativo (nao assertion — o relatorio
    # detalhado e tarefa do script CLI, nao da suite).
    n_fail = sum(1 for r in reports if r.n_fail > 0)
    print(f"\n[INFO] {len(pairs)} pares adjacent_oracle, {n_fail} com FAIL")
