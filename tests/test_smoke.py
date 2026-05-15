"""Phase 1 smoke test.

Verifies that:
- The local ARC-AGI-2 dataset (once fetched) parses into the expected shape.
- The `arc-agi` SDK can be imported and `Arcade().make("ls20")` returns an
  environment wrapper (not None).

Skip conditions for the AGI-3 case are narrow and documented; any other
failure surfaces as a test failure, not a skip.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AGI2_TRAINING_DIR = REPO_ROOT / "data" / "agi2" / "training"


def test_agi2_task_loads() -> None:
    """Load one ARC-AGI-2 training task and assert basic shape."""
    if not AGI2_TRAINING_DIR.exists():
        pytest.skip(
            "ARC-AGI-2 training data not fetched yet — run `just fetch-data` "
            f"to populate {AGI2_TRAINING_DIR}"
        )
    task_files = sorted(AGI2_TRAINING_DIR.glob("*.json"))
    assert task_files, f"no JSON files found in {AGI2_TRAINING_DIR}"

    with task_files[0].open() as fh:
        task = json.load(fh)

    assert isinstance(task, dict), f"expected dict, got {type(task).__name__}"
    assert "train" in task, f"task {task_files[0].name} missing 'train' key"
    assert "test" in task, f"task {task_files[0].name} missing 'test' key"
    assert isinstance(task["train"], list) and task["train"], (
        f"task {task_files[0].name} 'train' must be a non-empty list"
    )


def test_agi3_env_constructs() -> None:
    """Construct an ARC-AGI-3 env via `arc_agi.Arcade()` and assert not None.

    `arc_agi.Arcade()` auto-acquires an anonymous API key when `ARC_API_KEY`
    is unset, and `arc.make("ls20")` downloads the game code locally on first
    use. Under normal conditions this test does not skip.

    Documented skip-paths:
      1. `arc_agi` fails to import.
      2. SDK explicitly raises an `api_key` / `ARC_API_KEY` requirement that
         we cannot satisfy from environment.
      3. SDK raises a clearly-marked "environment unavailable" / network error.

    Any other exception, or a `None` return, fails the test.
    """
    arc_agi = pytest.importorskip("arc_agi")

    try:
        arcade = arc_agi.Arcade()
        env = arcade.make("ls20")
    except Exception as exc:  # noqa: BLE001 - intentionally narrow handling below
        msg = str(exc).lower()
        api_key_missing = "api_key" in msg or "api key" in msg or "arc_api_key" in msg
        env_unavailable = (
            ("environment" in msg and ("unavailable" in msg or "not found" in msg))
            or "network" in msg
            or "connection" in msg
        )
        if api_key_missing and not os.environ.get("ARC_API_KEY"):
            pytest.skip(f"ARC_API_KEY required by SDK but not set: {exc}")
        if env_unavailable:
            pytest.skip(f"ARC-AGI-3 environment 'ls20' unavailable: {exc}")
        raise

    assert env is not None, "arc_agi.Arcade().make('ls20') returned None"
