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
from flepimop2.configuration import ConfigurationModel
from flepimop2.exceptions import Flepimop2ValidationError
from flepimop2.process.abc import build
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
p.add_argument('--repeat', type=int, default=1)
a = p.parse_args()
text = ''.join(Path(source).read_text() for source in a.source)
text = text.upper() if a.uppercase else text
Path(a.target).write_text(text * a.repeat)
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


def test_transform_converts_numeric_configuration_arguments(tmp_path: Path) -> None:
    """Numeric values reused from YAML configuration become script arguments."""
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    target = tmp_path / "target.txt"
    process = TransformProcess(
        sources=[source],
        script=_script(tmp_path / "transform.py"),
        args=["--repeat", 2],
        target=target,
    )

    process.execute()

    assert target.read_text(encoding="utf-8") == "hellohello"


def test_transform_reuses_fixed_parameter_through_yaml_anchor() -> None:
    """A YAML anchor can pass a static parameter value into script arguments."""
    config = ConfigurationModel.safe_load("""
parameters:
  missingness_cutoff: &missingness_cutoff 0.15
process:
  clean_observations:
    module: transform
    sources: [.cache/raw.csv]
    script: ./clean.py
    args: [--max-missing, *missingness_cutoff]
    target: .cache/clean.csv
""")

    process = build(config.process["clean_observations"])

    assert isinstance(process, TransformProcess)
    assert process.args == ["--max-missing", 0.15]


@pytest.mark.parametrize(
    ("force", "expected"),
    [
        (False, "would skip transform; target already exists"),
        (True, "would replace existing transform target"),
    ],
)
def test_transform_dry_run_reports_force_decision_for_existing_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    force: bool,
    expected: str,
) -> None:
    """Dry-run mirrors the selected skip or replace behavior."""
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text("cached", encoding="utf-8")
    process = TransformProcess(
        sources=[source], script=_script(tmp_path / "transform.py"), target=target
    )

    process.execute(dry_run=True, force=force)

    captured = capsys.readouterr().out
    assert expected in captured
    assert ("would run:" in captured) is force
    assert target.read_text(encoding="utf-8") == "cached"
