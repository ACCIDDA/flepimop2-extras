# flepimop2-transform: A cached transform process provider for flepimop2
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
"""Cached script-transform process for flepimop2."""

__all__ = ["TransformProcess"]

import os
import subprocess  # noqa: S404
import tempfile
import warnings
from pathlib import Path

from flepimop2.exceptions import Flepimop2ValidationError, ValidationIssue
from flepimop2.process.abc import ProcessABC
from pydantic import Field


class TransformProcess(ProcessABC, module="transform"):
    """Transform explicit source files into one durable target."""

    sources: list[Path] = Field(min_length=1)
    script: Path
    args: list[str] = Field(default_factory=list)
    target: Path

    def execute(self, *, dry_run: bool = False, force: bool = False) -> None:
        """Execute unless the target exists.

        Args:
            dry_run: Validate and report without running the script.
            force: Rerun even when the target exists.

        Raises:
            Flepimop2ValidationError: If an input or script is absent.
        """
        if (result := self._process_validate()) is not None and result:
            raise Flepimop2ValidationError(result)
        if not force and self.is_satisfied():
            print(f"target already exists: {self.target}; use --force to replace it")  # noqa: T201
            return
        if force and self.target.exists():
            warnings.warn(
                f"replacing existing transform target: {self.target}",
                RuntimeWarning,
                stacklevel=2,
            )
        self._process(dry_run=dry_run)

    def is_satisfied(self) -> bool:
        """Report whether the promised target exists.

        Returns:
            `True` when `target` is a file.
        """
        return self.target.is_file()

    def _process_validate(self) -> list[ValidationIssue] | None:
        """Validate source and script availability without writing.

        Returns:
            Validation issues, or `None` when every input is available.
        """
        issues = [
            ValidationIssue(
                msg=f"source does not exist: {source}", kind="file_not_found"
            )
            for source in self.sources
            if not source.is_file()
        ]
        if not self.script.is_file():
            issues.append(
                ValidationIssue(
                    msg=f"transform script does not exist: {self.script}",
                    kind="file_not_found",
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

    def _process(self, *, dry_run: bool) -> None:
        """Run the script and atomically replace the target.

        Raises:
            RuntimeError: If the script does not materialize its temporary target.
        """
        prefix = [str(self.script), *self.args]
        source_args = [
            item for source in self.sources for item in ("--source", str(source))
        ]
        if dry_run:
            print(" ".join([*prefix, *source_args, "--target", str(self.target)]))  # noqa: T201
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
            subprocess.run(  # noqa: S603
                [*prefix, *source_args, "--target", str(temporary)], check=True
            )
            if not temporary.is_file():
                msg = f"transform script did not materialize target: {temporary}"
                raise RuntimeError(msg)
            temporary.replace(self.target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
