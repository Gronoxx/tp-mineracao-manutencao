"""Testes do merge de saída do minerador — F1.

`mine()` escrevia cada `<smell>.jsonl` em modo `"w"`; o runner chama `mine()`
por repositório no mesmo diretório, então cada repo apagava o anterior. O fluxo
de escrita (`_merge_write`) agora mescla com o conteúdo já em disco.
"""
from extracao.mineracao import minerador


def _rec(rid: str, smell: str = "R1") -> dict:
    return {"id": rid, "smell_type": smell, "before_code": "a", "after_code": "b"}


def test_load_existing_arquivo_ausente(tmp_path):
    assert minerador._load_existing(tmp_path / "nao_existe.jsonl") == {}


def test_load_existing_indexa_por_id(tmp_path):
    f = tmp_path / "x.jsonl"
    f.write_text('{"id":"a","smell_type":"R1"}\n\n{"id":"b","smell_type":"R1"}\n')
    out = minerador._load_existing(f)
    assert set(out) == {"a", "b"}


def test_merge_write_acumula_entre_chamadas(tmp_path):
    """F1 — duas chamadas (= dois repos) no mesmo diretório acumulam."""
    minerador._merge_write(tmp_path, {"R1": {"id1": _rec("id1")}})
    minerador._merge_write(tmp_path, {"R1": {"id2": _rec("id2")}})
    out = minerador._load_existing(tmp_path / "long_method.jsonl")
    assert set(out) == {"id1", "id2"}   # o 2o repo nao apagou o 1o


def test_merge_write_idempotente(tmp_path):
    """Rodar o mesmo conteúdo 2× não duplica linhas (dedup por id)."""
    by_smell = {"R1": {"id1": _rec("id1")}}
    minerador._merge_write(tmp_path, by_smell)
    minerador._merge_write(tmp_path, by_smell)
    lines = (tmp_path / "long_method.jsonl").read_text().splitlines()
    assert len(lines) == 1


def test_merge_write_smells_distintos_nao_colidem(tmp_path):
    minerador._merge_write(tmp_path, {"R1": {"a": _rec("a", "R1")}})
    minerador._merge_write(tmp_path, {"R3": {"b": _rec("b", "R3")}})
    assert minerador._load_existing(tmp_path / "long_method.jsonl").keys() == {"a"}
    assert minerador._load_existing(tmp_path / "magic_numbers.jsonl").keys() == {"b"}


def test_merge_write_counts_sao_da_chamada_atual(tmp_path):
    """`counts` conta os pares DESTA chamada, não o total acumulado em disco
    — senão o runner somaria o mesmo par várias vezes."""
    minerador._merge_write(tmp_path, {"R1": {"id1": _rec("id1")}})
    counts = minerador._merge_write(tmp_path, {"R1": {"id2": _rec("id2")}})
    assert counts == {"R1": 1}
