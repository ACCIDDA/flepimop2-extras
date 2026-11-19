# Changelog

## Unreleased

### Added

- Support core PR #374's dependency-aware process plans in the Slurm provider,
  using native `sbatch` calls to submit one job per step with `afterok` dependencies.
  Advertise `supports_plan`, inherit core's public submission validation, and
  return per-step handles for core caching. Include dry runs and partial-failure
  journals. Development is pinned to merged core PR #379 (`0e32c71`); this feature requires
  the unreleased core API and is not compatible with flepimop2 0.3.0.

### Documentation

- Replace metapackage Git-install examples that could not resolve unpublished
  providers with commands supplying local packages in the same pip invocation.
  Describe the source-only alpha status and distinguish the distributable
  metapackage from its development workspace.

### Fixed

- Pin the compatible core Git revision in package metadata as well as the uv
  workspace, preventing source installs from selecting incompatible core 0.3.0.
  Replace this development dependency with a release before publishing to PyPI.

- Bound step-derived batch filenames, reject inherited cluster constraints, and
  permit explicitly disabled `SBATCH_WAIT=0` during plan submission.

- Reject conflicting Slurm environment settings and unsupported cluster targeting
  before plan submission. Preserve the caller's submission directory, propagate
  pipeline failures, and include Slurm diagnostics in partial-submission errors.

- Use core's step-submission template and symbolic dry-run dependencies, with
  whole-plan preflight validation and journal-backed partial-failure recovery.
  Parallel Slurm execution is now explicitly selected with `execution: parallel`;
  serial execution remains one workflow job. Remove the cmd-queue dependency.

- Serialize time limits in Slurm's `days-HH:MM:SS` format for both single-job
  and process-plan submission, including limits of 24 hours or more.

- Keep default plan-job logs in the configured working directory rather than
  submission-local temporary storage. Submit Bash batch files directly to retain
  exported module functions, and stop with an accepted-job diagnostic if writing
  the submission journal fails.

- Return validation issue lists from the notebook process and Slurm submission
  hooks, including an empty list on success. Support whole-configuration
  validation on merged FlepiMoP2 while retaining public 0.3.0 compatibility
  ([#32](https://github.com/ACCIDDA/flepimop2-extras/issues/32)).

### Development

- Require Twine 7 or later for strict validation of the Core Metadata 2.5 emitted
  by current builds. Runtime dependencies and shared package versions are
  unchanged ([#31](https://github.com/ACCIDDA/flepimop2-extras/issues/31)).
