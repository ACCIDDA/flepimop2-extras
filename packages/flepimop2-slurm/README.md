# `flepimop2-slurm`

An external provider package for [flepimop2](https://github.com/ACCIDDA/flepimop2) that provides a `SlurmJob` class for submitting jobs to Slurm-managed HPC clusters.

This package contributes the `slurm` job module to the `flepimop2.job` namespace. Once installed, flepimop2 configurations can reference it via:

```yaml
job:
  module: 'slurm'
  ...
```

## Installation

Like other packages in the `flepimop2-extras` package it can either be installed directly via:

```bash
pip install "flepimop2-slurm@git+https://github.com/ACCIDDA/flepimop2-extras.git@main#subdirectory=packages/flepimop2-slurm"
```

or as a part of a dependency group in `flepimop2-extras` if you're using multiple modules from this package:

```bash
pip install "flepimop2-extras[slurm]@git+https://github.com/ACCIDDA/flepimop2-extras.git@main"
# or
pip install "flepimop2-extras[all]@git+https://github.com/ACCIDDA/flepimop2-extras.git@main"
```

## Configuration

The slurm module can be configured in your YAML configuration file with the following settings:

```yaml
job:
  my_hpc:
    module: slurm
    cpus-per-task: 2
    memory: 4G
    nodes: 1
    ntasks: 2
    time: 2:45:00
    ...
```

- `cpus-per-task`: Corresponds directly to `sbatch`'s [`--cpus-per-task` option](https://slurm.schedmd.com/sbatch.html#OPT_cpus-per-task). This times the number of tasks will determine the number of CPUs to request.
- `memory`: Corresponds directly to `sbatch`'s [`--mem` option](https://slurm.schedmd.com/sbatch.html#OPT_mem). Should either be an int/float if specified in megabytes or if a string should specify its unit as a single string, e.g. '45.67G' or '1t'.
- `nodes`: Corresponds directly to `sbatch`'s [`--nodes` option](https://slurm.schedmd.schedmd.com/sbatch.html#OPT_nodes).
- `ntasks`: Corresponds directly to `sbatch`'s [`--ntasks` option](https://slurm.schedmd.com/sbatch.html#OPT_ntasks).
- `time`: Corresponds directly to `sbatch`'s [`--time` option](https://slurm.schedmd.com/sbatch.html#OPT_time). Can either be specified as slurm formatted duration string or as a [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339) string.
- `chdir`: Corresponds directly to `sbatch`'s [`--chdir` option](https://slurm.schedmd.com/sbatch.html#OPT_chdir). If not specified defaults to the current working directory which is typically the desired behavior.
- `debug`: Indicates if the batch script generated and submitted to slurm should have extra debugging enabled via `set -x`. This output is extremely verbose.
- `pre-commands`: Commands that should be ran before running the specified `flepimop2` CLI command. This typically corresponds to setup, like activating modules or ensuring certain directories are created ahead of time. This can be specified as a a list of commands to execute or just as a block of commands:

```yaml
job:
  my_hpc:
    module: slurm
    pre-commands:
      - 'module load anaconda'
      - 'conda activate my_env'
# or
job:
  my_hpc:
    module: slurm
    pre-commands: |-
      module load anaconda
      conda activate my_env
```

- `post-commands`: Commands that should be ran after running the specified `flepimop2` CLI command. This typically corresponds to clean up, like removing temporary files or moving results to a final destination. Similarly to `pre-commands`, this can be specified as a list of commands to execute or just as a block of commands.
- `sbatch-options`: Other [`sbatch` options](https://slurm.schedmd.com/sbatch.html) to be included in the job submission. Cannot include 'chdir', 'comment', 'cpus-per-task', 'job-name', 'mem', 'nodes', 'ntasks', or 'time' since those are configured by other options. Common examples include specifying a partition, email notifications, or requesting GPUs. E.g.

```yaml
job:
  my_hpc:
    module: slurm
    sbatch-options:
      partition: foobar
      mail-type: all
      mail-user: me@email.com
      gres: gpu:1
      ...
```

- `sbatch-directory`: The directory that the sbatch submission file is written to. If not specified a temporary directory will be created. It can be helpful for debugging purposes to retain these, but these should not be kept in version control as they are generated artifacts.
