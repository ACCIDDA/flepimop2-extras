# flepimop2-extras: Common external provider modules for flepimop2
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
"""Synchronize the shared version and flepimop2 constraint across the workspace.

The single source of truth lives in the root `pyproject.toml` under
`[tool.flepimop2-extras]`:

    [tool.flepimop2-extras]
    version = "0.1.0dev"
    flepimop2-constraint = "flepimop2>=0.0.0,<1.0.0"

Running this script with no arguments rewrites the root `[project].version`
and, for every package under `packages/`, the `[project].version` and the
`flepimop2` entry in `[project].dependencies` to match. With `--check` it
instead reports any drift and exits non-zero without modifying anything, which
is what CI uses to enforce that the workspace stays in sync.
"""

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGES_DIR = REPO_ROOT / "packages"

# Matches the canonical name at the start of a PEP 508 requirement, e.g.
# "flepimop2" in "flepimop2>=0.0.0,<1.0.0". Normalization per PEP 503.
_FLEPIMOP2_NAME = re.compile(r"^\s*flepimop2(?![\w.-])", re.IGNORECASE)


@dataclass(frozen=True)
class SharedConfig:
    """The values shared across every package in the workspace."""

    version: str
    flepimop2_constraint: str


def load_shared_config() -> SharedConfig:
    """Read the source-of-truth values from the root `pyproject.toml`.

    Returns:
        The shared version and flepimop2 constraint.

    Raises:
        SystemExit: If the `[tool.flepimop2-extras]` block is missing a key.
    """
    data = tomllib.loads(ROOT_PYPROJECT.read_text(encoding="utf-8"))
    try:
        shared = data["tool"]["flepimop2-extras"]
        return SharedConfig(
            version=shared["version"],
            flepimop2_constraint=shared["flepimop2-constraint"],
        )
    except KeyError as exc:
        msg = f"Missing {exc} in [tool.flepimop2-extras] of {ROOT_PYPROJECT}"
        raise SystemExit(msg) from exc


def _replace_version(text: str, version: str) -> str:
    """Rewrite the `version = "..."` line in a `[project]` table.

    Returns:
        The text with the version assignment updated.

    Raises:
        SystemExit: If there is not exactly one top-level version assignment.
    """
    pattern = re.compile(r'(?m)^(version\s*=\s*)"[^"]*"')
    new, count = pattern.subn(rf'\1"{version}"', text, count=1)
    if count != 1:
        msg = "Expected exactly one top-level `version = ...` assignment"
        raise SystemExit(msg)
    return new


def _replace_flepimop2_constraint(text: str, constraint: str) -> str:
    """Rewrite the `flepimop2` requirement inside `dependencies`.

    Returns:
        The text with the flepimop2 dependency updated.

    Raises:
        SystemExit: If no `flepimop2` dependency entry is found.
    """
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        stripped = line.split("#", 1)[0]
        match = re.search(r'"([^"]*)"', stripped)
        if match is not None and _FLEPIMOP2_NAME.match(match.group(1)):
            lines[index] = line[: match.start(1)] + constraint + line[match.end(1) :]
            return "".join(lines)
    msg = "Could not find a `flepimop2` dependency entry to update"
    raise SystemExit(msg)


def _pyproject_targets() -> list[tuple[Path, bool]]:
    """Return `(pyproject_path, sync_constraint)` pairs to process.

    The root metapackage has its version synced but no flepimop2 dependency, so
    its constraint is not synced.
    """
    targets: list[tuple[Path, bool]] = [(ROOT_PYPROJECT, False)]
    targets.extend(
        (package / "pyproject.toml", True)
        for package in sorted(PACKAGES_DIR.iterdir())
        if (package / "pyproject.toml").is_file()
    )
    return targets


def _synced_text(path: Path, shared: SharedConfig, *, sync_constraint: bool) -> str:
    """Return the contents of `path` with the shared values applied."""
    text = _replace_version(path.read_text(encoding="utf-8"), shared.version)
    if sync_constraint:
        text = _replace_flepimop2_constraint(text, shared.flepimop2_constraint)
    return text


def main() -> int:
    """Synchronize or check workspace versions and constraints.

    Returns:
        `0` on success, or `1` if `--check` found drift.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift and exit non-zero instead of writing changes",
    )
    args = parser.parse_args()

    shared = load_shared_config()
    drifted: list[Path] = []
    for path, sync_constraint in _pyproject_targets():
        current = path.read_text(encoding="utf-8")
        updated = _synced_text(path, shared, sync_constraint=sync_constraint)
        if current == updated:
            continue
        if args.check:
            drifted.append(path)
        else:
            path.write_text(updated, encoding="utf-8")
            print(f"updated {path.relative_to(REPO_ROOT)}")

    if args.check and drifted:
        print(
            "The following files are out of sync with [tool.flepimop2-extras]; "
            "run `just sync-versions`:",
        )
        for path in drifted:
            print(f"  {path.relative_to(REPO_ROOT)}")
        return 1
    if not args.check:
        print(
            f"synced version {shared.version!r} and "
            f"constraint {shared.flepimop2_constraint!r}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
