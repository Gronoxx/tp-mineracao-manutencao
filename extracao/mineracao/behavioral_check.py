"""C5c.4 (Dia 9 do sprint) — behavioral validation amostrada para pares
cross-file produzidos pelo AST similarity (Dia 6-7).

Objetivo: medir o RATIO de pares cross-file que são *behaviorally equivalent*
— mesmas entradas produzindo mesmas saídas — como gate empírico de precisão.
Calibração: se em uma amostra de N=50 pares cross-file, a taxa de aprovação
estiver > 70%, considera-se o pipeline confiável; abaixo de 50%, refinar
thresholds.

NOTA OPERACIONAL: este módulo executa código arbitrário do `before` e `after`
dentro de um sandbox restrito. NUNCA usar dentro de `mine()` (que processa
repos remotos) — só em validação offline (e.g., notebook ou script de
calibração após a mineração estar completa).

Implementação:
- Property-based testing via `hypothesis` (`@given` programático).
- Estratégias simples (int, str, list, None) — funções com tipagem mais
  complexa podem fugir do escopo. O caller decide se aceita um par com
  `INCONCLUSIVE` (zero amostras executadas) ou rejeita.
- Timeout por chamada via thread (cross-platform; ver `_with_timeout`). É um
  timeout *soft*: respeita o prazo para o caller, mas não mata a thread —
  aceitável porque roda offline sobre snippets pequenos já minerados.
"""
import ast
import concurrent.futures
from dataclasses import dataclass
from typing import Optional

from hypothesis import given, settings, strategies as st


@dataclass
class BehavioralCheckResult:
    """Resumo de uma rodada de behavioral check entre 2 funções."""
    equivalent: bool                    # True se TODAS as amostras casaram
    n_samples: int                      # tentativas
    n_matching: int                     # outputs iguais (ou ambas erram igual)
    n_one_raised: int                   # uma levantou, a outra não
    n_different_output: int             # ambas retornaram, valores diferem
    error_msg: Optional[str] = None     # erro estrutural (parse, sandbox)


def _compile_function(src: str, name_hint: str = "f"):
    """Compila uma função top-level a partir da fonte; retorna callable ou None."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    fn_def = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_def = node
            break
    if fn_def is None:
        return None
    # Renomeia a função para `name_hint` para evitar colisão de nomes entre
    # before/after no mesmo namespace.
    fn_def.name = name_hint
    module = ast.Module(body=[fn_def], type_ignores=[])
    ast.fix_missing_locations(module)
    code = compile(module, filename="<behavioral>", mode="exec")
    # Sandbox: namespace minimalista (sem __builtins__ não dá pra rodar quase
    # nada; com builtins padrão ainda há risco — assumimos que a chamada vem
    # de validação offline em código já minerado).
    namespace: dict = {"__builtins__": __builtins__}
    try:
        exec(code, namespace)
    except Exception:
        return None
    return namespace.get(name_hint)


def _n_params(src: str) -> int:
    """Quantidade de parâmetros posicionais regulares da função top-level."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return (len(node.args.args)
                    + len(node.args.posonlyargs))
    return 0


def _with_timeout(fn, args, timeout_seconds: float):
    """Executa ``fn(*args)`` com timeout cross-platform via thread. Retorna
    ``(value, exc)``.

    Diferente do antigo ``signal.alarm`` (só-UNIX, hard-kill), o timeout aqui é
    *soft*: a worker NÃO é interrompida. Se ``fn`` for um loop infinito
    CPU-bound, a chamada retorna ``TimeoutError`` no prazo, mas a thread segue
    viva em background até terminar (no pior caso, junta no encerramento do
    interpretador). É aceitável porque este módulo roda offline sobre snippets
    pequenos já minerados (ver nota no topo). Para hard-kill de código hostil,
    troque por ``multiprocessing`` com ``terminate()``.
    """
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(fn, *args)
    try:
        return future.result(timeout=timeout_seconds), None
    except concurrent.futures.TimeoutError:
        return None, TimeoutError("call exceeded timeout")
    except Exception as exc:
        return None, exc
    finally:
        # wait=False: não bloqueia o caller esperando uma worker que estourou o
        # prazo. (Num `with`, o __exit__ chamaria shutdown(wait=True) e travaria
        # exatamente no caso de timeout que queremos evitar.)
        ex.shutdown(wait=False)

def behavioral_check(
    src_before: str,
    src_after: str,
    n_samples: int = 10,
    timeout_seconds: float = 0.5,
) -> BehavioralCheckResult:
    """Compara `src_before` e `src_after` por amostragem de entradas.

    Retorna `BehavioralCheckResult.equivalent=True` apenas quando TODAS as
    `n_samples` casaram (mesmo retorno ou mesma exceção). Funções com tipagem
    incompatível com o gerador (e.g., recebem objetos custom) tendem a render
    `n_matching=0` e `equivalent=False` — o caller deve interpretar essa
    falha como `inconclusive`, não necessariamente como divergência semântica.
    """
    fn_b = _compile_function(src_before, name_hint="_before")
    fn_a = _compile_function(src_after, name_hint="_after")
    if fn_b is None or fn_a is None:
        return BehavioralCheckResult(
            equivalent=False, n_samples=0, n_matching=0,
            n_one_raised=0, n_different_output=0,
            error_msg="failed to compile one of the functions",
        )

    arity = max(_n_params(src_before), _n_params(src_after))
    if arity == 0:
        # Função sem parâmetros — apenas um chamado faz sentido.
        n_samples = 1

    # Estratégia simples: ints, strings curtas, listas pequenas, None.
    # Cobre uma fração dos casos reais, mas é resistente a side effects de
    # bibliotecas que não estão importadas no sandbox.
    base_strategy = st.one_of(
        st.integers(min_value=-100, max_value=100),
        st.text(max_size=10),
        st.lists(st.integers(min_value=0, max_value=10), max_size=5),
        st.none(),
    )

    matching = 0
    one_raised = 0
    diff = 0
    samples_run = 0

    @settings(max_examples=n_samples, deadline=None, derandomize=True)
    @given(args=st.tuples(*([base_strategy] * arity)) if arity > 0 else st.just(()))
    def _runner(args):
        nonlocal matching, one_raised, diff, samples_run
        if samples_run >= n_samples:
            return
        samples_run += 1
        b_val, b_exc = _with_timeout(fn_b, args, timeout_seconds)
        a_val, a_exc = _with_timeout(fn_a, args, timeout_seconds)
        if b_exc is not None and a_exc is not None:
            # Ambas levantaram — considerar equivalente se o tipo bate
            if type(b_exc) is type(a_exc):
                matching += 1
            else:
                diff += 1
        elif b_exc is None and a_exc is None:
            if b_val == a_val:
                matching += 1
            else:
                diff += 1
        else:
            one_raised += 1

    try:
        _runner()
    except Exception as exc:
        return BehavioralCheckResult(
            equivalent=False, n_samples=samples_run, n_matching=matching,
            n_one_raised=one_raised, n_different_output=diff,
            error_msg=f"runner crashed: {type(exc).__name__}: {exc}",
        )

    return BehavioralCheckResult(
        equivalent=(samples_run > 0 and matching == samples_run),
        n_samples=samples_run,
        n_matching=matching,
        n_one_raised=one_raised,
        n_different_output=diff,
    )
