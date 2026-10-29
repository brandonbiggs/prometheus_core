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

"""Tests for the Material Data agent.

The first test builds the server, which catches a broken agent_card.json or
workflow file; the rest exercise `_execute`. Extend these as you implement your
agent: every input-validation branch and every distinct result shape deserves a
test. Run with `uv run pytest`.
"""

from pathlib import Path

from agent import MATERIAL_DATABASE, MaterialDataAgent

AGENT_DIR = Path(__file__).resolve().parents[1]


def _make_agent() -> MaterialDataAgent:
    # agent_card.json is loaded lazily by run()/build_app(), not by the
    # constructor, so unit tests can instantiate the agent directly. A relative
    # path resolves against the running script, which under pytest isn't this
    # directory, so pass the card's absolute path.
    return MaterialDataAgent(agent_name="Material Data Agent", agent_card_path=str(AGENT_DIR / "agent_card.json"))


def test_build_app_loads_agent_card():
    # Builds the server as run() would, which loads agent_card.json and any
    # workflows/, without starting it or registering with LiteLLM.
    agent = _make_agent()

    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.skills


async def test_execute_lists_materials(context, event_queue):
    agent = _make_agent()

    result = await agent._execute({"skill_id": "list_materials"}, context, event_queue)

    assert result["count"] == len(MATERIAL_DATABASE)
    assert {m["material_id"] for m in result["materials"]} == set(MATERIAL_DATABASE)


async def test_execute_rejects_unknown_material(context, event_queue):
    agent = _make_agent()

    result = await agent._execute({"skill_id": "get_material_data", "material_id": "nope"}, context, event_queue)

    assert result["error"] == "Material nope not found"
    assert result["available_materials"] == list(MATERIAL_DATABASE)
