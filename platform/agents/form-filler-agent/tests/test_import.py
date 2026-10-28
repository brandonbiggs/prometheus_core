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

"""Import smoke tests for the form filler agent."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events import EventQueue

AGENT_DIR = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location("form_filler_agent_module", AGENT_DIR / "agent.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
FormFillerAgent = _MODULE.FormFillerAgent


@pytest.fixture
def agent(monkeypatch):
    # build_app() requires a bearer secret; the memory task store keeps it off Redis
    monkeypatch.setenv("AGENT_SECRET", "test-secret")
    monkeypatch.setenv("PROMETHEUS_TASK_STORE", "memory")
    return FormFillerAgent(agent_name="Form Filler Agent", agent_card_path=str(AGENT_DIR / "agent_card.json"))


def test_build_app(agent):
    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.name == "Form Filler Agent"
    assert [skill.id for skill in agent.agent_card.skills] == ["fill_form"]


async def test_execute_round_trips_state(agent):
    store = {}
    redis_client = MagicMock()
    redis_client.get.side_effect = store.get
    redis_client.set.side_effect = lambda key, value, ex: store.__setitem__(key, value)
    agent._redis_client = redis_client
    context = MagicMock(spec=RequestContext)
    context.context_id = "ctx-1"
    context.task_id = "task-1"
    queue = AsyncMock(spec=EventQueue)
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    # A new conversation with all values answered directly skips the LLM
    result = await agent._execute(
        {"context": "A form", "schema": schema, "followup_answers": {"name": "Ada"}},
        context,
        queue,
    )

    assert result["status"] == "completed"
    assert result["filled_data"] == {"name": "Ada"}
    assert agent.get_state("ctx-1")["extracted_values"] == {"name": "Ada"}


async def test_execute_requires_context(agent):
    context = MagicMock(spec=RequestContext)
    context.context_id = "ctx-1"
    queue = AsyncMock(spec=EventQueue)

    result = await agent._execute({}, context, queue)

    assert result["status"] == "error"
    queue.enqueue_event.assert_not_called()
