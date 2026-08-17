# `flepimop2-fetch`

Cached URL and script-driven fetch process providers for
[`flepimop2`](https://github.com/ACCIDDA/flepimop2).

## Validated HTTP(S) fetches

```yaml
process:
  observations:
    module: fetch
    source: https://example.org/observations.csv
    target: .cache/data/observations.csv
    sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

`target` is both the exposed local path and the cache entry. If it already
exists (and matches `sha256`, when supplied), the step is skipped. Use
`flepimop2 process --force --target observations ...` to refetch it.

Downloads are written to a temporary sibling and atomically moved into place,
so an interrupted request cannot leave a partial cache entry.

`sha256` is an optional, expected digest that must be known in advance. The
provider does not download the remote object when it checks an existing cache
entry, discover a digest for later use, or update the configuration. It hashes
only the local target during satisfaction checks and verifies bytes as they are
downloaded. This is useful for immutable inputs with a published checksum;
without it, any file at `target` satisfies the step.

Dry-run uses the supplied force flag: an existing satisfied target reports that
the fetch would be skipped, while `--force` reports that it would be replaced.
No network request is made in either case.

## Script-driven fetches

The separate `script_fetch` specialization handles arbitrary source types. It
deliberately provides less source-specific validation: the user-supplied script
is responsible for interpreting and checking `source`.

```yaml
process:
  observations:
    module: script_fetch
    source: s3://example-bucket/observations.csv
    script: ./fetch_s3.py
    args: [--profile, production]
    target: .cache/data/observations.csv
```

The provider validates that `script` is an executable file, then runs:

```text
fetch_s3.py <args> --source <source> --target <temporary-path>
```

The final source and target options are provider-owned. The script must create
the temporary target and return successfully; only then is the configured
target replaced atomically. URL-only options such as `sha256`, `timeout`, and
`user_agent` are intentionally unavailable on this specialization.
