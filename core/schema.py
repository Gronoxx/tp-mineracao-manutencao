"""Schema unificado do par de refatoração — o contrato A↔B (D-DEV-18).

`RefactoringPair` é o registro que o minerador (Trilha A) produz, o curador
(`filtro_smells.py`) revisa e a Trilha B consome. Substitui o antigo
`trilha_b/data/schema.py`, que passa a re-exportar daqui.

Os campos preenchidos pelo minerador e pelo curador são opcionais com default
— assim fixtures antigas (`trilha_b/data/sample_pairs/*.json`), que só têm o
núcleo do par, continuam válidas.
"""
import ast
import hashlib
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .smells import SmellType  # noqa: F401  (re-exportado para compatibilidade)

ReviewStatus = Literal["clean", "noisy", "rejected"]
Confianca = Literal["alta", "media", "baixa"]


class ReviewBlock(BaseModel):
    """Veredito da validação humana — estágio 4, preenchido pelo curador."""
    status: Optional[ReviewStatus] = None
    before_clean: Optional[str] = None   # par isolado, se o revisor recortou ruído
    after_clean: Optional[str] = None
    out_of_rule: bool = False            # D-DEV-05: par não segue a regra esperada
    reviewer: Optional[str] = None
    timestamp: Optional[str] = None
    notes: str = ""
    justificativa: Optional[str] = None  # obrigatória p/ `rejected`/`noisy` (no curador)
    confianca: Optional[Confianca] = None  # D3: confiança do revisor (opcional)


class RefactoringPair(BaseModel):
    """Um par (antes, depois) de refatoração de um dos 5 smells com LoRA."""

    # --- núcleo do par (obrigatório) ---
    before_code: str
    after_code: str
    smell_type: SmellType

    # --- proveniência ---
    repo: str
    commit_hash: str
    parent_commit: Optional[str] = None
    file: Optional[str] = None
    function_name: Optional[str] = None
    commit_msg: Optional[str] = None
    msg_keywords: list[str] = Field(default_factory=list)

    # --- preenchido pelo minerador (estágios 2–3) ---
    id: Optional[str] = None
    metrics_before: dict = Field(default_factory=dict)
    metrics_after: dict = Field(default_factory=dict)
    detector_before: Optional[dict] = None
    detector_after: Optional[dict] = None
    verified: bool = False
    # E1 — verificação permissiva: `True` quando o detector ainda dispara no
    # `after` mas com magnitude reduzida (refactor parcial). Default `False`
    # preserva o comportamento estrito (only-strict pairs nas execuções antigas).
    partial: bool = False
    n_functions_after: Optional[int] = None
    
    # --- avaliacao do smell (-1: negativo, 0: nao avaliado. 1: positivo)
    threshold = "NA"
    avaliacao: int = 0

    # --- proveniência do registro (D5 — sprint de mineração) ---
    # Separa pares minerados do nosso pipeline (train) de oracles externos
    # (held-out test) e variantes (PR-collapsed, adjacent, Java→Python).
    source: Optional[Literal[
        "mined_commit",     # nosso pipeline em commit individual (default)
        "mined_pr",         # nosso pipeline em PR colapsado (C2)
        "adjacent_oracle",  # nosso pipeline em commit citado por oracle (C3)
        "translated_java",  # tradução de SWE-Refactor/MaRV (C4)
        "cross_file",       # pareamento cross-file via AST similarity (C5c.2)
        "rule_id_mined",    # commit que corrige regra de linter por rule-ID (R2/R3/R4)
    ]] = "mined_commit"

    # --- preenchido pelo curador (estágio 4) ---
    review: Optional[ReviewBlock] = None

    @field_validator("before_code", "after_code")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("code field must not be empty")
        return v

    @model_validator(mode="after")
    def _fill_id(self) -> "RefactoringPair":
        """`id` estável (hash) se não vier preenchido — chave de dedup/curadoria."""
        if not self.id:
            # `smell_type` entra no hash (F4): o mesmo trecho before/after pode
            # ser verificado para 2 smells distintos — sem isso os dois pares
            # colidiriam no `id` e um sobrescreveria o outro na dedup.
            base = "|".join([
                self.repo, self.commit_hash, self.file or "",
                self.function_name or "", str(self.smell_type),
                self.before_code, self.after_code,
            ])
            self.id = hashlib.sha1(base.encode("utf-8", "replace")).hexdigest()[:16]
        return self

    def validate_python(self) -> tuple[bool, list[str]]:
        """Confere que `before_code` e `after_code` são Python parseável."""
        errors: list[str] = []
        for label, code in [("before_code", self.before_code),
                             ("after_code", self.after_code)]:
            try:
                ast.parse(code)
            except SyntaxError as exc:
                errors.append(f"{label}: SyntaxError at line {exc.lineno}: {exc.msg}")
        return len(errors) == 0, errors
