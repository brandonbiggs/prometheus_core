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

"""Tests for the Synthesis agent.

The first test builds the server, which catches a broken agent_card.json or
workflow file; the rest exercise `_execute`. Extend these as you implement your
agent: every input-validation branch and every distinct result shape deserves a
test. Run with `uv run pytest`.
"""

from pathlib import Path

from agent import SynthesisAgent

AGENT_DIR = Path(__file__).resolve().parents[1]


def _make_agent() -> SynthesisAgent:
    # agent_card.json is loaded lazily by run()/build_app(), not by the
    # constructor, so unit tests can instantiate the agent directly. A relative
    # path resolves against the running script, which under pytest isn't this
    # directory, so pass the card's absolute path.
    return SynthesisAgent(agent_name="Synthesis Agent", agent_card_path=str(AGENT_DIR / "agent_card.json"))


def test_build_app_loads_agent_card():
    # Builds the server as run() would, which loads agent_card.json and any
    # workflows/, without starting it or registering with LiteLLM.
    agent = _make_agent()

    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.skills


async def test_execute_rejects_missing_material_id(context, event_queue):
    agent = _make_agent()

    result = await agent._execute({"tool_results": {"a": 1}}, context, event_queue)

    assert result == {"error": "material_id is required"}


async def test_execute_rejects_missing_tool_results(context, event_queue):
    agent = _make_agent()

    result = await agent._execute({"material_id": "SS316"}, context, event_queue)

    assert "tool_results" in result["error"]
