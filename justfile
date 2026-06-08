# Git dependency spec used to source flepimop2 from its development (main
# branch) version. Override to target another branch/ref, e.g.
# `just flepimop2_dev_spec='flepimop2 @ git+https://github.com/ACCIDDA/flepimop2.git@some-branch' flepimop2-dev`.
flepimop2_dev_spec := 'flepimop2 @ git+https://github.com/ACCIDDA/flepimop2.git@main'

# Run all default tasks for local development
default: dev lint

# Run all default dev tasks
dev: ruff mypy test

# Run all default lint tasks
lint: yamllint

# Run all default CI tasks
ci: quality test

# Format code using `ruff`
[group('dev')]
ruff:
    uv run ruff format
    uv run ruff check --fix

# Run tests with coverage
[group('dev')]
cov:
    uv run pytest --cov=packages --cov-report=term-missing

# Run the full pytest suite without coverage report
[group('ci')]
pytest:
    uv run pytest

# Run the pytest suite against the locked dependency set
[group('ci')]
ci-pytest:
    uv run --locked pytest

# Run the test suite
[group('dev')]
test: cov

# Type check using `mypy`
[group('dev')]
mypy:
    uv run mypy

# Clean up generated venvs and caches
[group('dev')]
[unix]
clean:
    rm -rf .*cache
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf .venv
    rm -rf dist

# Run CI `ruff` formatting/linting checks
[group('ci')]
ci-ruff:
    uv run ruff format --check
    uv run ruff check --no-fix

# Write the shared version and flepimop2 constraint from the root
# [tool.flepimop2-extras] into every package
[group('dev')]
sync-versions:
    uv run scripts/sync_versions.py

# Fail if any package's version or flepimop2 constraint has drifted from the
# root [tool.flepimop2-extras]
[group('ci')]
check-versions:
    uv run scripts/sync_versions.py --check

# Run CI quality checks (format/lint/type check/version sync)
[group('ci')]
quality: ci-ruff mypy check-versions

# Mirrors `just dev`, but with flepimop2 sourced from git so you can develop
# against an upcoming release. This is ephemeral: the git overlay is installed
# only for the duration of each command, so `pyproject.toml`, `uv.lock`, and
# `.venv` are left untouched.
#
# Run all default dev tasks against the development (main branch) flepimop2
[group('flepimop2-dev')]
flepimop2-dev: flepimop2-dev-ruff flepimop2-dev-mypy flepimop2-dev-cov

# Format/lint against flepimop2 main (see `flepimop2-dev`)
[group('flepimop2-dev')]
flepimop2-dev-ruff:
    uv run --with '{{flepimop2_dev_spec}}' ruff format
    uv run --with '{{flepimop2_dev_spec}}' ruff check --fix

# Type check against flepimop2 main (see `flepimop2-dev`)
[group('flepimop2-dev')]
flepimop2-dev-mypy:
    uv run --with '{{flepimop2_dev_spec}}' mypy

# Run tests with coverage against flepimop2 main (see `flepimop2-dev`)
[group('flepimop2-dev')]
flepimop2-dev-cov:
    uv run --with '{{flepimop2_dev_spec}}' pytest --cov=packages --cov-report=term-missing

# The copies are generated (and gitignored); the root files are the single
# source of truth.
#
# Copy the centralized root LICENSE and AUTHORS into every package
[unix]
[group('build')]
sync-licenses:
    #!/usr/bin/env bash
    set -euo pipefail
    for pkg in packages/*/; do
        cp LICENSE "${pkg}LICENSE"
        cp AUTHORS "${pkg}AUTHORS"
    done

# Build sdist and wheel for the root metapackage and every package, then
# validate package metadata with twine
[unix]
[group('build')]
build-check: sync-versions sync-licenses
    #!/usr/bin/env bash
    set -euo pipefail
    rm -rf dist/
    uv run python -m build --outdir dist .
    for pkg in packages/*/; do
        uv run python -m build --outdir dist "${pkg}"
    done
    uv run python -m twine check --strict dist/*

# Lint YAML files using `yamllint`
[group('lint')]
yamllint:
    uv run yamllint --strict --config-file .yamllint.yaml .
