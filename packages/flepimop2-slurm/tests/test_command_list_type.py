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
"""Tests for the `CommandList` type used in the `flepimop2.job.slurm` provider."""

import pytest
from flepimop2.job.slurm._command_list import CommandList
from pydantic import TypeAdapter, ValidationError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("echo hello", ["echo hello"]),
        (
            "if [ -f foo ]; then\n  echo found\nfi",
            ["if [ -f foo ]; then\n  echo found\nfi"],
        ),
        (["echo hello", "echo goodbye"], ["echo hello", "echo goodbye"]),
    ],
)
def test_command_list_accepts_string_or_list(
    value: object, expected: list[str]
) -> None:
    """`CommandList` accepts a single command string or a command list."""
    assert TypeAdapter(CommandList).validate_python(value) == expected


@pytest.mark.parametrize("value", [1, ["echo hello", 1]])
def test_command_list_rejects_invalid_values(value: object) -> None:
    """`CommandList` rejects non-string commands."""
    with pytest.raises(ValidationError):
        TypeAdapter(CommandList).validate_python(value)
