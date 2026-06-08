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
"""Tests for the `MemoryStr` type used in the `flepimop2.job.slurm` provider."""

import pytest
from flepimop2.job.slurm._memory_str import MemoryStr
from pydantic import TypeAdapter


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123G", "123G"),
        ("1.2t", "1.2T"),
        ("512", "512M"),
    ],
)
def test_memory_str_normalizes_unit_case(value: str, expected: str) -> None:
    """`MemoryStr` validates and normalizes Slurm memory strings."""
    assert TypeAdapter(MemoryStr).validate_python(value) == expected
