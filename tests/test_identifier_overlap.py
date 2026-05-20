"""C5c.3 (Dia 8 do sprint) — identifier overlap mitigation.

Combate FP em cross-file matching: duas funções com mesma forma AST mas
vocabulário disjunto (e.g., `_validate_http_input` vs `_validate_db_input`
em domínios diferentes) recebem similaridade alta pelo APTED — mas o
Jaccard de identificadores fica baixo, permitindo descartá-las.

Testes cobrem o cálculo isolado e o impacto no `find_cross_file_candidates`
e no `mine()` end-to-end.
"""
import json
import subprocess
from pathlib import Path

import pytest

from extracao.mineracao.ast_similarity import (
    find_cross_file_candidates,
    identifier_overlap,
)
from extracao.mineracao.minerador import mine


# --- identifier_overlap puro ---

def test_identifier_overlap_funcoes_identicas_e_um():
    src = "def f(a, b):\n    return a + b\n"
    assert identifier_overlap(src, src) == 1.0


def test_identifier_overlap_vocabulario_disjunto_e_zero():
    """Mesma forma, identificadores totalmente diferentes → overlap = 0."""
    a = "def f(x):\n    return x.foo()\n"
    b = "def g(y):\n    return y.bar()\n"
    # x e y são parametros; foo e bar são atributos. Sem interseção.
    assert identifier_overlap(a, b) == 0.0


def test_identifier_overlap_parcial():
    """Algum vocabulário em comum → entre 0 e 1."""
    a = "def f(user, db):\n    return db.find(user.id)\n"
    b = "def f(user, cache):\n    return cache.get(user.id)\n"
    # comum: {user, id, find/get?, db/cache?}. find vs get diferem;
    # db vs cache diferem. Comum: user, id (+ "f" via Name? não — f é o nome
    # da função, está em FunctionDef.name, não em Name).
    overlap = identifier_overlap(a, b)
    assert overlap is not None
    assert 0.0 < overlap < 1.0


def test_identifier_overlap_codigo_invalido_e_none():
    assert identifier_overlap("def f(): return 1", "lixo ((( ") is None


def test_identifier_overlap_dois_validate_input_falsos_positivos():
    """Cenário-alvo do C5c.3: dois `_validate_input` em domínios diferentes.

    AST similarity entre eles é altíssima (estrutura idêntica), mas o
    vocabulário difere significativamente."""
    http = (
        "def _validate_input(request):\n"
        "    if not request.headers:\n"
        "        raise HTTPException(400)\n"
        "    return request.body\n"
    )
    db = (
        "def _validate_input(query):\n"
        "    if not query.columns:\n"
        "        raise DBException(400)\n"
        "    return query.rows\n"
    )
    overlap = identifier_overlap(http, db)
    assert overlap is not None
    # request/query, headers/columns, body/rows, HTTPException/DBException
    # tudo difere. A única interseção é o próprio "_validate_input"... que
    # NÃO entra (é o nome da função, não um ast.Name). E "400" é literal,
    # não nome. Overlap deve ser bem baixo (~0).
    assert overlap < 0.3


# --- Integração com find_cross_file_candidates ---

def test_find_cross_file_sem_overlap_filter_aceita_falsos_positivos():
    """Sem `identifier_overlap_threshold` (default 0.0), os dois
    `_validate_input` viram candidato (estrutura idêntica, AST sim = 1)."""
    before = {
        "http.py": (
            "def _validate_input(request):\n"
            "    if not request.headers:\n"
            "        raise HTTPException(400)\n"
            "    return request.body\n"
        ),
    }
    after = {
        "db.py": (
            "def _validate_input(query):\n"
            "    if not query.columns:\n"
            "        raise DBException(400)\n"
            "    return query.rows\n"
        ),
    }
    cands = find_cross_file_candidates(
        before, after,
        similarity_threshold=0.7,
        identifier_overlap_threshold=0.0,
    )
    assert len(cands) == 1   # FP aceito


def test_find_cross_file_com_overlap_filter_rejeita_falsos_positivos():
    """Com `identifier_overlap_threshold=0.5`, os dois `_validate_input` em
    domínios diferentes são REJEITADOS (vocabulário disjunto)."""
    before = {
        "http.py": (
            "def _validate_input(request):\n"
            "    if not request.headers:\n"
            "        raise HTTPException(400)\n"
            "    return request.body\n"
        ),
    }
    after = {
        "db.py": (
            "def _validate_input(query):\n"
            "    if not query.columns:\n"
            "        raise DBException(400)\n"
            "    return query.rows\n"
        ),
    }
    cands = find_cross_file_candidates(
        before, after,
        similarity_threshold=0.7,
        identifier_overlap_threshold=0.5,
    )
    assert cands == []   # FP rejeitado


def test_find_cross_file_overlap_preserva_true_positives():
    """A mesma função realmente movida tem overlap alto — não é filtrada."""
    before = {
        "utils.py": (
            "def helper():\n    return 1\n\n"
            "def process_user(user, db):\n"
            "    user.last_seen = db.now()\n"
            "    return db.save(user)\n"
        ),
    }
    after = {
        "models.py": (
            "def process_user(user, db):\n"
            "    user.last_seen = db.now()\n"
            "    return db.save(user)\n"
        ),
    }
    cands = find_cross_file_candidates(
        before, after,
        similarity_threshold=0.7,
        identifier_overlap_threshold=0.5,
    )
    assert len(cands) == 1
    c = cands[0]
    assert c["function_name_before"] == "process_user"
    assert c["function_name_after"] == "process_user"
    assert c["identifier_overlap"] == 1.0


# --- Integração end-to-end com mine() ---

def _git(d: Path, *args):
    subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)


@pytest.fixture
def repo_fp_overlap(tmp_path):
    """Cenário-FP: dois `_validate_input` quase idênticos em estrutura
    aparecem em arquivos diferentes (um sai de http.py, outro entra em
    db.py). AST sim ≈ 1.0, identifier_overlap baixo (~0.1).

    Sem `identifier_overlap_threshold`, mine() aceita o "par"; com o
    threshold, rejeita.
    """
    d = tmp_path / "repo"
    d.mkdir()
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t.t")
    _git(d, "config", "user.name", "t")
    (d / "http.py").write_text(
        "def _validate_input(request):\n"
        "    if not request.headers:\n"
        "        raise HTTPException(400)\n"
        "    return request.body\n",
        encoding="utf-8",
    )
    (d / "db.py").write_text(
        "class Model:\n    pass\n",
        encoding="utf-8",
    )
    _git(d, "add", "."); _git(d, "commit", "-q", "-m", "init")

    (d / "http.py").write_text(
        "# moved\n",
        encoding="utf-8",
    )
    (d / "db.py").write_text(
        "class Model:\n    pass\n\n"
        "def _validate_input(query):\n"
        "    if not query.columns:\n"
        "        raise DBException(400)\n"
        "    return query.rows\n",
        encoding="utf-8",
    )
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "refactor: consolidate validation")
    return str(d)


def test_mine_overlap_threshold_zero_aceita_fp(repo_fp_overlap, tmp_path):
    """Com `identifier_overlap_threshold=0.0` (default), os 2 `_validate_input`
    são pareados — não tem detector R1..R5 cobrindo isso (nenhum smell dispara
    nesses corpos triviais), então 0 pares saem. Mas o caminho cross-file
    PROCESSA o candidato (verificável via debug). Aqui só asseguramos que não
    crasha."""
    counts = mine(
        repo_url=repo_fp_overlap,
        output_path=tmp_path / "out",
        cross_file_threshold=0.7,
        identifier_overlap_threshold=0.0,
    )
    # Detectores não disparam → nenhum par emitido. Mas o pipeline rodou.
    assert isinstance(counts, dict)


def test_mine_overlap_threshold_alto_descarta_antes_de_verify(
    repo_fp_overlap, tmp_path
):
    """Threshold de overlap 0.5 — o candidato FP nem chega ao verify_pair.
    Sanity: pipeline roda sem crash. (Verificação positiva requer um caso
    onde o detector dispara, coberto em test_minerador_cross_file.py.)"""
    counts = mine(
        repo_url=repo_fp_overlap,
        output_path=tmp_path / "out",
        cross_file_threshold=0.7,
        identifier_overlap_threshold=0.5,
    )
    assert isinstance(counts, dict)
