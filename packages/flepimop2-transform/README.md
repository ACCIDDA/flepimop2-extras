# `flepimop2-transform`

A cached script-transform process provider for `flepimop2`.

```yaml
process:
  clean:
    module: transform
    depends: [fetch]
    sources: [.cache/raw.csv]
    script: ./clean.py
    args: [--drop-missing]
    target: .cache/clean.csv
```

The script receives its configured arguments, one `--source <path>` pair per
input, and `--target <temporary-path>`. It must create the temporary target;
the provider atomically replaces the configured target after success.
