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

## Dependency-aware process plans

The provider advertises `supports_plan = True` and implements `_submit_plan`
for core's inherited `JobABC.submit_plan` entrypoint. It imports `ProcessPlan`
from `flepimop2.process._plan`; core constructs the plan, validates the module,
and caches the returned per-step handles.

This integration currently requires core PR #374 at commit
`38013b063e57cafecefa101909785c617f911d3b`. The workspace's `tool.uv.sources`
pins that revision for development and CI (`uv sync` / `uv run pytest`).
Released flepimop2 0.3.0 lacks this API. Before publishing, replace the temporary
source pin and update the shared core version constraint to a release containing
that PR; uv source overrides are not included in published dependencies.

Each command is a complete argument vector and must execute only its own
process. The provider does not expand process prerequisites or add a
`flepimop2` executable prefix. Core remains responsible for target selection,
skip/force semantics, and constructing those individual commands.

`cmd_queue` renders one Slurm submission per step, with `afterok` dependencies
on the prerequisite job IDs. Independent steps can run concurrently. Submission
returns a dictionary mapping the original step names to `JobHandle` objects;
it does not wait for the compute jobs to finish. Existing single-command
submission continues to use `_submit`.

The configured resources, working directory, and pre/post commands apply to
every step. Step scripts stop on failure, so post-commands run only after a
successful process. Dependencies control execution order; processes must write
their outputs to storage accessible by downstream jobs.

A dry run returns `JobDryRun` with the generated submission script path and
step count, without invoking `sbatch`. Scripts, logs, and a submission journal
are retained in a unique subdirectory of `sbatch-directory` (or a temporary
directory). If submission fails midway, `PlanSubmissionError.handles` contains
the jobs already accepted by Slurm; those jobs are not automatically cancelled.

Plan submissions reserve `dependency`, `array`, `wrap`, `parsable`, `quiet`,
and `wait` in `sbatch-options` because these conflict with one tracked job per
step and dependency-aware submission. This implementation expects numeric
Slurm job IDs and does not support federated `jobid;cluster` responses.
