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
"""Tests for the `flepimop2.job.slurm` provider."""

import re
import subprocess  # noqa: S404
from pathlib import Path
from typing import Any

import flepimop2.job.slurm as slurm_module
import pytest
from flepimop2.cli import CliCommand
from flepimop2.job.abc import JobDryRun, JobHandle, JobStatus
from flepimop2.job.slurm import _SBATCH_OPTIONS_RESERVED_KEYS, SlurmJob
from flepimop2.typing import ExitCode
from pydantic import ValidationError


class ExampleCommand(CliCommand):
    """Example command for Slurm job tests."""

    def run(self, **kwargs: Any) -> ExitCode:
        """Run the example command.

        Returns:
            A successful exit code.
        """
        del kwargs
        return ExitCode.OKAY

    @property
    def target(self) -> str | None:
        """Get the example command target.

        Returns:
            The bound target value, if provided.
        """
        value = self.bound_kwargs.get("target")
        if value is None:
            return None
        return str(value)

    @classmethod
    def options(cls) -> list[str]:
        """Get CLI options used by the example command.

        Returns:
            The config and target options.
        """
        return ["config", "target"]


def _slurm_job_config(**overrides: Any) -> dict[str, Any]:
    """Create a minimal Slurm job config for tests.

    Returns:
        A raw Slurm job config dictionary.
    """
    return {
        "cpus-per-task": 1,
        "memory": "1.2t",
        "nodes": 1,
        "ntasks": 1,
        "time": "1:02:03",
    } | overrides


def test_slurm_job_accepts_string_commands() -> None:
    """`SlurmJob` accepts command strings for pre and post commands."""
    pre_commands = "if [ -f foo ]; then\n  echo found\nfi"
    post_commands = "echo complete"
    job = SlurmJob.model_validate(
        _slurm_job_config(**{
            "pre-commands": pre_commands,
            "post-commands": post_commands,
        })
    )
    assert job.pre_commands == [pre_commands]
    assert job.post_commands == [post_commands]


def test_slurm_job_accepts_arbitrary_sbatch_options() -> None:
    """`SlurmJob` accepts arbitrary non-reserved sbatch options."""
    job = SlurmJob.model_validate(
        _slurm_job_config(**{
            "sbatch-options": {"account": "my-account", "qos": "normal"}
        })
    )
    assert job.sbatch_options == {"account": "my-account", "qos": "normal"}


@pytest.mark.parametrize("key", sorted(_SBATCH_OPTIONS_RESERVED_KEYS))
def test_slurm_job_rejects_reserved_sbatch_options(key: str) -> None:
    """`SlurmJob` rejects sbatch options handled by dedicated fields."""
    with pytest.raises(ValidationError, match="sbatch-options cannot include reserved"):
        SlurmJob.model_validate(
            _slurm_job_config(**{"sbatch-options": {key: "reserved"}})
        )


def test_slurm_job_sbatch_contents() -> None:
    """`SlurmJob._sbatch_contents` builds the expected sbatch script."""
    pre_commands = "module load flepimop2"
    post_commands = "echo complete"
    job = SlurmJob.model_validate(
        _slurm_job_config(**{
            "pre-commands": pre_commands,
            "post-commands": post_commands,
            "sbatch-options": {"account": "my-account"},
        })
    )
    command = ExampleCommand(config=Path("config.yaml"), target="my_target")

    sbatch_script = job._sbatch_contents(command)

    assert sbatch_script.startswith("#!/usr/bin/env bash\n")
    assert '#SBATCH --account="my-account"' in sbatch_script
    assert '#SBATCH --job-name="flepimop2:example:config:my_target"' in sbatch_script
    assert (
        '#SBATCH --comment="command=example config=config.yaml target=my_target"'
        in sbatch_script
    )
    assert pre_commands in sbatch_script
    assert str(command) in sbatch_script
    assert post_commands in sbatch_script


def test_slurm_job_submit_writes_sbatch_file_and_returns_handle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SlurmJob._submit` writes and submits an sbatch file."""
    submitted_args: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        assert command == "sbatch"
        return "/usr/bin/sbatch"

    def fake_run(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        submitted_args.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="Submitted batch job 34987\n",
            stderr="",
        )

    monkeypatch.setattr(slurm_module, "which", fake_which)
    monkeypatch.setattr("flepimop2.job.slurm.subprocess.run", fake_run)

    job = SlurmJob.model_validate(
        _slurm_job_config(**{
            "pre-commands": "module load flepimop2",
            "sbatch-directory": tmp_path,
        })
    )
    command = ExampleCommand(config=Path("config.yaml"), target="my_target")

    handle = job._submit(command)

    assert isinstance(handle, JobHandle)
    assert handle.job_id == "34987"
    assert handle.backend == "slurm"
    assert len(submitted_args) == 1
    assert submitted_args[0][0] == "/usr/bin/sbatch"

    sbatch_file = Path(submitted_args[0][1])
    assert sbatch_file.parent == tmp_path.absolute()
    assert re.fullmatch(
        r"flepimop2_example_config_my_target_[0-9a-f]{8}\.batch", sbatch_file.name
    )
    assert sbatch_file.read_text(encoding="utf-8") == job._sbatch_contents(command)


def test_slurm_job_submit_dry_run_writes_file_but_does_not_submit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SlurmJob._submit(dry_run=True)` writes the sbatch file but skips sbatch."""

    def fake_which(command: str) -> str | None:
        assert command == "sbatch"
        return "/usr/bin/sbatch"

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        msg = "sbatch should not be invoked during a dry run"
        raise AssertionError(msg)

    monkeypatch.setattr(slurm_module, "which", fake_which)
    monkeypatch.setattr("flepimop2.job.slurm.subprocess.run", fake_run)

    job = SlurmJob.model_validate(_slurm_job_config(**{"sbatch-directory": tmp_path}))
    command = ExampleCommand(config=Path("config.yaml"), target="my_target")

    result = job._submit(command, dry_run=True)

    assert isinstance(result, JobDryRun)
    assert result.command.startswith("/usr/bin/sbatch ")
    sbatch_file = Path(result.command.split(" ", 1)[1])
    assert sbatch_file.parent == tmp_path.absolute()
    assert sbatch_file.read_text(encoding="utf-8") == job._sbatch_contents(command)


_SEFF_COMPLETED = (
    "Job ID: 34987\n"
    "Cluster: mycluster\n"
    "State: COMPLETED (exit code 0)\n"
    "Nodes: 1\n"
    "Cores per node: 4\n"
    "CPU Utilized: 00:05:00\n"
    "CPU Efficiency: 80.00% of 00:06:15 core-walltime\n"
    "Job Wall-clock time: 00:01:34\n"
    "Memory Utilized: 1.50 GB\n"
    "Memory Efficiency: 18.75% of 8.00 GB\n"
)


def test_slurm_job_status_parses_seff_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SlurmJob._status` maps `seff` State to a status and extracts details."""
    queried_args: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        assert command == "seff"
        return "/usr/bin/seff"

    def fake_run(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        queried_args.append(args)
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout=_SEFF_COMPLETED, stderr=""
        )

    monkeypatch.setattr(slurm_module, "which", fake_which)
    monkeypatch.setattr("flepimop2.job.slurm.subprocess.run", fake_run)

    job = SlurmJob.model_validate(_slurm_job_config())
    handle = JobHandle(job_id="34987", backend="slurm")

    result = job._status(handle)

    assert queried_args == [["/usr/bin/seff", "34987"]]
    assert result.job_id == "34987"
    assert result.backend == "slurm"
    assert result.status is JobStatus.SUCCESSFUL
    assert result.detail == {
        "state": "COMPLETED (exit code 0)",
        "cpu_utilized": "00:05:00",
        "cpu_efficiency": "80.00% of 00:06:15 core-walltime",
        "wall_clock_time": "00:01:34",
        "memory_utilized": "1.50 GB",
        "memory_efficiency": "18.75% of 8.00 GB",
    }


def test_slurm_job_status_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SlurmJob._status` reports `RUNNING` for an in-flight job."""

    def fake_which(_command: str) -> str | None:
        return "/usr/bin/seff"

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="Job ID: 1\nState: RUNNING\n",
            stderr="",
        )

    monkeypatch.setattr(slurm_module, "which", fake_which)
    monkeypatch.setattr("flepimop2.job.slurm.subprocess.run", fake_run)

    job = SlurmJob.model_validate(_slurm_job_config())
    result = job._status(JobHandle(job_id="1", backend="slurm"))

    assert result.status is JobStatus.RUNNING
    assert result.detail == {"state": "RUNNING"}


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("COMPLETED (exit code 0)", JobStatus.SUCCESSFUL),
        ("CANCELLED by 1000", JobStatus.FAILED),
        ("CANCELLED+", JobStatus.FAILED),
        ("TIMEOUT", JobStatus.FAILED),
        ("RUNNING", JobStatus.RUNNING),
        ("PENDING", JobStatus.PENDING),
        ("MADE_UP", JobStatus.FINISHED_UNKNOWN),
    ],
)
def test_slurm_job_seff_state_to_job_status(state: str, expected: JobStatus) -> None:
    """`seff` State strings map to the expected `JobStatus`, ignoring suffixes."""
    assert SlurmJob._seff_state_to_job_status(state) is expected


def test_slurm_job_status_raises_without_seff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`SlurmJob._status` raises when `seff` is not on PATH."""
    monkeypatch.setattr(slurm_module, "which", lambda _: None)

    job = SlurmJob.model_validate(_slurm_job_config())
    with pytest.raises(RuntimeError, match="'seff' executable not found"):
        job._status(JobHandle(job_id="1", backend="slurm"))


def test_slurm_job_status_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SlurmJob._status_validate` reports a missing `seff` executable."""
    monkeypatch.setattr(slurm_module, "which", lambda _: None)
    issues = SlurmJob._status_validate()
    assert issues is not None
    assert len(issues) == 1
    assert issues[0].kind == "executable_not_found"

    monkeypatch.setattr(slurm_module, "which", lambda _: "/usr/bin/seff")
    assert SlurmJob._status_validate() is None
