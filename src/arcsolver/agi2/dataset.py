"""Load ARC-AGI-2 tasks from the local `data/agi2/` tree.

The dataset is populated by `scripts/fetch_agi2_data.py` (Phase 1). Each
task is a JSON file with top-level keys `train` and `test`, each holding
a list of {input, output} grid pairs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from arcsolver.agi2.types import Pair, Task

Split = Literal["training", "evaluation"]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "agi2"


def split_dir(split: Split) -> Path:
    return DATA_DIR / split


def load_task(path: Path | str) -> Task:
    p = Path(path)
    with p.open() as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict) or "train" not in raw or "test" not in raw:
        raise ValueError(f"{p}: missing 'train'/'test' keys")
    train = [Pair(input=pair["input"], output=pair["output"]) for pair in raw["train"]]
    test = [Pair(input=pair["input"], output=pair["output"]) for pair in raw["test"]]
    return Task(task_id=p.stem, train=train, test=test)


def load_split(split: Split, limit: int | None = None) -> list[Task]:
    """Load all tasks in a split (optionally limited, sorted by filename)."""
    dirpath = split_dir(split)
    if not dirpath.is_dir():
        raise FileNotFoundError(
            f"ARC-AGI-2 {split} split not found at {dirpath}. Run `just fetch-data` to populate it."
        )
    files = sorted(dirpath.glob("*.json"))
    if limit is not None:
        files = files[:limit]
    return [load_task(f) for f in files]
