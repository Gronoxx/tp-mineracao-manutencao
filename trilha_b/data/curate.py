"""Curadoria de dados da Trilha B — do raw minerado ao `DatasetDict` HF.

Pipeline:
    raw `<smell>.jsonl` (minerador)  +  sidecar `<smell>.reviews.jsonl` (curador)
        -> aplica vereditos (clean / noisy-recortado; descarta rejected/não-revisado)
        -> valida contra `RefactoringPair`
        -> split por repositório -> `DatasetDict`

Uso (entrypoint):
    python -m trilha_b.data.curate --raw-dir data/raw --reviews-dir data/reviews \\
        --output-dir outputs/dataset
"""
import argparse
import csv
import json
import logging
import random
import sys
from collections import Counter
from pathlib import Path

from datasets import Dataset, DatasetDict

# `core/` é importável a partir da raiz do repo — garante a raiz em sys.path
# para que `python -m trilha_b.data.curate` funcione como entrypoint standalone.
_root = str(Path(__file__).resolve().parents[2])
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.schema import RefactoringPair  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Sidecar de vereditos do curador ──────────────────────────────────────────

def _load_jsonl(path: Path) -> list[dict]:
    """Registros de um arquivo JSONL (um objeto JSON por linha)."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_sidecar(reviews_dir: str | Path, stem: str) -> dict | None:
    """Vereditos do curador para `<stem>` — `<stem>.reviews.jsonl`, indexados
    por `id`. Retorna `None` se o sidecar não existir (vs `{}` = existe e vazio).
    """
    path = Path(reviews_dir) / f"{stem}.reviews.jsonl"
    if not path.exists():
        return None
    out: dict[str, dict] = {}
    for rec in _load_jsonl(path):
        if rec.get("id"):
            out[rec["id"]] = rec
    return out


def apply_verdicts(raw_records: list[dict], sidecar: dict) -> list[dict]:
    """Aplica os vereditos do curador aos pares crus.

    - `clean`    — mantém o par como está.
    - `noisy`    — mantém, mas reescreve before/after com o recorte
                   `before_clean`/`after_clean` (D4: o recorte humano é o
                   override; o detector não é re-rodado). Sem recorte utilizável
                   → descartado.
    - `rejected` — descartado.
    - sem veredito (não-revisado) — descartado.
    """
    kept: list[dict] = []
    for rec in raw_records:
        verdict = sidecar.get(rec.get("id")) if rec.get("id") else None
        if verdict is None:
            continue  # não-revisado
        status = verdict.get("status")
        if status == "clean":
            kept.append(rec)
        elif status == "noisy":
            bc, ac = verdict.get("before_clean"), verdict.get("after_clean")
            if not (bc and bc.strip() and ac and ac.strip()):
                logger.warning(
                    "Par noisy %s sem recorte before/after_clean — descartado",
                    rec.get("id"),
                )
                continue
            kept.append(dict(rec, before_code=bc, after_code=ac))
        # `rejected` (e qualquer status desconhecido) — descartado
    return kept


class DataCurator:
    def __init__(self):
        self._pairs: list[dict] = []

    def read_raw(self, path: str | Path) -> "DataCurator":
        """Lê um único arquivo de pares crus (`.json`, `.jsonl` ou `.csv`)."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Raw data file not found: {path}")
        suffix = path.suffix.lower()
        if suffix == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = raw if isinstance(raw, list) else [raw]
        elif suffix == ".jsonl":
            records = _load_jsonl(path)
        elif suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as fh:
                records = list(csv.DictReader(fh))
        else:
            raise ValueError(
                f"Unsupported file format: {path.suffix}. Use .json, .jsonl or .csv"
            )
        self._pairs = records
        logger.info("Loaded %d raw records from %s", len(self._pairs), path)
        return self

    def read_curated(self, raw_dir: str | Path, reviews_dir: str | Path,
                     allow_unreviewed: bool = False) -> "DataCurator":
        """Carrega todos os `<smell>.jsonl` de `raw_dir`, aplicando os vereditos
        do curador (sidecars de `reviews_dir`).

        Sem sidecar para um smell → erro (fail-fast): sem curadoria, todo par é
        não-revisado e seria descartado — falhar é mais seguro para um pipeline
        de treino do que produzir um dataset vazio silenciosamente.
        `allow_unreviewed=True` desativa a checagem e usa o raw sem curadoria.
        """
        raw_dir, reviews_dir = Path(raw_dir), Path(reviews_dir)
        raw_files = sorted(raw_dir.glob("*.jsonl"))
        if not raw_files:
            raise FileNotFoundError(f"Nenhum arquivo .jsonl em {raw_dir}")

        all_pairs: list[dict] = []
        for rf in raw_files:
            stem = rf.stem
            raw_records = _load_jsonl(rf)
            sidecar = load_sidecar(reviews_dir, stem)
            if sidecar is None:
                if not allow_unreviewed:
                    raise FileNotFoundError(
                        f"Sidecar de vereditos ausente para '{stem}' "
                        f"({reviews_dir}/{stem}.reviews.jsonl). Cure os pares no "
                        f"curador (filtro_smells), ou rode com --allow-unreviewed "
                        f"para usar o raw sem curadoria (NAO recomendado p/ treino)."
                    )
                logger.warning(
                    "Sem sidecar para %s — usando %d pares crus (--allow-unreviewed)",
                    stem, len(raw_records),
                )
                all_pairs.extend(raw_records)
            else:
                kept = apply_verdicts(raw_records, sidecar)
                logger.info("%s: %d crus -> %d apos curadoria",
                            stem, len(raw_records), len(kept))
                all_pairs.extend(kept)

        self._pairs = all_pairs
        logger.info("Total apos curadoria: %d pares de %d arquivo(s)",
                    len(all_pairs), len(raw_files))
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

    def save_hf_dataset(self, output_dir: str | Path, seed: int = 42) -> DatasetDict:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_data, val_data, test_data = self.split(seed=seed)

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


# ── Entrypoint ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Curadoria dos pares minerados -> DatasetDict HuggingFace."
    )
    ap.add_argument("--raw-dir", required=True,
                    help="Diretorio com os <smell>.jsonl do minerador")
    ap.add_argument("--reviews-dir", required=True,
                    help="Diretorio com os sidecars <smell>.reviews.jsonl do curador")
    ap.add_argument("--output-dir", required=True,
                    help="Destino do DatasetDict")
    ap.add_argument("--allow-unreviewed", action="store_true",
                    help="Usa pares sem sidecar de vereditos (NAO recomendado p/ treino)")
    ap.add_argument("--seed", type=int, default=42, help="Seed do split (default 42)")
    args = ap.parse_args(argv)

    curator = DataCurator()
    curator.read_curated(args.raw_dir, args.reviews_dir,
                         allow_unreviewed=args.allow_unreviewed)
    valid, invalid = curator.validate_all()
    if not valid:
        raise SystemExit("Nenhum par valido apos curadoria/validacao — nada a salvar.")
    curator.save_hf_dataset(args.output_dir, seed=args.seed)


if __name__ == "__main__":
    main()
