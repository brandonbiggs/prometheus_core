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

"""Static checks of .github/dependabot.yml against the repository."""

import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.fixture(scope="module")
def repo_root(project_root: Path) -> Path:
    """The repository root, one level above platform/."""
    return project_root.parent


@pytest.fixture(scope="module")
def dependabot_uv_dirs(repo_root: Path) -> list[str]:
    """Every directory listed in a uv entry of dependabot.yml, in order."""
    config = yaml.safe_load((repo_root / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    dirs = []
    for update in config["updates"]:
        if update["package-ecosystem"] == "uv":
            dirs += update.get("directories", [update.get("directory")])
    return dirs


def test_dependabot_lists_every_uv_lock(repo_root: Path, dependabot_uv_dirs: list[str]):
    """Each tracked uv.lock's directory is in exactly one uv entry, and nothing else is."""
    out = subprocess.run(
        ["git", "ls-files", "--", "uv.lock", "*/uv.lock"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    lock_dirs = {"/" + str(Path(name).parent).removeprefix(".") for name in out.splitlines()}
    assert lock_dirs, "No tracked uv.lock files found"

    duplicates = sorted({d for d in dependabot_uv_dirs if dependabot_uv_dirs.count(d) > 1})
    assert not duplicates, f"Listed more than once in dependabot.yml: {duplicates}"
    missing = sorted(lock_dirs - set(dependabot_uv_dirs))
    assert not missing, f"Has a uv.lock but isn't in dependabot.yml's uv entries: {missing}"
    stale = sorted(set(dependabot_uv_dirs) - lock_dirs)
    assert not stale, f"In dependabot.yml's uv entries but has no uv.lock: {stale}"
