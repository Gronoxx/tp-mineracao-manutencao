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


def _magnitude(res, smell_name: str) -> float:
    """Magnitude do smell em `res` — quão "grave" é. Maior = pior.

    Usado por `verify_pair` no modo permissivo (E1) para aceitar pares em
    que o detector ainda dispara no `after` mas com magnitude bem menor —
    captura refatorações parciais que a regra estrita "fires-before-and-NOT-after"
    perde."""
    ev = res.evidence or {}
    if smell_name == "long_method":
        return float(ev.get("lines_of_code") or ev.get("lines_fallback") or 0)
    if smell_name == "long_param_list":
        return float(ev.get("count", 0))
    if smell_name == "magic_numbers":
        return float(len(ev.get("magic_numbers", [])))
    if smell_name == "deep_nesting":
        return float(ev.get("max_depth", 0))
    if smell_name == "dead_code":
        return float(len(ev.get("dead_code", [])))
    return 0.0


# Redução mínima de magnitude (fração) para aceitar um par como `partial=True`
# quando o detector continua disparando no `after`. Calibrado empiricamente
# (sweep em pytest, 2026-05-19): 0.5 não pega nada (refactors incrementais);
# 0.0 incorpora "não-redução" que é ruído; 0.1 captura "uma unidade de
# melhoria" (depth 5→4, 8 magic→7, 80 LOC→70) sem ruído de zero-mudança.
PARTIAL_REDUCTION_MIN = 0.1


def verify_pair(candidate: dict, *, repo: str, commit_hash: str,
                parent_commit: str | None, commit_msg: str,
                msg_keywords: list[str], filename: str,
                partial_threshold: float | None = None,
                source: str = "mined_commit") -> list[RefactoringPair]:
    """Estágio 3 — roda os 5 detectores; emite um RefactoringPair por smell
    cujo detector dispara no `before`.

    Modo estrito (`partial_threshold=None`, default): só aceita pares cujo
    detector dispara no `before` e NÃO dispara no `after` — sinal limpo.

    Modo permissivo (E1, `partial_threshold=0.0..1.0`): ALÉM dos estritos,
    aceita pares em que o detector ainda dispara no `after` mas com magnitude
    reduzida em pelo menos `partial_threshold` (e.g., 0.5 = redução de 50%+).
    Esses pares são marcados `partial=True` — sinal mais ruidoso, ideal p/
    revisão humana (a fila do curador PR 6 está preparada pra isso)."""
    bf, af = candidate["before_fn"], candidate["after_fn"]
    records: list[RefactoringPair] = []

    for smell_name, detect in DETECTORS.items():
        # Resiliência: um detector que crashar num input estranho NÃO pode
        # derrubar a corrida — só pulamos esse smell para esse candidato e
        # logamos (corridas de produção são longas; um único bug não pode
        # custar horas de mineração).
        try:
            before_res = detect(bf)
            after_res = detect(af)
        except Exception as exc:
            print(f"  WARN: detector {smell_name!r} falhou em "
                  f"{candidate.get('function_name')!r}: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            continue
        if not before_res.detected:
            continue

        # Estrito = before dispara, after não.  Permissivo = before dispara
        # E after também, MAS a magnitude do after é <= before * (1 - threshold).
        is_partial = False
        if after_res.detected:
            if partial_threshold is None:
                continue   # modo estrito rejeita
            mag_b = _magnitude(before_res, smell_name)
            mag_a = _magnitude(after_res, smell_name)
            if mag_b <= 0 or mag_a > mag_b * (1.0 - partial_threshold):
                continue
            is_partial = True

        smell_code = NAME_TO_CODE[smell_name]
        after_code = af.source
        n_after = 1

        if smell_code == "R1":  # Extract Method — o `after` inclui os helpers
            helpers = candidate["helper_sources"]
            # F3: encurtar um Long Method sem extrair nenhum helper não é
            # Extract Method (pode ser inline, deleção etc.) — não é par R1.
            # A regra vale também no modo permissivo.
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
            partial=is_partial,
            n_functions_after=n_after,
            source=source,
        ))
    return records


def _load_existing(path: Path) -> dict[str, dict]:
    """Registros já gravados em `path` (JSONL), indexados por `id`.

    Permite que `mine()` mescle a saída de vários repositórios no mesmo
    diretório sem que um sobrescreva o outro (F1)."""
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = rec.get("id")
        if rid:
            out[rid] = rec
    return out


def _merge_write(output_path: Path, by_smell: dict[str, dict[str, dict]]) -> dict:
    """Escreve cada `<smell>.jsonl` mesclando com o conteúdo já em disco (F1).

    Padrão load → merge por `id` → write (análogo a `save_review()` do curador):
    registros de execuções anteriores são preservados; a execução atual tem
    precedência em caso de `id` repetido. `counts` reflete só o que ESTA
    execução encontrou (não o total acumulado em disco)."""
    counts: dict[str, int] = {}
    for smell_code, recs in by_smell.items():
        out_file = output_path / f"{CODE_TO_NAME[smell_code]}.jsonl"
        merged = _load_existing(out_file)
        merged.update(recs)
        with open(out_file, "w", encoding="utf-8") as f:
            for record in merged.values():
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        counts[smell_code] = len(recs)
    return counts


def _caps_atingidos(by_smell: dict[str, dict], caps: dict[str, int]) -> bool:
    """True se todo smell de `caps` já atingiu seu limite em `by_smell` —
    sinal para `mine()` parar de varrer o repositório mais cedo."""
    return all(len(by_smell.get(s, {})) >= n for s, n in caps.items())


def mine(repo_url: str, output_path: Path, since=None, to=None,
         max_commits: int | None = None,
         caps: dict[str, int] | None = None,
         partial_threshold: float | None = None,
         require_keyword: bool = True) -> dict:
    """Minera um repositório → mescla `<smell>.jsonl` em `output_path`.

    Escrita acumulativa: registros já em `output_path` (de execuções
    anteriores, p.ex. outros repositórios) são preservados — o merge é por
    `id`, então chamar `mine()` para vários repositórios no mesmo diretório
    acumula em vez de sobrescrever. Idempotente: rodar o mesmo repositório 2×
    não duplica. O `dict` retornado conta só os pares encontrados nesta
    chamada.

    `caps` (opcional): teto de pares por smell-code para ESTA chamada — quando
    um smell atinge o teto, novos pares dele são ignorados; quando todos os
    smells de `caps` enchem, a varredura do repositório para. O runner usa isso
    para distribuir o cap global entre os repositórios (diversidade).

    `require_keyword` (C5b — Dia 4 do sprint): quando `True` (default), pula
    commits cuja mensagem não casa nenhuma `SMELL_KEYWORDS` (pré-filtro de
    recall). Quando `False`, processa TODO commit — útil para mineração mais
    agressiva em janelas curtas, ao custo de mais commits varridos."""
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
        if require_keyword and not keywords:
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
                    partial_threshold=partial_threshold,
                ):
                    bucket = by_smell.setdefault(rec.smell_type, {})
                    # respeita o teto por smell desta chamada (`caps`)
                    if (caps is not None and rec.id not in bucket
                            and len(bucket) >= caps.get(rec.smell_type, float("inf"))):
                        continue
                    bucket[rec.id] = rec.model_dump()

        if caps is not None and _caps_atingidos(by_smell, caps):
            break   # todos os smells encheram o orçamento — para a varredura

    return _merge_write(output_path, by_smell)


def mine_specific_commits(repo_url: str, output_path: Path,
                          commit_hashes: list[str],
                          partial_threshold: float | None = 0.1,
                          source: str = "adjacent_oracle",
                          clone_repo_to: str | None = None,
                          only_no_merge: bool = True) -> dict:
    """C3 (Dia 3 do sprint) — minera commits PRÉ-IDENTIFICADOS como refatoração
    (não passa pelo filtro de keyword) e marca os pares resultantes com a tag
    de proveniência `source` (default `"adjacent_oracle"`).

    Diferenças vs. `mine()`:
        - Restringe a iteração a `commit_hashes` via PyDriller (`only_commits`).
        - **Não** chama `matched_keywords` para filtrar — esses commits já são
          conhecidos como refatoração (PyRef/Sourcery/ActRef etc.); a função
          de keyword foi pensada como pré-filtro de recall para mineração cega,
          não faz sentido aplicá-la aqui (perderia commits que PyRef já validou).
        - Default `partial_threshold=0.1`: aceita refatorações parciais por
          design (oracles podem rotular um aspecto de um commit multi-smell).
        - Default `source="adjacent_oracle"`: tag de proveniência.

    `only_no_merge=False` permite incluir merge commits — usado por `mine_pr()`
    para processar o merge commit de um PR como um único candidate batch.

    Idempotente: o merge por `id` continua valendo — rodar 2× não duplica.
    Retorna o dict de contagem por smell (mesmo formato de `mine()`).
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    by_smell: dict[str, dict[str, dict]] = {}
    if not commit_hashes:
        return _merge_write(output_path, by_smell)

    kwargs = dict(
        only_commits=list(commit_hashes),
        only_no_merge=only_no_merge,
        only_modifications_with_file_types=[".py"],
    )
    if clone_repo_to:
        kwargs["clone_repo_to"] = clone_repo_to
    repo = Repository(repo_url, **kwargs)

    for commit in repo.traverse_commits():
        parent = commit.parents[0] if commit.parents else None
        # Mensagem do commit ainda entra como metadado (útil pra rastreio),
        # mas as keywords NÃO viram filtro nem condicionam aceitação.
        keywords = matched_keywords(commit.msg)

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
                    partial_threshold=partial_threshold,
                    source=source,
                ):
                    bucket = by_smell.setdefault(rec.smell_type, {})
                    bucket[rec.id] = rec.model_dump()

    return _merge_write(output_path, by_smell)


def mine_pr(repo_url: str, output_path: Path,
            merge_commit_shas: list[str],
            partial_threshold: float | None = 0.1,
            clone_repo_to: str | None = None) -> dict:
    """C5a (Dia 4 do sprint) — minera PRs como diff único.

    Cada SHA em `merge_commit_shas` deve ser o **merge commit** que fechou um
    PR no repositório (resolução: `gh pr view <N> --json mergeCommit.oid`).
    PyDriller processa o merge commit comparando contra seu primeiro parent —
    em PRs squash-merged isso é o diff completo do PR; em true merges é o
    cumulativo desde a divergência da branch.

    Pares produzidos recebem `source="mined_pr"` (D5 do sprint — distingue
    pares colapsados-por-PR dos commit-a-commit do `mine()`).

    Implementação: thin wrapper sobre `mine_specific_commits` com
    `only_no_merge=False` (precisamos do merge commit) e `source="mined_pr"`.
    Bypassa o filtro de keyword pela mesma razão do C3: o PR já foi rotulado
    como "refactor" pelo label externo (C2 — Dia 10/11 vai povoar essa lista
    via GraphQL); o keyword na mensagem perderia PRs validados.
    """
    return mine_specific_commits(
        repo_url=repo_url,
        output_path=output_path,
        commit_hashes=merge_commit_shas,
        partial_threshold=partial_threshold,
        source="mined_pr",
        clone_repo_to=clone_repo_to,
        only_no_merge=False,
    )
