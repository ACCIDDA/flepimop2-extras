# Changelog

## Unreleased

### Added

- Support core PR #374's dependency-aware process plans in the Slurm provider,
  using `cmd_queue` to submit one job per step with `afterok` dependencies.
  Advertise `supports_plan`, inherit core's public submission validation, and
  return per-step handles for core caching. Include dry runs and partial-failure
  journals. Development is pinned to core commit `38013b0`; this feature requires
  the unreleased core API and is not compatible with flepimop2 0.3.0.

### Documentation

- Replace metapackage Git-install examples that could not resolve unpublished
  providers with commands supplying local packages in the same pip invocation.
  Describe the source-only alpha status and distinguish the distributable
  metapackage from its development workspace.

### Fixed

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
