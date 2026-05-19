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


def _find_unused_vars(fn_source: str) -> list[dict]:
    """Detecta variáveis LOCAIS atribuídas mas nunca lidas, via `ast`.

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
    """
    try:
        tree = ast.parse(fn_source)
    except SyntaxError:
        return []

    unused: list[dict] = []

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        params = _collect_param_names(fn.args)

        assigned: dict[str, int] = {}   # nome -> primeira linha de atribuição
        loaded: set[str] = set()        # nomes lidos (ctx=Load) em qualquer lugar
        augmented: set[str] = set()     # alvos de `x += ...`
        loop_targets: set[str] = set()  # alvos de `for`
        unpack_targets: set[str] = set()  # nomes em desempacotamento de tupla/lista
        deleted: set[str] = set()       # nomes em `del`
        decl_global: set[str] = set()   # nomes em `global`/`nonlocal`

        # `ast.walk` desce em funções aninhadas: isso é INTENCIONAL — um nome
        # lido dentro de uma closure interna conta como uso (caso "param/local
        # usado só na função aninhada"), evitando falso positivo.
        for node in ast.walk(fn):
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
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for tgt in targets:
                    # desempacotamento `a, b = ...` é idioma intencional comum
                    # (igual ao vulture, que também não reporta esses alvos).
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

        for name, lineno in assigned.items():
            if name in params:           # nunca reporta parâmetros (unsound)
                continue
            if name in loaded:           # lido em algum lugar (inclui closures)
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
            if name == "_" or name.startswith("_"):  # convenção "descartado"
                continue
            unused.append({"type": "unused_var", "lineno": lineno})

    return unused


def detect(fn: FunctionInfo) -> DetectionResult:

    dead = _find_unreachable(fn.source) + _find_unused_vars(fn.source)

    return DetectionResult(
        smell="dead_code",
        detected=len(dead) > 0,
        confidence=1.0,
        evidence={"dead_code": dead},
    )
