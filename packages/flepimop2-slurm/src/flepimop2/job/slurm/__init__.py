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
"""Slurm job provider for flepimop2.

This module contributes the `slurm` job module to the `flepimop2.job`
namespace, allowing flepimop2 configurations to reference `module: 'slurm'`
to submit jobs to Slurm-managed HPC clusters.
"""

__all__ = ["SlurmJob"]

import re
import subprocess  # noqa: S404
from pathlib import Path
from shutil import which
from tempfile import mkdtemp
from typing import Final
from zlib import adler32

from flepimop2.cli import CliCommand
from flepimop2.exceptions import ValidationIssue
from flepimop2.job.abc import (
    JobABC,
    JobDryRun,
    JobHandle,
    JobStatus,
    JobStatusResult,
)
from flepimop2.job.slurm._command_list import CommandList
from flepimop2.job.slurm._memory_str import MemoryStr
from flepimop2.job.slurm._slurm_timedelta import SlurmTimedelta
from pydantic import ConfigDict, Field, model_validator

_SBATCH_OPTIONS_RESERVED_KEYS: Final[frozenset[str]] = frozenset({
    "chdir",
    "comment",
    "cpus-per-task",
    "job-name",
    "mem",
    "nodes",
    "ntasks",
    "time",
})
_SBATCH_SUBMIT_REGEX: Final[re.Pattern[str]] = re.compile(
    r"Submitted batch job (?P<job_id>\S+)"
)
_SBATCH_JOB_NAME_UNSAFE_REGEX: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9]+")
_SEFF_LINE_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^(?P<key>[^:]+):\s*(?P<value>.*?)\s*$"
)
_SEFF_STATE_REGEX: Final[re.Pattern[str]] = re.compile(r"^(?P<state>[A-Z_]+)")
_SEFF_DETAIL_KEYS: Final[dict[str, str]] = {
    "CPU Utilized": "cpu_utilized",
    "CPU Efficiency": "cpu_efficiency",
    "Job Wall-clock time": "wall_clock_time",
    "Memory Utilized": "memory_utilized",
    "Memory Efficiency": "memory_efficiency",
}
# Maps Slurm job state codes onto flepimop2's `JobStatus` lifecycle. The keys
# are the full set of `squeue`/`sacct` JOB STATE CODES (see `man squeue` and
# <https://slurm.schedmd.com/job_state_codes.html>); `seff` reports the state
# via `sacct`, whose recognized set is a subset of squeue's, so the extra keys
# are simply never hit. Any state not listed here resolves to FINISHED_UNKNOWN.
_SEFF_STATE_TO_JOB_STATUS: Final[dict[str, JobStatus]] = {
    "BOOT_FAIL": JobStatus.FAILED,
    "CANCELLED": JobStatus.FAILED,
    "COMPLETED": JobStatus.SUCCESSFUL,
    "CONFIGURING": JobStatus.PENDING,
    "COMPLETING": JobStatus.RUNNING,
    "DEADLINE": JobStatus.FAILED,
    "FAILED": JobStatus.FAILED,
    "NODE_FAIL": JobStatus.FAILED,
    "OUT_OF_MEMORY": JobStatus.FAILED,
    "PENDING": JobStatus.PENDING,
    "PREEMPTED": JobStatus.FAILED,
    "RESV_DEL_HOLD": JobStatus.PENDING,
    "REQUEUE_FED": JobStatus.PENDING,
    "REQUEUE_HOLD": JobStatus.PENDING,
    "REQUEUED": JobStatus.PENDING,
    "RESIZING": JobStatus.RUNNING,
    "REVOKED": JobStatus.FAILED,
    "RUNNING": JobStatus.RUNNING,
    "SIGNALING": JobStatus.RUNNING,
    "SPECIAL_EXIT": JobStatus.FAILED,
    "STAGE_OUT": JobStatus.RUNNING,
    "STOPPED": JobStatus.RUNNING,
    "SUSPENDED": JobStatus.RUNNING,
    "TIMEOUT": JobStatus.FAILED,
}


class SlurmJob(JobABC, module="slurm"):
    """Submit and manage flepimop2 jobs on a Slurm HPC cluster.

    Attributes:
        cpus_per_task: The number of CPUs to request per task.
        memory: The amount of memory to request for the job, specified in a format like
            "1.2G" or "500M".
        nodes: The number of nodes to request for the job.
        ntasks: The number of tasks to request for the job.
        time: The job time limit, either specified
            [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339) format or in a
            [slurm time limit format](https://slurm.schedmd.com/sbatch.html#OPT_time).
        chdir: The working directory to use when executing the job command. Defaults to
            the current working directory at submission time.
        debug: If `True`, the job will be submitted in debug mode (e.g. with `set -x`).
        pre_commands: Optional commands to run before the main job command.
        post_commands: Optional commands to run after the main job command.
        sbatch_options: Additional options to pass to `sbatch` that are not covered by
            the other fields. Keys should be the long-form option name without the
            leading dashes (e.g. `account` for `--account`).
        sbatch_directory: The directory in which to place the generated sbatch file. If
            not specified or `None` a temporary directory will be used. It can be
            helpful for debugging or for keeping a record of the sbatch files.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    cpus_per_task: int = Field(alias="cpus-per-task", ge=1)
    memory: MemoryStr
    nodes: int = Field(ge=1)
    ntasks: int = Field(ge=1)
    time: SlurmTimedelta
    chdir: Path = Field(default_factory=Path.cwd)
    debug: bool = False
    pre_commands: CommandList = Field(alias="pre-commands", default_factory=list)
    post_commands: CommandList = Field(alias="post-commands", default_factory=list)
    sbatch_options: dict[str, str] = Field(alias="sbatch-options", default_factory=dict)
    sbatch_directory: Path | None = Field(alias="sbatch-directory", default=None)

    @model_validator(mode="before")
    @classmethod
    def _validate_sbatch_options(cls, data: object) -> object:
        """Validate arbitrary sbatch options before field validation.

        Args:
            data: The raw model input.

        Returns:
            The raw model input if `sbatch-options` does not include reserved
            options.

        Raises:
            ValueError: If `sbatch-options` includes an option handled by a
                dedicated `SlurmJob` field.

        Examples:
            >>> SlurmJob.model_validate({
            ...     "cpus-per-task": 2,
            ...     "memory": "1G",
            ...     "nodes": 1,
            ...     "ntasks": 1,
            ...     "time": "01:00:00",
            ...     "sbatch-options": {"chdir": "/foo/bar"},
            ... })
            Traceback (most recent call last):
                ...
            pydantic_core._pydantic_core.ValidationError: 1 validation error for SlurmJob
              Value error, sbatch-options cannot include reserved option(s): 'chdir' [...]
                For further information visit ...
        """  # noqa: E501
        if not isinstance(data, dict):
            return data
        sbatch_options = data.get("sbatch-options")
        if not isinstance(sbatch_options, dict):
            return data
        reserved_keys = sorted(_SBATCH_OPTIONS_RESERVED_KEYS & sbatch_options.keys())
        if reserved_keys:
            keys = ", ".join(repr(key) for key in reserved_keys)
            msg = f"sbatch-options cannot include reserved option(s): {keys}"
            raise ValueError(msg)
        return data

    @staticmethod
    def _command_metadata(command: CliCommand) -> dict[str, str]:
        """Extract relevant metadata from a CLI command for sbatch options.

        Args:
            command: The CLI command instance to extract metadata from.

        Returns:
            A dictionary containing the command's metadata.

        Examples:
            >>> from pathlib import Path
            >>> class ExampleCommand(CliCommand):
            ...     def run(self) -> int:
            ...         return 0
            ...
            ...     @property
            ...     def target(self) -> str:
            ...         return "target"
            ...
            ...     @classmethod
            ...     def options(cls) -> list[str]:
            ...         return ["config", "target"]
            >>> command = ExampleCommand(config=Path("config.yaml"), target="target")
            >>> SlurmJob._command_metadata(command)
            {'command': 'example', 'config': 'config.yaml', 'target': 'target'}
        """
        return {
            key: str(value)
            for key, value in {
                "command": command.command_name(),
                "config": command.config,
                "target": command.target,
            }.items()
            if value is not None
        }

    @staticmethod
    def _sbatch_job_name(command: CliCommand, delimiter: str = ":") -> str:
        """Build a Slurm job name from a CLI command.

        Args:
            command: The CLI command instance to submit.
            delimiter: The delimiter to use between job name parts.

        Returns:
            The Slurm job name.

        Examples:
            >>> from pathlib import Path
            >>> class ExampleCommand(CliCommand):
            ...     def run(self) -> int:
            ...         return 0
            ...
            ...     @property
            ...     def target(self) -> str:
            ...         return "target"
            ...
            ...     @classmethod
            ...     def options(cls) -> list[str]:
            ...         return ["config", "target"]
            >>> command = ExampleCommand(config=Path("config.yaml"), target="target")
            >>> SlurmJob._sbatch_job_name(command)
            'flepimop2:example:config:target'
            >>> SlurmJob._sbatch_job_name(command, delimiter="_")
            'flepimop2_example_config_target'
        """
        metadata = SlurmJob._command_metadata(command)
        if "config" in metadata:
            metadata["config"] = Path(metadata["config"]).stem
        name_parts = [
            metadata[key]
            for key in ("command", "config", "target")
            if metadata.get(key)
        ]
        name_parts = [
            _SBATCH_JOB_NAME_UNSAFE_REGEX.sub("_", part).strip("_")
            for part in name_parts
        ]
        name_parts = [part for part in name_parts if part]
        return delimiter.join(["flepimop2", *name_parts])

    @staticmethod
    def _sbatch_comment(command: CliCommand) -> str:
        """Build default Slurm metadata options from a CLI command.

        Args:
            command: The CLI command instance to submit.

        Returns:
            The default `comment` sbatch option, or an empty string when no command is
            available.

        Examples:
            >>> from pathlib import Path
            >>> class ExampleCommand(CliCommand):
            ...     def run(self) -> int:
            ...         return 0
            ...
            ...     @property
            ...     def target(self) -> str:
            ...         return "target"
            ...
            ...     @classmethod
            ...     def options(cls) -> list[str]:
            ...         return ["config", "target"]
            >>> command = ExampleCommand(config=Path("config.yaml"), target="target")
            >>> SlurmJob._sbatch_comment(command)
            'command=example config=config.yaml target=target'
            >>> SlurmJob._sbatch_comment(ExampleCommand())
            'command=example target=target'
        """
        return " ".join(
            f"{key}={value}"
            for key, value in SlurmJob._command_metadata(command).items()
        )

    @staticmethod
    def _sbatch_filename(command: CliCommand, sbatch_script: str) -> str:
        """Build an informative filename for a generated sbatch script.

        Args:
            command: The CLI command instance to submit.
            sbatch_script: The generated sbatch script contents.

        Returns:
            A filename with a sanitized job name and short checksum.

        Examples:
            >>> from pathlib import Path
            >>> class ExampleCommand(CliCommand):
            ...     def run(self) -> int:
            ...         return 0
            ...
            ...     @property
            ...     def target(self) -> str:
            ...         return "target"
            ...
            ...     @classmethod
            ...     def options(cls) -> list[str]:
            ...         return ["config", "target"]
            >>> command = ExampleCommand(config=Path("config.yaml"), target="target")
            >>> SlurmJob._sbatch_filename(command, "script")
            'flepimop2_example_config_target_08fe0296.batch'
        """
        job_name = SlurmJob._sbatch_job_name(command, delimiter="_")
        checksum = adler32(sbatch_script.encode("utf-8")) & 0xFFFFFFFF
        return f"{job_name}_{checksum:08x}.batch"

    @staticmethod
    def _parse_sbatch_job_id(stdout: str) -> str:
        r"""Parse the Slurm job ID from `sbatch` output.

        Args:
            stdout: Standard output emitted by `sbatch`.

        Returns:
            The submitted Slurm job ID.

        Raises:
            RuntimeError: If `stdout` does not contain a Slurm job ID.

        Examples:
            >>> SlurmJob._parse_sbatch_job_id("Submitted batch job 34987")
            '34987'
            >>> SlurmJob._parse_sbatch_job_id("sbatch: error: ...")
            Traceback (most recent call last):
                ...
            RuntimeError: Could not parse Slurm job id from sbatch output: 'sbatch: error: ...'
        """  # noqa: E501
        match = _SBATCH_SUBMIT_REGEX.search(stdout)
        if match is None:
            msg = f"Could not parse Slurm job id from sbatch output: {stdout!r}"
            raise RuntimeError(msg)
        return match.group("job_id")

    @staticmethod
    def _parse_seff(stdout: str) -> dict[str, str]:
        r"""Parse the colon-delimited key/value pairs emitted by `seff`.

        Args:
            stdout: Standard output emitted by `seff`.

        Returns:
            A mapping of `seff` field names to their string values.

        Examples:
            >>> from pprint import pp
            >>> stdout = (
            ...     "Job ID: 34987\n"
            ...     "State: COMPLETED (exit code 0)\n"
            ...     "CPU Utilized: 00:05:00\n"
            ...     "CPU Efficiency: 80.00% of 00:06:15 core-walltime\n"
            ...     "Job Wall-clock time: 00:01:34\n"
            ...     "Memory Utilized: 1.50 GB\n"
            ...     "Memory Efficiency: 18.75% of 8.00 GB\n"
            ... )
            >>> pp(SlurmJob._parse_seff(stdout))
            {'Job ID': '34987',
             'State': 'COMPLETED (exit code 0)',
             'CPU Utilized': '00:05:00',
             'CPU Efficiency': '80.00% of 00:06:15 core-walltime',
             'Job Wall-clock time': '00:01:34',
             'Memory Utilized': '1.50 GB',
             'Memory Efficiency': '18.75% of 8.00 GB'}
        """
        fields: dict[str, str] = {}
        for line in stdout.splitlines():
            match = _SEFF_LINE_REGEX.match(line)
            if match is not None:
                fields[match.group("key").strip()] = match.group("value")
        return fields

    @staticmethod
    def _seff_state_to_job_status(state: str) -> JobStatus:
        """Map a Slurm job state reported by `seff` to a `JobStatus`.

        Only the leading `[A-Z_]+` state token is used for the lookup, so the
        trailing detail `sacct`/`seff` may append is ignored: a parenthesized
        exit code (`"COMPLETED (exit code 0)"`), a space-delimited actor
        (`"CANCELLED by 1000"`), or the `"+"` truncation marker `sacct` adds when
        extra state information does not fit the field width (`"CANCELLED+"`).

        Args:
            state: The `State` value emitted by `seff` (e.g. `"COMPLETED (exit
                code 0)"`).

        Returns:
            The corresponding `JobStatus`. Unrecognized states are reported as
            `JobStatus.FINISHED_UNKNOWN`.

        Examples:
            >>> SlurmJob._seff_state_to_job_status("COMPLETED (exit code 0)")
            <JobStatus.SUCCESSFUL: 'successful'>
            >>> SlurmJob._seff_state_to_job_status("RUNNING")
            <JobStatus.RUNNING: 'running'>
            >>> SlurmJob._seff_state_to_job_status("CANCELLED by 1000")
            <JobStatus.FAILED: 'failed'>
            >>> SlurmJob._seff_state_to_job_status("CANCELLED+")
            <JobStatus.FAILED: 'failed'>
            >>> SlurmJob._seff_state_to_job_status("MADE_UP")
            <JobStatus.FINISHED_UNKNOWN: 'finished_unknown'>
        """
        match = _SEFF_STATE_REGEX.match(state)
        key = match.group("state") if match is not None else state
        return _SEFF_STATE_TO_JOB_STATUS.get(key, JobStatus.FINISHED_UNKNOWN)

    def _sbatch_options(self, command: CliCommand) -> dict[str, str]:
        """Get the complete set of sbatch options for this job.

        This method combines the user-specified `sbatch_options` with the
        options derived from the dedicated fields (e.g. `cpus-per-task` from
        `cpus_per_task`) to produce the complete set of options to pass to
        `sbatch`.

        Returns:
            A dictionary of sbatch option names and their corresponding values.

        Examples:
            >>> from pathlib import Path
            >>> from pprint import pp
            >>> class ExampleCommand(CliCommand):
            ...     def run(self) -> int:
            ...         return 0
            ...
            ...     @property
            ...     def target(self) -> str:
            ...         return "target"
            ...
            ...     @classmethod
            ...     def options(cls) -> list[str]:
            ...         return ["config", "target"]
            >>> command = ExampleCommand(config=Path("config.yaml"), target="target")
            >>> job = SlurmJob.model_validate({
            ...     "cpus-per-task": 4,
            ...     "memory": "8G",
            ...     "nodes": 2,
            ...     "ntasks": 4,
            ...     "time": "1:00:00",
            ...     "chdir": "/current/working/directory",
            ...     "sbatch-options": {"account": "my-account", "qos": "normal"},
            ... })
            >>> pp(job._sbatch_options(command))
            {'account': 'my-account',
             'chdir': '/current/working/directory',
             'comment': 'command=example config=config.yaml target=target',
             'cpus-per-task': '4',
             'job-name': 'flepimop2:example:config:target',
             'mem': '8G',
             'nodes': '2',
             'ntasks': '4',
             'qos': 'normal',
             'time': '1:00:00'}
        """
        opts = (
            {
                "comment": self._sbatch_comment(command),
                "job-name": self._sbatch_job_name(command),
            }
            | self.sbatch_options
            | {
                "chdir": str(self.chdir.absolute()),
                "cpus-per-task": str(self.cpus_per_task),
                "mem": str(self.memory),
                "nodes": str(self.nodes),
                "ntasks": str(self.ntasks),
                "time": str(self.time),
            }
        )
        return dict(sorted(opts.items()))

    def _sbatch_contents(self, command: CliCommand) -> str:
        """Build the complete sbatch script contents for a command.

        Args:
            command: The CLI command instance to submit.

        Returns:
            The sbatch script contents.
        """
        sbatch_contents: list[str] = [
            "#!/usr/bin/env bash",
            *[f'#SBATCH --{k}="{v}"' for k, v in self._sbatch_options(command).items()],
            "",
        ]
        if self.debug:
            sbatch_contents.extend(["set -x", ""])
        if self.pre_commands:
            sbatch_contents.extend([*self.pre_commands, ""])
        sbatch_contents.extend([str(command), ""])
        if self.post_commands:
            sbatch_contents.extend([*self.post_commands, ""])
        return "\n".join(sbatch_contents)

    def _submit(
        self, command: CliCommand, *, dry_run: bool = False
    ) -> JobHandle | JobDryRun:
        """Backend-specific submission implementation.

        Renders the sbatch script and writes it to disk regardless of `dry_run`;
        when `dry_run` is `True` it stops just before invoking `sbatch` and
        returns a `JobDryRun` describing the submission it skipped. The generated
        batch file already records every sbatch option, so no additional
        metadata is attached to the `JobDryRun`.

        Args:
            command: The CLI command instance to submit.
            dry_run: If `True`, render and write the sbatch file but do not
                invoke `sbatch`.

        Returns:
            A handle for the submitted Slurm job, or a `JobDryRun` describing the
            skipped submission when `dry_run=True`.

        Raises:
            RuntimeError: If the `sbatch` executable is not found in PATH.
        """
        sbatch = which("sbatch")
        if sbatch is None:
            msg = "Cannot submit SlurmJob: 'sbatch' executable not found in PATH"
            raise RuntimeError(msg)

        sbatch_script = self._sbatch_contents(command)

        sbatch_directory = (self.sbatch_directory or Path(mkdtemp())).absolute()
        sbatch_directory.mkdir(parents=True, exist_ok=True)
        sbatch_file = sbatch_directory / self._sbatch_filename(command, sbatch_script)
        if not sbatch_file.exists():
            sbatch_file.write_text(sbatch_script, encoding="utf-8")

        if dry_run:
            return JobDryRun(command=f"{sbatch} {sbatch_file}")

        result = subprocess.run(  # noqa: S603
            [sbatch, str(sbatch_file)],
            check=True,
            capture_output=True,
            text=True,
        )
        job_id = self._parse_sbatch_job_id(result.stdout)
        return JobHandle(job_id=job_id, backend="slurm")

    @staticmethod
    def _submit_validate() -> list[ValidationIssue] | None:
        """Validate that this backend is ready to accept submissions.

        Called by `submit` before delegating to `_submit`. Subclasses may
        override to perform backend-specific preflight checks (e.g. resolving
        executables, checking credentials, testing connectivity).

        Returns:
            A list of `ValidationIssue` objects if validation fails, an empty
            list if validation passes with no issues, or `None` if not
            implemented.
        """
        if which("sbatch") is None:
            msg = "SlurmJob requires the 'sbatch' executable to be available in PATH"
            return [ValidationIssue(msg=msg, kind="executable_not_found")]
        return None

    def _status(self, handle: JobHandle) -> JobStatusResult:
        """Report the status of a previously submitted Slurm job via `seff`.

        Runs `seff <job_id>` and parses its output to derive the job's lifecycle
        `status` from the reported Slurm `State`. The CPU utilized, CPU
        efficiency, job wall-clock time, memory utilized, and memory efficiency
        fields are extracted into the result's `detail` mapping when `seff`
        reports them (terminal jobs report all of them; in-flight jobs typically
        report a subset).

        Args:
            handle: The handle returned when the job was submitted.

        Returns:
            A `JobStatusResult` describing the job's current state.

        Raises:
            RuntimeError: If the `seff` executable is not found in PATH.
        """
        seff = which("seff")
        if seff is None:
            msg = "Cannot query SlurmJob status: 'seff' executable not found in PATH"
            raise RuntimeError(msg)

        result = subprocess.run(  # noqa: S603
            [seff, handle.job_id],
            check=True,
            capture_output=True,
            text=True,
        )
        fields = self._parse_seff(result.stdout)

        status = self._seff_state_to_job_status(fields.get("State", ""))
        detail: dict[str, str] = {}
        if "State" in fields:
            detail["state"] = fields["State"]
        for seff_key, detail_key in _SEFF_DETAIL_KEYS.items():
            if seff_key in fields:
                detail[detail_key] = fields[seff_key]

        return JobStatusResult(
            job_id=handle.job_id,
            backend=handle.backend,
            submitted_at=handle.submitted_at,
            metadata=handle.metadata,
            status=status,
            detail=detail,
        )

    @staticmethod
    def _status_validate() -> list[ValidationIssue] | None:
        """Validate that this backend is ready to report job status.

        Called by `status` before delegating to `_status`.

        Returns:
            A one-element list containing a `ValidationIssue` if the `seff`
            executable cannot be located on PATH, otherwise `None`.
        """
        if which("seff") is None:
            msg = "SlurmJob requires the 'seff' executable to be available in PATH"
            return [ValidationIssue(msg=msg, kind="executable_not_found")]
        return None
