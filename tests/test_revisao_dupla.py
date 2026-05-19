"""Testes da revisão dupla (PR 6, D1) — curador + curate.py.

Cobre: chave composta `(id, revisor)` no sidecar; filtro por bloco e modo
adjudicação no curador; merge dos 2 vereditos; Cohen's kappa; degradação para
o modo de revisor único (PR 5) quando não há `assignment.json`.
"""
import json

import pytest

from extracao.execucao import filtro_smells
from trilha_b.data.curate import (
    DataCurator, cohen_kappa_por_bloco, load_sidecar_keyed, merge_double_review,
)


def _write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _valid_pair(repo: str, n: int) -> dict:
    return {
        "id": f"id-{repo}-{n}",
        "before_code": f"def f{n}():\n    x = {n}\n    return x\n",
        "after_code": f"def f{n}():\n    return {n}\n",
        "smell_type": "R1", "repo": repo, "commit_hash": f"c{n}",
        "file": "m.py", "function_name": f"f{n}",
    }


def _block(r1, r2, adj):
    return {"revisores": [r1, r2], "adjudicator": adj}


# ── filtro_smells: chave composta (id, revisor) ──────────────────────────────

def test_save_review_chave_composta_coexiste(tmp_path):
    filtro_smells.save_review(tmp_path, "long_method",
                              {"id": "p1", "status": "clean", "reviewer": "A"})
    filtro_smells.save_review(tmp_path, "long_method",
                              {"id": "p1", "status": "rejected", "reviewer": "B"})
    reviews = filtro_smells.load_reviews(tmp_path, "long_method")
    assert reviews[("p1", "A")]["status"] == "clean"
    assert reviews[("p1", "B")]["status"] == "rejected"


def test_load_reviews_registro_legado_vira_id_none(tmp_path):
    (tmp_path / "long_method.reviews.jsonl").write_text(
        '{"id":"p1","status":"clean"}\n', encoding="utf-8")
    assert ("p1", None) in filtro_smells.load_reviews(tmp_path, "long_method")


def test_review_grava_reviewer_do_config_nao_do_cliente(tmp_path):
    reviews_dir = tmp_path / "reviews"
    app = filtro_smells.create_app(tmp_path / "raw", reviews_dir, 200, reviewer="ana")
    app.config["TESTING"] = True
    # o cliente tenta forjar reviewer="hacker" — deve ser ignorado
    app.test_client().post("/review", json={
        "smell": "long_method", "id": "p1", "status": "clean", "reviewer": "hacker"})
    rec = json.loads((reviews_dir / "long_method.reviews.jsonl").read_text().splitlines()[0])
    assert rec["reviewer"] == "ana"


# ── filtro_smells: load_pairs filtra por bloco ───────────────────────────────

def test_load_pairs_filtra_blocos_do_revisor(tmp_path):
    data_dir, reviews_dir = tmp_path / "raw", tmp_path / "reviews"
    data_dir.mkdir()
    reviews_dir.mkdir()
    raw = [{"id": f"p{i}", "before_code": "a", "after_code": "b", "smell_type": "R1"}
           for i in range(6)]
    _write_jsonl(data_dir / "long_method.jsonl", raw)
    assignment = {"blocos": [
        {"id": "B1", "revisores": ["A", "B"], "adjudicator": "C",
         "pares": [{"id": "p0", "smell": "long_method"}, {"id": "p1", "smell": "long_method"}]},
        {"id": "B2", "revisores": ["B", "C"], "adjudicator": "A",
         "pares": [{"id": "p2", "smell": "long_method"}, {"id": "p3", "smell": "long_method"}]},
        {"id": "B3", "revisores": ["C", "A"], "adjudicator": "B",
         "pares": [{"id": "p4", "smell": "long_method"}, {"id": "p5", "smell": "long_method"}]},
    ]}
    # A é revisor primário em B1 e B3 → vê p0,p1,p4,p5
    pairs, total, _ = filtro_smells.load_pairs(
        data_dir, reviews_dir, "long_method", "all", 100,
        reviewer="A", assignment=assignment)
    assert {p["id"] for p in pairs} == {"p0", "p1", "p4", "p5"}
    assert total == 4


def test_load_pairs_adjudicar_mostra_so_divergentes(tmp_path):
    data_dir, reviews_dir = tmp_path / "raw", tmp_path / "reviews"
    data_dir.mkdir()
    reviews_dir.mkdir()
    raw = [{"id": f"p{i}", "before_code": "a", "after_code": "b", "smell_type": "R1"}
           for i in range(2)]
    _write_jsonl(data_dir / "long_method.jsonl", raw)
    assignment = {"blocos": [
        {"id": "B1", "revisores": ["A", "B"], "adjudicator": "C",
         "pares": [{"id": "p0", "smell": "long_method"}, {"id": "p1", "smell": "long_method"}]}]}
    # p0: A clean / B rejected → divergente ; p1: A clean / B clean → consenso
    _write_jsonl(reviews_dir / "long_method.reviews.jsonl", [
        {"id": "p0", "status": "clean", "reviewer": "A"},
        {"id": "p0", "status": "rejected", "reviewer": "B"},
        {"id": "p1", "status": "clean", "reviewer": "A"},
        {"id": "p1", "status": "clean", "reviewer": "B"}])
    # C adjudica B1 — modo adjudicação mostra só o par divergente
    pairs, _, _ = filtro_smells.load_pairs(
        data_dir, reviews_dir, "long_method", "all", 100,
        reviewer="C", assignment=assignment, adjudicar=True)
    assert {p["id"] for p in pairs} == {"p0"}


# ── curate.py: merge dos 2 vereditos (D1) ────────────────────────────────────

def test_merge_consenso_clean_mantem():
    raw = [{"id": "p1", "before_code": "a", "after_code": "b"}]
    sk = {("p1", "A"): {"status": "clean"}, ("p1", "B"): {"status": "clean"}}
    assert len(merge_double_review(raw, sk, {"p1": _block("A", "B", "C")})) == 1


def test_merge_consenso_rejected_descarta():
    raw = [{"id": "p1"}]
    sk = {("p1", "A"): {"status": "rejected"}, ("p1", "B"): {"status": "rejected"}}
    assert merge_double_review(raw, sk, {"p1": _block("A", "B", "C")}) == []


def test_merge_divergencia_usa_veredito_do_adjudicador():
    raw = [{"id": "p1", "before_code": "a", "after_code": "b"}]
    sk = {("p1", "A"): {"status": "clean"}, ("p1", "B"): {"status": "rejected"},
          ("p1", "C"): {"status": "clean"}}
    assert len(merge_double_review(raw, sk, {"p1": _block("A", "B", "C")})) == 1


def test_merge_divergencia_adjudicador_rejected_descarta():
    raw = [{"id": "p1"}]
    sk = {("p1", "A"): {"status": "clean"}, ("p1", "B"): {"status": "rejected"},
          ("p1", "C"): {"status": "rejected"}}
    assert merge_double_review(raw, sk, {"p1": _block("A", "B", "C")}) == []


def test_merge_divergencia_sem_adjudicacao_descarta():
    raw = [{"id": "p1"}]
    sk = {("p1", "A"): {"status": "clean"}, ("p1", "B"): {"status": "rejected"}}
    assert merge_double_review(raw, sk, {"p1": _block("A", "B", "C")}) == []


def test_merge_revisao_incompleta_descarta():
    raw = [{"id": "p1"}]
    sk = {("p1", "A"): {"status": "clean"}}  # B ainda não revisou
    assert merge_double_review(raw, sk, {"p1": _block("A", "B", "C")}) == []


def test_merge_noisy_vai_para_adjudicacao():
    """Dois `noisy` não são consenso clean/rejected — o adjudicador decide."""
    raw = [{"id": "p1", "before_code": "a", "after_code": "b"}]
    sk = {("p1", "A"): {"status": "noisy", "before_clean": "x", "after_clean": "y"},
          ("p1", "B"): {"status": "noisy", "before_clean": "x2", "after_clean": "y2"},
          ("p1", "C"): {"status": "clean"}}
    kept = merge_double_review(raw, sk, {"p1": _block("A", "B", "C")})
    assert len(kept) == 1 and kept[0]["before_code"] == "a"  # adjudicador C: clean


# ── curate.py: Cohen's kappa ─────────────────────────────────────────────────

def test_kappa_misto_bate_com_sklearn():
    from sklearn.metrics import cohen_kappa_score
    labels = {"A": ["clean", "clean", "rejected", "rejected"],
              "B": ["clean", "rejected", "rejected", "clean"]}
    assignment = {"blocos": [{"id": "B1", "revisores": ["A", "B"], "adjudicator": "C",
        "pares": [{"id": f"p{i}", "smell": "lm"} for i in range(4)]}]}
    sk = {}
    for i in range(4):
        sk[(f"p{i}", "A")] = {"status": labels["A"][i]}
        sk[(f"p{i}", "B")] = {"status": labels["B"][i]}
    out = cohen_kappa_por_bloco({"lm": sk}, assignment)
    assert out["B1"] == pytest.approx(cohen_kappa_score(labels["A"], labels["B"]))


def test_kappa_rotulos_identicos_e_none():
    assignment = {"blocos": [{"id": "B1", "revisores": ["A", "B"], "adjudicator": "C",
        "pares": [{"id": f"p{i}", "smell": "lm"} for i in range(3)]}]}
    sk = {}
    for i in range(3):
        sk[(f"p{i}", "A")] = {"status": "clean"}
        sk[(f"p{i}", "B")] = {"status": "clean"}
    assert cohen_kappa_por_bloco({"lm": sk}, assignment)["B1"] is None


def test_kappa_poucos_pares_e_none():
    assignment = {"blocos": [{"id": "B1", "revisores": ["A", "B"], "adjudicator": "C",
        "pares": [{"id": "p0", "smell": "lm"}]}]}
    sk = {("p0", "A"): {"status": "clean"}, ("p0", "B"): {"status": "rejected"}}
    assert cohen_kappa_por_bloco({"lm": sk}, assignment)["B1"] is None


# ── curate.py: load_sidecar_keyed ────────────────────────────────────────────

def test_load_sidecar_keyed_ausente_retorna_none(tmp_path):
    assert load_sidecar_keyed(tmp_path, "long_method") is None


def test_load_sidecar_keyed_indexa_por_id_revisor(tmp_path):
    _write_jsonl(tmp_path / "lm.reviews.jsonl", [
        {"id": "a", "status": "clean"},  # legado, sem reviewer
        {"id": "b", "status": "clean", "reviewer": "A"}])
    sk = load_sidecar_keyed(tmp_path, "lm")
    assert ("a", None) in sk and ("b", "A") in sk


# ── curate.py: integração read_curated ───────────────────────────────────────

def test_read_curated_degrada_para_revisor_unico_sem_assignment(tmp_path):
    """Sem assignment.json, read_curated == modo PR 5 (um veredito por par)."""
    raw_dir, reviews_dir = tmp_path / "raw", tmp_path / "reviews"
    raw_dir.mkdir()
    reviews_dir.mkdir()
    pairs = [_valid_pair("r", i) for i in range(3)]
    _write_jsonl(raw_dir / "long_method.jsonl", pairs)
    _write_jsonl(reviews_dir / "long_method.reviews.jsonl",
                 [{"id": p["id"], "status": "clean", "reviewer": None} for p in pairs])
    cur = DataCurator().read_curated(raw_dir, reviews_dir)
    assert len(cur._pairs) == 3
    assert cur.kappa is None  # sem revisão dupla


def test_read_curated_modo_duplo_mescla_e_calcula_kappa(tmp_path):
    raw_dir, reviews_dir = tmp_path / "raw", tmp_path / "reviews"
    raw_dir.mkdir()
    reviews_dir.mkdir()
    pairs = [_valid_pair("r", i) for i in range(3)]
    _write_jsonl(raw_dir / "long_method.jsonl", pairs)
    assignment = {"seed": 1, "revisores": ["A", "B", "C"], "blocos": [
        {"id": "B1", "revisores": ["A", "B"], "adjudicator": "C",
         "pares": [{"id": p["id"], "smell": "long_method"} for p in pairs]}]}
    (reviews_dir / "assignment.json").write_text(json.dumps(assignment), encoding="utf-8")
    # p0 consenso clean ; p1 divergente → adjudicador clean ; p2 consenso rejected
    _write_jsonl(reviews_dir / "long_method.reviews.jsonl", [
        {"id": pairs[0]["id"], "status": "clean", "reviewer": "A"},
        {"id": pairs[0]["id"], "status": "clean", "reviewer": "B"},
        {"id": pairs[1]["id"], "status": "clean", "reviewer": "A"},
        {"id": pairs[1]["id"], "status": "rejected", "reviewer": "B"},
        {"id": pairs[1]["id"], "status": "clean", "reviewer": "C"},
        {"id": pairs[2]["id"], "status": "rejected", "reviewer": "A"},
        {"id": pairs[2]["id"], "status": "rejected", "reviewer": "B"}])
    cur = DataCurator().read_curated(raw_dir, reviews_dir)
    assert len(cur._pairs) == 2  # p0 + p1 mantidos, p2 (consenso rejected) descartado
    assert cur.kappa is not None and "B1" in cur.kappa
