# flepimop2-slurm

An external provider package for [flepimop2](https://github.com/ACCIDDA/flepimop2)
that provides a `SlurmJob` class for submitting jobs to Slurm-managed HPC
clusters.

This package contributes the `slurm` job module to the `flepimop2.job`
namespace. Once installed, flepimop2 configurations can reference it via:

```yaml
job:
  module: 'slurm'
```

## Status

Early development - `SlurmJob` is currently a placeholder that raises
`NotImplementedError`.

## License

Distributed under the terms of the [GPLv3 license](LICENSE).
