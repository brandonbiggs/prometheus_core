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

"""Import smoke tests for the radiation damage agent."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events import EventQueue
from a2a.types import TaskState

AGENT_DIR = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location("radiation_agent_module", AGENT_DIR / "agent.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
RadiationDamageAgent = _MODULE.RadiationDamageAgent


@pytest.fixture
def agent(monkeypatch):
    # build_app() requires a bearer secret; the memory task store keeps it off Redis
    monkeypatch.setenv("AGENT_SECRET", "test-secret")
    monkeypatch.setenv("PROMETHEUS_TASK_STORE", "memory")
    return RadiationDamageAgent(
        agent_name="Radiation Damage Analysis Agent",
        agent_card_path=str(AGENT_DIR / "agent_card.json"),
    )


def test_build_app(agent):
    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.name == "Radiation Damage Analysis Agent"
    assert [skill.id for skill in agent.agent_card.skills] == [
        "analyze_radiation_damage",
        "calculate_dpa",
        "assess_embrittlement",
    ]


async def test_execute_requests_material_id(agent):
    context = MagicMock(spec=RequestContext)
    context.context_id = "ctx-1"
    context.task_id = "task-1"
    context.message = MagicMock(parts=[])
    queue = AsyncMock(spec=EventQueue)

    result = await agent._execute({}, context, queue)

    assert result == {"status": "input_required"}
    event = queue.enqueue_event.call_args[0][0]
    assert event.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
