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
"""Memory string utilities for Slurm job submission."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator

_MEMORY_STR_REGEX = re.compile(
    r"^(?P<amount>\d+(?:\.\d+)?)(?P<unit>[KMGTPE])?$",
    re.IGNORECASE,
)


def _validate_memory_str(memory: object) -> str:
    """Validate and normalize a Slurm memory string.

    Slurm accepts memory specifications in the form of an integer or decimal
    followed by an optional unit suffix. Valid units are `K`, `M`, `G`, `T`,
    `P`, and `E` and are treated case-insensitively.

    Args:
        memory: The memory specification to validate.

    Returns:
        The validated and normalized memory specification.

    Raises:
        ValueError: If `memory` is not a valid Slurm memory specification.

    Examples:
        >>> _validate_memory_str("4G")
        '4G'
        >>> _validate_memory_str("1024")
        '1024M'
        >>> _validate_memory_str("2.5T")
        '2.5T'
        >>> _validate_memory_str("500m")
        '500M'
        >>> _validate_memory_str("1P")
        '1P'
        >>> _validate_memory_str(123.45)
        '123.45M'
        >>> _validate_memory_str("invalid")
        Traceback (most recent call last):
            ...
        ValueError: Invalid memory specification: 'invalid'
    """
    match = _MEMORY_STR_REGEX.fullmatch(str(memory))
    if match is None:
        msg = f"Invalid memory specification: {memory!r}"
        raise ValueError(msg)
    amount = match.group("amount")
    unit = match.group("unit") or "M"
    return f"{amount}{unit.upper()}"


MemoryStr = Annotated[str, BeforeValidator(_validate_memory_str)]
