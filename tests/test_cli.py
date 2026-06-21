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


# ---------------------------------------------------------------------------
# Filtro por ID do smell (R1–R5) — além do nome
# ---------------------------------------------------------------------------

def test_scan_filtro_por_id_do_smell(runner, tmp_path):
    """`--smell R2` deve filtrar exatamente como `--smell long_param_list`."""
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq), "--smell", "R2", "--json"])
    assert res.exit_code == 0
    assert set(json.loads(res.output)["resumo"]) == {"long_param_list"}


def test_scan_filtro_por_id_case_insensitive(runner, tmp_path):
    """O ID é aceito em minúsculas (`r2` == `R2`)."""
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq), "--smell", "r2", "--json"])
    assert res.exit_code == 0
    assert set(json.loads(res.output)["resumo"]) == {"long_param_list"}


def test_scan_id_e_nome_sao_deduplicados(runner, tmp_path):
    """`--smell R2 --smell long_param_list` referem o mesmo smell → uma entrada."""
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(
        cli, ["scan", str(arq), "--smell", "R2", "--smell", "long_param_list", "--json"])
    assert res.exit_code == 0
    assert set(json.loads(res.output)["resumo"]) == {"long_param_list"}


def test_scan_smell_invalido_falha_com_mensagem(runner, tmp_path):
    """Valor que não é ID nem nome → erro de uso (exit 2) com mensagem clara."""
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq), "--smell", "R9"])
    assert res.exit_code == 2
    assert "não é um smell" in res.output


# ---------------------------------------------------------------------------
# Versionamento semântico (--version)
# ---------------------------------------------------------------------------

def test_version_exibe_semver(runner):
    """`--version` imprime a versão 1.0.0 e termina com sucesso."""
    res = runner.invoke(cli, ["--version"])
    assert res.exit_code == 0
    assert "1.0.0" in res.output


@pytest.mark.parametrize("flag", ["-V", "--version", "--V"])
def test_version_aceita_todos_os_aliases(runner, flag):
    """A versão é exibível por `-V`, `--version` e `--V`."""
    res = runner.invoke(cli, [flag])
    assert res.exit_code == 0
    assert "1.0.0" in res.output


# ---------------------------------------------------------------------------
# Linha de resumo / veredito
# ---------------------------------------------------------------------------

def test_scan_veredito_quando_detecta(runner, tmp_path):
    """Com smells, o veredito final informa a contagem total de detecções."""
    arq = _escrever(tmp_path, "smelly.py", CODIGO_COM_SMELLS)
    res = runner.invoke(cli, ["scan", str(arq)])
    assert res.exit_code == 0
    assert "smell(s) em" in res.output
    assert "função(ões)" in res.output


def test_scan_veredito_quando_limpo(runner, tmp_path):
    """Sem smells e sem filtro, o veredito final é genérico."""
    arq = _escrever(tmp_path, "limpo.py", CODIGO_LIMPO)
    res = runner.invoke(cli, ["scan", str(arq)])
    assert res.exit_code == 0
    assert "Nenhum smell detectado" in res.output


def test_scan_veredito_limpo_com_filtro_nomeia_o_smell(runner, tmp_path):
    """Limpo com `--smell R2`, o veredito identifica o smell buscado."""
    arq = _escrever(tmp_path, "limpo.py", CODIGO_LIMPO)
    res = runner.invoke(cli, ["scan", str(arq), "--smell", "R2"])
    assert res.exit_code == 0
    assert "Nenhum smell do tipo R2 (long_param_list) detectado" in res.output


# ---------------------------------------------------------------------------
# Documentação do --help
# ---------------------------------------------------------------------------

def test_scan_help_documenta_codigos_de_saida(runner):
    """O help do `scan` documenta os códigos de saída (0/1/2)."""
    res = runner.invoke(cli, ["scan", "--help"])
    assert res.exit_code == 0
    assert "Códigos de saída" in res.output
    assert "--fail-on-detect" in res.output
