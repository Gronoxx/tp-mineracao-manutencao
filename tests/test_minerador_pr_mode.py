"""Testes de `mine_pr` (C5a) e da flag `require_keyword` em `mine()` (C5b).

C5a (`mine_pr`): processa o merge commit de um PR como um único candidate
batch — diff base..head colapsado em uma única passagem.

C5b (`require_keyword=False`): permite mineração sem o pré-filtro de keyword
na mensagem, útil para janelas curtas onde a maioria dos commits refatora
sem mencionar "refactor"/"extract" na msg.
"""
import json
import subprocess
from pathlib import Path

import pytest

from extracao.mineracao.minerador import mine, mine_pr


def _git(d, *args):
    subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)


def _rev_parse(d, ref="HEAD"):
    return subprocess.run(
        ["git", "rev-parse", ref], cwd=d, check=True,
        capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def repo_com_pr(tmp_path_factory):
    """Repo git local simulando um PR squash-merged.

    main: commit inicial.
    feature: 2 commits incrementais que juntos refatoram 3 funcs de 8→1 param.
    Volta a main, faz merge --squash, commita → este é o "merge commit do PR".

    A asserção-chave: o squash commit, sozinho, contém o diff completo da
    refatoração — `mine_pr` processa esse único commit e encontra 3 pares R2.
    """
    d = tmp_path_factory.mktemp("repo_pr")
    _git(d, "init", "-q", "-b", "main")
    _git(d, "config", "user.email", "t@t.t")
    _git(d, "config", "user.name", "t")
    antes = "\n\n".join(
        f"def f{i}(a, b, c, d, e, f, g, h):\n"
        f"    return a + b + c + d + e + f + g + h"
        for i in range(3))
    (d / "mod.py").write_text(antes + "\n", encoding="utf-8")
    _git(d, "add", ".")
    _git(d, "commit", "-q", "-m", "init")

    _git(d, "checkout", "-q", "-b", "feat-pr")
    # commit incremental 1 — refatora f0 e f1
    parcial = "\n\n".join([
        "def f0(cfg):\n    return cfg.total",
        "def f1(cfg):\n    return cfg.total",
        "def f2(a, b, c, d, e, f, g, h):\n"
        "    return a + b + c + d + e + f + g + h",
    ])
    (d / "mod.py").write_text(parcial + "\n", encoding="utf-8")
    _git(d, "add", ".")
    _git(d, "commit", "-q", "-m", "wip 1")
    # commit incremental 2 — refatora f2
    completo = "\n\n".join(f"def f{i}(cfg):\n    return cfg.total" for i in range(3))
    (d / "mod.py").write_text(completo + "\n", encoding="utf-8")
    _git(d, "add", ".")
    _git(d, "commit", "-q", "-m", "wip 2")

    # Volta a main, squash-merge
    _git(d, "checkout", "-q", "main")
    _git(d, "merge", "--squash", "feat-pr")
    _git(d, "commit", "-q", "-m", "tweak")  # SEM keyword
    sha_squash = _rev_parse(d)

    return {"path": str(d), "sha_squash_pr": sha_squash}


@pytest.fixture(scope="module")
def repo_keyword_e_no_keyword(tmp_path_factory):
    """2 commits de refatoração: um com keyword na mensagem, outro sem.

    Permite testar a flag `require_keyword` do `mine()`:
        - require_keyword=True  → 3 pares (só o commit com keyword)
        - require_keyword=False → 6 pares (ambos)
    """
    d = tmp_path_factory.mktemp("repo_kw")
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t.t")
    _git(d, "config", "user.name", "t")
    antes_a = "\n\n".join(
        f"def a{i}(a, b, c, d, e, f, g, h):\n"
        f"    return a + b + c + d + e + f + g + h"
        for i in range(3))
    (d / "a.py").write_text(antes_a + "\n", encoding="utf-8")
    (d / "b.py").write_text(antes_a.replace("def a", "def b") + "\n", encoding="utf-8")
    _git(d, "add", ".")
    _git(d, "commit", "-q", "-m", "init")

    # commit 1 — mensagem SEM keyword
    depois_a = "\n\n".join(f"def a{i}(cfg):\n    return cfg.total" for i in range(3))
    (d / "a.py").write_text(depois_a + "\n", encoding="utf-8")
    _git(d, "add", ".")
    _git(d, "commit", "-q", "-m", "tweak")

    # commit 2 — mensagem COM keyword "parameter object"
    depois_b = "\n\n".join(f"def b{i}(cfg):\n    return cfg.total" for i in range(3))
    (d / "b.py").write_text(depois_b + "\n", encoding="utf-8")
    _git(d, "add", ".")
    _git(d, "commit", "-q", "-m", "refactor: introduce parameter object")

    return str(d)


# --- C5b — require_keyword flag em mine() ---

def test_mine_default_filtra_por_keyword(repo_keyword_e_no_keyword, tmp_path):
    """Default `require_keyword=True`: só o commit 'parameter object' passa."""
    counts = mine(repo_url=repo_keyword_e_no_keyword, output_path=tmp_path / "out")
    assert counts.get("R2") == 3   # apenas b0..b2


def test_mine_require_keyword_false_processa_todos(repo_keyword_e_no_keyword, tmp_path):
    """`require_keyword=False`: ambos os commits viram pares (3 + 3 = 6)."""
    counts = mine(repo_url=repo_keyword_e_no_keyword,
                  output_path=tmp_path / "out",
                  require_keyword=False)
    assert counts.get("R2") == 6   # a0..a2 + b0..b2


def test_mine_require_keyword_false_aceita_caps(repo_keyword_e_no_keyword, tmp_path):
    """Cap ainda funciona com keyword filter desligado."""
    counts = mine(repo_url=repo_keyword_e_no_keyword,
                  output_path=tmp_path / "out",
                  require_keyword=False,
                  caps={"R1": 99, "R2": 4, "R3": 99, "R4": 99, "R5": 99})
    assert counts.get("R2") == 4   # cap limita


# --- C5a — mine_pr ---

def test_mine_pr_processa_squash_commit(repo_com_pr, tmp_path):
    """O squash commit, sozinho, contém o diff completo da refatoração:
    `mine_pr` processa esse commit e encontra 3 pares R2."""
    counts = mine_pr(
        repo_url=repo_com_pr["path"], output_path=tmp_path / "out",
        merge_commit_shas=[repo_com_pr["sha_squash_pr"]],
    )
    assert counts.get("R2") == 3


def test_mine_pr_aplica_source_mined_pr(repo_com_pr, tmp_path):
    """Todos os pares produzidos por mine_pr devem ter `source='mined_pr'`."""
    out = tmp_path / "out"
    mine_pr(
        repo_url=repo_com_pr["path"], output_path=out,
        merge_commit_shas=[repo_com_pr["sha_squash_pr"]],
    )
    records = [json.loads(l) for l in
               (out / "long_param_list.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip()]
    assert records and all(r["source"] == "mined_pr" for r in records)


def test_mine_pr_lista_vazia(repo_com_pr, tmp_path):
    """Sem SHAs, sem pares."""
    counts = mine_pr(
        repo_url=repo_com_pr["path"], output_path=tmp_path / "out",
        merge_commit_shas=[],
    )
    assert counts == {}


def test_mine_pr_idempotente(repo_com_pr, tmp_path):
    """Rodar 2x não duplica (mesmo merge por `id`)."""
    out = tmp_path / "out"
    mine_pr(repo_url=repo_com_pr["path"], output_path=out,
            merge_commit_shas=[repo_com_pr["sha_squash_pr"]])
    mine_pr(repo_url=repo_com_pr["path"], output_path=out,
            merge_commit_shas=[repo_com_pr["sha_squash_pr"]])
    records = [json.loads(l) for l in
               (out / "long_param_list.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip()]
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids)) == 3
