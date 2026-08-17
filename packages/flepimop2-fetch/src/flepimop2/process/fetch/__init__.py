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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Cached, validated HTTP(S) fetch process for flepimop2."""

__all__ = ["FetchProcess"]

import hashlib
import tempfile
from pathlib import Path
from typing import BinaryIO, cast
from urllib.request import Request, urlopen

from flepimop2.process.fetch.abc import FetchProcessABC
from pydantic import Field, HttpUrl

_CHUNK_SIZE = 1024 * 1024


def _sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_and_hash(source: BinaryIO, destination: BinaryIO) -> str:
    """Copy a binary stream while calculating its SHA-256 digest.

    Returns:
        The lowercase hexadecimal digest of the copied content.
    """
    digest = hashlib.sha256()
    while chunk := source.read(_CHUNK_SIZE):
        destination.write(chunk)
        digest.update(chunk)
    return digest.hexdigest()


class FetchProcess(FetchProcessABC, module="fetch"):
    """Fetch an HTTP(S) URL once and expose it as a durable local target.

    Attributes:
        source: HTTP(S) URL to download.
        target: Local file the process promises to materialize.
        sha256: Optional, pre-known SHA-256 content digest. It is never
            discovered from the remote source or written back to configuration.
        timeout: Network timeout in seconds.
        user_agent: HTTP User-Agent sent with the request.
    """

    source: HttpUrl
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    timeout: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default="flepimop2-fetch/0.3", min_length=1)

    def is_satisfied(self) -> bool:
        """Check only the local artifact and, when supplied, its expected hash.

        This method performs no network request. A configured digest must be
        known in advance; it is compared with the bytes already at `target`.

        Returns:
            `True` when the cache entry exists and, if configured, its digest
            matches.
        """
        if not self.target.is_file():
            return False
        return self.sha256 is None or _sha256(self.target) == self.sha256.lower()

    def _process(self, *, dry_run: bool) -> None:
        """Download the configured source atomically into the cache entry.

        Raises:
            ValueError: If downloaded content does not match the expected digest.
        """
        if dry_run:
            print(f"would fetch {self.source} -> {self.target}")  # noqa: T201
            return

        self.target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with (
                tempfile.NamedTemporaryFile(
                    dir=self.target.parent,
                    prefix=f".{self.target.name}.",
                    suffix=".part",
                    delete=False,
                ) as destination,
            ):
                temporary = Path(destination.name)
                request = Request(  # noqa: S310
                    str(self.source), headers={"User-Agent": self.user_agent}
                )
                with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                    observed = _copy_and_hash(response, cast("BinaryIO", destination))
            if self.sha256 is not None and observed != self.sha256.lower():
                msg = (
                    f"SHA-256 mismatch for {self.source}: expected "
                    f"{self.sha256.lower()}, observed {observed}"
                )
                raise ValueError(msg)
            Path(temporary).replace(self.target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
