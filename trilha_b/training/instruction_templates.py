"""Templates de instrução por smell para o fine-tuning dos LoRAs (R1–R5).

D-DEV-04: o prompt de treino usa o **chat template oficial do tokenizer**
(`tokenizer.apply_chat_template`) em vez de um template proprietário. O modelo
já viu esse formato no pretraining → converge melhor, e o baseline B0
(zero-shot) fica comparável.

D-DEV-05: as regras em `_TEMPLATES` impõem estilo (ALL_CAPS, dataclass
`__post_init__`, guard clauses left-aligned). Se os pares minerados reais não
seguirem essas regras, a instrução contradiz o label. Antes do treino, auditar
uma amostra dos pares minerados contra estas regras (ver plano, decisão nº 6).
"""
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.smells import SmellType  # noqa: E402,F401

_TEMPLATES: dict[str, dict[str, str]] = {
    "R1": {
        "smell_description": (
            "refactor a Long Method by applying the Extract Method pattern"
        ),
        "refactoring_rule": (
            "Identify cohesive groups of statements within the function and extract each group "
            "into a well-named helper function. The original function must become a thin "
            "orchestrator that calls the extracted helpers. Do not change observable behaviour."
        ),
    },
    "R2": {
        "smell_description": (
            "refactor a Long Parameter List by introducing a Parameter Object"
        ),
        "refactoring_rule": (
            "Group logically related parameters into a dataclass (or named tuple). "
            "Replace the long parameter list in the original function signature with a single "
            "object of the new type. Validation that was inline in the function body should move "
            "into the dataclass __post_init__. Do not change observable behaviour."
        ),
    },
    "R3": {
        "smell_description": (
            "refactor Magic Numbers and Magic Strings by replacing them with Named Constants"
        ),
        "refactoring_rule": (
            "Every literal number or string that encodes domain knowledge must be extracted to a "
            "module-level constant with a descriptive ALL_CAPS name. The constant name must convey "
            "the business meaning, not just the value (e.g. MAX_RETRY_COUNT = 3, not THREE = 3). "
            "Do not change observable behaviour."
        ),
    },
    "R4": {
        "smell_description": (
            "refactor Deeply Nested Conditionals by introducing Guard Clauses"
        ),
        "refactoring_rule": (
            "Invert each nesting level into an early return (guard clause) that handles the "
            "error or edge case immediately. The main success path must be left-aligned with no "
            "deep nesting. Each guard clause must return or raise before the next clause. "
            "Do not change observable behaviour."
        ),
    },
    "R5": {
        "smell_description": (
            "refactor Dead Code inside a function by removing unreachable statements"
        ),
        "refactoring_rule": (
            "Remove all statements that can never be executed: code after an unconditional "
            "return/raise, variables assigned but never read, branches whose condition is always "
            "false, and commented-out code blocks. Do not remove intentional no-ops or logging. "
            "Do not change observable behaviour."
        ),
    },
}

_SYSTEM = (
    "You are a Python refactoring assistant. Your task is to {smell_description}.\n"
    "Apply the refactoring strictly: {refactoring_rule}\n"
    "Return ONLY the refactored code, no explanations."
)


def build_messages(
    smell_type: SmellType,
    before_code: str,
    after_code: str | None = None,
) -> list[dict]:
    """Lista de mensagens `[system, user, (assistant)]` para o chat template.

    `after_code=None` → mensagens só até o turno do usuário (uso em inferência).
    """
    if smell_type not in _TEMPLATES:
        raise ValueError(f"Unknown smell type: {smell_type}. Must be one of {list(_TEMPLATES)}")
    ctx = _TEMPLATES[smell_type]
    messages = [
        {"role": "system", "content": _SYSTEM.format(**ctx)},
        {"role": "user", "content": before_code},
    ]
    if after_code is not None:
        messages.append({"role": "assistant", "content": after_code})
    return messages


def build_training_text(
    smell_type: SmellType,
    before_code: str,
    after_code: str,
    tokenizer,
) -> str:
    """Texto de treino (conversa completa) via o chat template oficial do modelo."""
    return tokenizer.apply_chat_template(
        build_messages(smell_type, before_code, after_code),
        tokenize=False,
    )


def build_inference_text(
    smell_type: SmellType,
    before_code: str,
    tokenizer,
) -> str:
    """Prompt para inferência — termina no início do turno do assistente."""
    return tokenizer.apply_chat_template(
        build_messages(smell_type, before_code),
        tokenize=False,
        add_generation_prompt=True,
    )
