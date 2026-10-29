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

"""Tests for platform/scripts/check_image_pins.py."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_image_pins.py"
DIGEST = "@sha256:" + "0" * 64


@pytest.fixture(scope="module")
def pins():
    """The check_image_pins script, imported as a module."""
    spec = importlib.util.spec_from_file_location("check_image_pins", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dockerfile_flags_unpinned_images(pins):
    """A tag alone, a short digest, or a lowercase from all fail."""
    text = "\n".join(
        [
            "FROM node:22 AS base",
            "from python:3.12",
            f"FROM nginx:1.31.8-alpine@sha256:{'0' * 63}",
            "FROM --platform=linux/amd64 nginx:alpine AS prod",
        ]
    )
    assert pins.check_dockerfile(text) == [
        (1, "node:22"),
        (2, "python:3.12"),
        (3, f"nginx:1.31.8-alpine@sha256:{'0' * 63}"),
        (4, "nginx:alpine"),
    ]


def test_dockerfile_allows_pins_stages_scratch_and_variables(pins):
    """Digests, earlier stages, scratch, variables, and comments all pass."""
    text = "\n".join(
        [
            f"FROM node:22.19.0-bookworm-slim{DIGEST} AS base",
            "FROM base AS deps",
            "FROM DEPS AS build",
            f"FROM --platform=linux/amd64 nginx:1.31.8-alpine{DIGEST} AS prod",
            "FROM scratch",
            "FROM ${PROMETHEUS_API_BASE_IMAGE_REPO}:${PROMETHEUS_API_BASE_IMAGE_HASH}",
            "# FROM python:3.12",
        ]
    )
    assert pins.check_dockerfile(text) == []


def test_dockerfile_stage_must_be_defined_first(pins):
    """A stage name used before its AS counts as an unpinned image."""
    assert pins.check_dockerfile("FROM later\nFROM python:3.12 AS later") == [(1, "later"), (2, "python:3.12")]


def test_compose_flags_unpinned_images(pins):
    """Plain and quoted tags without a digest fail."""
    text = "\n".join(
        [
            "services:",
            "  a:",
            "    image: postgres:16-alpine",
            "  b:",
            '    image: "valkey/valkey-bundle:9.1.0"  # quoted',
        ]
    )
    assert pins.check_compose(text) == [(3, "postgres:16-alpine"), (5, "valkey/valkey-bundle:9.1.0")]


def test_compose_allows_pins_and_variables(pins):
    """Digests, plain or quoted, variables, and comments all pass."""
    text = "\n".join(
        [
            "services:",
            "  a:",
            f"    image: postgres:16.15-alpine{DIGEST}",
            "  b:",
            f"    image: 'ghcr.io/berriai/litellm:v1.92.0{DIGEST}'",
            "  c:",
            "    image: ${AGENT_IMAGE}",
            "    # image: commented:out",
        ]
    )
    assert pins.check_compose(text) == []


def test_repository_images_are_pinned(pins):
    """Every image in the repository's tracked files is pinned."""
    assert pins.main([]) == 0
