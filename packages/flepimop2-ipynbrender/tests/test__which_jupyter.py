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
"""Unit tests for `_which_jupyter` internal utility."""

import pytest
from flepimop2.process.ipynbrender._utils import _which_jupyter


@pytest.mark.parametrize("jupyter", ["/path/to/jupyter"])
def test_which_jupyter_found(monkeypatch: pytest.MonkeyPatch, jupyter: str) -> None:
    """Test that `_which_jupyter` returns the correct path when jupyter is found."""
    monkeypatch.setattr(
        "flepimop2.process.ipynbrender._utils.which",
        lambda name: jupyter,  # noqa: ARG005
    )
    assert _which_jupyter() == jupyter


def test_which_jupyter_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `_which_jupyter` raises FileNotFoundError when jupyter is not found."""
    monkeypatch.setattr("flepimop2.process.ipynbrender._utils.which", lambda name: None)  # noqa: ARG005
    with pytest.raises(
        FileNotFoundError, match=r"^jupyter executable not found in PATH$"
    ):
        _which_jupyter()
