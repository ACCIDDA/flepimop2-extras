# flepimop2-ipynbrender: A notebook rendering provider for flepimop2
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
"""Notebook validation must return issues compatible with whole-config checks."""

from pathlib import Path

import pytest
from flepimop2.process.ipynbrender import IpynbRenderProcess


@pytest.mark.parametrize("available", [True, False])
def test_notebook_validation_returns_issue_list(
    tmp_path: Path, *, available: bool
) -> None:
    """Preserve missing-tool issues and represent successful validation by a list."""
    notebook = tmp_path / "report.ipynb"
    notebook.write_text(
        '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}',
        encoding="utf-8",
    )
    process = IpynbRenderProcess.model_validate({
        "file": notebook,
        "output": tmp_path / "report.html",
    })
    process._jupyter = "/usr/bin/jupyter" if available else None
    issues = process._process_validate()
    assert isinstance(issues, list)
    assert [issue.kind for issue in issues] == ([] if available else ["file_not_found"])
