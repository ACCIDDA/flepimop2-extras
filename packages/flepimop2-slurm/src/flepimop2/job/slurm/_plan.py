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
"""Native Slurm step submission and plan recovery artifacts."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess  # noqa: S404
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from pathlib import Path
from tempfile import mkdtemp
from typing import TYPE_CHECKING

from flepimop2.job.abc import JobDryRun, JobHandle

if TYPE_CHECKING:
    from flepimop2.job.slurm import SlurmJob
    from flepimop2.process.abc import ProcessPlan


class PlanSubmissionError(RuntimeError):
    """Submission failed; accepted jobs remain available in handles."""

    def __init__(
        self, handles: dict[str, JobHandle], directory: Path, reason: str
    ) -> None:
        self.handles = handles.copy()
        self.directory = directory
        super().__init__(
            f"Plan submission failed: {reason}; submitted jobs: {handles}. "
            f"Batch files and submission journal retained in {directory}."
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
    forbidden = {
        "dependency",
        "array",
        "wrap",
        "parsable",
        "quiet",
        "wait",
        "clusters",
        "cluster-constraint",
    }
    if conflicts := forbidden & provider.sbatch_options.keys():
        msg = f"Plan submission manages these sbatch options: {sorted(conflicts)}."
        raise ValueError(msg)
    conflicting_environment = {
        "SBATCH_ARRAY_INX",
        "SBATCH_WAIT",
        "SBATCH_CLUSTER_CONSTRAINT",
        "SBATCH_CLUSTERS",
        "SLURM_CLUSTERS",
    } & os.environ.keys()
    if os.environ.get("SBATCH_WAIT") == "0":
        conflicting_environment.discard("SBATCH_WAIT")
    if conflicting_environment:
        msg = (
            "Unset these environment variables before plan submission: "
            f"{sorted(conflicting_environment)}. "
            "Configure supported options on the provider."
        )
        raise ValueError(msg)
    options = provider.sbatch_options | {
        "cpus-per-task": str(provider.cpus_per_task),
        "mem": str(provider.memory),
        "nodes": str(provider.nodes),
        "ntasks": str(provider.ntasks),
        "time": provider.model_dump(mode="json", include={"time"})["time"],
        "chdir": str(provider.chdir.absolute()),
    }
    return [f"--{key}={value}" for key, value in sorted(options.items())]


@dataclass
class PlanSubmission:
    """Artifacts and accepted handles scoped to one plan submission."""

    directory: Path
    handles: dict[str, JobHandle] = field(default_factory=dict)
    index: int = 0

    @classmethod
    def create(cls, provider: SlurmJob) -> PlanSubmission:
        """Create retained artifacts for a submission.

        Returns:
            A fresh submission context.
        """
        parent = provider.sbatch_directory
        if parent is not None:
            parent.mkdir(parents=True, exist_ok=True)
        return cls(Path(mkdtemp(prefix="flepimop-plan-", dir=parent)).absolute())

    def submit_step(
        self,
        provider: SlurmJob,
        name: str,
        command: list[str],
        depends_on: list[JobHandle],
        *,
        dry_run: bool,
    ) -> JobHandle | JobDryRun:
        """Submit one Bash batch file with native Slurm dependencies.

        Returns:
            The accepted handle or a display-only dry-run command.

        Raises:
            RuntimeError: Slurm returns an invalid job ID.
        """
        label = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:120]
        job_name = f"step-{self.index:04d}-{label}"
        self.index += 1
        batch = self.directory / f"{job_name}.batch"
        batch.write_text(
            "\n".join([
                "#!/usr/bin/env bash",
                "set -e -o pipefail",
                *(["set -x"] if provider.debug else []),
                *provider.pre_commands,
                shlex.join(command),
                *provider.post_commands,
                "",
            ]),
            encoding="utf-8",
        )
        args = ["sbatch", "--parsable", *_submission_options(provider)]
        if "job-name" not in provider.sbatch_options:
            args.append(f"--job-name={job_name}")
        if "output" not in provider.sbatch_options:
            args.append(f"--output={provider.chdir.absolute() / 'slurm-%x-%j.out'}")
        if depends_on:
            args.append(
                "--dependency=afterok:" + ":".join(h.job_id for h in depends_on)
            )
        args.append(str(batch))
        if dry_run:
            return JobDryRun(command=shlex.join(args), details={"batch": str(batch)})
        result = subprocess.run(  # noqa: S603
            args,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            diagnostic = (
                result.stderr.strip()
                or result.stdout.strip()
                or "No diagnostic output."
            )
            msg = (
                f"sbatch failed for step {name!r} "
                f"(exit {result.returncode}): {diagnostic}"
            )
            raise RuntimeError(msg)
        job_id = result.stdout.strip()
        if re.fullmatch(r"[0-9]+", job_id) is None:
            msg = f"Invalid or unsupported sbatch job ID: {job_id!r}."
            raise RuntimeError(msg)
        handle = JobHandle(
            job_id=job_id,
            backend="slurm",
            metadata={"step": name, "script": str(batch)},
        )
        # Track acceptance before writing: even a journal failure retains this ID.
        self.handles[name] = handle
        with (self.directory / "submitted.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"step": name, "handle": handle.model_dump(mode="json")})
                + "\n"
            )
        return handle
