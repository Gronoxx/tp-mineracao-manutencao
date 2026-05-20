"""C5c.2 (Dia 6-7 do sprint) — integração end-to-end de cross-file matching
em `mine()`.

O caso que `extract_candidates` per-file NÃO cobre e o `RENAME` do git tampouco
(quando a similaridade entre os arquivos cai abaixo do threshold do git):
uma função se move de `utils.py` para `models.py` (com possível rename), e
nenhum dos arquivos sozinho fornece o par before/after — o casamento exige
visão conjunta dos arquivos do commit.

Estes testes ativam a flag `cross_file_threshold` em `mine()` e validam que:
    1. O modo desligado (default) preserva comportamento anterior (sem par).
    2. O modo ligado captura o par cross-file.
    3. O smell correto é atribuído conforme o detector dispara.
"""
import json
import subprocess
from pathlib import Path

import pytest

from extracao.mineracao.minerador import mine


def _git(d: Path, *args):
    subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)


def _init_repo(d: Path):
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t.t")
    _git(d, "config", "user.name", "t")


@pytest.fixture
def repo_funcao_movida_entre_arquivos(tmp_path):
    """Função `foo` migra de `utils.py` → `models.py` ENTRE arquivos
    estruturalmente diferentes (git não detecta file rename) E sofre dead
    code removal (smell R5).

    Refatorações que mudam drasticamente a estrutura (Parameter Object 8→1)
    têm AST similarity muito baixa (~0.17 medido empiricamente), abaixo de
    qualquer threshold realista (~0.7). Cross-file matching é mais útil
    para refatorações que PRESERVAM estrutura: dead code, magic number→
    constant, guard clauses. Aqui usamos dead code.
    """
    d = tmp_path / "repo"
    d.mkdir()
    _init_repo(d)
    # utils.py: helper_x + foo com variáveis mortas
    (d / "utils.py").write_text(
        "def helper_x():\n    return 1\n\n"
        "def foo(x, y):\n"
        "    dead1 = x + y\n"
        "    dead2 = x * y\n"
        "    dead3 = x - y\n"
        "    result = x ** 2 + y ** 2\n"
        "    return result\n",
        encoding="utf-8",
    )
    # models.py: classe sem foo
    (d / "models.py").write_text(
        "class Model:\n    def __init__(self):\n        self.x = 0\n",
        encoding="utf-8",
    )
    _git(d, "add", "."); _git(d, "commit", "-q", "-m", "init")

    # depois: foo sai de utils.py e aparece em models.py SEM as variáveis mortas
    (d / "utils.py").write_text(
        "def helper_x():\n    return 1\n",
        encoding="utf-8",
    )
    (d / "models.py").write_text(
        "class Model:\n    def __init__(self):\n        self.x = 0\n\n"
        "def foo(x, y):\n"
        "    result = x ** 2 + y ** 2\n"
        "    return result\n",
        encoding="utf-8",
    )
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "refactor: move foo to models and remove dead code")
    return str(d)


def test_mine_sem_cross_file_nao_pareia_movida(
    repo_funcao_movida_entre_arquivos, tmp_path
):
    """Default `cross_file_threshold=None`: comportamento anterior preservado;
    o par cross-file passa despercebido."""
    counts = mine(
        repo_url=repo_funcao_movida_entre_arquivos,
        output_path=tmp_path / "out",
    )
    # Sem cross-file, nenhum dos arquivos sozinho fornece um par válido.
    assert counts.get("R5", 0) == 0
    assert counts.get("R2", 0) == 0


def test_mine_com_cross_file_captura_o_par_movido(
    repo_funcao_movida_entre_arquivos, tmp_path
):
    """`cross_file_threshold=0.4` ATIVA o caminho cross-file. O par
    foo(utils)→foo(models) tem similaridade ≈0.45 (remoção de 3 stmts
    Assign muda ~30% dos nós AST); o detector R5 dispara no before
    (3 vars mortas) e não dispara no after.

    A escolha de 0.4 documenta empiricamente que refatorações de remoção
    moderada caem nesse regime; calibração formal fica para o Dia 12."""
    out = tmp_path / "out"
    counts = mine(
        repo_url=repo_funcao_movida_entre_arquivos,
        output_path=out,
        cross_file_threshold=0.4,
    )
    assert counts.get("R5") == 1
    pairs = [json.loads(l) for l in
             (out / "dead_code.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    assert pairs and pairs[0]["function_name"] == "foo"
    # filename aponta para o destino (models.py) — onde a função existe no after.
    assert pairs[0]["file"] == "models.py"
    # Pareamento cross-file recebe source="cross_file" (não mined_commit),
    # permitindo filtrar/calibrar este caminho separadamente no Dia 12.
    assert pairs[0]["source"] == "cross_file"


def test_mine_cross_file_threshold_apertado_descarta(
    repo_funcao_movida_entre_arquivos, tmp_path
):
    """Threshold muito alto (0.99) descarta o par — remover 3 vars muda
    a estrutura o suficiente para a similaridade ficar < 0.99."""
    counts = mine(
        repo_url=repo_funcao_movida_entre_arquivos,
        output_path=tmp_path / "out",
        cross_file_threshold=0.99,
    )
    assert counts.get("R5", 0) == 0


def test_mine_cross_file_ids_unicos(
    repo_funcao_movida_entre_arquivos, tmp_path
):
    """Sanity: pares cross-file usam o `id` hash padrão (baseado em
    repo+commit+file+function_name+code). Sem duplicação."""
    out = tmp_path / "out"
    mine(
        repo_url=repo_funcao_movida_entre_arquivos,
        output_path=out,
        cross_file_threshold=0.4,
    )
    pairs = [json.loads(l) for l in
             (out / "dead_code.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    ids = [p["id"] for p in pairs]
    assert len(ids) == len(set(ids))
