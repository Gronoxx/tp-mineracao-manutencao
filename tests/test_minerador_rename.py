"""C5c.1 (Dia 5 do sprint) — testes de regressão para arquivos RENAMEADOS.

Quando o git detecta rename de arquivo (similaridade ≥ 50% por default), o
`ModifiedFile` que PyDriller entrega tem `change_type=RENAME`, com `old_path`,
`new_path`, `source_code_before` (conteúdo no caminho antigo) e `source_code`
(conteúdo no caminho novo) populados. `extract_candidates` casa funções com
mesmo nome entre os dois — não precisa de lógica adicional.

Cenários cobertos:
    1. RENAME + refactor por Parameter Object (R2) no mesmo commit.
    2. RENAME + Extract Method (R1).
    3. ADD/DELETE separados (similaridade abaixo do threshold do git) — caso
       que NÃO é detectado como rename; documenta o limite da abordagem.
"""
import json
import subprocess
from pathlib import Path

import pytest

from extracao.mineracao.minerador import mine


def _git(d, *args):
    subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)


def _init_repo(d: Path):
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t.t")
    _git(d, "config", "user.name", "t")


@pytest.fixture
def repo_rename_r2(tmp_path):
    """RENAME (alta similaridade) + Parameter Object → deve produzir 1 par R2."""
    d = tmp_path / "repo_rename_r2"
    d.mkdir()
    _init_repo(d)
    # Conteúdo com várias funções util para manter a similaridade alta entre
    # `old.py` e `new.py` (sem isso, git vê 2 mudanças independentes).
    helpers = "\n".join([
        "def util_one():\n    return 1",
        "def util_two():\n    return 2",
        "def util_three():\n    return 3",
    ])
    (d / "old.py").write_text(
        helpers + "\n\n"
        "def foo(a, b, c, d, e, f, g, h):\n"
        "    return a + b + c + d + e + f + g + h\n",
        encoding="utf-8",
    )
    _git(d, "add", "."); _git(d, "commit", "-q", "-m", "init")

    (d / "old.py").unlink()
    (d / "new.py").write_text(
        helpers + "\n\n"
        "def foo(cfg):\n"
        "    return cfg.total\n",
        encoding="utf-8",
    )
    _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "refactor: parameter object")
    return str(d)


@pytest.fixture
def repo_rename_r1(tmp_path):
    """RENAME + Extract Method → deve produzir 1 par R1.

    Para o git detectar rename, o conteúdo `before`/`after` precisa ter alta
    similaridade. Como `foo` muda drasticamente (40 linhas → 3 linhas), o
    delta proporcional é alto; usamos `~80 funções util` idênticas para
    diluir esse delta abaixo do threshold default do git (50%).
    """
    d = tmp_path / "repo_rename_r1"
    d.mkdir()
    _init_repo(d)
    # ~160 linhas comuns aos dois arquivos → mantém similaridade > 50% mesmo
    # com foo mudando 40 linhas.
    common = "\n\n".join(
        f"def util_{i}():\n    return {i}" for i in range(80)
    )
    body_long = "\n    ".join(f"x{i} = {i}" for i in range(40))
    (d / "old.py").write_text(
        common + "\n\n"
        f"def foo():\n"
        f"    {body_long}\n"
        f"    return x39\n",
        encoding="utf-8",
    )
    _git(d, "add", "."); _git(d, "commit", "-q", "-m", "init")

    (d / "old.py").unlink()
    (d / "new.py").write_text(
        common + "\n\n"
        "def _setup_xs():\n"
        "    return [i for i in range(40)]\n\n"
        "def foo():\n"
        "    xs = _setup_xs()\n"
        "    return xs[39]\n",
        encoding="utf-8",
    )
    _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "refactor: extract method")
    return str(d)


def test_mine_detecta_par_em_arquivo_renomeado_r2(repo_rename_r2, tmp_path):
    """O par foo(8 params)→foo(cfg) deve ser encontrado mesmo com file rename."""
    out = tmp_path / "out"
    counts = mine(repo_url=repo_rename_r2, output_path=out)
    assert counts.get("R2") == 1
    pairs = [json.loads(l) for l in
             (out / "long_param_list.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    assert pairs and pairs[0]["function_name"] == "foo"
    # File registrado é o new_path (convenção atual do mine()).
    assert pairs[0]["file"] == "new.py"


def test_mine_detecta_par_em_arquivo_renomeado_r1(repo_rename_r1, tmp_path):
    """Extract Method via file rename — confere helper detectado e par R1."""
    out = tmp_path / "out"
    counts = mine(repo_url=repo_rename_r1, output_path=out)
    assert counts.get("R1") == 1
    pairs = [json.loads(l) for l in
             (out / "long_method.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    assert pairs and pairs[0]["function_name"] == "foo"
    # n_functions_after = 1 (foo) + helpers (>=1)
    assert pairs[0]["n_functions_after"] >= 2


def test_baixa_similaridade_e_add_delete_nao_pareia(tmp_path):
    """Documenta o limite atual: quando o conteúdo muda muito, git vê ADD+DELETE
    e não detecta rename → não há `source_code_before` no ADD nem `source_code`
    no DELETE → nenhum par sai.

    Este teste fixa o comportamento atual; se virmos cross-file matching no
    Dia 6-7 (AST similarity), o teste pode precisar virar `xfail`."""
    d = tmp_path / "repo_no_rename"
    d.mkdir()
    _init_repo(d)
    (d / "x.py").write_text(
        "def foo(a, b, c, d, e, f, g, h):\n"
        "    return a + b + c + d + e + f + g + h\n",
        encoding="utf-8",
    )
    _git(d, "add", "."); _git(d, "commit", "-q", "-m", "init")
    (d / "x.py").unlink()
    # arquivo novo com nome totalmente diferente E só com foo refatorada
    # (similaridade baixa → git não detecta rename).
    (d / "y.py").write_text(
        "def foo(cfg):\n    return cfg.total\n",
        encoding="utf-8",
    )
    _git(d, "add", "-A"); _git(d, "commit", "-q", "-m", "refactor: parameter object")
    counts = mine(repo_url=str(d), output_path=tmp_path / "out")
    # Comportamento esperado HOJE: nenhum par detectado (caso fica para Dia 6-7).
    assert counts.get("R2", 0) == 0
