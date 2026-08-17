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
"""Shared target and execution behavior for fetch processes."""

__all__ = ["FetchProcessABC"]

import os
import warnings
from abc import ABC
from pathlib import Path

from flepimop2.exceptions import Flepimop2ValidationError, ValidationIssue
from flepimop2.process.abc import ProcessABC
from pydantic import ConfigDict, Field


class FetchProcessABC(ProcessABC, ABC):
    """Share the cached-target contract without coupling fetch strategies."""

    model_config = ConfigDict(extra="forbid")

    # Compatibility with flepimop2 0.3. Core owns this field from 0.4 onward.
    depends: list[str] = Field(default_factory=list)
    target: Path

    def execute(self, *, dry_run: bool = False, force: bool = False) -> None:
        """Validate and execute with target-aware dry-run and force behavior.

        Args:
            dry_run: Report the action selected by `force` without writing.
            force: Fetch even when the local target is already satisfied.

        Raises:
            Flepimop2ValidationError: If the configuration cannot be executed.
        """
        if issues := self._process_validate():
            raise Flepimop2ValidationError(issues)

        if not force and self.is_satisfied():
            prefix = "would skip fetch; " if dry_run else ""
            print(  # noqa: T201
                f"{prefix}target already exists: {self.target}; "
                "use --force to replace it"
            )
            return

        if force and self.target.exists():
            message = f"replacing existing fetch target: {self.target}"
            if dry_run:
                print(  # noqa: T201
                    f"would replace existing fetch target: {self.target}"
                )
            else:
                warnings.warn(message, RuntimeWarning, stacklevel=2)

        self._process(dry_run=dry_run)

    def is_satisfied(self) -> bool:
        """Report whether the promised target is a file.

        Returns:
            `True` when `target` is a file.
        """
        return self.target.is_file()

    def _process_validate(self) -> list[ValidationIssue] | None:
        """Validate the target shape and destination without writing.

        Returns:
            Validation issues, or `None` when the destination is usable.
        """
        issues: list[ValidationIssue] = []
        if self.target.exists() and not self.target.is_file():
            issues.append(
                ValidationIssue(
                    msg=f"fetch target is not a file: {self.target}",
                    kind="invalid_target",
                )
            )

        parent = self.target.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not parent.is_dir() or not os.access(parent, os.W_OK):
            issues.append(
                ValidationIssue(
                    msg=f"target destination is not writable: {self.target}",
                    kind="permission_denied",
                )
            )
        return issues or None
