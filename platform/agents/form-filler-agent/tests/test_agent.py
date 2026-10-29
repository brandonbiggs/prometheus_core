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

"""Tests for the Form Filler agent.

The first test builds the server, which catches a broken agent_card.json or
workflow file; the rest exercise `_execute`. Extend these as you implement your
agent: every input-validation branch and every distinct result shape deserves a
test. Run with `uv run pytest`.
"""

from pathlib import Path
from unittest.mock import MagicMock

from agent import FormFillerAgent

AGENT_DIR = Path(__file__).resolve().parents[1]


def _make_agent() -> FormFillerAgent:
    # agent_card.json is loaded lazily by run()/build_app(), not by the
    # constructor, so unit tests can instantiate the agent directly. A relative
    # path resolves against the running script, which under pytest isn't this
    # directory, so pass the card's absolute path.
    return FormFillerAgent(agent_name="Form Filler Agent", agent_card_path=str(AGENT_DIR / "agent_card.json"))


def test_build_app_loads_agent_card():
    # Builds the server as run() would, which loads agent_card.json and any
    # workflows/, without starting it or registering with LiteLLM.
    agent = _make_agent()

    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.skills


async def test_execute_completes_form_from_answers(context, event_queue):
    agent = _make_agent()
    store = {}
    redis_client = MagicMock()
    redis_client.get.side_effect = store.get
    redis_client.set.side_effect = lambda key, value, ex: store.__setitem__(key, value)
    agent._redis_client = redis_client
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    # A new conversation with every required value answered directly skips the LLM
    result = await agent._execute(
        {"context": "A form", "schema": schema, "followup_answers": {"name": "Ada"}},
        context,
        event_queue,
    )

    assert result["status"] == "completed"
    assert result["filled_data"] == {"name": "Ada"}
    assert agent.get_state("test-conversation")["extracted_values"] == {"name": "Ada"}


async def test_execute_rejects_missing_context(context, event_queue):
    agent = _make_agent()

    result = await agent._execute({}, context, event_queue)

    assert result["status"] == "error"
    assert "context" in result["error"]
