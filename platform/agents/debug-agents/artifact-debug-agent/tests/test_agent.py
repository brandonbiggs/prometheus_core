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

"""Tests for the Artifact Debug agent.

The first test builds the server, which catches a broken agent_card.json or
workflow file; the rest exercise `_execute`. Extend these as you implement your
agent: every input-validation branch and every distinct result shape deserves a
test. Run with `uv run pytest`.
"""

import importlib.util
from pathlib import Path

from agent import ArtifactDebugAgent

AGENT_DIR = Path(__file__).resolve().parents[1]


def _make_agent() -> ArtifactDebugAgent:
    # agent_card.json is loaded lazily by run()/build_app(), not by the
    # constructor, so unit tests can instantiate the agent directly. A relative
    # path resolves against the running script, which under pytest isn't this
    # directory, so pass the card's absolute path.
    return ArtifactDebugAgent(agent_name="Artifact Debug Agent", agent_card_path=str(AGENT_DIR / "agent_card.json"))


def test_build_app_loads_agent_card():
    # Builds the server as run() would, which loads agent_card.json and any
    # workflows/, without starting it or registering with LiteLLM.
    agent = _make_agent()

    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.skills


def test_cairosvg_installed():
    # agent.py imports cairosvg lazily, so check that pyproject.toml declares it
    assert importlib.util.find_spec("cairosvg") is not None


async def test_execute_requires_storage_credentials(context, event_queue, monkeypatch, tmp_path):
    for name in ("DEEPLYNX_KEY", "DEEPLYNX_SECRET", "DEEPLYNX_JWT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    # ConnectionConfig.from_env() also reads a .env in the working directory
    monkeypatch.chdir(tmp_path)
    agent = _make_agent()

    result = await agent._execute({"skill_id": "create_svg_artifact", "word": "hi"}, context, event_queue)

    assert result["status"] == "error"
    assert "DEEPLYNX_" in result["message"]
