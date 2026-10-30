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

"""Unit tests for scripts/deeplynx_setup.py, against a stub DeepLynx API."""

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
API = "/api/v1"


def _load_deeplynx_setup():
    """Import scripts/deeplynx_setup.py as a module."""
    spec = importlib.util.spec_from_file_location("deeplynx_setup", SCRIPTS / "deeplynx_setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ds = _load_deeplynx_setup()


class StubDeepLynx(ThreadingHTTPServer):
    """The parts of the DeepLynx API the script uses, with an in-memory state."""

    def __init__(self):
        """Start healthy, with no projects or keys."""
        super().__init__(("127.0.0.1", 0), StubHandler)
        self.port = self.server_address[1]
        self.healthy = True
        self.projects: list[dict] = []
        self.keys: dict[str, str] = {}
        # Status to answer instead, by "METHOD path"
        self.fail: dict[str, int] = {}
        self.requests: list[str] = []

    @property
    def api(self) -> str:
        """The API base URL, as the script builds it."""
        return f"http://127.0.0.1:{self.port}{API}"


class StubHandler(BaseHTTPRequestHandler):
    """Answer the stub's routes from its state."""

    server: StubDeepLynx

    def _reply(self, status: int, body: object = None):
        """Send ``body`` as JSON with ``status``."""
        raw = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)

    def _route(self, method: str):
        """Dispatch a request to the matching route, or 404."""
        stub = self.server
        path = self.path.removeprefix(API)
        stub.requests.append(f"{method} {path}")
        if status := stub.fail.get(f"{method} {path}"):
            return self._reply(status)
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        projects = f"/organizations/{ds.ORG_ID}/projects"

        if method == "GET" and path == "/health":
            return self._reply(200, {"status": "healthy"}) if stub.healthy else self._reply(503)
        if method == "GET" and path == projects:
            return self._reply(200, stub.projects)
        if method == "POST" and path == projects:
            project = {"id": len(stub.projects) + 1, "name": body["name"], "isArchived": False}
            stub.projects.append(project)
            return self._reply(200, project)
        if method == "GET" and path.startswith(f"{projects}/"):
            pid = path.rsplit("/", 1)[1]
            if any(str(p["id"]) == pid for p in stub.projects):
                return self._reply(200, {"id": int(pid)})
            return self._reply(400)
        if method == "POST" and path == "/oauth/keys":
            key = f"key{len(stub.keys) + 1}"
            stub.keys[key] = f"secret{len(stub.keys) + 1}"
            return self._reply(200, {"apiKey": key, "apiSecret": stub.keys[key]})
        if method == "POST" and path == "/oauth/tokens":
            if stub.keys.get(body["apiKey"]) == body["apiSecret"]:
                return self._reply(200, "token")
            return self._reply(404)
        return self._reply(404)

    def do_GET(self):
        """Handle a GET."""
        self._route("GET")

    def do_POST(self):
        """Handle a POST."""
        self._route("POST")

    def log_message(self, *args):
        """Keep request logs out of the test output."""


@pytest.fixture
def stub():
    """A running StubDeepLynx."""
    server = StubDeepLynx()
    # A short poll interval keeps shutdown() from waiting the default 0.5s
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A .env with DeepLynx settings for another server, used by the script."""
    path = tmp_path / ".env"
    path.write_text(
        "OTHER=kept\n"
        "DEEPLYNX_BASE_URL=https://deeplynx.example.com/api/v1\n"
        "DEEPLYNX_KEY=\n"
        "DEEPLYNX_SECRET=\n"
        "DEEPLYNX_JWT_TOKEN=old-token\n"
        "DEEPLYNX_ORG_ID=\n"
        "DEEPLYNX_PROJECT_ID=\n"
        "#DEEPLYNX_DATA_SOURCE_ID=\n"
    )
    monkeypatch.setattr(ds, "ENV", path)
    return path


def _values(path: Path) -> dict[str, str]:
    """The assignments in an env file."""
    return ds._load_init_env().values(path.read_text())


def _run_main(monkeypatch, stub, *args):
    """Run main() against the stub, without waiting between polls; return its exit code."""
    monkeypatch.setattr(sys, "argv", ["deeplynx_setup.py", "--port", str(stub.port), "--timeout", "0.2", *args])
    monkeypatch.setattr(ds.time, "sleep", lambda _: None)
    return ds.main()


@pytest.fixture(autouse=True)
def _ipv4_localhost(monkeypatch):
    """Have main() reach the IPv4-only stub through 127.0.0.1, not localhost."""
    real = ds.request

    def request(method, url, body=None):
        """Call the real request() with localhost replaced."""
        return real(method, url.replace("://localhost:", "://127.0.0.1:"), body)

    monkeypatch.setattr(ds, "request", request)


def test_wait_healthy(stub):
    """True once the server reports healthy."""
    assert ds.wait_healthy(stub.api, 1, 0)


def test_wait_healthy_times_out(stub):
    """False when the server never reports healthy."""
    stub.healthy = False
    assert not ds.wait_healthy(stub.api, 0.2, 0.05)


def test_wait_healthy_without_a_server():
    """False when nothing listens, instead of raising."""
    assert not ds.wait_healthy("http://127.0.0.1:9/api/v1", 0.2, 0.05)


def test_find_or_create_project_creates_one(stub):
    """With no matching project, one named PROJECT_NAME is created."""
    assert ds.find_or_create_project(stub.api) == 1
    assert stub.projects[0]["name"] == ds.PROJECT_NAME


def test_find_or_create_project_reuses_one(stub):
    """An existing project with the name is reused, skipping archived ones."""
    stub.projects = [
        {"id": 1, "name": "Other", "isArchived": False},
        {"id": 2, "name": ds.PROJECT_NAME, "isArchived": True},
        {"id": 3, "name": ds.PROJECT_NAME, "isArchived": False},
    ]
    assert ds.find_or_create_project(stub.api) == 3
    assert f"POST /organizations/{ds.ORG_ID}/projects" not in stub.requests


@pytest.mark.parametrize("route", ["GET", "POST"])
def test_find_or_create_project_raises_on_errors(stub, route):
    """A failed list or create raises RuntimeError."""
    stub.fail[f"{route} /organizations/{ds.ORG_ID}/projects"] = 500
    with pytest.raises(RuntimeError, match="HTTP 500"):
        ds.find_or_create_project(stub.api)


def test_create_key(stub):
    """Returns the new key and secret."""
    assert ds.create_key(stub.api) == ("key1", "secret1")


def test_create_key_raises_on_errors(stub):
    """A failed request raises RuntimeError."""
    stub.fail["POST /oauth/keys"] = 500
    with pytest.raises(RuntimeError, match="HTTP 500"):
        ds.create_key(stub.api)


def _configured_env(stub, **overrides) -> dict[str, str]:
    """Settings for a valid key and project on the stub, with ``overrides``."""
    stub.projects = [{"id": 1, "name": ds.PROJECT_NAME, "isArchived": False}]
    stub.keys = {"key1": "secret1"}
    env = {
        "DEEPLYNX_BASE_URL": ds.INTERNAL_URL,
        "DEEPLYNX_KEY": "key1",
        "DEEPLYNX_SECRET": "secret1",
        "DEEPLYNX_PROJECT_ID": "1",
    }
    return {**env, **overrides}


def test_configured(stub):
    """True for this server's URL, a key it accepts and a project that exists."""
    assert ds.configured(stub.api, _configured_env(stub))
    # A trailing slash is the same URL
    assert ds.configured(stub.api, _configured_env(stub, DEEPLYNX_BASE_URL=ds.INTERNAL_URL + "/"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"DEEPLYNX_BASE_URL": "https://deeplynx.example.com/api/v1"},
        {"DEEPLYNX_KEY": ""},
        {"DEEPLYNX_SECRET": "wrong"},
        {"DEEPLYNX_PROJECT_ID": "2"},
    ],
    ids=["other server", "no key", "rejected key", "missing project"],
)
def test_not_configured(stub, overrides):
    """False when any part of the settings doesn't work on this server."""
    assert not ds.configured(stub.api, _configured_env(stub, **overrides))


def test_main_sets_up_env(monkeypatch, stub, env):
    """Creates a project and key and writes every DeepLynx setting to .env."""
    assert _run_main(monkeypatch, stub) == 0
    values = _values(env)
    assert values["DEEPLYNX_BASE_URL"] == ds.INTERNAL_URL
    assert (values["DEEPLYNX_KEY"], values["DEEPLYNX_SECRET"]) == ("key1", "secret1")
    assert values["DEEPLYNX_ORG_ID"] == str(ds.ORG_ID)
    assert values["DEEPLYNX_PROJECT_ID"] == "1"
    assert values["DEEPLYNX_JWT_TOKEN"] == ""
    assert values["DEEPLYNX_DATA_SOURCE_ID"] == ""
    assert values["OTHER"] == "kept"


def test_main_keeps_a_working_setup(monkeypatch, stub, env):
    """A second run leaves .env as it is and creates no new key or project."""
    assert _run_main(monkeypatch, stub) == 0
    before = env.read_text()
    assert _run_main(monkeypatch, stub) == 0
    assert env.read_text() == before
    assert len(stub.keys) == 1
    assert len(stub.projects) == 1


def test_main_replaces_a_stale_key(monkeypatch, stub, env):
    """After the DeepLynx data is gone, a new key and project are saved."""
    assert _run_main(monkeypatch, stub) == 0
    stub.keys.clear()
    stub.projects.clear()
    stub.requests.clear()
    assert _run_main(monkeypatch, stub) == 0
    assert "POST /oauth/keys" in stub.requests
    assert f"POST /organizations/{ds.ORG_ID}/projects" in stub.requests
    values = _values(env)
    assert stub.keys == {values["DEEPLYNX_KEY"]: values["DEEPLYNX_SECRET"]}


def test_main_without_env_file(monkeypatch, stub, tmp_path, capsys):
    """Fails without touching DeepLynx when .env doesn't exist."""
    monkeypatch.setattr(ds, "ENV", tmp_path / "missing.env")
    assert _run_main(monkeypatch, stub) == 1
    assert "make init-env" in capsys.readouterr().err
    assert stub.requests == []


def test_main_when_unhealthy(monkeypatch, stub, env, capsys):
    """Fails and leaves .env alone when the server never reports healthy."""
    stub.healthy = False
    before = env.read_text()
    assert _run_main(monkeypatch, stub) == 1
    assert "didn't answer" in capsys.readouterr().err
    assert env.read_text() == before


def test_main_on_api_errors(monkeypatch, stub, env, capsys):
    """Fails and leaves .env alone when DeepLynx refuses a key."""
    stub.fail["POST /oauth/keys"] = 500
    before = env.read_text()
    assert _run_main(monkeypatch, stub) == 1
    assert "HTTP 500" in capsys.readouterr().err
    assert env.read_text() == before
