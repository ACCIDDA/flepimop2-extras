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
"""Command list utilities for Slurm job submission."""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator


def _validate_command_list(commands: object) -> object:
    """Normalize a Slurm command list.

    Args:
        commands: The command list value to validate.

    Returns:
        A one-item list if `commands` is a string, otherwise the original value.

    Examples:
        >>> _validate_command_list("echo hello")
        ['echo hello']
        >>> _validate_command_list(["echo hello", "echo goodbye"])
        ['echo hello', 'echo goodbye']
    """
    if isinstance(commands, str):
        return [commands]
    return commands


CommandList = Annotated[list[str], BeforeValidator(_validate_command_list)]
