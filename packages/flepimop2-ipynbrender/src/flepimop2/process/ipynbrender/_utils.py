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
from shutil import which


def _which_jupyter() -> str:
    """
    Find the 'jupyter' executable in the system PATH.

    Returns:
        The absolute path to the 'jupyter' executable as a string.

    Raises:
        FileNotFoundError: If 'jupyter' is not found in the system PATH.
    """
    jupyter = which("jupyter")
    if jupyter is None:
        msg = "jupyter executable not found in PATH"
        raise FileNotFoundError(msg)
    return jupyter
