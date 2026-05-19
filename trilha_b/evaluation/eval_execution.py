"""Avaliação execution-based dos LoRAs de refatoração.

Roda a suíte de testes do projeto-alvo antes e depois de aplicar a refatoração
e compara o pass rate.

D-DEV-11: a contagem de testes vem do JUnit XML (`--junit-xml`, embutido no
pytest — sem plugin) em vez do parsing por regex, frágil. O regex fica só como
fallback.

D-DEV-10: a corrida "depois" mede a **cobertura do arquivo/função refatorada**
(`--cov`, pytest-cov). Se os testes não exercitam o código refatorado, o
`pass_rate` inalterado não significa "refatoração segura" — significa que o
teste não viu a mudança. O resultado é sinalizado nesse caso.
"""
import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import pytest_cov  # noqa: F401
    _HAS_PYTEST_COV = True
except ImportError:
    _HAS_PYTEST_COV = False


@dataclass
class EvaluationResult:
    tests_before: int
    tests_after: int
    passed_before: int
    passed_after: int
    pass_rate_before: float
    pass_rate_after: float
    pass_rate_delta: float
    error_before: Optional[str]
    error_after: Optional[str]
    # D-DEV-10 — cobertura do código refatorado pelos testes
    refactored_exercised: Optional[bool] = None   # None = não foi possível medir
    refactored_coverage: Optional[float] = None   # fração das linhas alvo cobertas

    def summary(self) -> str:
        base = (
            f"Before: {self.passed_before}/{self.tests_before} passed "
            f"({self.pass_rate_before:.1%})  |  "
            f"After: {self.passed_after}/{self.tests_after} passed "
            f"({self.pass_rate_after:.1%})  |  "
            f"Delta: {self.pass_rate_delta:+.1%}"
        )
        if self.refactored_exercised is False:
            base += ("  |  ATENCAO: codigo refatorado NAO exercitado pelos "
                     "testes — o delta de pass rate nao e confiavel")
        elif self.refactored_exercised is True:
            base += f"  |  cobertura do refatorado: {self.refactored_coverage:.0%}"
        return base


# ---------------------------------------------------------------- parsing ----
def _parse_junit_xml(xml_path: Path) -> Optional[tuple[int, int]]:
    """(total, passed) a partir do JUnit XML do pytest. None se ausente/inválido.
    `total` exclui skipped/xfailed; `passed` = total − failures − errors."""
    if not xml_path.exists() or xml_path.stat().st_size == 0:
        return None
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return None
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    total = passed = 0
    for s in suites:
        tests = int(s.get("tests", 0) or 0)
        failures = int(s.get("failures", 0) or 0)
        errors = int(s.get("errors", 0) or 0)
        skipped = int(s.get("skipped", 0) or 0)
        counted = tests - skipped
        total += counted
        passed += counted - failures - errors
    return total, passed


def _parse_pytest_output(output: str) -> tuple[int, int]:
    """Fallback por regex — usado só se o JUnit XML não for produzido."""
    pattern = re.search(r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error)?", output)
    if pattern:
        passed = int(pattern.group(1))
        failed = int(pattern.group(2) or 0)
        errors = int(pattern.group(3) or 0)
        return passed + failed + errors, passed
    short = re.search(r"(\d+) failed", output)
    if short:
        failed = int(short.group(1))
        pp = re.search(r"(\d+) passed", output)
        passed = int(pp.group(1)) if pp else 0
        return passed + failed, passed
    return 0, 0


def _coverage_of_target(
    cov_json: Path,
    target_file: Path,
    project_dir: Path,
    lineno: Optional[int] = None,
    end_lineno: Optional[int] = None,
) -> Optional[tuple[bool, float]]:
    """(exercitado, fração coberta) do arquivo/função alvo. None se não medível."""
    if not cov_json.exists():
        return None
    try:
        data = json.loads(cov_json.read_text(encoding="utf-8"))
    except Exception:
        return None
    target = target_file.resolve()
    entry = None
    for key, val in data.get("files", {}).items():
        kp = Path(key)
        if target in (kp.resolve(), (project_dir / kp).resolve()) or kp.name == target.name:
            entry = val
            break
    if entry is None:
        return None
    executed = set(entry.get("executed_lines", []))
    missing = set(entry.get("missing_lines", []))
    if lineno is not None and end_lineno is not None:
        # Corpo da função: exclui a linha do `def` — ela sempre executa no
        # import, então incluí-la faria qualquer função parecer "exercitada".
        rng = set(range(lineno + 1, end_lineno + 1))
        executed, missing = executed & rng, missing & rng
    denom = len(executed) + len(missing)
    return len(executed) > 0, (len(executed) / denom if denom else 0.0)


# --------------------------------------------------------------- execução ----
def _clear_pycache(directory: Path) -> None:
    """Remove `__pycache__`/`*.pyc` sob `directory`.

    Sem isso, o teste "depois" pode rodar o bytecode obsoleto do módulo: trocar
    o arquivo não invalida o `.pyc` se o novo `mtime` não for maior que o
    registrado no `.pyc` — e o pass rate "depois" mediria o código antigo."""
    for cache in directory.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    for pyc in directory.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)


def _run_pytest(
    test_cmd: str,
    project_dir: Path,
    timeout: int,
    cov_target: Optional[Path] = None,
    work_dir: Optional[Path] = None,
) -> tuple[int, int, Optional[str], Optional[Path]]:
    """Roda os testes; devolve (total, passed, erro, caminho do cov.json|None).

    Anexa `--junit-xml` (D-DEV-11) e, se `cov_target` (um diretório) e
    pytest-cov disponível, `--cov`/`--cov-report=json` (D-DEV-10). O `--cov`
    precisa de um diretório/pacote — coverage.py não rastreia um arquivo solto."""
    junit = work_dir / "junit.xml"
    cov_json: Optional[Path] = None
    extra = f' --junit-xml="{junit}"'
    if cov_target is not None and _HAS_PYTEST_COV:
        cov_json = work_dir / "coverage.json"
        extra += f' --cov="{cov_target}" --cov-report=json:"{cov_json}"'
    try:
        result = subprocess.run(
            test_cmd + extra, shell=True, cwd=str(project_dir),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 0, 0, f"Test command timed out after {timeout}s", None
    except Exception as exc:  # noqa: BLE001
        return 0, 0, str(exc), None

    parsed = _parse_junit_xml(junit)
    if parsed is None:
        total, passed = _parse_pytest_output(result.stdout + result.stderr)
    else:
        total, passed = parsed
    return total, passed, None, (cov_json if cov_json and cov_json.exists() else None)


class ExecutionEvaluator:
    def __init__(self, timeout_seconds: int = 120):
        self.timeout_seconds = timeout_seconds

    def evaluate(
        self,
        original_file: str | Path,
        refactored_file: str | Path,
        test_cmd: str,
        project_dir: str | Path,
        refactored_lineno: Optional[int] = None,
        refactored_end_lineno: Optional[int] = None,
    ) -> EvaluationResult:
        # Resolvidos para absoluto: os testes rodam com cwd=project_dir, então
        # um caminho relativo em `--cov` apontaria para o lugar errado.
        original_file = Path(original_file).resolve()
        refactored_file = Path(refactored_file).resolve()
        project_dir = Path(project_dir).resolve()

        if not original_file.exists():
            raise FileNotFoundError(f"Original file not found: {original_file}")
        if not refactored_file.exists():
            raise FileNotFoundError(f"Refactored file not found: {refactored_file}")
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        work = Path(tempfile.mkdtemp(prefix="eval_exec_"))
        try:
            _clear_pycache(project_dir)
            total_before, passed_before, err_before, _ = _run_pytest(
                test_cmd, project_dir, self.timeout_seconds, work_dir=work
            )

            backup = original_file.with_suffix(original_file.suffix + ".bak")
            # copyfile (não copy2): não copia o mtime do arquivo refatorado —
            # combinado com _clear_pycache, garante que o teste "depois" rode o
            # código novo, não um .pyc obsoleto.
            shutil.copyfile(original_file, backup)
            try:
                shutil.copyfile(refactored_file, original_file)
                _clear_pycache(project_dir)
                total_after, passed_after, err_after, cov_json = _run_pytest(
                    test_cmd, project_dir, self.timeout_seconds,
                    cov_target=original_file.parent, work_dir=work,
                )
            finally:
                shutil.copyfile(backup, original_file)
                backup.unlink(missing_ok=True)
                _clear_pycache(project_dir)

            exercised, coverage = None, None
            if cov_json is not None:
                cov = _coverage_of_target(
                    cov_json, original_file, project_dir,
                    refactored_lineno, refactored_end_lineno,
                )
                if cov is not None:
                    exercised, coverage = cov
        finally:
            shutil.rmtree(work, ignore_errors=True)

        rate_before = passed_before / total_before if total_before > 0 else 0.0
        rate_after = passed_after / total_after if total_after > 0 else 0.0

        return EvaluationResult(
            tests_before=total_before,
            tests_after=total_after,
            passed_before=passed_before,
            passed_after=passed_after,
            pass_rate_before=rate_before,
            pass_rate_after=rate_after,
            pass_rate_delta=rate_after - rate_before,
            error_before=err_before,
            error_after=err_after,
            refactored_exercised=exercised,
            refactored_coverage=coverage,
        )

    def evaluate_batch(
        self,
        pairs: list[dict],
        test_cmd: str,
        project_dir: str | Path,
    ) -> list[EvaluationResult]:
        results = []
        for pair in pairs:
            results.append(self.evaluate(
                original_file=pair["original_file"],
                refactored_file=pair["refactored_file"],
                test_cmd=test_cmd,
                project_dir=project_dir,
                refactored_lineno=pair.get("refactored_lineno"),
                refactored_end_lineno=pair.get("refactored_end_lineno"),
            ))
        return results
