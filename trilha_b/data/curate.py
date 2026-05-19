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


def _aplicar_veredito_final(rec: dict, verdict: dict) -> dict | None:
    """Aplica um veredito único a um par cru.

    - `clean`    — mantém o par como está.
    - `noisy`    — mantém, reescrevendo before/after com o recorte
                   `before_clean`/`after_clean` (D4: o recorte humano é o
                   override; o detector não re-roda). Sem recorte → descartado.
    - `rejected` / status desconhecido — descartado (`None`).
    """
    status = verdict.get("status")
    if status == "clean":
        return rec
    if status == "noisy":
        bc, ac = verdict.get("before_clean"), verdict.get("after_clean")
        if not (bc and bc.strip() and ac and ac.strip()):
            logger.warning("Par noisy %s sem recorte before/after_clean — descartado",
                            rec.get("id"))
            return None
        return dict(rec, before_code=bc, after_code=ac)
    return None


def apply_verdicts(raw_records: list[dict], sidecar: dict) -> list[dict]:
    """Aplica os vereditos do curador (revisor único) aos pares crus.

    `sidecar` indexado por `id`. Pares sem veredito são descartados."""
    kept: list[dict] = []
    for rec in raw_records:
        verdict = sidecar.get(rec.get("id")) if rec.get("id") else None
        if verdict is None:
            continue  # não-revisado
        out = _aplicar_veredito_final(rec, verdict)
        if out is not None:
            kept.append(out)
    return kept


# ── Revisão dupla (D1) ───────────────────────────────────────────────────────

def load_assignment(path: str | Path) -> dict | None:
    """`assignment.json` (de `gerar_blocos.py`), ou `None` se ausente."""
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_sidecar_keyed(reviews_dir: str | Path, stem: str) -> dict | None:
    """Sidecar `<stem>.reviews.jsonl` indexado por `(id, revisor)` — para a
    revisão dupla, em que o mesmo par tem um veredito por revisor. `None` se
    ausente. Registros legados sem `reviewer` viram chave `(id, None)`."""
    path = Path(reviews_dir) / f"{stem}.reviews.jsonl"
    if not path.exists():
        return None
    out: dict = {}
    for rec in _load_jsonl(path):
        if rec.get("id"):
            out[(rec["id"], rec.get("reviewer"))] = rec
    return out


def merge_double_review(raw_records: list[dict], sidecar_keyed: dict,
                        id_to_block: dict) -> list[dict]:
    """Mescla os 2 vereditos por par (D1).

    consenso `clean` → mantém; consenso `rejected` → descarta; divergência
    (qualquer outra combinação, inclui `noisy`) → usa o veredito do adjudicador
    se houver, senão o par fica pendente de adjudicação e é descartado do treino.
    Pares ainda não revisados pelos 2 primários são ignorados (incompletos)."""
    kept: list[dict] = []
    for rec in raw_records:
        pid = rec.get("id")
        bloco = id_to_block.get(pid)
        if bloco is None:
            continue  # par não atribuído a nenhum bloco
        r1, r2 = bloco["revisores"]
        v1 = sidecar_keyed.get((pid, r1))
        v2 = sidecar_keyed.get((pid, r2))
        if v1 is None or v2 is None:
            continue  # revisão incompleta
        s1, s2 = v1.get("status"), v2.get("status")
        if s1 == s2 == "clean":
            kept.append(rec)
            continue
        if s1 == s2 == "rejected":
            continue
        # divergência → adjudicador
        adj_v = sidecar_keyed.get((pid, bloco["adjudicator"]))
        if adj_v is None:
            logger.warning("Par %s divergente e sem adjudicacao — descartado", pid)
            continue
        out = _aplicar_veredito_final(rec, adj_v)
        if out is not None:
            kept.append(out)
    return kept


def cohen_kappa_por_bloco(sidecar_por_stem: dict, assignment: dict) -> dict:
    """Cohen's kappa entre os 2 revisores primários, por bloco.

    `sidecar_por_stem`: `{stem: {(id,revisor): rec}}`. Calculado só sobre os
    pares que ambos os primários revisaram. Retorna `{bloco_id: kappa|None}`;
    `None` quando indefinido (<2 pares revisados por ambos, ou rótulos todos
    iguais — kappa não é definido nesses casos)."""
    from sklearn.metrics import cohen_kappa_score

    out: dict = {}
    for bloco in assignment["blocos"]:
        r1, r2 = bloco["revisores"]
        labels1: list[str] = []
        labels2: list[str] = []
        for par in bloco["pares"]:
            sc = sidecar_por_stem.get(par["smell"], {})
            v1, v2 = sc.get((par["id"], r1)), sc.get((par["id"], r2))
            if v1 and v2 and v1.get("status") and v2.get("status"):
                labels1.append(v1["status"])
                labels2.append(v2["status"])
        if len(labels1) < 2 or len(set(labels1 + labels2)) < 2:
            out[bloco["id"]] = None
        else:
            out[bloco["id"]] = float(cohen_kappa_score(labels1, labels2))
    return out


class DataCurator:
    def __init__(self):
        self._pairs: list[dict] = []
        self.kappa: dict | None = None  # Cohen's kappa por bloco (revisão dupla)

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
                     allow_unreviewed: bool = False, use_assignment: bool = True,
                     assignment_path: str | Path | None = None) -> "DataCurator":
        """Carrega todos os `<smell>.jsonl` de `raw_dir`, aplicando os vereditos
        do curador (sidecars de `reviews_dir`).

        Se houver `assignment.json` (revisão dupla), mescla os 2 vereditos por
        par (D1) e calcula o Cohen's kappa por bloco. Sem `assignment.json`,
        degrada para o modo de revisor único — um veredito por par.

        Sem sidecar para um smell → erro (fail-fast): sem curadoria, todo par é
        não-revisado e seria descartado — falhar é mais seguro para um pipeline
        de treino do que produzir um dataset vazio silenciosamente.
        `allow_unreviewed=True` desativa a checagem e usa o raw sem curadoria.
        `use_assignment=False` ignora o `assignment.json` (força revisor único).
        """
        raw_dir, reviews_dir = Path(raw_dir), Path(reviews_dir)
        raw_files = sorted(raw_dir.glob("*.jsonl"))
        if not raw_files:
            raise FileNotFoundError(f"Nenhum arquivo .jsonl em {raw_dir}")

        if assignment_path is None:
            assignment_path = reviews_dir / "assignment.json"
        assignment = load_assignment(assignment_path) if use_assignment else None

        if assignment is not None:
            self._read_double(raw_files, reviews_dir, assignment, allow_unreviewed)
        else:
            self._read_single(raw_files, reviews_dir, allow_unreviewed)
        return self

    @staticmethod
    def _missing_sidecar_error(stem: str, reviews_dir: Path) -> FileNotFoundError:
        return FileNotFoundError(
            f"Sidecar de vereditos ausente para '{stem}' "
            f"({reviews_dir}/{stem}.reviews.jsonl). Cure os pares no curador "
            f"(filtro_smells), ou rode com --allow-unreviewed para usar o raw "
            f"sem curadoria (NAO recomendado p/ treino)."
        )

    def _read_single(self, raw_files: list[Path], reviews_dir: Path,
                     allow_unreviewed: bool) -> None:
        """Modo de revisor único — um veredito por par (chave `id`)."""
        all_pairs: list[dict] = []
        for rf in raw_files:
            stem = rf.stem
            raw_records = _load_jsonl(rf)
            sidecar = load_sidecar(reviews_dir, stem)
            if sidecar is None:
                if not allow_unreviewed:
                    raise self._missing_sidecar_error(stem, reviews_dir)
                logger.warning("Sem sidecar para %s — usando %d pares crus (--allow-unreviewed)",
                                stem, len(raw_records))
                all_pairs.extend(raw_records)
            else:
                kept = apply_verdicts(raw_records, sidecar)
                logger.info("%s: %d crus -> %d apos curadoria",
                            stem, len(raw_records), len(kept))
                all_pairs.extend(kept)
        self._pairs = all_pairs
        logger.info("Total apos curadoria (revisor unico): %d pares de %d arquivo(s)",
                    len(all_pairs), len(raw_files))

    def _read_double(self, raw_files: list[Path], reviews_dir: Path,
                     assignment: dict, allow_unreviewed: bool) -> None:
        """Modo de revisão dupla — mescla 2 vereditos por par (D1) + kappa."""
        id_to_block = {par["id"]: b
                       for b in assignment["blocos"] for par in b["pares"]}
        sidecar_por_stem: dict = {}
        all_pairs: list[dict] = []
        for rf in raw_files:
            stem = rf.stem
            raw_records = _load_jsonl(rf)
            sk = load_sidecar_keyed(reviews_dir, stem)
            if sk is None:
                if not allow_unreviewed:
                    raise self._missing_sidecar_error(stem, reviews_dir)
                logger.warning("Sem sidecar para %s — usando %d pares crus (--allow-unreviewed)",
                                stem, len(raw_records))
                all_pairs.extend(raw_records)
                sidecar_por_stem[stem] = {}
            else:
                sidecar_por_stem[stem] = sk
                kept = merge_double_review(raw_records, sk, id_to_block)
                logger.info("%s: %d crus -> %d apos revisao dupla",
                            stem, len(raw_records), len(kept))
                all_pairs.extend(kept)
        self._pairs = all_pairs
        self.kappa = cohen_kappa_por_bloco(sidecar_por_stem, assignment)
        logger.info("Total apos revisao dupla: %d pares · Cohen's kappa por bloco: %s",
                    len(all_pairs), self.kappa)

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
    ap.add_argument("--no-assignment", action="store_true",
                    help="Ignora o assignment.json — força o modo de revisor unico")
    ap.add_argument("--seed", type=int, default=42, help="Seed do split (default 42)")
    args = ap.parse_args(argv)

    curator = DataCurator()
    curator.read_curated(args.raw_dir, args.reviews_dir,
                         allow_unreviewed=args.allow_unreviewed,
                         use_assignment=not args.no_assignment)
    valid, invalid = curator.validate_all()
    if not valid:
        raise SystemExit("Nenhum par valido apos curadoria/validacao — nada a salvar.")
    curator.save_hf_dataset(args.output_dir, seed=args.seed)


if __name__ == "__main__":
    main()
