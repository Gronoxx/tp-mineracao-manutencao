"""Testes do catálogo de oracles (D5/C3 — sprint Dia 2).

Cobre: schema `OracleEntry`, parsers do adaptador PyRef e ingestão
end-to-end de uma amostra mínima de cada fonte.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.oracle import OracleEntry
from scripts.ingest_oracles import (
    PYREF_TO_SMELL,
    ingest_pyref,
    ingest_sourcery,
    parse_pyref_commit_url,
    parse_pyref_description,
)


# --- OracleEntry: validação de schema ---

def test_oracle_entry_minimo():
    """Repo + source_dataset + external_refactoring_type bastam para criar."""
    e = OracleEntry(
        source_dataset="pyref",
        external_refactoring_type="Extract Method",
        repo="https://github.com/foo/bar",
    )
    assert e.validation == "unknown"
    assert e.smell_type is None
    assert e.commit_hash is None


def test_oracle_entry_round_trip_jsonl():
    """Serialização compatível com jsonl (model_dump_json + parse)."""
    e1 = OracleEntry(
        source_dataset="pyref", external_refactoring_type="Extract Method",
        repo="https://github.com/foo/bar", commit_hash="abc123",
        smell_type="R1", validation="TP",
    )
    e2 = OracleEntry.model_validate_json(e1.model_dump_json())
    assert e2 == e1


def test_oracle_entry_smell_type_invalido():
    """Smells fora de R1..R5 rejeitados (pydantic Literal)."""
    with pytest.raises(ValidationError):
        OracleEntry(
            source_dataset="pyref",
            external_refactoring_type="X",
            repo="https://github.com/foo/bar",
            smell_type="R99",
        )


def test_oracle_entry_source_dataset_invalido():
    """Fontes fora do conjunto canônico rejeitadas."""
    with pytest.raises(ValidationError):
        OracleEntry(
            source_dataset="unknown_source",
            external_refactoring_type="X",
            repo="https://github.com/foo/bar",
        )


# --- Parsers PyRef ---

def test_parse_pyref_commit_url_valida():
    repo, sha = parse_pyref_commit_url(
        "https://github.com/dit/dit/commit/03506ef2d7839511ca4e0f6bee856a248a15f244"
    )
    assert repo == "https://github.com/dit/dit"
    assert sha == "03506ef2d7839511ca4e0f6bee856a248a15f244"


def test_parse_pyref_commit_url_invalida():
    repo, sha = parse_pyref_commit_url("not a url")
    assert repo is None and sha is None


def test_parse_pyref_description_extrai_file_e_method():
    file, func = parse_pyref_description(
        'Location: dit/algorithms/jsd.py\nThe method "JSD" is renamed to "jensen_shannon_divergence"'
    )
    assert file == "dit/algorithms/jsd.py"
    assert func == "JSD"  # primeira ocorrência entre aspas


def test_parse_pyref_description_vazia():
    file, func = parse_pyref_description("")
    assert file is None and func is None


def test_pyref_smell_mapping_extract_method_e_r1():
    """Sanity check do mapeamento: Extract Method → R1 (único smell direto)."""
    assert PYREF_TO_SMELL["Extract Method"] == "R1"
    assert PYREF_TO_SMELL["Rename Method"] is None  # não há LoRA correspondente


# --- Ingestão end-to-end (fixtures pequenas em tmp_path) ---

def test_ingest_pyref_grava_jsonl_carregavel(tmp_path: Path):
    """PyRef CSV → jsonl → OracleEntry round-trip."""
    csv_path = tmp_path / "pyref.csv"
    csv_path.write_text(
        'commit,refactoring type,description,tool,validation,note\n'
        'https://github.com/foo/bar/commit/deadbeef1234567890abcdef1234567890abcdef,'
        'Extract Method,"Location: mod.py\nfn `g`",PyRef,TP,\n'
        'https://github.com/foo/bar/commit/cafebabe1234567890abcdef1234567890abcdef,'
        'Rename Method,"Location: mod.py\nfn `h`",PyRef,FP,\n',
        encoding="utf-8",
    )
    out = tmp_path / "out.jsonl"
    n = ingest_pyref(csv_path, out)
    assert n == 2
    records = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    extract = next(r for r in records if r["external_refactoring_type"] == "Extract Method")
    assert extract["smell_type"] == "R1"
    assert extract["validation"] == "TP"
    rename = next(r for r in records if r["external_refactoring_type"] == "Rename Method")
    assert rename["smell_type"] is None
    assert rename["validation"] == "FP"
    # Round-trip: cada linha deve carregar como OracleEntry
    for r in records:
        OracleEntry.model_validate(r)


def test_ingest_sourcery_extrai_funcoes(tmp_path: Path):
    """Sourcery .py → uma OracleEntry por função/classe."""
    src_dir = tmp_path / "refactorings"
    src_dir.mkdir()
    (src_dir / "demo.py").write_text(
        "def alpha():\n    return 1\n"
        "def beta(x):\n    return x + 1\n",
        encoding="utf-8",
    )
    out = tmp_path / "sourcery.jsonl"
    n = ingest_sourcery(src_dir, out)
    assert n == 2
    records = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    names = {r["function_name"] for r in records}
    assert names == {"alpha", "beta"}
    assert all(r["source_dataset"] == "sourcery" for r in records)
    assert all(r["smell_type"] is None for r in records)  # sem mapeamento direto


# --- Sanity check sobre o catálogo real (se presente) ---

def test_pyref_test_jsonl_presente_e_consistente():
    """Se o catálogo PyRef foi ingerido, deve carregar inteiro como OracleEntry."""
    p = Path(__file__).resolve().parent.parent / "data" / "test" / "oracle_pyref_test.jsonl"
    if not p.exists():
        pytest.skip(f"catálogo {p} não foi gerado neste ambiente")
    with p.open(encoding="utf-8") as f:
        entries = [OracleEntry.model_validate_json(l) for l in f if l.strip()]
    assert len(entries) > 100  # PyRef tem ~573 entradas
    # Pelo menos um Extract Method TP mapeado a R1
    r1_tp = [e for e in entries
             if e.smell_type == "R1" and e.validation == "TP"]
    assert len(r1_tp) >= 15  # plano-mãe assume ~15-25 disponíveis
