"""Testes do cap por smell — PR 9.

`_orcamento_repo` (runner): distribui o cap global entre os repositórios para
diversidade de proveniência. `mine(caps=...)`: respeita o teto por smell.
"""
import subprocess

import pytest

from extracao.execucao.mineracao import CAP_POR_SMELL, _orcamento_repo
from extracao.mineracao.minerador import _caps_atingidos, mine


# ── _orcamento_repo — lógica de diversidade ──────────────────────────────────
# `CAP_POR_SMELL` é um dict per-smell (Plano 3); valores reais vêm das
# recomendações de literatura LoRA. Os asserts usam um cap arbitrário passado
# explicitamente para não acoplar aos valores de produção.

CAP_TESTE = {"R1": 300, "R2": 300, "R3": 300, "R4": 300, "R5": 300}


def test_orcamento_fresh_distribui_entre_todos_os_repos():
    # cap R1=300, 16 repos -> ceil(300/16) = 19 por smell
    assert _orcamento_repo({}, repos_restantes=16, cap=CAP_TESTE)["R1"] == 19


def test_orcamento_ultimo_repo_pega_o_resto():
    orc = _orcamento_repo({"R1": 290}, repos_restantes=1, cap=CAP_TESTE)
    assert orc["R1"] == 10


def test_orcamento_smell_no_cap_recebe_zero():
    orc = _orcamento_repo({"R1": 300}, repos_restantes=5, cap=CAP_TESTE)
    assert orc["R1"] == 0


def test_orcamento_cresce_quando_repos_renderam_pouco():
    # 100 minerados, 10 repos restantes -> ceil(200/10)=20 (> 19 do fresh)
    assert _orcamento_repo({"R1": 100}, repos_restantes=10, cap=CAP_TESTE)["R1"] == 20


def test_orcamento_aceita_caps_diferentes_por_smell():
    """A produção usa caps assimétricos (R1=4000, R3=1500, ...) — confere
    que cada smell é tratado independentemente."""
    cap_assim = {"R1": 4000, "R2": 3500, "R3": 1500, "R4": 2500, "R5": 2000}
    orc = _orcamento_repo({}, repos_restantes=10, cap=cap_assim)
    assert orc["R1"] == 400 and orc["R3"] == 150


def test_cap_por_smell_de_producao_e_dict_com_5_smells():
    """Smoke: o CAP de produção tem exatamente os 5 smells do enum."""
    assert set(CAP_POR_SMELL) == {"R1", "R2", "R3", "R4", "R5"}
    assert all(isinstance(v, int) and v > 0 for v in CAP_POR_SMELL.values())


# ── _caps_atingidos ──────────────────────────────────────────────────────────

def test_caps_atingidos_todos_cheios():
    assert _caps_atingidos({"R2": {"a": {}, "b": {}, "c": {}}}, {"R2": 3}) is True


def test_caps_atingidos_um_smell_faltando():
    assert _caps_atingidos({"R2": {"a": {}, "b": {}}}, {"R2": 3}) is False


def test_caps_atingidos_smell_ausente_de_by_smell():
    assert _caps_atingidos({}, {"R2": 1}) is False


# ── mine() respeita o cap (repositório git local) ────────────────────────────

@pytest.fixture(scope="module")
def repo_r2(tmp_path_factory):
    """Repo git local cujo 2º commit refatora 6 funções de 8 params → 1
    (Parameter Object) — produz 6 pares R2 verificáveis."""
    d = tmp_path_factory.mktemp("repo_r2")

    def git(*args):
        subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    antes = "\n\n".join(
        f"def f{i}(a, b, c, d, e, f, g, h):\n"
        f"    return a + b + c + d + e + f + g + h"
        for i in range(6))
    (d / "mod.py").write_text(antes + "\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    depois = "\n\n".join(f"def f{i}(cfg):\n    return cfg.total" for i in range(6))
    (d / "mod.py").write_text(depois + "\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "refactor: introduce parameter object")
    return str(d)


def test_mine_sem_cap_encontra_os_6_pares(repo_r2, tmp_path):
    counts = mine(repo_url=repo_r2, output_path=tmp_path / "out")
    assert counts.get("R2") == 6


def test_mine_com_cap_limita_o_smell(repo_r2, tmp_path):
    counts = mine(repo_url=repo_r2, output_path=tmp_path / "out",
                  caps={"R1": 99, "R2": 3, "R3": 99, "R4": 99, "R5": 99})
    assert counts.get("R2") == 3
