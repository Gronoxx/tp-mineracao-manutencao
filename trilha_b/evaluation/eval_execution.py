import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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

    def summary(self) -> str:
        return (
            f"Before: {self.passed_before}/{self.tests_before} passed "
            f"({self.pass_rate_before:.1%})  |  "
            f"After: {self.passed_after}/{self.tests_after} passed "
            f"({self.pass_rate_after:.1%})  |  "
            f"Delta: {self.pass_rate_delta:+.1%}"
        )


def _parse_pytest_output(output: str) -> tuple[int, int]:
    pattern = re.search(
        r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error)?",
        output,
    )
    if pattern:
        passed = int(pattern.group(1))
        failed = int(pattern.group(2) or 0)
        errors = int(pattern.group(3) or 0)
        total = passed + failed + errors
        return total, passed

    short_pattern = re.search(r"(\d+) failed", output)
    if short_pattern:
        failed = int(short_pattern.group(1))
        passed_pattern = re.search(r"(\d+) passed", output)
        passed = int(passed_pattern.group(1)) if passed_pattern else 0
        return passed + failed, passed

    if "no tests ran" in output.lower() or "collected 0 items" in output.lower():
        return 0, 0

    return 0, 0


def _run_tests(
    test_cmd: str,
    project_dir: Path,
    timeout: int = 120,
) -> tuple[int, int, Optional[str]]:
    try:
        result = subprocess.run(
            test_cmd,
            shell=True,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        combined_output = result.stdout + result.stderr
        total, passed = _parse_pytest_output(combined_output)
        return total, passed, None
    except subprocess.TimeoutExpired:
        return 0, 0, f"Test command timed out after {timeout}s"
    except Exception as exc:
        return 0, 0, str(exc)


class ExecutionEvaluator:
    def __init__(self, timeout_seconds: int = 120):
        self.timeout_seconds = timeout_seconds

    def evaluate(
        self,
        original_file: str | Path,
        refactored_file: str | Path,
        test_cmd: str,
        project_dir: str | Path,
    ) -> EvaluationResult:
        original_file = Path(original_file)
        refactored_file = Path(refactored_file)
        project_dir = Path(project_dir)

        if not original_file.exists():
            raise FileNotFoundError(f"Original file not found: {original_file}")
        if not refactored_file.exists():
            raise FileNotFoundError(f"Refactored file not found: {refactored_file}")
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        total_before, passed_before, err_before = _run_tests(
            test_cmd, project_dir, self.timeout_seconds
        )

        backup_path = original_file.with_suffix(original_file.suffix + ".bak")
        shutil.copy2(original_file, backup_path)
        try:
            shutil.copy2(refactored_file, original_file)
            total_after, passed_after, err_after = _run_tests(
                test_cmd, project_dir, self.timeout_seconds
            )
        finally:
            shutil.copy2(backup_path, original_file)
            backup_path.unlink(missing_ok=True)

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
        )

    def evaluate_batch(
        self,
        pairs: list[dict],
        test_cmd: str,
        project_dir: str | Path,
    ) -> list[EvaluationResult]:
        results = []
        for pair in pairs:
            result = self.evaluate(
                original_file=pair["original_file"],
                refactored_file=pair["refactored_file"],
                test_cmd=test_cmd,
                project_dir=project_dir,
            )
            results.append(result)
        return results
