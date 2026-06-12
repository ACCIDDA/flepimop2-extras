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
"""Module defining the `IpynbRenderProcess` for rendering Jupyter notebooks."""

__all__ = ["IpynbRenderProcess"]

import subprocess  # noqa: S404
from pathlib import Path
from shutil import which

import nbformat
from flepimop2.exceptions import ValidationIssue
from flepimop2.process.abc import ProcessABC
from flepimop2.process.ipynbrender._utils import (  # noqa: PLC2701
    NbConvertFormat,
    _extension_to_format,
)
from pydantic import Field, PrivateAttr


class IpynbRenderProcess(ProcessABC, module="ipynbrender"):
    """
    Process to render Jupyter notebooks.

    Attributes:
        module: The module type, fixed to "ipynbrender".
        file: Path to the input Jupyter notebook file.
        output: Path to the output rendered file.
        format: The format to render the notebook into. Supported formats include
            "html", "latex", "pdf", "webpdf", "slides", "markdown", "asciidoc", "rst",
            and "notebook". If not specified, it is inferred from the output file
            extension.
        version: The notebook version to use for reading and validation. Default is 4.

    """

    file: Path
    output: Path
    format: NbConvertFormat = Field(
        default_factory=lambda data: _extension_to_format(data["output"].suffix)
    )
    version: int | None = Field(default=None, gt=0)

    _jupyter: str | None = PrivateAttr(default_factory=lambda: which("jupyter"))

    def _process_validate(self) -> list[ValidationIssue] | None:
        """
        Process validation hook.

        Returns:
            A list of validation issues indicating if the jupyter notebook given is not
            in valid notebook format, otherwise `None`.

        """
        validation_issues: list[ValidationIssue] = []
        if self._jupyter is None:
            validation_issues.append(
                ValidationIssue(
                    msg="`jupyter` executable not found in PATH", kind="file_not_found"
                )
            )
        with self.file.open("r", encoding="utf-8") as f:
            notebook_content = nbformat.read(
                f, as_version=self.version or nbformat.NO_CONVERT
            )  # type: ignore[no-untyped-call]
        try:
            nbformat.validate(notebook_content)
        except nbformat.ValidationError as e:
            validation_issues.append(
                ValidationIssue(
                    msg=str(e),
                    kind="invalid_notebook",
                    ctx={"location": str(self.file)},
                )
            )
        if validation_issues:
            return validation_issues
        return None

    def _process(self, *, dry_run: bool) -> None:
        """
        Execute the notebook rendering process.

        Args:
            dry_run: If `True`, the command that would have been executed to run the
                notebook will be printed but not executed.

        Raises:
            FileNotFoundError: If the `jupyter` executable is not found in the PATH.

        """
        if self._jupyter is None:
            msg = "`jupyter` executable not found in PATH"
            raise FileNotFoundError(msg)
        cmd = [
            self._jupyter,
            "nbconvert",
            "--to",
            self.format,
            str(self.file.absolute()),
            "--output",
            str(self.output.absolute()),
        ]
        if dry_run:
            print(" ".join(cmd))  # noqa: T201
            return
        subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
