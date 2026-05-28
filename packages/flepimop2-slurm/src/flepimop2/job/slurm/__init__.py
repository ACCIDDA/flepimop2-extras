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
"""Slurm job provider for flepimop2.

This module contributes the `slurm` job module to the `flepimop2.job`
namespace, allowing flepimop2 configurations to reference `module: 'slurm'`
to submit jobs to Slurm-managed HPC clusters.
"""

from typing import Any


class SlurmJob:
    """Submit and manage flepimop2 jobs on a Slurm HPC cluster.

    Warning:
        This is a placeholder. The implementation is not yet written.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a `SlurmJob`.

        Raises:
            NotImplementedError: Always, until the provider is implemented.
        """
        raise NotImplementedError


__all__ = ["SlurmJob"]
