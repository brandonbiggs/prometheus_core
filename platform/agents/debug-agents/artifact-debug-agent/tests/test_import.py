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

"""Import smoke tests for the artifact debug agent."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events import EventQueue

AGENT_DIR = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location("artifact_debug_agent_module", AGENT_DIR / "agent.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
ArtifactDebugAgent = _MODULE.ArtifactDebugAgent


@pytest.fixture
def agent(monkeypatch):
    # build_app() requires a bearer secret; the memory task store keeps it off Redis
    monkeypatch.setenv("AGENT_SECRET", "test-secret")
    monkeypatch.setenv("PROMETHEUS_TASK_STORE", "memory")
    return ArtifactDebugAgent(agent_name="Artifact Debug Agent", agent_card_path=str(AGENT_DIR / "agent_card.json"))


def test_build_app(agent):
    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.name == "Artifact Debug Agent"
    assert [skill.id for skill in agent.agent_card.skills] == [
        "create_svg_artifact",
        "convert_svg_to_png",
        "create_json_artifact",
    ]


def test_cairosvg_installed():
    # Imported lazily by the agent, so check that it is declared and installed
    assert importlib.util.find_spec("cairosvg") is not None


async def test_execute_requires_storage_credentials(agent, monkeypatch, tmp_path):
    for name in ("DEEPLYNX_KEY", "DEEPLYNX_SECRET", "DEEPLYNX_JWT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    # ConnectionConfig.from_env() also reads a .env in the working directory
    monkeypatch.chdir(tmp_path)
    context = MagicMock(spec=RequestContext)
    context.context_id = "ctx-1"
    context.task_id = "task-1"
    queue = AsyncMock(spec=EventQueue)

    result = await agent._execute({"skill_id": "create_svg_artifact", "word": "hi"}, context, queue)

    assert result == {
        "status": "error",
        "conversation_id": "ctx-1",
        "message": "DEEPLYNX_* credentials not configured.",
    }
