"""Baseline LLM agent: a single prompt to Claude, no tool use, no search.

The recorded headline number for Phase 2 comes from running this agent on a
defined subset of the public ARC-AGI-2 evaluation split.

Implementation notes:
- Default model: Claude Opus 4.7 (strongest available; gives Phase 4's solver
  work a meaningful "did the fancy approach actually beat best-LLM-only" target).
- Anthropic prompt caching: `cache_control: ephemeral` on the reusable
  ARC-AGI instruction block (large enough to be worth caching). Per-task
  content stays uncached.
- Two independent attempts per test input (temperature=0.7 each), matching
  the Kaggle 2-attempt scoring rule.
- Response parser is tolerant of markdown fences and surrounding whitespace.
  Parse failure => Attempt(grid=None, parse_error=...) which scores as wrong.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from arcsolver.agi2.agents.base import (
    Agent,
    AgentTaskRun,
    CallUsage,
    grid_to_text,
)
from arcsolver.agi2.pricing import DEFAULT_MODEL
from arcsolver.agi2.types import Attempt, Grid, Task

# Reusable instruction block — gets cache_control: ephemeral so repeat calls
# read from cache rather than re-paying input cost. Keep this long enough that
# caching is worth the bookkeeping (well over the ~1k-token caching threshold).
INSTRUCTIONS = (
    "You are solving an ARC-AGI-2 puzzle.\n"
    "\n"
    "An ARC-AGI-2 task gives you a small number of example input/output grid pairs"
    " that demonstrate a single transformation rule. Your job is to:\n"
    "  1. Infer the rule from the training examples.\n"
    "  2. Apply that rule to the test input.\n"
    "  3. Return the predicted output grid.\n"
    "\n"
    "GRIDS:\n"
    "- A grid is a 2D array of integers, each in 0-9. Each integer denotes a color.\n"
    '- Common conventions: 0 is often background ("black"), but every task can'
    " redefine the palette.\n"
    "- Grid dimensions are not fixed: the output grid can have different dimensions"
    " from the input grid. Some tasks change shape; many do not. Infer the shape"
    " from the examples.\n"
    "\n"
    "RULES TO LOOK FOR (non-exhaustive):\n"
    "- Color swaps, color counting, color-to-shape mappings.\n"
    "- Geometric transforms: rotation, reflection, translation, tiling, scaling.\n"
    "- Symmetry completion, gravity / falling, flood fill.\n"
    "- Object extraction, object counting, largest/smallest selection.\n"
    "- Pattern continuation, sequence prediction.\n"
    "- Compositions of any of the above.\n"
    "\n"
    "RESPONSE FORMAT (strict):\n"
    "Return ONLY the predicted output grid, formatted as a JSON 2D array (a list"
    " of lists of integers). No prose, no markdown code fences, no commentary, no"
    " leading/trailing whitespace beyond what's natural for JSON. Just the JSON array.\n"
    "\n"
    "Examples of valid responses:\n"
    "[[0, 0, 1], [0, 1, 1], [1, 1, 1]]\n"
    "[[5]]\n"
    "[[1, 2, 3], [4, 5, 6], [7, 8, 9]]\n"
    "\n"
    "If you are unsure, still produce your best guess in the required format."
    " Returning anything other than a valid JSON 2D array of integers will be"
    " scored as wrong.\n"
)


def _render_task_user_message(task: Task, test_index: int) -> str:
    """Render one task into a user-message string targeting a specific test input."""
    lines: list[str] = ["TRAINING EXAMPLES:", ""]
    for i, pair in enumerate(task.train, start=1):
        lines.append(f"Example {i}:")
        lines.append("Input:")
        lines.append(grid_to_text(pair.input))
        lines.append("Output:")
        lines.append(grid_to_text(pair.output))
        lines.append("")
    lines.append("TEST INPUT:")
    lines.append(grid_to_text(task.test[test_index].input))
    lines.append("")
    lines.append("Return ONLY the predicted output grid as a JSON 2D array.")
    return "\n".join(lines)


_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_grid(text: str) -> tuple[Grid | None, str | None]:
    """Try to parse a JSON 2D int array out of the model's response.

    Returns (grid, None) on success, (None, error_message) on failure.
    Tolerates surrounding whitespace and markdown code fences.
    """
    cleaned = _CODE_FENCE.sub("", text.strip()).strip()
    # Best-effort: find the first '[' and the matching final ']'.
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None, "no JSON array found in response"
    candidate = cleaned[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, f"JSON decode failed: {exc.msg}"
    if not isinstance(parsed, list) or not parsed:
        return None, "top-level value is not a non-empty list"
    grid: Grid = []
    for row_idx, row in enumerate(parsed):
        if not isinstance(row, list) or not row:
            return None, f"row {row_idx} is not a non-empty list"
        coerced_row: list[int] = []
        for col_idx, cell in enumerate(row):
            if not isinstance(cell, int) or isinstance(cell, bool):
                return None, f"cell ({row_idx},{col_idx}) is not an int"
            if not 0 <= cell <= 9:
                return None, f"cell ({row_idx},{col_idx})={cell} out of range 0-9"
            coerced_row.append(cell)
        grid.append(coerced_row)
    # Rectangular check.
    width = len(grid[0])
    if any(len(r) != width for r in grid):
        return None, "rows have inconsistent widths"
    return grid, None


def _usage_from_response(resp: Any) -> CallUsage:
    """Read the four token-usage buckets off an Anthropic Message response.

    Defaults missing fields to 0 so SDK shape drift doesn't crash the run.
    """
    usage = getattr(resp, "usage", None)
    if usage is None:
        return CallUsage()
    return CallUsage(
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        cache_creation_input_tokens=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        cache_read_input_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
    )


def _extract_text(resp: Any) -> str:
    """Concatenate text blocks from a Messages response."""
    chunks: list[str] = []
    for block in getattr(resp, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            chunks.append(text)
    return "".join(chunks)


class BaselineLLM:
    """Single-shot LLM agent: prompt -> grid, twice per test input."""

    name = "baseline_llm"

    def __init__(
        self,
        *,
        client: Any | None = None,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        if client is None:
            # Lazy import so just-importing this module doesn't require the SDK.
            import anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set; cannot construct BaselineLLM "
                    "without an explicit client."
                )
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _one_attempt(self, user_message: str) -> tuple[Attempt, CallUsage]:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=[
                {
                    "type": "text",
                    "text": INSTRUCTIONS,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[
                {"role": "user", "content": user_message},
            ],
        )
        text = _extract_text(resp)
        grid, err = parse_grid(text)
        usage = _usage_from_response(resp)
        return Attempt(grid=grid, parse_error=err), usage

    def solve(self, task: Task) -> AgentTaskRun:
        attempts_per_test: list[list[Attempt]] = []
        calls: list[CallUsage] = []
        for test_idx in range(len(task.test)):
            user_message = _render_task_user_message(task, test_idx)
            test_attempts: list[Attempt] = []
            for _ in range(2):
                attempt, usage = self._one_attempt(user_message)
                test_attempts.append(attempt)
                calls.append(usage)
            attempts_per_test.append(test_attempts)
        return AgentTaskRun(task_id=task.task_id, attempts_per_test=attempts_per_test, calls=calls)


__all__ = ["BaselineLLM", "INSTRUCTIONS", "parse_grid"]


def _typecheck_protocol() -> Agent:  # pragma: no cover - structural typing check
    # Satisfies mypy that BaselineLLM conforms to the Agent Protocol.
    return BaselineLLM(client=object())
