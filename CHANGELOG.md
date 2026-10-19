# Changelog

## Unreleased

### Fixed

- Return validation issue lists from the notebook process and Slurm submission
  hooks, including an empty list on success. Support whole-configuration
  validation on merged FlepiMoP2 while retaining public 0.3.0 compatibility
  ([#32](https://github.com/ACCIDDA/flepimop2-extras/issues/32)).

### Development

- Require Twine 7 or later for strict validation of the Core Metadata 2.5 emitted
  by current builds. Runtime dependencies and shared package versions are
  unchanged ([#31](https://github.com/ACCIDDA/flepimop2-extras/issues/31)).
