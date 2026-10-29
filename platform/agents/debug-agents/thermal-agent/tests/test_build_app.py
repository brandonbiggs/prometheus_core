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

"""Test that the thermal agent's server builds, as in the agent template."""

import importlib.util
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location("thermal_agent_module_build", AGENT_DIR / "agent.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


@pytest.fixture(autouse=True)
def agent_env(monkeypatch) -> None:
    """Let build_app() run offline: it requires a bearer secret, and the
    in-memory task store keeps it off Redis."""
    monkeypatch.setenv("AGENT_SECRET", "test-secret")
    monkeypatch.setenv("PROMETHEUS_TASK_STORE", "memory")


def test_build_app_loads_agent_card():
    # A relative path resolves against the running script, which under pytest
    # isn't this directory, so pass the card's absolute path.
    agent = _MODULE.ThermalAnalysisAgent(
        agent_name="Thermal Analysis Agent", agent_card_path=str(AGENT_DIR / "agent_card.json")
    )

    # Builds the server as run() would, which loads agent_card.json and any
    # workflows/, without starting it or registering with LiteLLM.
    assert agent.build_app(register_on_startup=False) is not None
    assert agent.agent_card.skills
