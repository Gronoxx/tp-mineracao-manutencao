import ast
from typing import Literal, Optional
from pydantic import BaseModel, field_validator, model_validator


SmellType = Literal["R1", "R2", "R3", "R4", "R5"]


class RefactoringPair(BaseModel):
    before_code: str
    after_code: str
    smell_type: SmellType
    repo: str
    commit_hash: str
    function_name: Optional[str] = None

    @field_validator("before_code", "after_code")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("code field must not be empty")
        return v

    def validate_python(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for label, code in [("before_code", self.before_code), ("after_code", self.after_code)]:
            try:
                ast.parse(code)
            except SyntaxError as exc:
                errors.append(f"{label}: SyntaxError at line {exc.lineno}: {exc.msg}")
        return len(errors) == 0, errors
