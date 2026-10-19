# `flepimop2-slurm`

`flepimop2-slurm` supplies the `SlurmJob` provider for submitting
[flepimop2](https://github.com/ACCIDDA/flepimop2) commands to Slurm clusters.

After installation, select `module: slurm` in a job configuration:

```yaml
job:
  module: 'slurm'
  ...
```

## Installation

Install the provider directly:

```bash
pip install "flepimop2-slurm@git+https://github.com/ACCIDDA/flepimop2-extras.git@main#subdirectory=packages/flepimop2-slurm"
```

The provider and metapackage are source-only alpha packages. To select the
provider through the metapackage, clone the repository and run this from its
root so pip can resolve the unpublished provider locally:

```bash
python -m pip install ./packages/flepimop2-slurm '.[slurm]'
```

See the [repository installation instructions](../../README.md#installation)
for installing all providers or using the development workspace.

## Configuration

| Example request | Scheduler meaning | Interpretation |
| --- | --- | --- |
| `cpus-per-task: 2`, `ntasks: 2` | Two tasks requesting two CPUs each | Allocated resources; model parallelism needs its own execution configuration. |
| `nodes: 1` | One requested node | Does not choose a numerical backend. |
| `memory: 4G` | Node memory request | Separate from application-specific memory limits. |
| `time: 2:45:00` | Requested wall time | Separate from a model's simulated time span. |
| `pre-commands` / `post-commands` | Shell setup / cleanup | Keep environment setup explicit and portable. |

The job provider schedules a command. The system and engine providers still
define and integrate the scientific model; process providers handle separately
configured analysis and reporting steps.

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
- `nodes`: Corresponds directly to `sbatch`'s [`--nodes` option](https://slurm.schedmd.com/sbatch.html#OPT_nodes).
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
