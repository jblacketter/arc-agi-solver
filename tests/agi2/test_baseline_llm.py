"""Tests for arcsolver.agi2.agents.baseline_llm.

These tests stub the Anthropic SDK at the boundary so they run offline.
The real network is never touched; `just check` stays free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from arcsolver.agi2.agents.baseline_llm import (
    INSTRUCTIONS,
    BaselineLLM,
    parse_grid,
)
from arcsolver.agi2.types import Pair, Task

# --- parse_grid -------------------------------------------------------------


def test_parse_grid_plain() -> None:
    grid, err = parse_grid("[[1, 2], [3, 4]]")
    assert err is None
    assert grid == [[1, 2], [3, 4]]


def test_parse_grid_with_code_fence() -> None:
    grid, err = parse_grid("```json\n[[1, 2], [3, 4]]\n```")
    assert err is None
    assert grid == [[1, 2], [3, 4]]


def test_parse_grid_with_surrounding_text() -> None:
    # Best-effort: model wraps the array in prose. Parser should still find it.
    grid, err = parse_grid("Here is the output:\n[[5, 5], [5, 5]]\nThat's my answer.")
    assert err is None
    assert grid == [[5, 5], [5, 5]]


def test_parse_grid_rejects_out_of_range() -> None:
    grid, err = parse_grid("[[1, 2], [3, 99]]")
    assert grid is None
    assert err is not None
    assert "out of range" in err


def test_parse_grid_rejects_ragged_rows() -> None:
    grid, err = parse_grid("[[1, 2], [3]]")
    assert grid is None
    assert err is not None
    assert "widths" in err


def test_parse_grid_rejects_non_int() -> None:
    grid, err = parse_grid('[["a", "b"]]')
    assert grid is None
    assert err is not None


def test_parse_grid_rejects_no_array() -> None:
    grid, err = parse_grid("I am sorry, I cannot answer.")
    assert grid is None
    assert err is not None
    assert "no JSON array" in err


def test_parse_grid_rejects_booleans() -> None:
    # `True` / `False` would coerce as int in Python; we want to reject them.
    grid, err = parse_grid("[[true, false]]")
    assert grid is None
    assert err is not None


# --- BaselineLLM with a fake client ----------------------------------------


@dataclass
class _FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class _FakeTextBlock:
    text: str


@dataclass
class _FakeResponse:
    content: list[_FakeTextBlock]
    usage: _FakeUsage = field(default_factory=_FakeUsage)


class _FakeMessages:
    """Captures kwargs and returns the next scripted response."""

    def __init__(self, scripted: list[_FakeResponse]) -> None:
        self.scripted = list(scripted)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self.scripted:
            raise AssertionError("FakeMessages: out of scripted responses")
        return self.scripted.pop(0)


class _FakeClient:
    def __init__(self, scripted: list[_FakeResponse]) -> None:
        self.messages = _FakeMessages(scripted)


def _task_one_test() -> Task:
    return Task(
        task_id="fake-1",
        train=[Pair(input=[[0]], output=[[1]])],
        test=[Pair(input=[[2]], output=[[3]])],
    )


def test_baseline_makes_two_calls_per_test_input() -> None:
    scripted = [
        _FakeResponse(content=[_FakeTextBlock("[[3]]")]),
        _FakeResponse(content=[_FakeTextBlock("[[9]]")]),
    ]
    client = _FakeClient(scripted)
    agent = BaselineLLM(client=client, model="claude-opus-4-7")
    run = agent.solve(_task_one_test())
    assert len(run.attempts_per_test) == 1
    assert len(run.attempts_per_test[0]) == 2
    assert run.attempts_per_test[0][0].grid == [[3]]
    assert run.attempts_per_test[0][1].grid == [[9]]
    assert len(run.calls) == 2


def test_baseline_request_has_cache_control_on_instructions() -> None:
    client = _FakeClient(
        [
            _FakeResponse(content=[_FakeTextBlock("[[0]]")]),
            _FakeResponse(content=[_FakeTextBlock("[[0]]")]),
        ]
    )
    agent = BaselineLLM(client=client)
    agent.solve(_task_one_test())
    request = client.messages.calls[0]
    system = request["system"]
    assert isinstance(system, list) and len(system) == 1
    block = system[0]
    assert block["text"] == INSTRUCTIONS
    assert block["cache_control"] == {"type": "ephemeral"}


def test_baseline_records_usage_with_cache_fields() -> None:
    client = _FakeClient(
        [
            _FakeResponse(
                content=[_FakeTextBlock("[[1]]")],
                usage=_FakeUsage(
                    input_tokens=100,
                    output_tokens=5,
                    cache_creation_input_tokens=200,
                    cache_read_input_tokens=0,
                ),
            ),
            _FakeResponse(
                content=[_FakeTextBlock("[[2]]")],
                usage=_FakeUsage(
                    input_tokens=100,
                    output_tokens=5,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=200,  # cache hit on the second call
                ),
            ),
        ]
    )
    agent = BaselineLLM(client=client)
    run = agent.solve(_task_one_test())
    assert run.calls[0].cache_creation_input_tokens == 200
    assert run.calls[1].cache_read_input_tokens == 200


def test_baseline_parse_failure_is_a_wrong_attempt_not_a_crash() -> None:
    client = _FakeClient(
        [
            _FakeResponse(content=[_FakeTextBlock("I refuse to answer.")]),
            _FakeResponse(content=[_FakeTextBlock("[[3]]")]),
        ]
    )
    agent = BaselineLLM(client=client)
    run = agent.solve(_task_one_test())
    assert run.attempts_per_test[0][0].grid is None
    assert run.attempts_per_test[0][0].parse_error is not None
    # Second attempt still runs and parses.
    assert run.attempts_per_test[0][1].grid == [[3]]


def test_baseline_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        BaselineLLM()  # no client, no env var -> fail fast
