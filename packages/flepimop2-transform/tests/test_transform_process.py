# flepimop2-transform: A cached transform process provider for flepimop2
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
"""Tests for the cached transform process."""

import stat
from pathlib import Path

import pytest
from flepimop2.exceptions import Flepimop2ValidationError
from flepimop2.process.transform import TransformProcess


def _script(path: Path) -> Path:
    """Write a tiny executable transform fixture.

    Returns:
        The executable script path.
    """
    path.write_text(
        """#!/usr/bin/env python3
import argparse
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--source', action='append', required=True)
p.add_argument('--target', required=True)
p.add_argument('--uppercase', action='store_true')
a = p.parse_args()
text = ''.join(Path(source).read_text() for source in a.source)
Path(a.target).write_text(text.upper() if a.uppercase else text)
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_transform_materializes_and_skips_target(tmp_path: Path) -> None:
    """A transform writes its target once and then becomes a no-op."""
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    target = tmp_path / "target.txt"
    process = TransformProcess(
        sources=[source], script=_script(tmp_path / "transform.py"), target=target
    )
    process.execute()
    source.write_text("changed", encoding="utf-8")
    process.execute()
    assert target.read_text(encoding="utf-8") == "hello"


def test_transform_force_warns_and_replaces_target(tmp_path: Path) -> None:
    """A forced transform warns and replaces its target."""
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text("old", encoding="utf-8")
    process = TransformProcess(
        sources=[source],
        script=_script(tmp_path / "transform.py"),
        args=["--uppercase"],
        target=target,
    )
    with pytest.warns(RuntimeWarning, match="replacing existing transform target"):
        process.execute(force=True)
    assert target.read_text(encoding="utf-8") == "HELLO"


def test_transform_rejects_missing_source(tmp_path: Path) -> None:
    """Missing inputs fail before the script is invoked."""
    process = TransformProcess(
        sources=[tmp_path / "missing.txt"],
        script=_script(tmp_path / "transform.py"),
        target=tmp_path / "target.txt",
    )
    with pytest.raises(Flepimop2ValidationError, match="source does not exist"):
        process.execute()


def test_transform_dry_run_does_not_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run reports the structured command without writing."""
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    target = tmp_path / "target.txt"
    process = TransformProcess(
        sources=[source], script=_script(tmp_path / "transform.py"), target=target
    )
    process.execute(dry_run=True)
    assert not target.exists()
    assert f"--source {source} --target {target}" in capsys.readouterr().out
