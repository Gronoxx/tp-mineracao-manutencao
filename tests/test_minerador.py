"""Testes do minerador — `extracao/mineracao/minerador.py`.

Foco PR 2:
  - F3: `verify_pair` não pode aceitar R1 sem nenhum helper extraído.
  - Menor: filtro de arquivos de teste por componente de caminho (não substring).
"""
from extracao.mineracao import minerador


# --- filtro de arquivos de teste (_is_test_path) -------------------------

def test_is_test_path_aceita_codigo_de_producao():
    # "test" como substring não deve disparar o filtro.
    assert minerador._is_test_path("latest/modulo.py") is False
    assert minerador._is_test_path("contest.py") is False
    assert minerador._is_test_path("src/contest/main.py") is False
    assert minerador._is_test_path("pkg/fastest.py") is False


def test_is_test_path_filtra_arquivos_de_teste():
    assert minerador._is_test_path("tests/foo.py") is True
    assert minerador._is_test_path("test/foo.py") is True
    assert minerador._is_test_path("pkg/tests/sub/bar.py") is True
    assert minerador._is_test_path("test_x.py") is True
    assert minerador._is_test_path("pkg/test_modulo.py") is True
    assert minerador._is_test_path("pkg/modulo_test.py") is True


# --- F3: verify_pair rejeita R1 sem helper -------------------------------

class _FakeRes:
    """Resultado de detector falso — só `detected` e `evidence`."""
    def __init__(self, detected: bool):
        self.detected = detected
        self.evidence = {}


class _FakeFn:
    """FunctionInfo falso — verify_pair só lê `.source`."""
    def __init__(self, source: str):
        self.source = source


def _fake_long_detector(fn):
    """Dispara em funções que contêm o marcador 'LONGO' no corpo."""
    return _FakeRes("LONGO" in fn.source)


def _candidate(helper_sources):
    return {
        "function_name": "f",
        "before_fn": _FakeFn("def f():\n    # LONGO\n    return 1\n"),
        "after_fn": _FakeFn("def f():\n    return ajuda()\n"),
        "helper_sources": helper_sources,
    }


def _verify(cand):
    return minerador.verify_pair(
        cand, repo="r", commit_hash="c", parent_commit=None,
        commit_msg="m", msg_keywords=[], filename="modulo.py",
    )


def test_verify_pair_rejeita_r1_sem_helper(monkeypatch):
    """Long Method encurtado sem extrair helper não é Extract Method."""
    monkeypatch.setattr(minerador, "DETECTORS", {"long_method": _fake_long_detector})
    assert _verify(_candidate(helper_sources=[])) == []


def test_verify_pair_aceita_r1_com_helper(monkeypatch):
    monkeypatch.setattr(minerador, "DETECTORS", {"long_method": _fake_long_detector})
    records = _verify(_candidate(helper_sources=["def ajuda():\n    return 1\n"]))
    assert len(records) == 1
    assert records[0].smell_type == "R1"
    assert records[0].n_functions_after == 2


def test_verify_pair_rejeita_r1_com_helper_longo(monkeypatch):
    """Se o helper extraído é ele mesmo um Long Method, o smell não foi resolvido."""
    monkeypatch.setattr(minerador, "DETECTORS", {"long_method": _fake_long_detector})
    helper = "def ajuda():\n    # LONGO\n    return 1\n"
    assert _verify(_candidate(helper_sources=[helper])) == []
