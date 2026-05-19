"""Minerador de pares de refatoração (R1–R5) — pipeline em 3 estágios.

Estágio 1 — recall: a palavra-chave na mensagem do commit é só um pré-filtro de
            velocidade (decide se vale olhar o commit) e um metadado. NÃO é o
            rótulo.
Estágio 2 — extração: para cada função que mudou, monta um par candidato; para
            Extract Method (R1), captura as funções-helper novas que o
            orquestrador passa a chamar.
Estágio 3 — verificação: roda os detectores estáticos de `detectores/`; um par
            só é aceito (e rotulado) se o detector dispara no `before` e NÃO
            dispara no `after`. O detector é o rotulador — não a keyword.

Saída: registros `core.schema.RefactoringPair`, um JSONL por smell, escrita
idempotente (dedup por `id`).
"""
import ast
import json
import sys
from pathlib import Path

from pydriller import Repository

_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.schema import RefactoringPair          # noqa: E402
from core.smells import NAME_TO_CODE, CODE_TO_NAME  # noqa: E402
from detectores import DETECTORS                 # noqa: E402
from .ast_utils import parse_file_from_string    # noqa: E402

# Estágio 1 — palavras-chave: pré-filtro de recall (não é rótulo).
SMELL_KEYWORDS = [
    "extract method", "extract function", "split method", "split function",
    "refactor", "decompose", "break down", "too long", "large method",
    "parameter object", "introduce parameter", "too many params",
    "too many arguments", "reduce params",
    "magic number", "named constant", "replace literal", "extract constant",
    "hardcoded", "magic string",
    "guard clause", "early return", "reduce nesting", "flatten",
    "nested if", "deep nesting", "simplify condition",
    "remove dead code", "dead code", "unused variable", "unreachable",
    "remove unused", "cleanup", "clean up",
]


def matched_keywords(commit_msg: str) -> list[str]:
    """Palavras-chave de refatoração presentes na mensagem (metadado)."""
    msg = (commit_msg or "").lower()
    return [kw for kw in SMELL_KEYWORDS if kw in msg]


def _is_test_path(path: str) -> bool:
    """True se `path` é de um arquivo de teste.

    Casa por componente de caminho, não por substring — `"test" in path`
    pegava `latest/`, `contest.py` etc. por engano.
    """
    parts = Path(path).parts
    if any(p in ("test", "tests") for p in parts[:-1]):
        return True
    name = parts[-1] if parts else ""
    return name.startswith("test_") or name.endswith("_test.py")


def is_valid_pair(before: str, after: str) -> bool:
    """Par sintaticamente válido, não-trivial e de fato alterado."""
    try:
        ast.parse(before)
        ast.parse(after)
    except SyntaxError:
        return False
    if before.strip() == after.strip():
        return False
    if len(after.strip()) < 10:
        return False
    return True


def _calls_in(source: str) -> set[str]:
    """Nomes de função chamados no corpo de `source` (`f()` e `obj.f()`)."""
    names: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def _funcinfo(source: str):
    """FunctionInfo da primeira função de um trecho, ou None."""
    try:
        fns = parse_file_from_string(source)["functions"]
    except SyntaxError:
        return None
    return fns[0] if fns else None


def extract_candidates(before_src: str, after_src: str, filename: str) -> list[dict]:
    """Estágio 2 — pares candidatos: funções que mudaram entre before/after.

    Cada candidato carrega os `FunctionInfo` antes/depois e os `helper_sources`
    (funções novas no arquivo que o corpo do `after` passou a chamar — usado
    pelo R1 Extract Method)."""
    try:
        before = parse_file_from_string(before_src, filename)
        after = parse_file_from_string(after_src, filename)
    except SyntaxError:
        return []

    def flat(parsed: dict) -> dict:
        d = {f.name: f for f in parsed["functions"]}
        for cls in parsed["classes"]:
            for m in cls.methods:
                d[f"{cls.name}.{m.name}"] = m
        return d

    before_fns, after_fns = flat(before), flat(after)
    new_names = set(after_fns) - set(before_fns)   # candidatas a helper

    candidates = []
    for name, bf in before_fns.items():
        af = after_fns.get(name)
        if af is None or bf.source == af.source:
            continue
        if not is_valid_pair(bf.source, af.source):
            continue
        called = _calls_in(af.source)
        helper_sources = [
            after_fns[hn].source for hn in new_names
            if hn.split(".")[-1] in called
        ]
        candidates.append({
            "function_name": name,
            "before_fn": bf,
            "after_fn": af,
            "helper_sources": helper_sources,
        })
    return candidates


def verify_pair(candidate: dict, *, repo: str, commit_hash: str,
                parent_commit: str | None, commit_msg: str,
                msg_keywords: list[str], filename: str) -> list[RefactoringPair]:
    """Estágio 3 — roda os 5 detectores; emite um RefactoringPair por smell
    cujo detector dispara no `before` e não no `after`."""
    bf, af = candidate["before_fn"], candidate["after_fn"]
    records: list[RefactoringPair] = []

    for smell_name, detect in DETECTORS.items():
        before_res = detect(bf)
        after_res = detect(af)
        if not (before_res.detected and not after_res.detected):
            continue

        smell_code = NAME_TO_CODE[smell_name]
        after_code = af.source
        n_after = 1

        if smell_code == "R1":  # Extract Method — o `after` inclui os helpers
            helpers = candidate["helper_sources"]
            # F3: encurtar um Long Method sem extrair nenhum helper não é
            # Extract Method (pode ser inline, deleção etc.) — não é par R1.
            if not helpers:
                continue
            long_det = DETECTORS["long_method"]
            # nenhum helper pode ser longo (senão não resolveu o smell)
            helper_infos = [_funcinfo(h) for h in helpers]
            if any(hi and long_det(hi).detected for hi in helper_infos):
                continue
            after_code = af.source + "\n\n\n" + "\n\n\n".join(helpers)
            n_after = 1 + len(helpers)

        records.append(RefactoringPair(
            before_code=bf.source,
            after_code=after_code,
            smell_type=smell_code,
            repo=repo,
            commit_hash=commit_hash,
            parent_commit=parent_commit,
            file=filename,
            function_name=candidate["function_name"],
            commit_msg=commit_msg,
            msg_keywords=msg_keywords,
            metrics_before=dict(before_res.evidence or {}),
            metrics_after=dict(after_res.evidence or {}),
            detector_before={"detected": before_res.detected,
                             "evidence": before_res.evidence},
            detector_after={"detected": after_res.detected,
                            "evidence": after_res.evidence},
            verified=True,
            n_functions_after=n_after,
        ))
    return records


def mine(repo_url: str, output_path: Path, since=None, to=None,
         max_commits: int | None = None) -> dict:
    """Minera um repositório → escreve `<smell>.jsonl` em `output_path`.

    Escrita idempotente: cada arquivo é reescrito por execução e os registros
    são deduplicados por `id` — rodar 2× não duplica."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    by_smell: dict[str, dict[str, dict]] = {}   # smell_code -> {id -> record}
    scanned = 0

    repo = Repository(
        repo_url, since=since, to=to,
        only_no_merge=True,
        only_modifications_with_file_types=[".py"],
    )
    for commit in repo.traverse_commits():
        keywords = matched_keywords(commit.msg)   # estágio 1
        if not keywords:
            continue
        if max_commits is not None and scanned >= max_commits:
            break
        scanned += 1
        parent = commit.parents[0] if commit.parents else None

        for mf in commit.modified_files:
            path = mf.new_path or mf.old_path or mf.filename or ""
            if not path.endswith(".py") or _is_test_path(path):
                continue
            if mf.source_code_before is None or mf.source_code is None:
                continue

            for cand in extract_candidates(mf.source_code_before,
                                           mf.source_code, path):
                for rec in verify_pair(
                    cand, repo=repo_url, commit_hash=commit.hash,
                    parent_commit=parent, commit_msg=commit.msg,
                    msg_keywords=keywords, filename=path,
                ):
                    by_smell.setdefault(rec.smell_type, {})[rec.id] = rec.model_dump()

    counts = {}
    for smell_code, recs in by_smell.items():
        out_file = output_path / f"{CODE_TO_NAME[smell_code]}.jsonl"
        with open(out_file, "w", encoding="utf-8") as f:
            for record in recs.values():
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        counts[smell_code] = len(recs)
    return counts
