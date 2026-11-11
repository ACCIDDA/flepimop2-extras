# flepimop2-slurm: A Slurm job provider for flepimop2
# Copyright (C) 2026  Carl Pearson, Joshua Macdonald, Timothy Willard
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Translate core process plans into cmd_queue Slurm submissions."""

from __future__ import annotations

import re
import shlex
import subprocess  # noqa: S404
from graphlib import TopologicalSorter
from pathlib import Path
from tempfile import mkdtemp
from typing import TYPE_CHECKING, Any

from cmd_queue.slurm_queue import SlurmQueue
from flepimop2.job.abc import JobDryRun, JobHandle

if TYPE_CHECKING:
    from flepimop2.job.slurm import SlurmJob
    from flepimop2.process._plan import ProcessPlan


class PlanSubmissionError(RuntimeError):
    """Submission failed; already submitted jobs remain available in handles."""

    def __init__(self, handles: dict[str, JobHandle], script: Path) -> None:
        self.handles = handles
        self.script = script
        super().__init__(
            f"Plan submission failed; submitted jobs: {handles}. "
            f"Submission script and journal retained in {script.parent}."
        )


def _plan_order(plan: ProcessPlan) -> list[str]:
    """Validate the plan before creating artifacts.

    Returns:
        Step names in topological order.

    Raises:
        ValueError: A command is empty or a dependency is unknown.
    """
    for name, step in plan.items():
        if not step["command"]:
            msg = f"Process step {name!r} has an empty command."
            raise ValueError(msg)
        unknown = set(step["depends"]) - plan.keys()
        if unknown:
            msg = f"Process step {name!r} has unknown dependencies: {sorted(unknown)}."
            raise ValueError(msg)
    return list(
        TopologicalSorter({n: s["depends"] for n, s in plan.items()}).static_order()
    )


def _submission_options(provider: SlurmJob) -> list[str]:
    """Render provider resources as argv, preserving Slurm memory units.

    Returns:
        Quoted by the caller, one argument per option.

    Raises:
        ValueError: An option conflicts with plan submission.
    """
    forbidden = {"dependency", "array", "wrap", "parsable", "quiet", "wait"}
    if conflicts := forbidden & provider.sbatch_options.keys():
        msg = f"Plan submission manages these sbatch options: {sorted(conflicts)}."
        raise ValueError(msg)
    options = provider.sbatch_options | {
        "cpus-per-task": str(provider.cpus_per_task),
        "mem": str(provider.memory),
        "nodes": str(provider.nodes),
        "ntasks": str(provider.ntasks),
        "time": str(provider.time),
        "chdir": str(provider.chdir.absolute()),
    }
    return [f"--{key}={value}" for key, value in sorted(options.items())]


def submit_plan(  # noqa: PLR0914
    provider: SlurmJob, plan: ProcessPlan, *, dry_run: bool
) -> dict[str, JobHandle] | JobDryRun:
    """Render a queue and submit without waiting for compute jobs to finish.

    cmd_queue generates the sbatch calls and afterok edges. A shell wrapper
    journals each returned ID and rejects failed/invalid submissions before
    dependent jobs can be submitted. Resources are passed as quoted argv in
    that wrapper, avoiding cmd_queue's memory-unit conversion and option filter.

    Returns:
        Handles keyed by process name, or a rendered dry-run description.

    Raises:
        RuntimeError: The submission journal contains an invalid entry.
        PlanSubmissionError: Submission failed, possibly after submitting jobs.
    """
    order = _plan_order(plan)
    options = _submission_options(provider)
    if not order:
        return JobDryRun(command="", details={"steps": "0"}) if dry_run else {}
    parent = provider.sbatch_directory
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    directory = Path(mkdtemp(prefix="flepimop-plan-", dir=parent)).absolute()
    queue = SlurmQueue(name="flepimop-plan")
    # cmd_queue paths are ubelt.Path instances (finalize_text uses augment).
    # Render relative paths: cmd_queue interpolates paths into double quotes.
    # The wrapper changes directory using shell-safe quoting instead.
    queue.dpath = type(queue.dpath)(".")
    queue.log_dpath = queue.dpath / "logs"
    queue.fpath = queue.dpath / "submit.sh"
    if "output" not in provider.sbatch_options:
        options.append(f"--output={provider.chdir.absolute() / 'slurm-%x-%j.out'}")
    jobs: dict[str, Any] = {}
    names = {}
    for index, name in enumerate(order):
        label = re.sub(r"[^A-Za-z0-9_-]", "_", name)
        job_name = f"step-{index:04d}-{label}"
        names[job_name] = name
        body = "\n".join([
            "#!/usr/bin/env bash",
            "set -e",
            *(["set -x"] if provider.debug else []),
            *provider.pre_commands,
            shlex.join(plan[name]["command"]),
            *provider.post_commands,
        ])
        batch = directory / f"{job_name}.batch"
        batch.write_text(body + "\n", encoding="utf-8")
        jobs[name] = queue.submit(  # type: ignore[no-untyped-call]
            str(batch),
            name=job_name,
            output_fpath="",
            depends=[jobs[dep] for dep in plan[name]["depends"]],
        )
    journal = directory / "submitted.tsv"
    # This function runs inside each cmd_queue command substitution. Keep its
    # stdout exclusively for the ID so cmd_queue can construct dependency flags.
    wrapper = "\n".join([
        "#!/usr/bin/env bash",
        "set -e",
        f"cd {shlex.quote(str(directory))}",
        "sbatch() {",
        "  local result name batch",
        "  local -a args=()",
        "  while (( $# )); do",
        '    case "$1" in',
        '      --job-name=*) name="${1#--job-name=}"; args+=("$1") ;;',
        '      --wrap) shift; batch="$1" ;;',
        '      --wrap=*) batch="${1#--wrap=}" ;;',
        '      *) args+=("$1") ;;',
        "    esac",
        "    shift",
        "  done",
        # Replace cmd_queue's wrap payload with a file submitted directly to
        # Slurm. Its Bash shebang avoids an intermediate /bin/sh environment.
        '  [[ -n "$batch" && -f "$batch" ]] || return 1',
        (
            f"  result=$(command sbatch {shlex.join(options)} "
            '"${args[@]}" "$batch") || return $?'
        ),
        '  if [[ ! "$result" =~ ^[0-9]+$ ]]; then',
        '    printf "Invalid sbatch job ID: %s\\n" "$result" >&2',
        "    return 1",
        "  fi",
        (
            '  if ! printf "%s\\t%s\\n" "$name" "$result" >> '
            f"{shlex.quote(str(journal))}; then"
        ),
        (
            '    printf "Failed to record accepted Slurm job %s (%s); '
            'stopping submission.\\n" "$result" "$name" >&2'
        ),
        "    return 1",
        "  fi",
        '  printf "%s\\n" "$result"',
        "}",
    ])
    script = directory / "submit.sh"
    script.write_text(wrapper + "\n" + queue.finalize_text() + "\n", encoding="utf-8")
    command = shlex.join(["bash", str(script)])
    if dry_run:
        return JobDryRun(
            command=command, details={"script": str(script), "steps": str(len(plan))}
        )
    result = subprocess.run(["bash", str(script)], check=False)  # noqa: S603, S607
    handles = {}
    if journal.is_file():
        for line in journal.read_text(encoding="utf-8").splitlines():
            job_name, job_id = line.split("\t")
            if job_name not in names or re.fullmatch(r"[0-9]+", job_id) is None:
                msg = f"Invalid submission journal entry: {line!r}"
                raise RuntimeError(msg)
            name = names[job_name]
            handles[name] = JobHandle(
                job_id=job_id,
                backend="slurm",
                metadata={"step": name, "script": str(script)},
            )
    if result.returncode or handles.keys() != plan.keys():
        raise PlanSubmissionError(handles, script)
    return handles
