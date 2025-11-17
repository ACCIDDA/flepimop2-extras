"""Module defining the `IpynbRenderProcess` for rendering Jupyter notebooks."""

__all__ = ["IpynbRenderProcess"]

import subprocess  # noqa: S404
from pathlib import Path
from typing import Literal

import nbformat
from flepimop2.abcs import ProcessABC
from flepimop2.configuration import ModuleModel
from flepimop2.exceptions import ValidationIssue
from pydantic import Field, PrivateAttr

from flepimop2.process.ipynbrender._utils import _which_jupyter  # noqa: PLC2701


class IpynbRenderProcess(ModuleModel, ProcessABC):
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

    module: Literal["flepimop2.process.ipynbrender"] = "flepimop2.process.ipynbrender"
    file: Path
    output: Path
    format: Literal[
        "html",
        "latex",
        "pdf",
        "webpdf",
        "slides",
        "markdown",
        "asciidoc",
        "rst",
        "notebook",
    ] = Field(default_factory=lambda data: data["output"].suffix.lstrip("."))
    version: int = Field(default=4, gt=0, le=4)

    _jupyter: str = PrivateAttr(default_factory=_which_jupyter)

    def _process_validate(self) -> list[ValidationIssue] | None:
        """
        Process validation hook.

        Returns:
            A list of validation issues indicating if the jupyter notebook given is not
            in valid notebook format, otherwise `None`.

        """
        with self.file.open("r", encoding="utf-8") as f:
            notebook_content = nbformat.read(f, as_version=self.version)  # type: ignore[no-untyped-call]
        try:
            nbformat.validate(notebook_content)
        except nbformat.ValidationError as e:
            return [
                ValidationIssue(
                    msg=str(e),
                    kind="invalid_notebook",
                    ctx={"location": str(self.file)},
                )
            ]
        return None

    def _process(self, *, dry_run: bool) -> None:
        """
        Execute the notebook rendering process.

        Args:
            dry_run: If `True`, the command that would have been executed to run the
                notebook will be printed but not executed.
        """
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
