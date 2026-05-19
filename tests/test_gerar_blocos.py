"""Testes da atribuição de blocos — `extracao/execucao/gerar_blocos.py` (PR 6).

Foco: distribuição estratificada por smell em 3 blocos, rodízio de revisores
com adjudicador, e recusa de sobrescrever um assignment existente.
"""
import pytest

from extracao.execucao.gerar_blocos import _coletar_pares, assign_blocks, write_assignment


def _pares(n: int, smell: str = "long_method") -> list[dict]:
    return [{"id": f"{smell}-{i}", "smell": smell} for i in range(n)]


def test_assign_blocks_tres_blocos_com_rodizio_de_revisores():
    a = assign_blocks(_pares(9), ["A", "B", "C"])
    assert len(a["blocos"]) == 3
    blocos = {b["id"]: b for b in a["blocos"]}
    assert blocos["B1"]["revisores"] == ["A", "B"] and blocos["B1"]["adjudicator"] == "C"
    assert blocos["B2"]["revisores"] == ["B", "C"] and blocos["B2"]["adjudicator"] == "A"
    assert blocos["B3"]["revisores"] == ["C", "A"] and blocos["B3"]["adjudicator"] == "B"


def test_assign_blocks_estratifica_por_smell():
    pares = _pares(9, "long_method") + _pares(9, "magic_numbers")
    a = assign_blocks(pares, ["A", "B", "C"], seed=1)
    for smell in ("long_method", "magic_numbers"):
        por_bloco = [sum(1 for p in b["pares"] if p["smell"] == smell)
                     for b in a["blocos"]]
        assert max(por_bloco) - min(por_bloco) <= 1  # cada smell ~1/3 por bloco


def test_assign_blocks_cada_par_aparece_uma_vez():
    pares = _pares(10)
    a = assign_blocks(pares, ["A", "B", "C"])
    todos = [p["id"] for b in a["blocos"] for p in b["pares"]]
    assert sorted(todos) == sorted(p["id"] for p in pares)
    assert len(todos) == len(set(todos))


def test_assign_blocks_exige_tres_revisores_distintos():
    with pytest.raises(ValueError):
        assign_blocks(_pares(3), ["A", "B"])
    with pytest.raises(ValueError):
        assign_blocks(_pares(3), ["A", "B", "A"])


def test_assign_blocks_deterministico():
    pares = _pares(12)
    assert (assign_blocks(pares, ["A", "B", "C"], seed=42)
            == assign_blocks(pares, ["A", "B", "C"], seed=42))


def test_write_assignment_recusa_sobrescrever(tmp_path):
    f = tmp_path / "assignment.json"
    a = assign_blocks(_pares(6), ["A", "B", "C"])
    write_assignment(f, a)
    with pytest.raises(FileExistsError):
        write_assignment(f, a)
    write_assignment(f, a, force=True)  # --force sobrescreve


def test_coletar_pares_le_jsonl_e_marca_o_smell(tmp_path):
    (tmp_path / "long_method.jsonl").write_text(
        '{"id":"a","smell_type":"R1"}\n{"id":"b","smell_type":"R1"}\n', encoding="utf-8")
    pares = _coletar_pares(tmp_path)
    assert {p["id"] for p in pares} == {"a", "b"}
    assert all(p["smell"] == "long_method" for p in pares)
