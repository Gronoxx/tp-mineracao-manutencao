"""C5c.2 (Dia 6-7 do sprint) — similaridade entre funções por tree-edit distance.

Objetivo: parear funções movidas/renomeadas ENTRE arquivos quando o git NÃO
detectou file rename (similaridade ADD/DELETE abaixo do threshold do git).

Pipeline em duas etapas:
    1. `shape_hash(src)`  — O(n): conta statements, parâmetros e profundidade
       da AST. Pares cuja shape difere muito são descartados ANTES do APTED.
    2. `ast_similarity(src1, src2)`  — O(n²) via APTED: converte cada função
       para árvore de tipos AST, computa tree-edit distance e normaliza para
       [0, 1] (1 = idênticas em estrutura).

Atenção: a similaridade ignora **nomes de identificadores** — só compara TIPOS
de nó AST (e.g., `If`, `Assign`, `Call`). Isso é proposital: refatorações que
renomeiam variáveis preservam estrutura, então `1 - D/max(N1, N2)` continua
alto. Para filtrar pares com nomes totalmente diferentes (FP de "estruturas
genéricas similares mas semânticas distintas") usar `identifier_overlap`
do Dia 8 (próxima sub-etapa do sprint).
"""
import ast
from dataclasses import dataclass
from typing import Optional

from apted import APTED, Config
from apted.helpers import Tree


@dataclass(frozen=True)
class ShapeHash:
    """Resumo O(n) da forma de uma função, para pré-filtro rápido."""
    n_stmts: int        # statements no corpo (top-level)
    n_params: int       # parâmetros (incluindo *args, **kwargs)
    depth: int          # profundidade máxima da AST (linhas aninhadas)
    n_returns: int      # número de `return` (proxy para múltiplos paths)


def _parse_function(src: str) -> Optional[ast.AST]:
    """Parseia `src` esperando que contenha UMA função top-level.

    Retorna o nó `ast.FunctionDef` (ou `AsyncFunctionDef`) — `None` se a
    string não parseia ou não contém função no topo.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def _max_depth(node: ast.AST, current: int = 0) -> int:
    """Profundidade máxima de aninhamento sintático (qualquer filho)."""
    max_child = current
    for child in ast.iter_child_nodes(node):
        d = _max_depth(child, current + 1)
        if d > max_child:
            max_child = d
    return max_child


def shape_hash(src: str) -> Optional[ShapeHash]:
    """`ShapeHash` da função em `src` — `None` se não parseia/sem função."""
    fn = _parse_function(src)
    if fn is None:
        return None
    args = fn.args
    n_params = (
        len(args.args)
        + len(args.posonlyargs)
        + len(args.kwonlyargs)
        + (1 if args.vararg else 0)
        + (1 if args.kwarg else 0)
    )
    n_returns = sum(1 for n in ast.walk(fn) if isinstance(n, ast.Return))
    return ShapeHash(
        n_stmts=len(fn.body),
        n_params=n_params,
        depth=_max_depth(fn),
        n_returns=n_returns,
    )


def shape_distance(a: ShapeHash, b: ShapeHash) -> float:
    """Distância L1 normalizada entre dois `ShapeHash` (0 = idênticos).

    Pondera cada dimensão pelo máximo observado (evita que `n_stmts` domine
    se for muito maior que `n_params`).
    """
    def _norm(x: int, y: int) -> float:
        m = max(x, y, 1)
        return abs(x - y) / m
    return sum([
        _norm(a.n_stmts, b.n_stmts),
        _norm(a.n_params, b.n_params),
        _norm(a.depth, b.depth),
        _norm(a.n_returns, b.n_returns),
    ]) / 4.0


def _ast_to_apted_tree(node: ast.AST) -> str:
    """Converte um `ast.AST` para bracket-notation do APTED.

    Usa apenas o **nome da classe** do nó (e.g., `If`, `Assign`, `Call`) —
    ignora nomes de identificadores e literais. Isso torna a similaridade
    robusta a renomeações triviais, mas sensível a mudanças estruturais.
    """
    children = list(ast.iter_child_nodes(node))
    if not children:
        return "{" + type(node).__name__ + "}"
    inner = "".join(_ast_to_apted_tree(c) for c in children)
    return "{" + type(node).__name__ + inner + "}"


def _count_nodes(node: ast.AST) -> int:
    return 1 + sum(_count_nodes(c) for c in ast.iter_child_nodes(node))


def ast_similarity(src1: str, src2: str) -> Optional[float]:
    """Similaridade estrutural entre duas funções, em [0, 1].

    Definição: `1 - D / max(N1, N2)`, onde D é o tree-edit distance APTED
    sobre as árvores de tipos AST e N_i o número total de nós da i-ésima.
    Retorna `None` se alguma das fontes não parseia.

    Custo: APTED é O((N1 N2)²) no pior caso, prático até ~150 nós (funções
    típicas até ~30 linhas). Use `shape_hash` como pré-filtro.
    """
    fn1, fn2 = _parse_function(src1), _parse_function(src2)
    if fn1 is None or fn2 is None:
        return None
    t1 = Tree.from_text(_ast_to_apted_tree(fn1))
    t2 = Tree.from_text(_ast_to_apted_tree(fn2))
    distance = APTED(t1, t2, Config()).compute_edit_distance()
    n1, n2 = _count_nodes(fn1), _count_nodes(fn2)
    denom = max(n1, n2)
    if denom == 0:
        return 1.0
    return max(0.0, 1.0 - distance / denom)


def _identifiers_of(fn: ast.AST) -> set[str]:
    """Conjunto de "identificadores semânticos" de uma função:

    - Nomes lidos/escritos (`ast.Name`) — captura variáveis, params, classes.
    - Atributos acessados (`ast.Attribute.attr`) — `cfg.total` → `{cfg, total}`.
    - Função-alvo de chamadas quando expressa como `f(...)` ou `obj.f(...)`
      (cobertas pelos casos acima).

    Identifica o **domínio** da função: duas funções com mesma forma AST
    mas usando nomes totalmente diferentes (e.g., `_validate_http_input`
    vs `_validate_db_input`) ficam separáveis por este conjunto.

    Ignora: literais (numbers, strings), keywords sintáticas, parâmetros
    formais (já considerados pela ShapeHash).
    """
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def identifier_overlap(src1: str, src2: str) -> Optional[float]:
    """Jaccard sobre identificadores de duas funções, em [0, 1].

    `|A ∩ B| / |A ∪ B|`. Quando os dois conjuntos são vazios (improvável,
    mas possível para funções `pass`), retorna 1.0 (não diferenciáveis).
    Retorna `None` se alguma das fontes não parseia ou não contém função.

    Uso típico (C5c.3): rejeitar par cross-file quando overlap < 0.5
    mesmo que `ast_similarity > 0.7` — funções estruturalmente parecidas
    mas semanticamente distintas (mesma forma genérica em domínios
    diferentes) caem aqui.
    """
    fn1, fn2 = _parse_function(src1), _parse_function(src2)
    if fn1 is None or fn2 is None:
        return None
    a, b = _identifiers_of(fn1), _identifiers_of(fn2)
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def find_cross_file_candidates(
    before_files: dict[str, str],
    after_files: dict[str, str],
    shape_threshold: float = 0.5,
    similarity_threshold: float = 0.7,
    identifier_overlap_threshold: float = 0.0,
) -> list[dict]:
    """Pareia funções movidas entre arquivos diferentes em um mesmo commit.

    Args:
        before_files: `{path: source}` no estado anterior do commit.
        after_files: `{path: source}` no estado posterior.
        shape_threshold: distância máxima de `ShapeHash` (default 0.5; valores
            altos relaxam o pré-filtro).
        similarity_threshold: similaridade mínima do APTED (default 0.7).
        identifier_overlap_threshold: Jaccard mínimo entre identificadores
            (default 0.0 = sem filtro). C5c.3 do sprint sugere 0.5 — funções
            com mesma forma estrutural mas vocabulário disjunto (e.g.,
            `_validate_http_input` vs `_validate_db_input`) são rejeitadas.

    Retorna lista de candidatos `{function_name_before, function_name_after,
    file_before, file_after, similarity, identifier_overlap}`. Não chama
    `verify_pair` — só identifica os pares.

    Heurística: só considera funções que NÃO estão presentes nos arquivos
    correspondentes (gone_from_before, new_in_after) — funções modificadas
    no MESMO arquivo já são tratadas por `extract_candidates`.
    """
    # Coleta todas as funções top-level por arquivo.
    def _functions_in(files: dict[str, str]) -> dict[tuple[str, str], str]:
        """`{(file, fn_name): source}` para cada função top-level."""
        out: dict[tuple[str, str], str] = {}
        for path, src in files.items():
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[(path, node.name)] = ast.get_source_segment(src, node) or ""
        return out

    bf = _functions_in(before_files)
    af = _functions_in(after_files)

    # Funções top-level "removidas" e "adicionadas" (cross-file de verdade —
    # mesma chave (path, name) presente em só um lado).
    bf_keys = set(bf)
    af_keys = set(af)
    gone = [k for k in (bf_keys - af_keys)]
    fresh = [k for k in (af_keys - bf_keys)]

    candidates: list[dict] = []
    for gk in gone:
        g_src = bf[gk]
        g_shape = shape_hash(g_src)
        if g_shape is None:
            continue
        for fk in fresh:
            # Mesmo arquivo — já é coberto pelo extract_candidates per-file.
            if gk[0] == fk[0]:
                continue
            f_src = af[fk]
            f_shape = shape_hash(f_src)
            if f_shape is None:
                continue
            if shape_distance(g_shape, f_shape) > shape_threshold:
                continue
            sim = ast_similarity(g_src, f_src)
            if sim is None or sim < similarity_threshold:
                continue
            # C5c.3: filtro adicional por sobreposição de identificadores.
            # Pares estruturalmente parecidos mas com vocabulário disjunto
            # (mesma forma genérica em domínios diferentes) ficam de fora.
            overlap = identifier_overlap(g_src, f_src)
            if overlap is None:
                continue
            if overlap < identifier_overlap_threshold:
                continue
            candidates.append({
                "file_before": gk[0],
                "function_name_before": gk[1],
                "file_after": fk[0],
                "function_name_after": fk[1],
                "similarity": sim,
                "identifier_overlap": overlap,
                "before_source": g_src,
                "after_source": f_src,
            })
    # Quando uma função "gone" casa com várias "fresh" acima do threshold,
    # mantemos só a melhor por gone (evita explosão combinatória nos pares).
    best_per_gone: dict[tuple[str, str], dict] = {}
    for c in candidates:
        key = (c["file_before"], c["function_name_before"])
        if key not in best_per_gone or c["similarity"] > best_per_gone[key]["similarity"]:
            best_per_gone[key] = c
    return list(best_per_gone.values())
