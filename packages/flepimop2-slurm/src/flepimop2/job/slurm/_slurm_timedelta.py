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
"""Slurm time utilities for Slurm job submission."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, PlainSerializer

_SECONDS_PER_DAY = 86_400
_SECONDS_PER_HOUR = 3_600
_SLURM_TIME_REGEX = re.compile(
    r"""
    ^
    (?:
        (?P<days>\d+)-(?:
            (?P<day_hours>\d+)
            (?:
                :(?P<day_minutes>\d+)
                (?:
                    :(?P<day_seconds>\d+)
                )?
            )?
        )
        |
        (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+)
        |
        (?P<minutes_only>\d+):(?P<seconds_only>\d+)
        |
        (?P<minutes_scalar>\d+)
    )
    $
    """,
    re.VERBOSE,
)


def _required_group(match: re.Match[str], name: str, value: str) -> str:
    """Extract a required regex group.

    Args:
        match: The Slurm time regex match.
        name: The group name to extract.
        value: The original Slurm time string, used for error reporting.

    Returns:
        The regex group value.

    Raises:
        ValueError: If the group is unexpectedly missing.
    """
    group = match.group(name)
    if group is None:
        msg = f"Invalid Slurm time specification: {value!r}"
        raise ValueError(msg)
    return group


def _match_to_timedelta(match: re.Match[str], value: str) -> timedelta:
    """Convert a Slurm time regex match into a `timedelta`.

    Args:
        match: The Slurm time regex match.
        value: The original Slurm time string, used for error reporting.

    Returns:
        The parsed `timedelta`.
    """
    if (days := match.group("days")) is not None:
        return timedelta(
            days=int(days),
            hours=int(_required_group(match, "day_hours", value)),
            minutes=int(match.group("day_minutes") or 0),
            seconds=int(match.group("day_seconds") or 0),
        )

    if (hours := match.group("hours")) is not None:
        return timedelta(
            hours=int(hours),
            minutes=int(_required_group(match, "minutes", value)),
            seconds=int(_required_group(match, "seconds", value)),
        )

    if (minutes := match.group("minutes_only")) is not None:
        return timedelta(
            minutes=int(minutes),
            seconds=int(_required_group(match, "seconds_only", value)),
        )

    return timedelta(minutes=int(_required_group(match, "minutes_scalar", value)))


def _parse_slurm_timedelta(value: object) -> timedelta:
    """Parse a Slurm `--time` specification into a `timedelta`.

    Args:
        value: The Slurm time string to parse, or an existing `timedelta`.

    Returns:
        The parsed `timedelta`.

    Raises:
        ValueError: If `value` does not match a supported Slurm time format.

    Examples:
        >>> _parse_slurm_timedelta("5")
        datetime.timedelta(seconds=300)
        >>> _parse_slurm_timedelta("1:02")
        datetime.timedelta(seconds=62)
        >>> _parse_slurm_timedelta("2:03:04")
        datetime.timedelta(seconds=7384)
        >>> _parse_slurm_timedelta("1-02")
        datetime.timedelta(days=1, seconds=7200)
        >>> _parse_slurm_timedelta("1-02:03")
        datetime.timedelta(days=1, seconds=7380)
        >>> _parse_slurm_timedelta("1-02:03:04")
        datetime.timedelta(days=1, seconds=7384)
        >>> _parse_slurm_timedelta(timedelta(minutes=7))
        datetime.timedelta(seconds=420)
        >>> _parse_slurm_timedelta(60)
        datetime.timedelta(seconds=3600)
        >>> _parse_slurm_timedelta("invalid")
        Traceback (most recent call last):
            ...
        ValueError: Invalid Slurm time specification: 'invalid'
    """
    if isinstance(value, timedelta):
        return value
    value = str(value)
    match = _SLURM_TIME_REGEX.fullmatch(value)
    if match is None:
        msg = f"Invalid Slurm time specification: {value!r}"
        raise ValueError(msg)
    return _match_to_timedelta(match, value)


def _validate_whole_seconds(value: timedelta) -> timedelta:
    """Ensure the `timedelta` has whole-second precision.

    Args:
        value: The `timedelta` to validate.

    Returns:
        The same `timedelta` if it is non-negative and has no microseconds.

    Raises:
        ValueError: If `value` is negative.
        ValueError: If `value` contains a fractional-second component.

    Examples:
        >>> _validate_whole_seconds(timedelta(minutes=5))
        datetime.timedelta(seconds=300)
        >>> _validate_whole_seconds(timedelta(seconds=1, microseconds=1))
        Traceback (most recent call last):
            ...
        ValueError: SlurmTimedelta requires whole-second precision
    """
    if value < timedelta(0):
        msg = "SlurmTimedelta cannot be negative"
        raise ValueError(msg)
    if value.microseconds != 0:
        msg = "SlurmTimedelta requires whole-second precision"
        raise ValueError(msg)
    return value


def _format_slurm_timedelta(value: timedelta) -> str:
    """Format a `timedelta` in canonical Slurm `--time` form.

    Args:
        value: The time delta to format.

    Returns:
        A canonical Slurm `--time` string in `days-hours:minutes:seconds` form.

    Raises:
        ValueError: If `value` is negative or contains fractional seconds.

    Examples:
        >>> _format_slurm_timedelta(timedelta(minutes=5))
        '0-00:05:00'
        >>> _format_slurm_timedelta(timedelta(seconds=30))
        '0-00:00:30'
        >>> _format_slurm_timedelta(timedelta(hours=1, minutes=2))
        '0-01:02:00'
        >>> _format_slurm_timedelta(timedelta(hours=1, minutes=2, seconds=3))
        '0-01:02:03'
        >>> _format_slurm_timedelta(timedelta(days=1, hours=2))
        '1-02:00:00'
        >>> _format_slurm_timedelta(timedelta(days=1, hours=2, minutes=3))
        '1-02:03:00'
        >>> _format_slurm_timedelta(
        ...     timedelta(days=1, hours=2, minutes=3, seconds=4)
        ... )
        '1-02:03:04'
    """
    if value < timedelta(0):
        msg = "SlurmTimedelta cannot be negative"
        raise ValueError(msg)
    if value.microseconds != 0:
        msg = "SlurmTimedelta requires whole-second precision"
        raise ValueError(msg)

    total_seconds = value.days * _SECONDS_PER_DAY + value.seconds
    days, remainder = divmod(total_seconds, _SECONDS_PER_DAY)
    hours, remainder = divmod(remainder, _SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}-{hours:02d}:{minutes:02d}:{seconds:02d}"


SlurmTimedelta = Annotated[
    timedelta,
    BeforeValidator(_parse_slurm_timedelta),
    AfterValidator(_validate_whole_seconds),
    PlainSerializer(_format_slurm_timedelta, return_type=str),
]
