# flepimop2-fetch: Cached fetch process providers for flepimop2
# Copyright (C) 2026  Carl Pearson, Joshua Macdonald, Timothy Willard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""Cached script-driven fetch process for flepimop2."""

__all__ = ["ScriptFetchProcess"]

import os
import shlex
import subprocess  # noqa: S404
import tempfile
from pathlib import Path
from typing import TypeAlias

from flepimop2.exceptions import ValidationIssue
from flepimop2.process.fetch.abc import FetchProcessABC
from pydantic import Field

Argument: TypeAlias = str | int | float


class ScriptFetchProcess(FetchProcessABC, module="script_fetch"):
    """Delegate source-specific fetching to an executable script.

    The provider controls the final two positional arguments passed to the
    script: `<source> <temporary-path>`. The script owns source validation and
    must create the temporary target before returning success.

    Attributes:
        source: Identifier understood by `script`.
        script: Executable implementing the custom fetch.
        args: Literal arguments passed before the provider-owned positions.
        target: Local file the process promises to materialize.
    """

    source: str = Field(min_length=1)
    script: Path
    args: list[Argument] = Field(default_factory=list)

    def _command(self, target: Path) -> list[str]:
        """Build the controlled script command for a target path.

        Args:
            target: Path the script must materialize.

        Returns:
            The executable and its complete argument vector.
        """
        return [
            str(self.script),
            *(str(argument) for argument in self.args),
            self.source,
            str(target),
        ]

    def _process_validate(self) -> list[ValidationIssue] | None:
        """Validate the executable and destination without invoking the script.

        Returns:
            Validation issues, or `None` when local execution is possible.
        """
        issues = super()._process_validate() or []
        if not self.script.is_file():
            issues.append(
                ValidationIssue(
                    msg=f"fetch script does not exist: {self.script}",
                    kind="file_not_found",
                )
            )
        elif not os.access(self.script, os.X_OK):
            issues.append(
                ValidationIssue(
                    msg=f"fetch script is not executable: {self.script}",
                    kind="permission_denied",
                )
            )
        return issues or None

    def _process(self, *, dry_run: bool) -> None:
        """Run the script and atomically install the materialized target.

        Raises:
            RuntimeError: If the script does not materialize its temporary target.
        """
        if dry_run:
            print(f"would run: {shlex.join(self._command(self.target))}")  # noqa: T201
            return

        self.target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.target.parent,
                prefix=f".{self.target.name}.",
                suffix=".part",
                delete=False,
            ) as placeholder:
                temporary = Path(placeholder.name)
            temporary.unlink()
            subprocess.run(self._command(temporary), check=True)  # noqa: S603
            if not temporary.is_file():
                msg = f"fetch script did not materialize target: {temporary}"
                raise RuntimeError(msg)
            temporary.replace(self.target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
