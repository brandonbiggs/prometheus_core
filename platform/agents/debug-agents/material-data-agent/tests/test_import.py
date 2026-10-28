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

"""Import smoke tests for the material data agent."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events import EventQueue

AGENT_DIR = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location("material_data_agent_module", AGENT_DIR / "agent.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
MaterialDataAgent = _MODULE.MaterialDataAgent


@pytest.fixture
def agent(monkeypatch):
    # build_app() requires a bearer secret; the memory task store keeps it off Redis
    monkeypatch.setenv("AGENT_SECRET", "test-secret")
    monkeypatch.setenv("PROMETHEUS_TASK_STORE", "memory")
    return MaterialDataAgent(agent_name="Material Data Agent", agent_card_path=str(AGENT_DIR / "agent_card.json"))


def test_build_app(agent):
    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.name == "Material Data Agent"
    assert [skill.id for skill in agent.agent_card.skills] == [
        "list_materials",
        "get_material_data",
        "get_material_properties",
        "get_material_history",
        "get_regulatory_limits",
    ]


async def test_execute_lists_materials(agent):
    context = MagicMock(spec=RequestContext)
    context.context_id = "ctx-1"
    context.task_id = "task-1"
    queue = AsyncMock(spec=EventQueue)

    result = await agent._execute({"skill_id": "list_materials"}, context, queue)

    assert result["count"] == len(_MODULE.MATERIAL_DATABASE)
    assert {m["material_id"] for m in result["materials"]} == set(_MODULE.MATERIAL_DATABASE)
