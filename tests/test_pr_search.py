"""Testes de `extracao/execucao/pr_search.py` (C2 — Dia 10 do sprint).

Foco em parsing/cache (offline). A query GraphQL real (`gh api graphql`)
é coberta por smoke separado documentado no PR — não é testada aqui para
não acoplar a suíte ao estado da rede / rate limits do GitHub.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from extracao.execucao.pr_search import (
    DEFAULT_LABELS,
    load_cache,
    merge_cache,
    save_cache,
    search_label_year,
)


# --- merge_cache ---

def test_merge_cache_vazio_mais_novo():
    new = [
        {"repo": "a/b", "pr_number": 1, "merge_commit_sha": "abc"},
        {"repo": "a/b", "pr_number": 2, "merge_commit_sha": "def"},
    ]
    out = merge_cache([], new)
    assert len(out) == 2
    assert {p["pr_number"] for p in out} == {1, 2}


def test_merge_cache_dedup_por_repo_pr():
    """Mesmo (repo, pr) → o novo sobrescreve o existente."""
    existing = [{"repo": "a/b", "pr_number": 1, "merge_commit_sha": "old", "title": "v1"}]
    new = [{"repo": "a/b", "pr_number": 1, "merge_commit_sha": "new", "title": "v2"}]
    out = merge_cache(existing, new)
    assert len(out) == 1
    assert out[0]["merge_commit_sha"] == "new"
    assert out[0]["title"] == "v2"


def test_merge_cache_ordena_por_repo_e_pr():
    out = merge_cache(
        [{"repo": "z/z", "pr_number": 1, "merge_commit_sha": "x"}],
        [{"repo": "a/b", "pr_number": 5, "merge_commit_sha": "y"},
         {"repo": "a/b", "pr_number": 2, "merge_commit_sha": "z"}],
    )
    keys = [(p["repo"], p["pr_number"]) for p in out]
    assert keys == [("a/b", 2), ("a/b", 5), ("z/z", 1)]


# --- load/save_cache ---

def test_load_cache_inexistente_retorna_vazio(tmp_path):
    assert load_cache(tmp_path / "noexiste.json") == []


def test_save_e_load_cache_round_trip(tmp_path):
    data = [{"repo": "a/b", "pr_number": 7, "merge_commit_sha": "abc"}]
    p = tmp_path / "cache.json"
    save_cache(p, data)
    assert load_cache(p) == data


def test_save_cache_cria_diretorios_pai(tmp_path):
    """`save_cache` deve criar o `data/` se não existir."""
    p = tmp_path / "nested" / "dir" / "cache.json"
    save_cache(p, [{"repo": "x/y", "pr_number": 1, "merge_commit_sha": "z"}])
    assert p.exists()


# --- search_label_year (com mock do _gh_graphql) ---

def _fake_response(nodes, has_next=False, cursor=None):
    return {
        "data": {
            "search": {
                "issueCount": len(nodes),
                "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                "nodes": nodes,
            }
        }
    }


def test_search_label_year_filtra_prs_sem_merge_commit():
    """PRs sem `mergeCommit.oid` (cancelados?) são ignorados."""
    nodes = [
        {"repository": {"nameWithOwner": "a/b"}, "number": 1,
         "mergeCommit": {"oid": "deadbeef"}, "mergedAt": "2024-01-01", "title": "ok"},
        {"repository": {"nameWithOwner": "a/b"}, "number": 2,
         "mergeCommit": None, "mergedAt": None, "title": "cancelled"},
        {"repository": {"nameWithOwner": "a/b"}, "number": 3,
         "mergeCommit": {"oid": "cafebabe"}, "mergedAt": "2024-02-01", "title": "ok"},
    ]
    with patch("extracao.execucao.pr_search._gh_graphql",
               return_value=_fake_response(nodes)):
        out = search_label_year("refactor", 2024)
    assert len(out) == 2
    assert {p["pr_number"] for p in out} == {1, 3}
    assert all(p["label"] == "refactor" and p["year"] == 2024 for p in out)


def test_search_label_year_paginacao():
    """Funcao deve seguir pagineção até `hasNextPage=False`."""
    page1 = _fake_response(
        [{"repository": {"nameWithOwner": "a/b"}, "number": i,
          "mergeCommit": {"oid": f"sha{i}"}, "mergedAt": "2024-01-01",
          "title": f"PR {i}"} for i in range(1, 4)],
        has_next=True, cursor="abc",
    )
    page2 = _fake_response(
        [{"repository": {"nameWithOwner": "a/b"}, "number": i,
          "mergeCommit": {"oid": f"sha{i}"}, "mergedAt": "2024-01-01",
          "title": f"PR {i}"} for i in range(4, 6)],
        has_next=False, cursor=None,
    )
    with patch("extracao.execucao.pr_search._gh_graphql",
               side_effect=[page1, page2]) as mock_call:
        out = search_label_year("refactor", 2024)
    assert len(out) == 5
    # 2 chamadas — uma sem cursor, outra com cursor="abc".
    assert mock_call.call_count == 2
    second_call_kwargs = mock_call.call_args_list[1].kwargs
    assert second_call_kwargs.get("cursor") == "abc"


def test_search_label_year_levanta_em_erro_graphql():
    bad = {"errors": [{"message": "rate limit exceeded"}]}
    with patch("extracao.execucao.pr_search._gh_graphql", return_value=bad):
        with pytest.raises(RuntimeError, match="GraphQL errors"):
            search_label_year("refactor", 2024)


def test_default_labels_inclui_refactoring_e_cleanup():
    """Sanity: as labels canônicas estão no default."""
    assert "refactoring" in DEFAULT_LABELS
    assert "cleanup" in DEFAULT_LABELS
    assert "tech-debt" in DEFAULT_LABELS
