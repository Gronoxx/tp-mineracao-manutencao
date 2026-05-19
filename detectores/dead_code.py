import ast
from .data_structs import FunctionInfo
from .base import DetectionResult

def _find_unreachable(fn_source: str) -> list[dict]:

    """Encontra statements após return/raise no mesmo bloco."""

    try:
        tree = ast.parse(fn_source)
    except SyntaxError:
        return []

    dead = []
    for node in ast.walk(tree):
        # itera sobre listas de statements (body, orelse, handlers, etc.)

        for stmts in [getattr(node, "body", []),
                      getattr(node, "orelse", []),
                      getattr(node, "finalbody", [])]:

            # F6: em `IfExp` (ternario) e `Lambda`, `body`/`orelse` sao um nó
            # de expressao único, não uma lista de statements — pular.
            if not isinstance(stmts, list):
                continue

            terminal_seen = False

            for stmt in stmts:
                if terminal_seen:
                    dead.append({"type": "unreachable", "lineno": stmt.lineno})

                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    terminal_seen = True

    return dead


def _collect_param_names(args: ast.arguments) -> set[str]:
    """Todos os nomes ligados como parâmetros, incluindo *args/**kwargs."""
    names: set[str] = set()
    for grp in (args.posonlyargs, args.args, args.kwonlyargs):
        names.update(a.arg for a in grp)
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


# Nodes que criam um escopo próprio em Python: `ast.walk` os atravessa, mas
# para análise de variáveis precisamos tratá-los como caixa-preta — bindings
# internos NÃO contam para o escopo externo (revisão de PR #16 — C1).
_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda,
                ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _walk_no_scope_descent(node):
    """`ast.walk` que NÃO desce em escopos aninhados.

    Nodes em `_SCOPE_TYPES` são retornados (para o chamador agregar suas
    variáveis livres) mas seus interiores não são visitados."""
    yield node
    if isinstance(node, _SCOPE_TYPES):
        return
    for child in ast.iter_child_nodes(node):
        yield from _walk_no_scope_descent(child)


def _walk_into_scope(scope):
    """Itera os nodes DENTRO de `scope` (decorators, args, body, …), tratando
    qualquer escopo aninhado encontrado como folha (yielda o node de escopo
    aninhado mas não desce). Usado quando estamos analisando `scope` por
    dentro — contrast com `_walk_no_scope_descent`, que para quando o próprio
    input é um escopo (usado durante a recursão)."""
    for child in ast.iter_child_nodes(scope):
        yield from _walk_no_scope_descent(child)


def _scope_local_bindings(scope) -> set[str]:
    """Nomes ligados localmente em `scope`: parâmetros (se função/lambda),
    alvos das comprehensions, e Stores diretos no corpo (sem descer em
    escopos aninhados internos)."""
    bound: set[str] = set()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        bound |= _collect_param_names(scope.args)
    if isinstance(scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        for gen in scope.generators:
            for n in ast.walk(gen.target):
                if isinstance(n, ast.Name):
                    bound.add(n.id)
    for node in _walk_into_scope(scope):
        if isinstance(node, _SCOPE_TYPES):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
    return bound


def _scope_free_vars(scope) -> set[str]:
    """Variáveis livres de `scope` — nomes lidos dentro de `scope` (ou de
    seus escopos aninhados internos) que NÃO são ligados localmente nele.

    São os nomes que o escopo "puxa" do escopo externo — i.e., os usos
    legítimos de closure que devem contar como uso na análise do externo.
    Crucialmente: um nome reusado *com binding próprio* num escopo interno
    NÃO sobe para o externo, evitando mascarar um local externo morto (C1)."""
    bound = _scope_local_bindings(scope)
    loaded: set[str] = set()
    for node in _walk_into_scope(scope):
        if isinstance(node, _SCOPE_TYPES):
            # escopo aninhado-mais-interno: agrega suas free vars
            loaded |= _scope_free_vars(node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)
    return loaded - bound


def _analyze_function(fn) -> list[dict]:
    """Analisa UMA `FunctionDef`/`AsyncFunctionDef` por variáveis locais
    atribuídas e nunca lidas. Não desce em escopos aninhados — closures que
    carregam um nome do externo contam como uso (via `_scope_free_vars`);
    closures que reusam o nome com binding próprio NÃO mascaram o externo."""
    params = _collect_param_names(fn.args)
    assigned: dict[str, int] = {}     # nome -> primeira linha
    loaded: set[str] = set()          # nomes lidos neste escopo + free vars de aninhados
    augmented: set[str] = set()       # alvos de `x += ...`
    loop_targets: set[str] = set()    # alvos de `for`
    unpack_targets: set[str] = set()  # alvos em desempacotamento de tupla/lista
    walrus_targets: set[str] = set()  # alvos de `:=` (consumidos pela expressão envolvente)
    deleted: set[str] = set()         # nomes em `del`
    decl_global: set[str] = set()     # `global`/`nonlocal`

    for node in _walk_into_scope(fn):
        if isinstance(node, _SCOPE_TYPES):
            # escopo aninhado: caixa-preta — só agrega suas variáveis livres.
            loaded |= _scope_free_vars(node)
            continue
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            decl_global.update(node.names)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                augmented.add(node.target.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if isinstance(node.target, ast.Name):
                loop_targets.add(node.target.id)
            else:
                for t in ast.walk(node.target):
                    if isinstance(t, ast.Name):
                        loop_targets.add(t.id)
        elif isinstance(node, ast.NamedExpr):
            # walrus `:=`: o valor é consumido pela expressão envolvente;
            # o alvo é binding mas não-uso aparente — não reportar.
            if isinstance(node.target, ast.Name):
                walrus_targets.add(node.target.id)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for tgt in targets:
                # desempacotamento `a, b = ...`: idioma intencional comum —
                # marcamos todos os alvos para não reportar nenhum deles.
                if isinstance(tgt, (ast.Tuple, ast.List)):
                    for sub in ast.walk(tgt):
                        if isinstance(sub, ast.Name):
                            unpack_targets.add(sub.id)
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    deleted.add(t.id)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                assigned.setdefault(node.id, node.lineno)
            elif isinstance(node.ctx, ast.Load):
                loaded.add(node.id)

    unused: list[dict] = []
    for name, lineno in assigned.items():
        if name in params:           # nunca reporta parâmetros (unsound — interface)
            continue
        if name in loaded:           # lido em algum lugar (inclui closures legítimas)
            continue
        if name in decl_global:      # global/nonlocal: usado fora do escopo
            continue
        if name in deleted:          # `del x` referencia o binding
            continue
        if name in augmented:        # `x += ...`: efeito colateral plausível
            continue
        if name in loop_targets:     # var de loop não usada: idioma comum
            continue                 # (trade-off deliberado p/ reduzir FP)
        if name in unpack_targets:   # desempacotamento parcial é intencional
            continue
        if name in walrus_targets:   # walrus: valor consumido pela expressão
            continue
        if name == "_" or name.startswith("_"):  # convenção "descartado"
            continue
        unused.append({"type": "unused_var", "lineno": lineno})
    return unused


def _find_unused_vars(fn_source: str) -> list[dict]:
    """Detecta variáveis LOCAIS atribuídas mas nunca lidas, via análise AST.

    Motivação (investigação F-R5): a implementação anterior rodava
    `vulture <tmpfile> --min-confidence 80` sobre a função isolada. Empiricamente
    (vulture 2.16):

      * variáveis locais não usadas  -> rótulo "unused variable" a 60% de confiança
      * parâmetros não usados        -> rótulo "unused variable" a 100% de confiança

    Com o corte em 80%, o detector fazia exatamente o OPOSTO do pretendido:
    descartava todo local genuinamente morto (sound) e disparava apenas em
    parâmetros (unsound — um parâmetro não usado no corpo pode existir só para
    satisfazer um contrato de interface: callback, hook de framework, **kwargs;
    não é dead code). Analisar a função isolada torna a checagem de parâmetro
    inerentemente insegura — só o módulo/chamadores revelam o contrato.

    Esta versão analisa apenas variáveis locais, cujo escopo É a função, logo a
    decisão é sound mesmo com a função isolada. Parâmetros, `*args`/`**kwargs`
    nunca são reportados. Sem subprocesso, sem arquivo temporário.

    Tratamento de escopos aninhados (revisão de PR #16 — C1): cada
    `FunctionDef`/`AsyncFunctionDef` é analisada independentemente, sem descer
    em escopos internos. Closures que carregam um nome do externo (via
    variável livre) contam como uso; closures que reusam o nome com binding
    próprio NÃO mascaram o local externo. Comprehensions e walrus também
    tratados explicitamente (I1, I2).
    """
    try:
        tree = ast.parse(fn_source)
    except SyntaxError:
        return []

    unused: list[dict] = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            unused.extend(_analyze_function(fn))
    return unused


def detect(fn: FunctionInfo) -> DetectionResult:

    dead = _find_unreachable(fn.source) + _find_unused_vars(fn.source)

    return DetectionResult(
        smell="dead_code",
        detected=len(dead) > 0,
        confidence=1.0,
        evidence={"dead_code": dead},
    )
