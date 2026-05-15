#!/usr/bin/env python3
"""Fetch the ARC-AGI-2 public dataset at a pinned upstream commit.

The dataset is sourced from https://github.com/arcprize/ARC-AGI-2 — specifically
the commit referenced by `_PINNED_REV` below. We clone the repo into a temp
directory, check out the exact SHA, copy the training and evaluation JSON files
into `data/agi2/`, and verify the expected counts before declaring success.

If upstream restructures the repo or the counts drift, this script aborts
non-zero rather than silently producing stale data.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Pin to a specific commit of arcprize/ARC-AGI-2. Bump deliberately when we want
# to track a new upstream revision.
_PINNED_REV = "f3283f727488ad98fe575ea6a5ac981e4a188e49"
_UPSTREAM_URL = "https://github.com/arcprize/ARC-AGI-2.git"

_EXPECTED_TRAINING_COUNT = 1000
_EXPECTED_EVALUATION_COUNT = 120

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST_DIR = REPO_ROOT / "data" / "agi2"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _fetch_into(temp_dir: Path) -> Path:
    clone_dir = temp_dir / "ARC-AGI-2"
    _run(["git", "clone", "--no-checkout", _UPSTREAM_URL, str(clone_dir)])
    _run(["git", "checkout", _PINNED_REV], cwd=clone_dir)
    return clone_dir


def _copy_split(src: Path, dest: Path, expected_count: int, label: str) -> None:
    if not src.is_dir():
        sys.exit(f"error: upstream split missing at {src} (label={label})")
    dest.mkdir(parents=True, exist_ok=True)
    # Wipe existing files to keep this idempotent.
    for existing in dest.glob("*.json"):
        existing.unlink()
    json_files = sorted(src.glob("*.json"))
    for f in json_files:
        shutil.copy2(f, dest / f.name)
    actual = len(list(dest.glob("*.json")))
    if actual != expected_count:
        sys.exit(
            f"error: expected {expected_count} {label} task files, got {actual}. "
            f"Upstream layout may have changed at rev {_PINNED_REV}."
        )


def main() -> int:
    print(f"Fetching ARC-AGI-2 dataset at rev {_PINNED_REV} ...")
    with tempfile.TemporaryDirectory(prefix="arc-agi-2-fetch-") as tmp:
        clone_dir = _fetch_into(Path(tmp))
        _copy_split(
            clone_dir / "data" / "training",
            DEST_DIR / "training",
            _EXPECTED_TRAINING_COUNT,
            "training",
        )
        _copy_split(
            clone_dir / "data" / "evaluation",
            DEST_DIR / "evaluation",
            _EXPECTED_EVALUATION_COUNT,
            "evaluation",
        )
    print(
        f"OK: {_EXPECTED_TRAINING_COUNT} training + {_EXPECTED_EVALUATION_COUNT} "
        f"evaluation tasks written to {DEST_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
