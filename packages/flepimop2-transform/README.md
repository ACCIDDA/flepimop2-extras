# `flepimop2-transform`

A cached script-transform process provider for `flepimop2`.

## Script contract

```yaml
process:
  observations:
    module: fetch
    source: https://example.org/observations.csv
    target: .cache/raw.csv
  clean_observations:
    module: transform
    depends: [observations]
    sources: [.cache/raw.csv]
    script: ./clean.py
    args: [--drop-missing]
    target: .cache/clean.csv
```

The script receives its configured arguments, one `--source <path>` pair per
input, and `--target <temporary-path>`. It must create the temporary target;
the provider atomically replaces the configured target after success.

For the example above, the command interface is:

```text
./clean.py --drop-missing --source .cache/raw.csv --target <temporary-path>
```

The provider rejects missing input files or a missing script before invoking
the script. A satisfied target is skipped unless forced. Dry-run mirrors that
decision: it reports a skip without `--force`, or the replacement and command
that would run with `--force`, without writing either way.

## Reusing a configuration parameter

`args` are literal command-line values. YAML anchors can reuse a static value
declared elsewhere in the same configuration, including a fixed parameter:

```yaml
parameters:
  missingness_cutoff: &missingness_cutoff 0.15

process:
  clean_observations:
    module: transform
    sources: [.cache/raw.csv]
    script: ./clean.py
    args: [--max-missing, *missingness_cutoff]
    target: .cache/clean.csv
```

This runs the script with `--max-missing 0.15`. String and numeric argument
values are accepted and converted to strings in the final argument vector.

The anchor is YAML-level reuse, not runtime parameter resolution. A transform
process receives only its own configuration block, so it cannot sample a
parameter provider or inspect the full `parameters` section. If a value is
computed at runtime, materialize it in an upstream process, declare that step
in `depends`, and include the resulting file in `sources`.
