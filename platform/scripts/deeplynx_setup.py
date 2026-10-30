#!/usr/bin/env python3
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

"""Point the platform at the local DeepLynx from docker-compose.deeplynx.yml.

Run by ``make deeplynx-setup`` (and before every start target when
LOCAL_DEEPLYNX=true), once deeplynx-server is up:

1. Wait until the server answers on its host port.
2. If .env already holds an API key that this server accepts, for a project
   that still exists, stop: there is nothing to do.
3. Otherwise find the project PROJECT_NAME in the default organization, or
   create it, and generate an API key.
4. Write DEEPLYNX_BASE_URL (the server's address on the compose network),
   DEEPLYNX_KEY, DEEPLYNX_SECRET, DEEPLYNX_ORG_ID and DEEPLYNX_PROJECT_ID to
   .env, and blank DEEPLYNX_JWT_TOKEN and DEEPLYNX_DATA_SOURCE_ID.

The server runs with authentication disabled, so creating the project and the
key needs no credentials. After ``make down-v`` the DeepLynx database is gone
and the next run creates both again.

    deeplynx_setup.py [--port 5000] [--timeout 300]

Standard library only. Run from anywhere; paths resolve relative to this file.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"

# deeplynx-server on the compose network, as the agents and backend reach it
INTERNAL_URL = "http://deeplynx-server:5000/api/v1"
# The organization DeepLynx's migrations create
ORG_ID = 1
PROJECT_NAME = "Prometheus"


def _load_init_env():
    """init_env.py, for reading and writing .env the same way."""
    spec = importlib.util.spec_from_file_location("init_env", ROOT / "scripts" / "init_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request(method: str, url: str, body: dict | None = None) -> tuple[int, object]:
    """Send a JSON request; return the status and the decoded body (or None)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        return status, json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return status, None


def wait_healthy(api: str, timeout: float) -> bool:
    """Whether the server reports healthy within ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, body = request("GET", f"{api}/health")
            if status == 200 and isinstance(body, dict) and body.get("status") == "healthy":
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    return False


def configured(api: str, env: dict[str, str]) -> bool:
    """Whether .env already points at this server with a key it accepts."""
    key, secret, project = env.get("DEEPLYNX_KEY"), env.get("DEEPLYNX_SECRET"), env.get("DEEPLYNX_PROJECT_ID")
    if env.get("DEEPLYNX_BASE_URL", "").rstrip("/") != INTERNAL_URL or not (key and secret and project):
        return False
    status, _ = request("POST", f"{api}/oauth/tokens", {"apiKey": key, "apiSecret": secret, "expirationMinutes": 1})
    if status != 200:
        return False
    status, _ = request("GET", f"{api}/organizations/{ORG_ID}/projects/{project}")
    return status == 200


def find_or_create_project(api: str) -> int:
    """The ID of the PROJECT_NAME project, created if there is none."""
    status, projects = request("GET", f"{api}/organizations/{ORG_ID}/projects")
    if status != 200 or not isinstance(projects, list):
        raise RuntimeError(f"Listing the projects returned HTTP {status}")
    for project in projects:
        if project.get("name") == PROJECT_NAME and not project.get("isArchived"):
            return int(project["id"])
    status, project = request("POST", f"{api}/organizations/{ORG_ID}/projects", {"name": PROJECT_NAME})
    if status != 200 or not isinstance(project, dict):
        raise RuntimeError(f"Creating the project returned HTTP {status}")
    print(f"Created the DeepLynx project {PROJECT_NAME!r} (ID {project['id']}).")
    return int(project["id"])


def create_key(api: str) -> tuple[str, str]:
    """A new API key and secret for the local developer."""
    status, body = request("POST", f"{api}/oauth/keys")
    if status != 200 or not isinstance(body, dict) or not body.get("apiKey"):
        raise RuntimeError(f"Creating an API key returned HTTP {status}")
    return body["apiKey"], body["apiSecret"]


def main() -> int:
    """Set up DeepLynx in .env if it isn't already; return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=5000, help="deeplynx-server's host port")
    parser.add_argument("--timeout", type=float, default=300, help="seconds to wait for the server")
    args = parser.parse_args()
    api = f"http://localhost:{args.port}/api/v1"

    if not ENV.exists():
        print(f"[ERROR] {ENV} does not exist; run make init-env first.", file=sys.stderr)
        return 1
    if not wait_healthy(api, args.timeout):
        print(f"[ERROR] DeepLynx didn't answer at {api}/health within {args.timeout:.0f}s.", file=sys.stderr)
        return 1

    init_env = _load_init_env()
    text = ENV.read_text()
    if configured(api, init_env.values(text)):
        print(f"DeepLynx is already set up in {ENV.name}.")
        return 0

    try:
        project_id = find_or_create_project(api)
        key, secret = create_key(api)
    except (RuntimeError, urllib.error.URLError, OSError) as e:
        print(f"[ERROR] Setting up DeepLynx at {api}: {e}", file=sys.stderr)
        return 1

    for var, value in {
        "DEEPLYNX_BASE_URL": INTERNAL_URL,
        "DEEPLYNX_KEY": key,
        "DEEPLYNX_SECRET": secret,
        "DEEPLYNX_JWT_TOKEN": "",
        "DEEPLYNX_ORG_ID": str(ORG_ID),
        "DEEPLYNX_PROJECT_ID": str(project_id),
        "DEEPLYNX_DATA_SOURCE_ID": "",
    }.items():
        text = init_env.set_var(text, var, value)
    ENV.write_text(text)
    print(f"Saved a new DeepLynx API key for project {project_id} in {ENV.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
