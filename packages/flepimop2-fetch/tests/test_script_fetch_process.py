# flepimop2-fetch: Cached fetch process providers for flepimop2
# Copyright (C) 2026  Carl Pearson, Joshua Macdonald, Timothy Willard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""Tests for the script-driven fetch specialization."""

import stat
from pathlib import Path

import pytest
from flepimop2.exceptions import Flepimop2ValidationError
from flepimop2.process.abc import build
from flepimop2.process.script_fetch import ScriptFetchProcess
from pydantic import ValidationError


def _script(path: Path) -> Path:
    """Create an executable custom fetcher.

    Returns:
        The executable script path.
    """
    path.write_text(
        """#!/usr/bin/env python3
import argparse
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--prefix', required=True)
p.add_argument('--source', required=True)
p.add_argument('--target', required=True)
a = p.parse_args()
Path(a.target).write_text(f'{a.prefix}:{a.source}')
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_script_fetches_non_http_source_with_structured_arguments(
    tmp_path: Path,
) -> None:
    """The script specialization receives controlled source and target options."""
    target = tmp_path / "artifact.txt"
    process = ScriptFetchProcess(
        source="s3://example-bucket/item",
        script=_script(tmp_path / "fetch.py"),
        args=["--prefix", 42],
        target=target,
    )

    process.execute()

    assert target.read_text(encoding="utf-8") == "42:s3://example-bucket/item"


def test_script_fetch_builds_from_its_own_module(tmp_path: Path) -> None:
    """Dynamic module loading selects the script specialization explicitly."""
    process = build({
        "module": "script_fetch",
        "source": "custom:item",
        "script": _script(tmp_path / "fetch.py"),
        "target": tmp_path / "artifact.txt",
    })

    assert isinstance(process, ScriptFetchProcess)


def test_script_fetch_rejects_url_only_hash_option(tmp_path: Path) -> None:
    """Content verification policy remains with the URL specialization."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ScriptFetchProcess.model_validate({
            "source": "custom:item",
            "script": _script(tmp_path / "fetch.py"),
            "sha256": "0" * 64,
            "target": tmp_path / "artifact.txt",
        })


def test_script_fetch_validates_executable_before_running(tmp_path: Path) -> None:
    """A script must be executable before it receives provider-owned arguments."""
    script = tmp_path / "fetch.py"
    script.write_text("", encoding="utf-8")
    process = ScriptFetchProcess(
        source="custom:item",
        script=script,
        target=tmp_path / "artifact.txt",
    )

    with pytest.raises(Flepimop2ValidationError, match="script is not executable"):
        process.execute()
