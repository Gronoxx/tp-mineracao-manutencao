"""Quality check automatico para pares de refatoracao em data/raw/.

Substitui a inspecao manual por um conjunto de heuristicas ESTATICAS que
sinalizam falsos positivos sem precisar de julgamento humano. Cada par
recebe lista de issues com severidade FAIL/WARN. O exit code reflete o
agregado — `>0 FAIL` resulta em exit 1 (utilizavel em CI / mass mine gate).

NAO executa o codigo dos pares (sem behavioral check aqui — esse e o
escopo do `behavioral_check.py`, que e mais lento e tem risco de side
effects). Foco em sinais estaticos:

  FAIL (sinal forte de FP — rejeicao):
    - before_code == after_code  (nao ha refactoring)
    - AST nao parseia em algum lado
    - AST similarity < 0.10  (codigos completamente diferentes — mismatch)

  WARN (sinal de revisao manual):
    - AST similarity in [0.10, 0.30)  (mudanca muito drastica)
    - before/after com < 3 linhas  (trivial demais — pouco sinal)
    - mesmo helper_sources vazio em R1  (ja rejeitado pelo F3 no verify_pair,
      mas vale checar regressao)
    - magnitude_after >= magnitude_before  no modo permissivo (deveria reduzir)
    - smell_type fora do conjunto canonico R1..R5

Filtros disponiveis por CLI: `--source mined_commit|adjacent_oracle|mined_pr|
translated_java` e `--smell R1..R5`.
"""
import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extracao.mineracao.ast_similarity import ast_similarity  # noqa: E402
from core.smells import CODE_TO_NAME, SMELL_CODES  # noqa: E402


Severity = Literal["fail", "warn"]

# Limiares parametricos do quality check. Documentados aqui para que
# ajustes futuros (Dia 12 calibracao) sejam centralizados.
AST_SIM_FAIL_BELOW = 0.10
AST_SIM_WARN_BELOW = 0.30
MIN_LINES_WARN = 3


@dataclass
class Issue:
    severity: Severity
    rule: str
    detail: str


@dataclass
class PairReport:
    pair_id: str
    smell_type: str
    source: str
    repo: str
    file: Optional[str]
    function_name: Optional[str]
    ast_similarity: Optional[float]
    issues: list[Issue] = field(default_factory=list)

    @property
    def n_fail(self) -> int:
        return sum(1 for i in self.issues if i.severity == "fail")

    @property
    def n_warn(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warn")


def _safe_parse(code: str) -> Optional[ast.AST]:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _count_nonblank_lines(code: str) -> int:
    return sum(1 for ln in code.splitlines() if ln.strip())


def check_pair(record: dict) -> PairReport:
    """Roda todas as heuristicas sobre um registro `RefactoringPair.model_dump()`.

    Retorna `PairReport` com lista de issues. Nao falha — coleta tudo.
    """
    rep = PairReport(
        pair_id=record.get("id", "<no-id>"),
        smell_type=record.get("smell_type", "?"),
        source=record.get("source", "?"),
        repo=record.get("repo", "?"),
        file=record.get("file"),
        function_name=record.get("function_name"),
        ast_similarity=None,
    )

    before = record.get("before_code", "")
    after = record.get("after_code", "")

    # --- 1. before == after (nao ha refactoring) ---
    if before == after:
        rep.issues.append(Issue(
            "fail", "no_change",
            "before_code identico a after_code — nao e refactoring",
        ))
        return rep   # demais checks sao redundantes

    # --- 2. Parseabilidade ---
    before_tree = _safe_parse(before)
    after_tree = _safe_parse(after)
    if before_tree is None:
        rep.issues.append(Issue(
            "fail", "before_unparseable",
            "before_code nao parseia como Python",
        ))
    if after_tree is None:
        rep.issues.append(Issue(
            "fail", "after_unparseable",
            "after_code nao parseia como Python",
        ))
    if before_tree is None or after_tree is None:
        return rep

    # --- 3. AST similarity ---
    # `ast_similarity` espera UMA funcao top-level. RefactoringPair guarda a
    # funcao isolada no `before_code`. Em R1, `after_code` inclui helpers
    # concatenados — pegamos so a primeira funcao para compatibilidade.
    sim = ast_similarity(before, _first_function_source(after) or after)
    rep.ast_similarity = sim
    if sim is None:
        rep.issues.append(Issue(
            "warn", "similarity_unavailable",
            "ast_similarity retornou None (estrutura inesperada)",
        ))
    else:
        if sim < AST_SIM_FAIL_BELOW:
            rep.issues.append(Issue(
                "fail", "similarity_too_low",
                f"ast_similarity={sim:.3f} < {AST_SIM_FAIL_BELOW} — "
                "codigos muito diferentes, suspeita de mismatch",
            ))
        elif sim < AST_SIM_WARN_BELOW:
            rep.issues.append(Issue(
                "warn", "similarity_borderline",
                f"ast_similarity={sim:.3f} < {AST_SIM_WARN_BELOW} — "
                "mudanca estrutural drastica, revisar",
            ))

    # --- 4. Linhas minimas ---
    bn, an = _count_nonblank_lines(before), _count_nonblank_lines(after)
    if bn < MIN_LINES_WARN:
        rep.issues.append(Issue(
            "warn", "before_too_short",
            f"before_code com {bn} linhas — pouco sinal para treino",
        ))
    if an < MIN_LINES_WARN:
        rep.issues.append(Issue(
            "warn", "after_too_short",
            f"after_code com {an} linhas — pouco sinal para treino",
        ))

    # --- 5. Smell canonico ---
    if rep.smell_type not in SMELL_CODES:
        rep.issues.append(Issue(
            "fail", "smell_invalid",
            f"smell_type={rep.smell_type!r} fora de {SMELL_CODES}",
        ))

    # --- 6. R1 sem helper (regressao da F3) ---
    if rep.smell_type == "R1":
        n_funcs_after = record.get("n_functions_after", 1)
        if not n_funcs_after or n_funcs_after < 2:
            rep.issues.append(Issue(
                "warn", "r1_no_helper",
                f"R1 sem helper extraido (n_functions_after={n_funcs_after}) — "
                "F3 deveria ter rejeitado",
            ))

    # --- 7. Permissive sem reducao de magnitude ---
    if record.get("partial"):
        before_ev = (record.get("detector_before") or {}).get("evidence") or {}
        after_ev = (record.get("detector_after") or {}).get("evidence") or {}
        mag_b = _magnitude_from_evidence(before_ev, rep.smell_type)
        mag_a = _magnitude_from_evidence(after_ev, rep.smell_type)
        if mag_b is not None and mag_a is not None and mag_b > 0:
            reduction = (mag_b - mag_a) / mag_b
            if reduction < 0.05:   # menos de 5% de reducao = mudanca trivial
                rep.issues.append(Issue(
                    "warn", "trivial_reduction",
                    f"magnitude reduziu {reduction*100:.1f}% — mudanca trivial "
                    f"(mag_b={mag_b}, mag_a={mag_a})",
                ))

    return rep


def _first_function_source(code: str) -> Optional[str]:
    """Retorna o source da primeira funcao top-level (R1 concatena helpers
    apos a funcao principal — precisamos isolar para `ast_similarity`)."""
    tree = _safe_parse(code)
    if tree is None:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ast.get_source_segment(code, node)
    return None


def _magnitude_from_evidence(ev: dict, smell_code: str) -> Optional[float]:
    """Extrai a magnitude (numero proxy) que o detector usa por smell.

    Espelha `_magnitude` em `extracao/mineracao/minerador.py` — duplicacao
    proposital para nao acoplar quality check a runtime do minerador.
    """
    # Mantemos chave -> evidence-field por smell. Se evolui, atualizar aqui.
    if smell_code == "R1":
        return ev.get("lines_of_code") or ev.get("lines_fallback")
    if smell_code == "R2":
        return ev.get("parametros") or ev.get("n_params")
    if smell_code == "R3":
        return ev.get("magic_numbers_count")
    if smell_code == "R4":
        return ev.get("max_depth") or ev.get("profundidade")
    if smell_code == "R5":
        return ev.get("dead_count") or ev.get("dead_vars")
    return None


def load_pairs(raw_dir: Path, source_filter: Optional[str],
               smell_filter: Optional[str]) -> list[dict]:
    """Le todos os jsonls em raw_dir, aplica filtros opcionais."""
    pairs: list[dict] = []
    for jsonl in sorted(raw_dir.glob("*.jsonl")):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if source_filter and rec.get("source") != source_filter:
                continue
            if smell_filter and rec.get("smell_type") != smell_filter:
                continue
            pairs.append(rec)
    return pairs


def print_report(reports: list[PairReport], verbose: bool) -> dict:
    """Imprime resumo + detalhes. Retorna estatisticas agregadas."""
    n_total = len(reports)
    n_fail = sum(1 for r in reports if r.n_fail > 0)
    n_warn = sum(1 for r in reports if r.n_warn > 0 and r.n_fail == 0)
    n_clean = n_total - n_fail - n_warn

    print(f"\n=== Quality Check — {n_total} pares ===")
    print(f"  CLEAN: {n_clean}  ({n_clean/n_total*100:.1f}%)" if n_total else "  CLEAN: 0")
    print(f"  WARN:  {n_warn}  ({n_warn/n_total*100:.1f}%)" if n_total else "  WARN:  0")
    print(f"  FAIL:  {n_fail}  ({n_fail/n_total*100:.1f}%)" if n_total else "  FAIL:  0")

    # Agrega por regra
    rule_counts: dict[tuple[Severity, str], int] = {}
    for r in reports:
        for i in r.issues:
            key = (i.severity, i.rule)
            rule_counts[key] = rule_counts.get(key, 0) + 1
    if rule_counts:
        print("\n  Issues por regra:")
        for (sev, rule), n in sorted(rule_counts.items(),
                                     key=lambda kv: (-kv[1], kv[0])):
            print(f"    [{sev.upper():4}] {rule:30}  {n}")

    if verbose:
        for r in reports:
            if r.n_fail == 0 and r.n_warn == 0:
                continue
            print(f"\n  [{r.smell_type}] {r.repo} {r.file or '?'}::{r.function_name or '?'}  id={r.pair_id[:8]}")
            print(f"    source={r.source}  ast_sim={r.ast_similarity}")
            for issue in r.issues:
                print(f"    [{issue.severity.upper():4}] {issue.rule}: {issue.detail}")

    return {"total": n_total, "fail": n_fail, "warn": n_warn, "clean": n_clean}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"),
                        help="diretorio com os jsonls a verificar (default: data/raw)")
    parser.add_argument("--source", choices=[
        "mined_commit", "adjacent_oracle", "mined_pr", "translated_java"
    ], help="filtra por source tag")
    parser.add_argument("--smell", choices=SMELL_CODES, help="filtra por smell")
    parser.add_argument("--verbose", action="store_true",
                        help="imprime detalhe de cada par com issue")
    parser.add_argument("--fail-on-warn", action="store_true",
                        help="exit 1 tambem em caso de WARN (default: so FAIL)")
    args = parser.parse_args()

    if not args.raw_dir.is_dir():
        print(f"ERRO: {args.raw_dir} nao e diretorio", file=sys.stderr)
        return 2

    pairs = load_pairs(args.raw_dir, args.source, args.smell)
    if not pairs:
        print(f"Nenhum par encontrado em {args.raw_dir} "
              f"(source={args.source}, smell={args.smell}).")
        return 0

    reports = [check_pair(p) for p in pairs]
    stats = print_report(reports, args.verbose)

    if stats["fail"] > 0:
        return 1
    if args.fail_on_warn and stats["warn"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
