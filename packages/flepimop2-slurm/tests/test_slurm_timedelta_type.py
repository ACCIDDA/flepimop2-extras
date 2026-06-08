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
"""Tests for the `SlurmTimedelta` type used in the `flepimop2.job.slurm` provider."""

from datetime import timedelta

import pytest
from flepimop2.job.slurm._slurm_timedelta import SlurmTimedelta
from pydantic import TypeAdapter, ValidationError


@pytest.mark.parametrize(
    ("value", "expected", "serialized"),
    [
        ("0", timedelta(0), "0-00:00:00"),
        ("5", timedelta(minutes=5), "0-00:05:00"),
        ("1:02", timedelta(minutes=1, seconds=2), "0-00:01:02"),
        ("2:03:04", timedelta(hours=2, minutes=3, seconds=4), "0-02:03:04"),
        ("1-02", timedelta(days=1, hours=2), "1-02:00:00"),
        ("1-02:03", timedelta(days=1, hours=2, minutes=3), "1-02:03:00"),
        ("1-02:03:04", timedelta(days=1, hours=2, minutes=3, seconds=4), "1-02:03:04"),
    ],
)
def test_slurm_timedelta_parses_and_serializes(
    value: str,
    expected: timedelta,
    serialized: str,
) -> None:
    """`SlurmTimedelta` validates, normalizes, and serializes Slurm time strings."""
    adapter = TypeAdapter(SlurmTimedelta)
    assert adapter.validate_python(value) == expected
    assert adapter.dump_python(expected) == serialized


@pytest.mark.parametrize(
    "value",
    ["abc", "1:2:3:4", "1--2", "1-2:3:4:5", "-1", ""],
)
def test_slurm_timedelta_rejects_invalid_values(value: str) -> None:
    """`SlurmTimedelta` rejects invalid Slurm time strings."""
    with pytest.raises(ValidationError, match="Invalid Slurm time specification"):
        TypeAdapter(SlurmTimedelta).validate_python(value)


def test_slurm_timedelta_rejects_fractional_seconds() -> None:
    """`SlurmTimedelta` rejects timedeltas with fractional seconds."""
    with pytest.raises(ValidationError, match="whole-second precision"):
        TypeAdapter(SlurmTimedelta).validate_python(
            timedelta(seconds=1, microseconds=1)
        )
