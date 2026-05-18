import json
import logging
import csv
import random
from collections import Counter
from pathlib import Path

from datasets import Dataset, DatasetDict

from schema import RefactoringPair

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class DataCurator:
    def __init__(self):
        self._pairs: list[dict] = []

    def read_raw(self, path: str | Path) -> "DataCurator":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Raw data file not found: {path}")
        if path.suffix.lower() == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = raw if isinstance(raw, list) else [raw]
        elif path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8") as fh:
                records = list(csv.DictReader(fh))
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}. Use .json or .csv")
        self._pairs = records
        logger.info("Loaded %d raw records from %s", len(self._pairs), path)
        return self

    def validate_all(self) -> tuple[list[dict], list[dict]]:
        valid: list[dict] = []
        invalid: list[dict] = []
        for i, record in enumerate(self._pairs):
            try:
                pair = RefactoringPair(**record)
                ok, errors = pair.validate_python()
                if ok:
                    valid.append(pair.model_dump())
                else:
                    for err in errors:
                        logger.warning("Record %d validation error: %s", i, err)
                    invalid.append({"record_index": i, "record": record, "errors": errors})
            except Exception as exc:
                logger.warning("Record %d schema error: %s", i, exc)
                invalid.append({"record_index": i, "record": record, "errors": [str(exc)]})
        logger.info(
            "Validation complete: %d valid, %d invalid (%.1f%% pass rate)",
            len(valid),
            len(invalid),
            100 * len(valid) / max(len(valid) + len(invalid), 1),
        )
        self._pairs = valid
        return valid, invalid

    def split(
        self,
        train: float = 0.8,
        val: float = 0.1,
        test: float = 0.1,
        seed: int = 42,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Split train/val/test **agrupado por repositório** (D-DEV-08).

        Funções do mesmo repo nunca caem em splits diferentes — sem isso há
        vazamento e o F1 reportado infla ~20–30pp (CATALOGO §4: within-project
        0.85 → cross-project ~0.55–0.65).
        """
        if abs(train + val + test - 1.0) > 1e-6:
            raise ValueError("train + val + test must sum to 1.0")
        if len(self._pairs) < 5:
            raise ValueError("Need at least 5 validated records to split")

        # D-DEV-09: mínimo por classe — evita split degenerado (0 amostras de
        # algum smell em val/test).
        counts = Counter(p["smell_type"] for p in self._pairs)
        scarce = {s: n for s, n in counts.items() if n < 3}
        if scarce:
            raise ValueError(f"Each smell_type needs >= 3 records to split; scarce: {scarce}")

        # Particiona os REPOSITÓRIOS (não os registros): cada repo inteiro vai
        # para um único split. Garante ausência de vazamento por construção e é
        # robusto para qualquer contagem de repos >= 3.
        groups = [p.get("repo") or f"__norepo_{i}" for i, p in enumerate(self._pairs)]
        repos = sorted(set(groups))
        if len(repos) < 3:
            raise ValueError(
                f"Need >= 3 distinct repos for a leakage-free split; got {len(repos)}"
            )
        random.Random(seed).shuffle(repos)
        n = len(repos)
        n_test = max(1, round(test * n))
        n_val = max(1, round(val * n))
        if n_test + n_val >= n:
            raise ValueError(
                f"Too few repos ({n}) for a {train:.0%}/{val:.0%}/{test:.0%} split"
            )
        test_repos = set(repos[:n_test])
        val_repos = set(repos[n_test:n_test + n_val])
        train_repos = set(repos[n_test + n_val:])

        def _take(repo_set: set) -> list[dict]:
            return [p for p, g in zip(self._pairs, groups) if g in repo_set]

        train_data, val_data, test_data = _take(train_repos), _take(val_repos), _take(test_repos)

        logger.info(
            "Split por repo: train=%d  val=%d  test=%d  (repos: %d/%d/%d)",
            len(train_data), len(val_data), len(test_data),
            len(train_repos), len(val_repos), len(test_repos),
        )
        return train_data, val_data, test_data

    def save_hf_dataset(self, output_dir: str | Path) -> DatasetDict:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_data, val_data, test_data = self.split()

        dataset_dict = DatasetDict(
            {
                "train": Dataset.from_list(train_data),
                "validation": Dataset.from_list(val_data),
                "test": Dataset.from_list(test_data),
            }
        )
        dataset_dict.save_to_disk(str(output_dir))
        logger.info("HuggingFace DatasetDict saved to %s", output_dir)
        return dataset_dict
