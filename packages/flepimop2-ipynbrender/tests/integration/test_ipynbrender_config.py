# flepimop2-slurm: A Slurm job provider for flepimop2
# Copyright (C) 2026  Carl Pearson, Joshua Macdonald, Timothy Willard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Integration tests for 'ipynbrender' module via the `flepimop2 process` CLI."""

import shutil
import subprocess  # noqa: S404
from pathlib import Path
from shutil import which

import pytest


@pytest.mark.parametrize("output", ["test.html", "example.html"])
def test_run_nb_from_config(tmp_path: Path, output: str) -> None:
    """Test running the 'ipynbrender' module."""
    # Copy test files to temporary directory and find flepimop2 executable
    integration_dir = Path(__file__).parent
    shutil.copy(integration_dir / "test.ipynb", tmp_path / "test.ipynb")
    (tmp_path / "config.yaml").write_text(
        f"""
---
process:
  run_nb:
    module: 'ipynbrender'
    file: 'test.ipynb'
    output: '{output}'
""",
        encoding="utf-8",
    )
    output_path = tmp_path / output
    flepimop2 = which("flepimop2")
    # Ensure flepimop2 is found
    assert isinstance(flepimop2, str)
    assert not output_path.exists()
    # Run flepimop2 process command with dry run
    first_result = subprocess.run(  # noqa: S603
        [flepimop2, "process", "--dry-run", "--target", "run_nb", "config.yaml"],
        check=False,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    # Check that the dry run process completed successfully
    assert first_result.returncode == 0
    assert not output_path.exists()
    # Run flepimop2 process command
    second_result = subprocess.run(  # noqa: S603
        [flepimop2, "process", "--target", "run_nb", "config.yaml"],
        check=False,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    # Check that the process completed successfully
    assert second_result.returncode == 0
    assert output_path.exists()
