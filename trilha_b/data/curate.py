import json
import logging
import csv
from pathlib import Path
from typing import Optional

from datasets import Dataset, DatasetDict
from sklearn.model_selection import StratifiedShuffleSplit

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
        if abs(train + val + test - 1.0) > 1e-6:
            raise ValueError("train + val + test must sum to 1.0")
        if len(self._pairs) < 5:
            raise ValueError("Need at least 5 validated records to split")

        labels = [p["smell_type"] for p in self._pairs]
        indices = list(range(len(self._pairs)))

        splitter = StratifiedShuffleSplit(n_splits=1, test_size=(val + test), random_state=seed)
        train_idx, temp_idx = next(splitter.split(indices, labels))

        temp_labels = [labels[i] for i in temp_idx]
        relative_test = test / (val + test)
        splitter2 = StratifiedShuffleSplit(n_splits=1, test_size=relative_test, random_state=seed)
        val_rel_idx, test_rel_idx = next(splitter2.split(temp_idx, temp_labels))

        val_idx = [temp_idx[i] for i in val_rel_idx]
        test_idx = [temp_idx[i] for i in test_rel_idx]

        train_data = [self._pairs[i] for i in train_idx]
        val_data = [self._pairs[i] for i in val_idx]
        test_data = [self._pairs[i] for i in test_idx]

        logger.info(
            "Split: train=%d  val=%d  test=%d",
            len(train_data),
            len(val_data),
            len(test_data),
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
