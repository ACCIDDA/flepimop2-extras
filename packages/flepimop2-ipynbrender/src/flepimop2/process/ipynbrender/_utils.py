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
from typing import Literal

NbConvertFormat = Literal[
    "html",
    "latex",
    "pdf",
    "webpdf",
    "slides",
    "markdown",
    "asciidoc",
    "rst",
    "notebook",
]


def _extension_to_format(
    extension: str,
) -> NbConvertFormat:
    """
    Convert a file extension to the corresponding notebook format.

    Args:
        extension: The file extension (e.g., ".html", ".pdf").

    Returns:
        The corresponding notebook format (e.g., "html", "pdf").

    Examples:
        >>> _extension_to_format(".html")
        'html'
        >>> _extension_to_format(".pdf")
        'pdf'
        >>> _extension_to_format(".ipynb")
        'notebook'
        >>> _extension_to_format(".md")
        'markdown'
    """
    extension_to_format: dict[str, NbConvertFormat] = {
        ".html": "html",
        ".htm": "html",
        ".latex": "latex",
        ".tex": "latex",
        ".pdf": "pdf",
        ".webpdf": "webpdf",
        ".slides": "slides",
        ".markdown": "markdown",
        ".md": "markdown",
        ".asciidoc": "asciidoc",
        ".adoc": "asciidoc",
        ".txt": "asciidoc",
        ".rst": "rst",
        ".notebook": "notebook",
        ".ipynb": "notebook",
    }
    return extension_to_format.get(extension, "notebook")
