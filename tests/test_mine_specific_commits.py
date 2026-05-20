"""Testes de `mine_specific_commits` — C3 (Dia 3 do sprint).

Foco:
- filtragem por commit hash (só commits passados são processados);
- bypass do filtro de keyword (`matched_keywords`) — commits sem keyword
  ainda produzem pares quando os detectores disparam;
- propagação da tag `source` (default `adjacent_oracle`) aos `RefactoringPair`;
- idempotência via merge por `id`.
"""
import json
import subprocess
from pathlib import Path

import pytest

from extracao.mineracao.minerador import mine_specific_commits


@pytest.fixture(scope="module")
def repo_sem_keyword(tmp_path_factory):
    """Repo git local com 2 commits SEM keywords de refatoração na mensagem.

    Commit 1: dump inicial (init).
    Commit 2: refatora 3 funções de 8 params -> 1 (Parameter Object) com
              mensagem genérica "tweak" — `matched_keywords()` retorna [].
    Commit 3: alteração trivial (whitespace) — `RefactoringPair` zero.

    Permite testar bypass de keyword (commit 2 ainda produz pares R2) e
    a filtragem por commit hash (commit 3 não deve aparecer se não passado).
    """
    d = tmp_path_factory.mktemp("repo_no_kw")

    def git(*args):
        subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    antes = "\n\n".join(
        f"def f{i}(a, b, c, d, e, f, g, h):\n"
        f"    return a + b + c + d + e + f + g + h"
        for i in range(3))
    (d / "mod.py").write_text(antes + "\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    sha_init = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=d, check=True,
        capture_output=True, text=True).stdout.strip()

    depois = "\n\n".join(f"def f{i}(cfg):\n    return cfg.total" for i in range(3))
    (d / "mod.py").write_text(depois + "\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "tweak")   # SEM keyword de refatoração
    sha_refactor = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=d, check=True,
        capture_output=True, text=True).stdout.strip()

    # commit 3 trivial — só p/ testar filtro por commit hash
    (d / "mod.py").write_text(depois + "\n# noop\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "noop")
    sha_noop = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=d, check=True,
        capture_output=True, text=True).stdout.strip()

    return {"path": str(d), "sha_init": sha_init,
            "sha_refactor": sha_refactor, "sha_noop": sha_noop}


def _load_pairs(out_dir: Path, smell_file: str) -> list[dict]:
    p = out_dir / smell_file
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_mine_specific_commits_bypassa_keyword_filter(repo_sem_keyword, tmp_path):
    """O commit `sha_refactor` tem mensagem 'tweak' (sem keyword) — `mine()`
    o ignoraria; `mine_specific_commits` deve processá-lo e emitir 3 pares R2."""
    out = tmp_path / "out"
    counts = mine_specific_commits(
        repo_url=repo_sem_keyword["path"],
        output_path=out,
        commit_hashes=[repo_sem_keyword["sha_refactor"]],
    )
    assert counts.get("R2") == 3, f"esperado 3 pares R2, contagens={counts}"


def test_mine_specific_commits_aplica_source_tag(repo_sem_keyword, tmp_path):
    """Todos os pares gerados devem ter `source='adjacent_oracle'` (default)."""
    out = tmp_path / "out"
    mine_specific_commits(
        repo_url=repo_sem_keyword["path"],
        output_path=out,
        commit_hashes=[repo_sem_keyword["sha_refactor"]],
    )
    pairs = _load_pairs(out, "long_param_list.jsonl")
    assert pairs and all(p["source"] == "adjacent_oracle" for p in pairs)


def test_mine_specific_commits_source_customizavel(repo_sem_keyword, tmp_path):
    """Permite tag diferente (e.g., quando uma fonte futura precisar)."""
    out = tmp_path / "out"
    mine_specific_commits(
        repo_url=repo_sem_keyword["path"],
        output_path=out,
        commit_hashes=[repo_sem_keyword["sha_refactor"]],
        source="mined_pr",
    )
    pairs = _load_pairs(out, "long_param_list.jsonl")
    assert pairs and all(p["source"] == "mined_pr" for p in pairs)


def test_mine_specific_commits_lista_vazia(repo_sem_keyword, tmp_path):
    """Sem commits, sem pares — não deve crashar."""
    out = tmp_path / "out"
    counts = mine_specific_commits(
        repo_url=repo_sem_keyword["path"],
        output_path=out,
        commit_hashes=[],
    )
    assert counts == {}


def test_mine_specific_commits_filtra_por_hash(repo_sem_keyword, tmp_path):
    """Passar só o `sha_noop` (que não tem refatoração) deve render 0 pares."""
    out = tmp_path / "out"
    counts = mine_specific_commits(
        repo_url=repo_sem_keyword["path"],
        output_path=out,
        commit_hashes=[repo_sem_keyword["sha_noop"]],
    )
    assert counts == {}


def test_mine_specific_commits_idempotente(repo_sem_keyword, tmp_path):
    """Rodar 2× no mesmo output_path não duplica — merge por `id`."""
    out = tmp_path / "out"
    mine_specific_commits(
        repo_url=repo_sem_keyword["path"], output_path=out,
        commit_hashes=[repo_sem_keyword["sha_refactor"]],
    )
    mine_specific_commits(
        repo_url=repo_sem_keyword["path"], output_path=out,
        commit_hashes=[repo_sem_keyword["sha_refactor"]],
    )
    pairs = _load_pairs(out, "long_param_list.jsonl")
    ids = [p["id"] for p in pairs]
    assert len(ids) == len(set(ids)) == 3
