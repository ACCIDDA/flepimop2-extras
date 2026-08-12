# `flepimop2-fetch`

A cached URL-fetch process provider for
[`flepimop2`](https://github.com/ACCIDDA/flepimop2).

```yaml
process:
  observations:
    module: fetch
    source: https://example.org/observations.csv
    target: .cache/data/observations.csv
    sha256: 8b1a9953c4611296a827abf8c47804d7f76...
```

`target` is both the exposed local path and the cache entry. If it already
exists (and matches `sha256`, when supplied), the step is skipped. Use
`flepimop2 process --force --target observations ...` to refetch it.

Downloads are written to a temporary sibling and atomically moved into place,
so an interrupted request cannot leave a partial cache entry. Supplying
`sha256` makes the content identity explicit and is recommended for immutable
inputs; without it, the URL and configured target path identify the cached
artifact.

A custom fetcher can handle another source type. It receives the source and a
temporary target through a stable command-line interface:

```yaml
process:
  observations:
    module: fetch
    source: s3://example-bucket/observations.csv
    script: ./fetch_s3.py
    args: [--profile, production]
    target: .cache/data/observations.csv
```

This runs `fetch_s3.py <args> --source <source> --target <temporary-path>`.
