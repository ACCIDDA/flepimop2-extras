"""Unit tests for `_which_jupyter` internal utility."""

import pytest

from flepimop2.process.ipynbrender._utils import _which_jupyter


@pytest.mark.parametrize("jupyter", ["/path/to/jupyter"])
def test_which_jupyter_found(monkeypatch: pytest.MonkeyPatch, jupyter: str) -> None:
    """Test that `_which_jupyter` returns the correct path when jupyter is found."""
    monkeypatch.setattr(
        "flepimop2.process.ipynbrender._utils.which",
        lambda name: jupyter,  # noqa: ARG005
    )
    assert _which_jupyter() == jupyter


def test_which_jupyter_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that `_which_jupyter` raises FileNotFoundError when jupyter is not found."""
    monkeypatch.setattr("flepimop2.process.ipynbrender._utils.which", lambda name: None)  # noqa: ARG005
    with pytest.raises(
        FileNotFoundError, match=r"^jupyter executable not found in PATH$"
    ):
        _which_jupyter()
