from typing import Literal

SmellType = Literal["R1", "R2", "R3", "R4", "R5"]

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

_PROMPT_TEMPLATE = """\
<|system|>
You are a Python refactoring assistant. Your task is to {smell_description}.
Apply the refactoring strictly: {refactoring_rule}
Return ONLY the refactored code, no explanations.
<|user|>
{before_code}
<|assistant|>
{after_code}"""


def build_prompt(
    smell_type: SmellType,
    before_code: str,
    after_code: str = "",
) -> str:
    if smell_type not in _TEMPLATES:
        raise ValueError(f"Unknown smell type: {smell_type}. Must be one of {list(_TEMPLATES)}")
    ctx = _TEMPLATES[smell_type]
    return _PROMPT_TEMPLATE.format(
        smell_description=ctx["smell_description"],
        refactoring_rule=ctx["refactoring_rule"],
        before_code=before_code,
        after_code=after_code,
    )


def build_inference_prompt(smell_type: SmellType, before_code: str) -> str:
    """Returns the prompt up to (but not including) the assistant turn, for inference."""
    return build_prompt(smell_type, before_code, after_code="").rstrip()
