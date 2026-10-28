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

"""Import smoke tests for the thread pattern debug agent."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events import EventQueue

AGENT_DIR = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location("thread_pattern_agent_module", AGENT_DIR / "agent.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
ThreadPatternAgent = _MODULE.ThreadPatternAgent


@pytest.fixture
def agent(monkeypatch):
    # build_app() requires a bearer secret; the memory task store keeps it off Redis
    monkeypatch.setenv("AGENT_SECRET", "test-secret")
    monkeypatch.setenv("PROMETHEUS_TASK_STORE", "memory")
    return ThreadPatternAgent(
        agent_name="Thread Pattern Debug Agent", agent_card_path=str(AGENT_DIR / "agent_card.json")
    )


def test_build_app(agent):
    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.name == "Thread Pattern Debug Agent"
    assert [skill.id for skill in agent.agent_card.skills] == [
        "run_blocking_task",
        "run_background_task",
    ]


def test_resolve_duration_seconds():
    resolve = ThreadPatternAgent._resolve_duration_seconds

    assert resolve({}) == _MODULE.DEFAULT_DURATION_SECONDS
    assert resolve({"duration_seconds": "bad"}) == _MODULE.DEFAULT_DURATION_SECONDS
    assert resolve({"duration_seconds": 0}) == 1
    assert resolve({"duration_seconds": 10_000}) == _MODULE.MAX_DURATION_SECONDS


class _FakeClock:
    """Stands in for the time module so the worker's blocking sleep is instant."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


async def test_execute_runs_worker(agent, monkeypatch):
    monkeypatch.setattr(_MODULE, "time", _FakeClock())
    monkeypatch.setattr(_MODULE, "POLL_INTERVAL_SECONDS", 0)
    context = MagicMock(spec=RequestContext)
    context.context_id = "ctx-1"
    context.task_id = "task-1"
    queue = AsyncMock(spec=EventQueue)

    result = await agent._execute({"skill_id": "run_blocking_task", "duration_seconds": 2}, context, queue)

    assert result["status"] == "success"
    assert result["elapsed_seconds"] == 2
    queue.enqueue_event.assert_called()
