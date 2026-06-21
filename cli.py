"""CLI da ferramenta de detecção de problemas de manutenção (enunciado do TP).

Embrulha os 5 detectores estáticos de `detectores/` numa ferramenta de linha
de comando: recebe arquivos ou diretórios Python, roda os detectores sobre
cada função/método e apresenta os smells encontrados (árvore Rich ou JSON).

Uso:
    python3 cli.py --version
    python3 cli.py scan caminho/arquivo.py
    python3 cli.py scan caminho/projeto/ --smell R1 --smell dead_code
    python3 cli.py scan projeto/ --json > resultado.json
    python3 cli.py smells
"""
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

# raiz do repo no sys.path (mesma convenção do conftest.py)
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from detectores import DETECTORS  # noqa: E402
from extracao.mineracao.ast_utils import parse_file  # noqa: E402

# Versão semântica da ferramenta (SemVer). Primeira release pública.
__version__ = "1.0.0"

# Diretórios que nunca contêm código do usuário a analisar
_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".tox", "node_modules",
              ".mypy_cache", ".ruff_cache", "build", "dist", ".eggs"}

# Descrição curta de cada smell (espelha docs/DECISOES_PROJETO.md)
SMELL_INFO = {
    "long_method":     ("R1", "Método longo / complexo demais — candidato a Extract Method"),
    "long_param_list": ("R2", "Lista de parâmetros longa — candidato a Parameter Object"),
    "magic_numbers":   ("R3", "Números mágicos — candidato a Named Constant"),
    "deep_nesting":    ("R4", "Aninhamento profundo — candidato a Guard Clauses"),
    "dead_code":       ("R5", "Código morto — candidato a remoção"),
}

# Mapa ID (R1–R5) → nome canônico do smell, para o usuário filtrar por qualquer um dos dois.
_ID_PARA_SMELL = {rid.upper(): nome for nome, (rid, _) in SMELL_INFO.items()}


def _normalizar_smells(ctx, param, valores):
    """Aceita ID (R1–R5, case-insensitive) ou nome do smell; normaliza para o nome canônico.

    Mantém a ordem de digitação e remove duplicatas (ex.: `--smell R2 --smell
    long_param_list` vira um único `long_param_list`). Erro de usuário claro
    quando o valor não corresponde a nenhum smell.
    """
    canonicos = []
    for valor in valores:
        chave = valor.strip()
        if chave in DETECTORS:
            canonicos.append(chave)
        elif chave.upper() in _ID_PARA_SMELL:
            canonicos.append(_ID_PARA_SMELL[chave.upper()])
        else:
            ids = ", ".join(f"{rid} ({nome})" for nome, (rid, _) in SMELL_INFO.items())
            raise click.BadParameter(
                f"'{valor}' não é um smell conhecido. Use o ID ou o nome: {ids}.")
    return tuple(dict.fromkeys(canonicos))  # dedup preservando ordem


def _coletar_arquivos(caminhos: tuple[str, ...]) -> list[Path]:
    """Expande arquivos/diretórios em uma lista ordenada de arquivos .py."""
    arquivos: list[Path] = []
    for c in caminhos:
        p = Path(c)
        if p.is_file() and p.suffix == ".py":
            arquivos.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                if not any(parte in _SKIP_DIRS for parte in f.parts):
                    arquivos.append(f)
    # remove duplicatas preservando ordem
    vistos: set[Path] = set()
    unicos = []
    for f in arquivos:
        r = f.resolve()
        if r not in vistos:
            vistos.add(r)
            unicos.append(f)
    return unicos


def _funcoes_do_arquivo(parsed: dict):
    """Itera (rotulo, FunctionInfo) sobre funções top-level e métodos."""
    for fn in parsed["functions"]:
        yield fn.name, fn
    for cls in parsed["classes"]:
        for m in cls.methods:
            yield f"{cls.name}.{m.name}", m


def _resumo_evidencia(smell: str, ev: dict) -> str:
    """Resume o dict de evidência de cada detector em uma linha legível."""
    if smell == "long_method":
        if "lines_of_code" in ev:
            return (f"{ev['lines_of_code']} linhas (limite {ev.get('line_threshold')}), "
                    f"complexidade {ev.get('complexidade_ciclomatica')} "
                    f"(limite {ev.get('complexidade_threshold')})")
        return f"{ev.get('lines_fallback')} linhas (limite {ev.get('threshold')})"
    if smell == "long_param_list":
        return f"{ev.get('count')} parâmetros (limite {ev.get('threshold')}): {', '.join(ev.get('params', []))}"
    if smell == "magic_numbers":
        itens = ev.get("magic_numbers", [])
        amostra = ", ".join(str(i.get("value", i)) if isinstance(i, dict) else str(i)
                            for i in itens[:5])
        extra = f" (+{len(itens) - 5})" if len(itens) > 5 else ""
        return f"{len(itens)} literais mágicos: {amostra}{extra}"
    if smell == "deep_nesting":
        return f"profundidade máxima {ev.get('max_depth')} (limite {ev.get('threshold')})"
    if smell == "dead_code":
        itens = ev.get("dead_code", [])
        amostra = ", ".join(
            f"{i.get('type', '?')}@L{i.get('lineno', '?')}" if isinstance(i, dict) else str(i)
            for i in itens[:4])
        extra = f" (+{len(itens) - 4})" if len(itens) > 4 else ""
        return f"{len(itens)} ocorrências: {amostra}{extra}"
    return json.dumps(ev, ensure_ascii=False, default=str)[:120]


def _analisar(arquivos: list[Path], smells: tuple[str, ...]) -> tuple[list[dict], list[str]]:
    """Roda os detectores selecionados; retorna (resultados por arquivo, avisos)."""
    resultados, avisos = [], []
    for arq in arquivos:
        try:
            parsed = parse_file(str(arq))
        except SyntaxError as e:
            avisos.append(f"{arq}: erro de sintaxe na linha {e.lineno} — arquivo ignorado")
            continue
        except (OSError, UnicodeDecodeError) as e:
            avisos.append(f"{arq}: não foi possível ler ({e}) — arquivo ignorado")
            continue

        funcoes = []
        for rotulo, fn in _funcoes_do_arquivo(parsed):
            achados = []
            for smell in smells:
                res = DETECTORS[smell](fn)
                if res.detected:
                    achados.append({"smell": smell, "evidence": res.evidence})
            if achados:
                funcoes.append({"funcao": rotulo, "lineno": fn.lineno, "smells": achados})
        if funcoes:
            resultados.append({"arquivo": str(arq), "funcoes": funcoes})
    return resultados, avisos


@click.group(
    epilog="\b\n"
           "Exemplos:\n"
           "  cli.py scan src/                    analisa um diretório inteiro\n"
           "  cli.py scan app.py --smell R1       só Long Method (filtro por ID)\n"
           "  cli.py scan src/ --json > out.json  saída estruturada p/ integração\n"
           "  cli.py smells                       lista os smells suportados\n")
@click.version_option(__version__, "-V", "--version", "--V", prog_name="PySniff")
def cli():
    """PySniff — detector de code smells em Python por análise estática.

    Aponte a ferramenta para arquivos ou diretórios e ela reporta, por
    função/método, os 5 smells de manutenção suportados (R1–R5) com a
    evidência métrica de cada detecção. Use `smells` para ver a lista e
    `scan --help` para os detalhes da análise.
    """


@cli.command(
    epilog="\b\n"
           "Códigos de saída:\n"
           "  0  análise concluída (mesmo com smells, exceto se --fail-on-detect)\n"
           "  1  --fail-on-detect ativo e ao menos um smell detectado\n"
           "  2  nenhum arquivo .py encontrado nos caminhos informados\n")
@click.argument("caminhos", nargs=-1, required=True, type=click.Path(exists=True),
                metavar="CAMINHOS...")
@click.option("--smell", "smells", multiple=True, metavar="SMELL", callback=_normalizar_smells,
              help="Restringe a um smell, por ID (R1–R5) ou nome (ex.: long_method). "
                   "Repetível. Padrão: todos.")
@click.option("--json", "como_json", is_flag=True,
              help="Emite JSON estruturado em vez da árvore visual (para integração/scripts).")
@click.option("--fail-on-detect", is_flag=True,
              help="Retorna código de saída 1 se algum smell for detectado (útil em CI).")
def scan(caminhos, smells, como_json, fail_on_detect):
    """Analisa CAMINHOS (arquivos .py ou diretórios) e reporta smells por função.

    Diretórios são percorridos recursivamente; pastas como .venv, .git e
    __pycache__ são ignoradas automaticamente.
    """
    console = Console(stderr=False)
    filtrado = bool(smells)  # o usuário restringiu os smells via --smell?
    smells = smells or tuple(sorted(DETECTORS, key=lambda s: SMELL_INFO[s][0]))
    arquivos = _coletar_arquivos(caminhos)
    if not arquivos:
        click.echo("Nenhum arquivo .py encontrado nos caminhos dados.", err=True)
        sys.exit(2)

    resultados, avisos = _analisar(arquivos, smells)
    total_por_smell = {s: 0 for s in smells}
    for r in resultados:
        for f in r["funcoes"]:
            for a in f["smells"]:
                total_por_smell[a["smell"]] += 1

    if como_json:
        click.echo(json.dumps(
            {"arquivos_analisados": len(arquivos), "resultados": resultados,
             "resumo": total_por_smell, "avisos": avisos},
            ensure_ascii=False, indent=1, default=str))
    else:
        console.print(f"[dim]Analisando {len(arquivos)} arquivo(s) "
                      f"com {len(smells)} detector(es)…[/dim]")
        for aviso in avisos:
            console.print(f"[yellow]aviso:[/yellow] {aviso}")
        for r in resultados:
            arvore = Tree(f"[bold]{r['arquivo']}[/bold]")
            for f in r["funcoes"]:
                no_fn = arvore.add(f"[cyan]{f['funcao']}[/cyan] (linha {f['lineno']})")
                for a in f["smells"]:
                    rid, _ = SMELL_INFO[a["smell"]]
                    no_fn.add(f"[red]{rid} {a['smell']}[/red] — "
                              f"{_resumo_evidencia(a['smell'], a['evidence'])}")
            console.print(arvore)

        total_deteccoes = sum(total_por_smell.values())
        if total_deteccoes == 0:
            if filtrado:
                quais = ", ".join(f"{SMELL_INFO[s][0]} ({s})" for s in smells)
                console.print(f"[bold green]✓ Nenhum smell do tipo {quais} detectado[/bold green] "
                              f"em {len(arquivos)} arquivo(s).")
            else:
                console.print(f"[bold green]✓ Nenhum smell detectado[/bold green] "
                              f"em {len(arquivos)} arquivo(s).")
        else:
            n_funcoes = sum(len(r["funcoes"]) for r in resultados)
            console.print(f"[bold red]✗ {total_deteccoes} smell(s)[/bold red] "
                          f"em {n_funcoes} função(ões) de {len(resultados)} arquivo(s) "
                          f"(de {len(arquivos)} analisado(s)).")
            tabela = Table(title="Detecções por smell")
            tabela.add_column("Smell")
            tabela.add_column("Detecções", justify="right")
            for s in smells:
                rid, desc = SMELL_INFO[s]
                tabela.add_row(f"{rid} {s}", str(total_por_smell[s]))
            console.print(tabela)

    if fail_on_detect and any(total_por_smell.values()):
        sys.exit(1)


@cli.command()
def smells():
    """Lista os 5 smells suportados, com critério de detecção."""
    console = Console()
    tabela = Table(title="Smells suportados")
    tabela.add_column("ID")
    tabela.add_column("Smell")
    tabela.add_column("Descrição")
    for nome in sorted(DETECTORS, key=lambda s: SMELL_INFO[s][0]):
        rid, desc = SMELL_INFO[nome]
        tabela.add_row(rid, nome, desc)
    console.print(tabela)


if __name__ == "__main__":
    cli()
