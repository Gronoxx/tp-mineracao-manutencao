"""Testes da curadoria da Trilha B — `trilha_b/data/curate.py`.

Foco PR 5 (F2): `read_raw` lê `.jsonl`; aplicação dos vereditos do sidecar
do curador; fail-fast sem sidecar; entrypoint CLI gera o `DatasetDict`.
"""
import json

import pytest

from trilha_b.data.curate import DataCurator, apply_verdicts, load_sidecar, main


def _pair(repo: str, n: int, smell: str = "R1") -> dict:
    return {
        "id": f"id-{repo}-{n}",
        "before_code": f"def f{n}():\n    x = {n}\n    return x\n",
        "after_code": f"def f{n}():\n    return {n}\n",
        "smell_type": smell,
        "repo": repo,
        "commit_hash": f"c{n}",
        "file": "m.py",
        "function_name": f"f{n}",
    }


def _write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


# ── read_raw: .jsonl ─────────────────────────────────────────────────────────

def test_read_raw_aceita_jsonl(tmp_path):
    f = tmp_path / "long_method.jsonl"
    _write_jsonl(f, [_pair("r", 1), _pair("r", 2)])
    assert len(DataCurator().read_raw(f)._pairs) == 2


def test_read_raw_rejeita_extensao_desconhecida(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("nada", encoding="utf-8")
    with pytest.raises(ValueError):
        DataCurator().read_raw(f)


# ── load_sidecar ─────────────────────────────────────────────────────────────

def test_load_sidecar_ausente_retorna_none(tmp_path):
    assert load_sidecar(tmp_path, "long_method") is None


def test_load_sidecar_presente_indexa_por_id(tmp_path):
    _write_jsonl(tmp_path / "long_method.reviews.jsonl",
                 [{"id": "a", "status": "clean"}, {"id": "b", "status": "rejected"}])
    sc = load_sidecar(tmp_path, "long_method")
    assert set(sc) == {"a", "b"} and sc["b"]["status"] == "rejected"


# ── apply_verdicts ───────────────────────────────────────────────────────────

def test_apply_verdicts_mantem_clean_descarta_rejected_e_nao_revisado():
    raw = [_pair("r", 1), _pair("r", 2), _pair("r", 3)]
    sidecar = {
        "id-r-1": {"id": "id-r-1", "status": "clean"},
        "id-r-2": {"id": "id-r-2", "status": "rejected"},
        # id-r-3 — sem veredito (não-revisado)
    }
    assert [k["id"] for k in apply_verdicts(raw, sidecar)] == ["id-r-1"]


def test_apply_verdicts_noisy_substitui_pelo_recorte():
    raw = [_pair("r", 1)]
    sidecar = {"id-r-1": {"id": "id-r-1", "status": "noisy",
                          "before_clean": "def g():\n    pass\n",
                          "after_clean": "def g():\n    return 1\n"}}
    kept = apply_verdicts(raw, sidecar)
    assert len(kept) == 1
    assert kept[0]["before_code"] == "def g():\n    pass\n"
    assert kept[0]["after_code"] == "def g():\n    return 1\n"


def test_apply_verdicts_noisy_sem_recorte_e_descartado():
    raw = [_pair("r", 1)]
    sidecar = {"id-r-1": {"id": "id-r-1", "status": "noisy",
                          "before_clean": None, "after_clean": None}}
    assert apply_verdicts(raw, sidecar) == []


# ── read_curated: fail-fast ──────────────────────────────────────────────────

def test_read_curated_falha_sem_sidecar(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_jsonl(raw_dir / "long_method.jsonl", [_pair("r", 1)])
    with pytest.raises(FileNotFoundError):
        DataCurator().read_curated(raw_dir, tmp_path / "reviews")


def test_read_curated_allow_unreviewed_usa_raw(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_jsonl(raw_dir / "long_method.jsonl", [_pair("r", 1), _pair("r", 2)])
    cur = DataCurator().read_curated(raw_dir, tmp_path / "reviews", allow_unreviewed=True)
    assert len(cur._pairs) == 2


# ── CLI end-to-end ───────────────────────────────────────────────────────────

def _dataset_fixture(tmp_path):
    """6 pares clean — 3 repos x 2 — satisfaz split() (>=3 repos, >=3/smell)."""
    raw_dir, reviews_dir = tmp_path / "raw", tmp_path / "reviews"
    raw_dir.mkdir()
    reviews_dir.mkdir()
    pairs, verdicts, n = [], [], 0
    for repo in ("repoA", "repoB", "repoC"):
        for _ in range(2):
            n += 1
            p = _pair(repo, n)
            pairs.append(p)
            verdicts.append({"id": p["id"], "status": "clean"})
    _write_jsonl(raw_dir / "long_method.jsonl", pairs)
    _write_jsonl(reviews_dir / "long_method.reviews.jsonl", verdicts)
    return raw_dir, reviews_dir


def test_cli_gera_datasetdict(tmp_path):
    from datasets import load_from_disk

    raw_dir, reviews_dir = _dataset_fixture(tmp_path)
    out_dir = tmp_path / "ds"
    main(["--raw-dir", str(raw_dir), "--reviews-dir", str(reviews_dir),
          "--output-dir", str(out_dir)])
    ds = load_from_disk(str(out_dir))
    assert set(ds.keys()) == {"train", "validation", "test"}
    assert sum(ds[k].num_rows for k in ds) == 6


def test_cli_falha_sem_sidecar(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    _write_jsonl(raw_dir / "long_method.jsonl", [_pair("r", 1)])
    with pytest.raises(FileNotFoundError):
        main(["--raw-dir", str(raw_dir), "--reviews-dir", str(tmp_path / "rev"),
              "--output-dir", str(tmp_path / "ds")])
