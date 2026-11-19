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

The provider advertises `supports_plan = True` and
`supports_detached_plan = True`. Core's inherited `submit_plan()` validates the
backend, and its default plan loop resolves prerequisite handles and calls our
`_submit_step()`. A small Slurm `_submit_plan()` wrapper validates and orders the
whole plan before submission and retains accepted handles on failure.

The workspace and package dependencies pin merged core PR #379 at commit
`0e32c714521a8f329e78c6f6b56e7200f26501dc` for source installation, development, and CI.
Before publishing to PyPI, replace the shared Git dependency with a released
core version containing that API and remove the temporary source override.
Core 0.3.0 is not compatible. The explicit package dependency also protects
installations outside the uv workspace from selecting that older core.

Configure `execution: parallel` on the Slurm job provider to submit one job per
process step. The default, `execution: serial`, submits one batch job running
the whole workflow in order. Parallel submission invokes `sbatch --parsable`
directly, with `--dependency=afterok:<ids>` for prerequisites. Independent steps
can run concurrently, and Slurm manages execution after the CLI exits.

Each command is a complete argument vector that runs only its own process.
Core owns target selection, skip/force semantics, and command construction.
Submission returns per-step handles for core logging and caching without
waiting for compute jobs to finish.

The configured resources, working directory, and pre/post commands apply to
every step. Step scripts use `set -e -o pipefail`, so post-commands run only after a
successful process. Each step is submitted as a Bash-shebang batch file, so an
intermediate `/bin/sh` cannot strip exported Bash functions such as `module`.
Dependencies control execution order; processes must write
their outputs to storage accessible by downstream jobs.

A dry run returns display-only `sbatch` commands with symbolic dependencies
such as `--dependency=afterok:dry-run-prepare`. These placeholders are not real
Slurm IDs; the preview must not be executed as a submission script. Batch files
and `dry-run.txt` are retained under the directory reported in `JobDryRun.details`.
Real submissions retain a `submitted.jsonl` journal of accepted handles.
Artifacts use a unique subdirectory of `sbatch-directory` (or a temporary
directory). Slurm reads batch files at submission; compute nodes do not need
access to that directory. Default output goes to `slurm-%x-%j.out` in the
configured working directory. Explicit `output` and `error` settings are
preserved; output directories must be compute-visible.

On failure, `PlanSubmissionError.handles` includes all known accepted jobs,
including a job whose journal write failed. Its `directory` identifies retained
artifacts; the chained exception explains the failure. Accepted jobs are not
automatically cancelled or retried, and partial handles are not automatically
cached by core. A crash between scheduler acceptance and receiving/recording
an ID still requires manual reconciliation.

Failed prerequisites prevent dependent jobs from running. Slurm's cluster
policy controls whether those jobs remain pending or are cancelled; set
`sbatch-options: {kill-on-invalid-dep: "yes"}` to request cancellation explicitly.

Plan submissions reserve `dependency`, `array`, `wrap`, `parsable`, `quiet`,
`wait`, `clusters`, and `cluster-constraint` in `sbatch-options` because these
conflict with one tracked local-cluster job per
step and dependency-aware submission. This implementation expects numeric
Slurm job IDs and does not support federated `jobid;cluster` responses.
Unset `SBATCH_ARRAY_INX`, `SBATCH_CLUSTER_CONSTRAINT`, `SBATCH_CLUSTERS`,
`SLURM_CLUSTERS`, and enabled `SBATCH_WAIT`
before submitting a plan (including dry runs); their presence is rejected rather
than silently changing the plan. `SBATCH_WAIT=0` is permitted. Other environment
settings are inherited. Batch filenames use bounded labels and unique step
indices; original process names are retained in handle metadata.
Submission preserves the caller's directory and hence `SLURM_SUBMIT_DIR`;
`chdir` independently selects the batch job's working directory.
Slurm submission failures include the failing step, exit code, and diagnostic
output in the exception, alongside any already accepted handles.
