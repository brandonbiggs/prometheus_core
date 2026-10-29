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

"""Check that every tracked Dockerfile and compose file pins its images by digest.

A pinned image ends in ``@sha256:`` and 64 hex digits, such as
``node:22.19.0-bookworm-slim@sha256:...``. Keep the tag in front so Dependabot
can update both. Not checked:

- ``FROM`` an earlier stage of the same Dockerfile, or ``scratch``
- an image built from variables, such as the agents'
  ``${PROMETHEUS_API_BASE_IMAGE_REPO}:${PROMETHEUS_API_BASE_IMAGE_HASH}``

    check_image_pins.py   # list unpinned images, exit 1 if there are any

Standard library only. Run from anywhere inside the repository.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

DOCKERFILES = ["*Dockerfile", "*Dockerfile.*", "*.Dockerfile"]
COMPOSE_FILES = ["*docker-compose*.yml", "*docker-compose*.yaml", "*compose.yml", "*compose.yaml"]
EXCLUDE = [
    # Syntax-highlighting fixtures for the code-render agent, not real files
    "platform/agents/debug-agents/code-render-debug-agent/samples/*",
]

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
# FROM [--flag=value ...] image [AS name]
FROM = re.compile(r"^\s*FROM\s+((?:--\S+\s+)*)(\S+)(?:\s+AS\s+(\S+))?\s*$", re.IGNORECASE)
# image: name, optionally quoted, ignoring a trailing comment
IMAGE = re.compile(r"""^\s*image:\s*["']?([^"'\s#]+)["']?\s*(?:#.*)?$""")


def is_pinned(image: str) -> bool:
    """Whether ``image`` ends in a digest, or is built from variables and can't be checked."""
    return "$" in image or DIGEST.search(image) is not None


def check_dockerfile(text: str) -> list[tuple[int, str]]:
    """Return the line number and image of each unpinned ``FROM`` in a Dockerfile."""
    stages: set[str] = set()
    unpinned = []
    for number, line in enumerate(text.splitlines(), 1):
        match = FROM.match(line)
        if not match:
            continue
        image, stage = match.group(2), match.group(3)
        if image.lower() not in stages and image != "scratch" and not is_pinned(image):
            unpinned.append((number, image))
        if stage:
            stages.add(stage.lower())
    return unpinned


def check_compose(text: str) -> list[tuple[int, str]]:
    """Return the line number and image of each unpinned ``image:`` in a compose file."""
    unpinned = []
    for number, line in enumerate(text.splitlines(), 1):
        match = IMAGE.match(line)
        if match and not is_pinned(match.group(1)):
            unpinned.append((number, match.group(1)))
    return unpinned


def tracked_files(root: Path) -> list[str]:
    """Return the repository's tracked files, relative to ``root``, minus ``EXCLUDE``."""
    out = subprocess.run(["git", "ls-files"], cwd=root, check=True, capture_output=True, text=True)
    return [name for name in out.stdout.splitlines() if not any(fnmatch.fnmatch(name, p) for p in EXCLUDE)]


def matches(name: str, patterns: list[str]) -> bool:
    """Whether the file name at the end of ``name`` matches any of ``patterns``."""
    base = name.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(base, pattern) for pattern in patterns)


def main(argv: list[str] | None = None) -> int:
    """Check every tracked Dockerfile and compose file; return 1 if any image is unpinned."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args(argv)

    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    checked = 0
    unpinned = []
    for name in tracked_files(root):
        if matches(name, DOCKERFILES):
            check = check_dockerfile
        elif matches(name, COMPOSE_FILES):
            check = check_compose
        else:
            continue
        checked += 1
        text = (root / name).read_text(encoding="utf-8")
        unpinned += [(name, number, image) for number, image in check(text)]

    if checked == 0:
        print("No Dockerfiles or compose files found", file=sys.stderr)
        return 1
    for name, number, image in unpinned:
        print(f"{name}:{number}: {image}")
    if unpinned:
        print(
            f"{len(unpinned)} image(s) aren't pinned by digest; add @sha256:<digest> after the tag",
            file=sys.stderr,
        )
        return 1
    print(f"Checked {checked} file(s); every image is pinned by digest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
