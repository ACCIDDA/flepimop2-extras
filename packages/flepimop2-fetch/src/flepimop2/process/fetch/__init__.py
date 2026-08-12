# flepimop2-fetch: A cached URL-fetch process provider for flepimop2
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
"""Cached URL-fetch process for flepimop2."""

__all__ = ["FetchProcess"]

import hashlib
import os
import subprocess  # noqa: S404
import tempfile
import warnings
from pathlib import Path
from typing import BinaryIO, Self, cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from flepimop2.exceptions import Flepimop2ValidationError, ValidationIssue
from flepimop2.process.abc import ProcessABC
from pydantic import Field, model_validator

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


class FetchProcess(ProcessABC, module="fetch"):
    """Fetch a source once and expose it as a durable local target.

    Attributes:
        source: HTTP(S) URL, or an identifier understood by `script`.
        target: Local file the process promises to materialize.
        script: Optional executable implementing a custom fetch strategy.
        args: Arguments passed before provider-owned source and target arguments.
        sha256: Optional expected lowercase SHA-256 content digest.
        timeout: Network timeout in seconds.
        user_agent: HTTP User-Agent sent with the request.
    """

    source: str = Field(min_length=1)
    target: Path
    script: Path | None = None
    args: list[str] = Field(default_factory=list)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    timeout: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default="flepimop2-fetch/0.3", min_length=1)

    @model_validator(mode="after")
    def _validate_strategy(self) -> Self:
        """Require HTTP(S) when no custom fetch script is configured.

        Returns:
            The validated process.

        Raises:
            ValueError: If the built-in strategy receives a non-HTTP source.
        """
        if self.script is None and urlparse(self.source).scheme not in {
            "http",
            "https",
        }:
            msg = "source must be HTTP(S) unless a custom script is configured"
            raise ValueError(msg)
        return self

    def execute(self, *, dry_run: bool = False, force: bool = False) -> None:
        """Execute the fetch unless its cache entry is already satisfied.

        This carries the cache-aware execution contract introduced in
        flepimop2 0.4 while the extras workspace still supports flepimop2 0.3.
        It can be removed when the workspace's minimum core version reaches
        0.4.

        Args:
            dry_run: Validate and report the fetch without downloading it.
            force: Refetch even when the cache entry is already satisfied.

        Raises:
            Flepimop2ValidationError: If dry-run validation fails.
        """
        if dry_run and (result := self._process_validate()) is not None:
            if result:
                raise Flepimop2ValidationError(result)
            return
        if not force and self.is_satisfied():
            print(f"target already exists: {self.target}; use --force to replace it")  # noqa: T201
            return
        if force and self.target.exists():
            warnings.warn(
                f"replacing existing fetch target: {self.target}",
                RuntimeWarning,
                stacklevel=2,
            )
        self._process(dry_run=dry_run)

    def is_satisfied(self) -> bool:
        """Report whether the local artifact exists and has valid content.

        Returns:
            `True` when the cache entry exists and, if configured, its digest
            matches.
        """
        if not self.target.is_file():
            return False
        return self.sha256 is None or _sha256(self.target) == self.sha256.lower()

    def _process_validate(self) -> list[ValidationIssue] | None:
        """Validate the custom script, when configured, without writing.

        Returns:
            Validation issues, or `None` when the configuration is usable.
        """
        issues: list[ValidationIssue] = []
        if self.script is not None and not self.script.is_file():
            issues.append(
                ValidationIssue(
                    msg=f"fetch script does not exist: {self.script}",
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
        """Download the configured source atomically into the cache entry.

        Raises:
            RuntimeError: If a custom script does not materialize its target.
            ValueError: If downloaded content does not match the expected digest.
        """
        if dry_run:
            print(f"fetch {self.source} -> {self.target}")  # noqa: T201
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
                if self.script is None:
                    request = Request(  # noqa: S310
                        self.source, headers={"User-Agent": self.user_agent}
                    )
                    with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                        observed = _copy_and_hash(
                            response, cast("BinaryIO", destination)
                        )
                else:
                    destination.close()
                    temporary.unlink()
                    subprocess.run(  # noqa: S603
                        [
                            str(self.script),
                            *self.args,
                            "--source",
                            self.source,
                            "--target",
                            str(temporary),
                        ],
                        check=True,
                    )
                    if not temporary.is_file():
                        msg = f"fetch script did not materialize target: {temporary}"
                        raise RuntimeError(msg)
                    observed = _sha256(temporary)
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
