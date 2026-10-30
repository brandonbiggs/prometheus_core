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

"""Integration tests for the local DeepLynx (LOCAL_DEEPLYNX=true).

Skipped unless deeplynx-server is running. The storage round trip runs inside
the backend container, so it uses the prometheus_api the platform is built
with and the DEEPLYNX_* settings `make deeplynx-setup` gave the services.
"""

import subprocess

import pytest


pytestmark = pytest.mark.integration

# Store an item and a file in DeepLynx and read both back
ROUND_TRIP = """
import pathlib, tempfile
from prometheus_api.storage_client import ConnectionConfig, ItemCreate, StorageClient

work = pathlib.Path(tempfile.mkdtemp())
source = work / "round-trip.txt"
source.write_text("stored by the platform integration tests")
with StorageClient(ConnectionConfig.from_env()) as client:
    item = client.items.create(ItemCreate(name="integration-round-trip", properties={"check": 1}))
    assert client.items.get(item.id).properties == {"check": 1}
    stored = client.files.upload(source)
    client.files.download(stored.id, work / "copy.txt")
    assert (work / "copy.txt").read_text() == source.read_text()
print("ok")
"""


def _status(container: str, field: str) -> str:
    """A ``docker inspect`` field of the container, or "" if it doesn't exist."""
    result = subprocess.run(
        ["docker", "inspect", "--format", field, container],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def local_deeplynx(docker_compose_up, container_id):
    """Skip unless the local DeepLynx is running."""
    if _status(container_id("deeplynx-server"), "{{.State.Status}}") != "running":
        pytest.skip("the local DeepLynx isn't running (LOCAL_DEEPLYNX=true)")


def test_deeplynx_server_healthy(local_deeplynx, container_id):
    """deeplynx-server passes its healthcheck."""
    assert _status(container_id("deeplynx-server"), "{{.State.Health.Status}}") == "healthy"


def test_backend_points_at_local_deeplynx(local_deeplynx, container_id):
    """make deeplynx-setup pointed the backend at deeplynx-server."""
    result = subprocess.run(
        ["docker", "exec", container_id("backend"), "printenv", "DEEPLYNX_BASE_URL"],
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "http://deeplynx-server:5000/api/v1"


def test_storage_round_trip(local_deeplynx, container_id):
    """The platform's storage client can store and read back an item and a file."""
    result = subprocess.run(
        ["docker", "exec", container_id("backend"), "python", "-c", ROUND_TRIP],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip().endswith("ok")
