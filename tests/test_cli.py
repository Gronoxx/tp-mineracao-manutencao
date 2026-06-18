"""Testes da CLI (`cli.py`) — scan de arquivos/diretórios e saída JSON."""
import json

import pytest
from click.testing import CliRunner

from cli import cli

# Função com long_param_list (8 > 5), magic_numbers e deep_nesting (4 > 3)
CODIGO_COM_SMELLS = '''
def processa(a, b, c, d, e, f, g, h):
    if a:
        for i in range(b):
            if c:
                if d:
                    return e * 437 + 982
    return 0
'''

CODIGO_LIMPO = '''
def soma(a, b):
    return a + b
'''

CODIGO_INVALIDO = "def quebrado(:\n    pass\n"


@pytest.fixture
def runner():
    return CliRunner()


def _escrever(tmp_path, nome, conteudo):
    p = tmp_path / nome
    p.write_text(conteudo, encoding="utf-8")
    return p


def test_scan_detecta_smells_em_arquivo(runner, tmp_path):
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq)])
    assert res.exit_code == 0
    assert "long_param_list" in res.output
    assert "magic_numbers" in res.output
    assert "deep_nesting" in res.output
    assert "processa" in res.output


def test_scan_arquivo_limpo_sem_deteccoes(runner, tmp_path):
    arq = _escrever(tmp_path, "limpo.py", CODIGO_LIMPO)
    res = runner.invoke(cli, ["scan", str(arq)])
    assert res.exit_code == 0
    assert "Nenhum smell detectado" in res.output


def test_scan_diretorio_recursivo(runner, tmp_path):
    sub = tmp_path / "pacote"
    sub.mkdir()
    _escrever(sub, "modulo.py", CODIGO_COM_SMELLS)
    _escrever(tmp_path, "limpo.py", CODIGO_LIMPO)
    res = runner.invoke(cli, ["scan", str(tmp_path)])
    assert res.exit_code == 0
    assert "modulo.py" in res.output


def test_scan_saida_json(runner, tmp_path):
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq), "--json"])
    assert res.exit_code == 0
    dados = json.loads(res.output)
    assert dados["arquivos_analisados"] == 1
    smells = {a["smell"]
              for r in dados["resultados"]
              for f in r["funcoes"]
              for a in f["smells"]}
    assert "long_param_list" in smells
    assert dados["resumo"]["long_param_list"] == 1


def test_scan_filtro_por_smell(runner, tmp_path):
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq), "--smell", "long_param_list", "--json"])
    dados = json.loads(res.output)
    assert set(dados["resumo"]) == {"long_param_list"}


def test_scan_metodos_de_classe(runner, tmp_path):
    codigo = "class C:\n" + "    def metodo(self, a, b, c, d, e, f, g):\n        return a\n"
    arq = _escrever(tmp_path, "classe.py", codigo)
    res = runner.invoke(cli, ["scan", str(arq), "--smell", "long_param_list"])
    assert "C.metodo" in res.output


def test_scan_arquivo_com_erro_de_sintaxe_avisa_e_continua(runner, tmp_path):
    _escrever(tmp_path, "quebrado.py", CODIGO_INVALIDO)
    _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(tmp_path)])
    output_normalizado = " ".join(res.output.split())
    assert res.exit_code == 0
    assert "erro de sintaxe" in output_normalizado
    assert "smelly.py" in res.output


def test_scan_fail_on_detect(runner, tmp_path):
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq), "--fail-on-detect"])
    assert res.exit_code == 1
    arq2 = _escrever(tmp_path, "limpo.py", CODIGO_LIMPO)
    res2 = runner.invoke(cli, ["scan", str(arq2), "--fail-on-detect"])
    assert res2.exit_code == 0


def test_scan_sem_arquivos_py(runner, tmp_path):
    res = runner.invoke(cli, ["scan", str(tmp_path)])
    assert res.exit_code == 2


def test_comando_smells_lista_os_cinco(runner):
    res = runner.invoke(cli, ["smells"])
    assert res.exit_code == 0
    for nome in ["long_method", "long_param_list", "magic_numbers",
                 "deep_nesting", "dead_code"]:
        assert nome in res.output
