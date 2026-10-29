# This file is part of Prometheus
# https://inl.gov/super-intelligence/prometheus/
#
# Copyright 2026 Battelle Energy Alliance, LLC
# All rights reserved, see NOTICE.txt for full restrictions
# https://github.com/idaholab/prometheus_core/blob/main/NOTICE.txt
#
# Licensed under the MIT License, please see LICENSE for details
# https://github.com/idaholab/prometheus_core/blob/main/LICENSE
#
# SPDX-License-Identifier: MIT

"""Tests for the Thread Pattern Debug agent.

The first test builds the server, which catches a broken agent_card.json or
workflow file; the rest exercise `_execute`. Extend these as you implement your
agent: every input-validation branch and every distinct result shape deserves a
test. Run with `uv run pytest`.
"""

from pathlib import Path

import agent as agent_module
from agent import DEFAULT_DURATION_SECONDS, MAX_DURATION_SECONDS, ThreadPatternAgent

AGENT_DIR = Path(__file__).resolve().parents[1]


def _make_agent() -> ThreadPatternAgent:
    # agent_card.json is loaded lazily by run()/build_app(), not by the
    # constructor, so unit tests can instantiate the agent directly. A relative
    # path resolves against the running script, which under pytest isn't this
    # directory, so pass the card's absolute path.
    return ThreadPatternAgent(
        agent_name="Thread Pattern Debug Agent", agent_card_path=str(AGENT_DIR / "agent_card.json")
    )


class _FakeClock:
    """Stands in for the time module so the worker's blocking sleep is instant."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_build_app_loads_agent_card():
    # Builds the server as run() would, which loads agent_card.json and any
    # workflows/, without starting it or registering with LiteLLM.
    agent = _make_agent()

    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.skills


async def test_execute_runs_blocking_worker(context, event_queue, monkeypatch):
    monkeypatch.setattr(agent_module, "time", _FakeClock())
    monkeypatch.setattr(agent_module, "POLL_INTERVAL_SECONDS", 0)
    agent = _make_agent()

    result = await agent._execute({"skill_id": "run_blocking_task", "duration_seconds": 2}, context, event_queue)

    assert result["status"] == "success"
    assert result["elapsed_seconds"] == 2
    # Progress updates were emitted through the event queue.
    assert event_queue.enqueue_event.await_count >= 1


def test_duration_is_clamped():
    resolve = ThreadPatternAgent._resolve_duration_seconds

    assert resolve({}) == DEFAULT_DURATION_SECONDS
    assert resolve({"duration_seconds": "bad"}) == DEFAULT_DURATION_SECONDS
    assert resolve({"duration_seconds": 0}) == 1
    assert resolve({"duration_seconds": 10_000}) == MAX_DURATION_SECONDS
