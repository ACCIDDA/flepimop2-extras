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
"""Tests for the cached fetch process."""

import hashlib
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
from flepimop2.process.fetch import FetchProcess
from pydantic import ValidationError


class _Handler(BaseHTTPRequestHandler):
    """Serve a fixed body and count requests."""

    body: ClassVar[bytes] = b"location,value\n37,42\n"
    requests: ClassVar[int] = 0

    def do_GET(self) -> None:
        """Serve the fixture body."""
        type(self).requests += 1
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress request logging in tests."""


@pytest.fixture
def source_url() -> Iterator[str]:
    """Run a local HTTP source for a test.

    Yields:
        The URL served by the local test server.
    """
    _Handler.requests = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = str(server.server_address[0])
        port = int(server.server_address[1])
        yield f"http://{host}:{port}/observations.csv"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_fetches_and_skips_cached_artifact(tmp_path: Path, source_url: str) -> None:
    """A second ordinary execution uses the existing local artifact."""
    output = tmp_path / "cache" / "observations.csv"
    process = FetchProcess.model_validate({"source": source_url, "target": output})

    process.execute()
    process.execute()

    assert output.read_bytes() == _Handler.body
    assert _Handler.requests == 1


def test_force_refetches_cached_artifact(tmp_path: Path, source_url: str) -> None:
    """Core's force flag bypasses the provider's satisfied target."""
    output = tmp_path / "observations.csv"
    process = FetchProcess.model_validate({"source": source_url, "target": output})

    process.execute()
    with pytest.warns(RuntimeWarning, match="replacing existing fetch target"):
        process.execute(force=True)

    assert _Handler.requests == 1 + 1


def test_url_fetch_rejects_non_http_source(tmp_path: Path) -> None:
    """The URL specialization rejects identifiers owned by custom scripts."""
    with pytest.raises(ValidationError, match="URL scheme should be 'http' or 'https'"):
        FetchProcess.model_validate({
            "source": "s3://example-bucket/artifact.csv",
            "target": tmp_path / "artifact.csv",
        })


def test_url_fetch_rejects_script_options(tmp_path: Path, source_url: str) -> None:
    """Script execution cannot silently weaken the URL provider's validation."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FetchProcess.model_validate({
            "source": source_url,
            "script": tmp_path / "fetch.py",
            "target": tmp_path / "artifact.csv",
        })


def test_sha256_mismatch_keeps_existing_artifact(
    tmp_path: Path, source_url: str
) -> None:
    """A failed refresh cannot replace a valid prior cache entry."""
    output = tmp_path / "observations.csv"
    output.write_bytes(b"previous")
    process = FetchProcess.model_validate({
        "source": source_url,
        "target": output,
        "sha256": "0" * 64,
    })

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        process.execute()

    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob("*.part"))


def test_matching_sha256_is_satisfied(tmp_path: Path, source_url: str) -> None:
    """An expected digest participates in cache validation."""
    output = tmp_path / "observations.csv"
    expected = hashlib.sha256(_Handler.body).hexdigest()
    process = FetchProcess.model_validate({
        "source": source_url,
        "target": output,
        "sha256": expected.upper(),
    })

    process.execute()

    assert process.is_satisfied()
    assert _Handler.requests == 1


def test_sha256_satisfaction_reads_only_local_target(
    tmp_path: Path, source_url: str
) -> None:
    """Checking a pre-known digest never pulls the remote object."""
    output = tmp_path / "observations.csv"
    output.write_bytes(_Handler.body)
    process = FetchProcess.model_validate({
        "source": source_url,
        "target": output,
        "sha256": hashlib.sha256(_Handler.body).hexdigest(),
    })

    assert process.is_satisfied()
    assert _Handler.requests == 0


def test_dry_run_does_not_fetch(
    tmp_path: Path, source_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run reports the transfer without touching disk or network."""
    output = tmp_path / "observations.csv"
    process = FetchProcess.model_validate({"source": source_url, "target": output})

    process.execute(dry_run=True)

    assert not output.exists()
    assert _Handler.requests == 0
    assert f"would fetch {source_url} -> {output}" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("force", "expected"),
    [
        (False, "would skip fetch; target already exists"),
        (True, "would replace existing fetch target"),
    ],
)
def test_dry_run_reports_force_decision_for_existing_target(
    tmp_path: Path,
    source_url: str,
    capsys: pytest.CaptureFixture[str],
    *,
    force: bool,
    expected: str,
) -> None:
    """Dry-run selects the same skip or replace branch as real execution."""
    output = tmp_path / "observations.csv"
    output.write_bytes(b"cached")
    process = FetchProcess.model_validate({"source": source_url, "target": output})

    process.execute(dry_run=True, force=force)

    captured = capsys.readouterr().out
    assert expected in captured
    assert ("would fetch" in captured) is force
    assert output.read_bytes() == b"cached"
    assert _Handler.requests == 0
