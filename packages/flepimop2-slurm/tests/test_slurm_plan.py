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
"""Exercise native Slurm submissions with a local fake sbatch executable."""

import json
import os
import shlex
import subprocess  # noqa: S404
import sys
from graphlib import CycleError
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from flepimop2.cli._job_command import job_group
from flepimop2.exceptions import Flepimop2ValidationError
from flepimop2.job.abc import JobDryRun
from flepimop2.job.slurm import SlurmJob
from flepimop2.job.slurm._plan import PlanSubmissionError
from flepimop2.process._plan import ProcessPlan


@pytest.fixture
def provider(tmp_path: Path) -> SlurmJob:
    """Return a provider retaining artifacts in the test directory."""
    return SlurmJob.model_validate({
        "cpus-per-task": 2,
        "memory": "1.2T",
        "nodes": 1,
        "ntasks": 1,
        "time": "01:00:00",
        "sbatch-directory": tmp_path,
        "chdir": tmp_path,
        "sbatch-options": {"account": "test account"},
    })


@pytest.fixture
def plan() -> ProcessPlan:
    """Return an intentionally unordered diamond plan."""
    return {
        "C": {"command": ["echo", "C"], "depends": ["A", "B"]},
        "A": {"command": ["echo", "A with spaces; $(false)"], "depends": []},
        "B": {"command": ["echo", "B"], "depends": []},
    }


@pytest.fixture
def fake_slurm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install an sbatch stub that records argv and returns increasing IDs.

    Returns:
        The JSON log of sbatch calls.
    """
    executable = tmp_path / "sbatch"
    executable.write_text(
        f"#!{sys.executable}\n" + "import json, os, pathlib, sys\n"
        "log = pathlib.Path(os.environ['SBATCH_LOG'])\n"
        "rows = json.loads(log.read_text(encoding='utf-8')) if log.exists() else []\n"
        "rows.append(sys.argv[1:])\n"
        "log.write_text(json.dumps(rows))\n"
        "if len(rows) == int(os.environ.get('SBATCH_FAIL_AT', '0')):\n"
        "    print('sbatch: error: Invalid account', file=sys.stderr); sys.exit(1)\n"
        "if os.environ.get('SBATCH_CWD_LOG'):\n"
        "    pathlib.Path(os.environ['SBATCH_CWD_LOG']).write_text(os.getcwd())\n"
        "if os.environ.get('SBATCH_BAD_ID'): print('invalid'); sys.exit(0)\n"
        "if os.environ.get('SBATCH_BREAK_JOURNAL'):\n"
        "    (pathlib.Path(sys.argv[-1]).parent / 'submitted.jsonl').mkdir()\n"
        "print(str(100 + len(rows)) if '--parsable' in sys.argv else "
        "'Submitted batch job ' + str(100 + len(rows)))\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    log = tmp_path / "calls.json"
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("SBATCH_LOG", str(log))
    return log


def test_plan_dependencies_and_handles(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
) -> None:
    """Independent jobs stay independent; C references actual prerequisite IDs."""
    handles = provider.submit_plan(plan)
    assert isinstance(handles, dict)
    assert {name: h.job_id for name, h in handles.items()} == {
        "A": "101",
        "B": "102",
        "C": "103",
    }
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    assert not any(arg.startswith("--dependency") for call in calls[:2] for arg in call)
    assert "--dependency=afterok:101:102" in calls[2]
    for call in calls:
        assert "--mem=1.2T" in call
        assert "--cpus-per-task=2" in call
        assert "--account=test account" in call
    assert all("--wrap" not in call for call in calls)
    batch = Path(calls[0][-1])
    assert batch.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")
    result = subprocess.run(  # noqa: S603
        ["bash", str(batch)],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "A with spaces; $(false)"


def test_plan_dry_run(provider: SlurmJob, plan: ProcessPlan, fake_slurm: Path) -> None:
    """Dry runs render all jobs and edges without invoking sbatch."""
    result = provider.submit_plan(plan, dry_run=True)
    assert isinstance(result, JobDryRun)
    script = result.command
    assert script.count("--parsable") == len(plan)
    assert "--dependency=afterok:dry-run-A:dry-run-B" in script
    assert not fake_slurm.exists()


def test_partial_failure(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stop after a failed submission and retain handles for accepted jobs."""
    monkeypatch.setenv("SBATCH_FAIL_AT", "2")
    with pytest.raises(PlanSubmissionError) as exc:
        provider.submit_plan(plan)
    assert list(exc.value.handles) == ["A"]
    assert exc.value.handles["A"].job_id == "101"
    assert len(json.loads(fake_slurm.read_text(encoding="utf-8"))) == len(plan) - 1


@pytest.mark.parametrize("mode", ["unknown", "cycle", "empty"])
def test_invalid_plan(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    mode: str,
) -> None:
    """Invalid plans fail before any sbatch call."""
    if mode == "unknown":
        plan["A"]["depends"] = ["missing"]
    elif mode == "cycle":
        plan["A"]["depends"] = ["C"]
    else:
        plan["A"]["command"] = []
    with pytest.raises((ValueError, CycleError)):
        provider.submit_plan(plan)
    assert not fake_slurm.exists()


def test_process_failure_is_not_masked(
    provider: SlurmJob,
    fake_slurm: Path,
    tmp_path: Path,
) -> None:
    """A failed process exits nonzero and does not run successful post-commands."""
    marker = tmp_path / "post-ran"
    provider.post_commands = [shlex.join(["touch", str(marker)])]
    provider.submit_plan({"fail": {"command": ["false"], "depends": []}})
    call = json.loads(fake_slurm.read_text(encoding="utf-8"))[0]
    result = subprocess.run(["bash", call[-1]], check=False)  # noqa: S603, S607
    assert result.returncode != 0
    assert not marker.exists()


def test_empty_plan(provider: SlurmJob, fake_slurm: Path) -> None:
    """Empty plans submit nothing."""
    assert provider.submit_plan({}) == {}
    assert isinstance(provider.submit_plan({}, dry_run=True), JobDryRun)
    assert not fake_slurm.exists()


def test_invalid_job_id(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never submit dependent work when sbatch returns an unusable ID."""
    monkeypatch.setenv("SBATCH_BAD_ID", "1")
    with pytest.raises(PlanSubmissionError) as exc:
        provider.submit_plan(plan)
    assert exc.value.handles == {}
    assert len(json.loads(fake_slurm.read_text(encoding="utf-8"))) == 1


def test_artifact_paths_are_quoted(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    tmp_path: Path,
) -> None:
    """Literal shell characters in artifact paths survive script generation."""
    provider.sbatch_directory = tmp_path / "artifacts with spaces '$dollar"
    handles = provider.submit_plan(plan)
    assert isinstance(handles, dict)
    assert handles.keys() == plan.keys()
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    assert any(str(provider.sbatch_directory) in arg for arg in calls[0])


@pytest.mark.parametrize(
    "option",
    [
        "dependency",
        "array",
        "wrap",
        "quiet",
        "wait",
        "parsable",
        "clusters",
        "cluster-constraint",
    ],
)
def test_conflicting_options(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    option: str,
) -> None:
    """Reject options that could break job-ID tracking or dependencies."""
    provider.sbatch_options[option] = "value"
    with pytest.raises(ValueError, match="Plan submission manages"):
        provider.submit_plan(plan)
    assert not fake_slurm.exists()


def test_public_submission_validates_backend(
    provider: SlurmJob,
    plan: ProcessPlan,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inherited submission rejects an unavailable backend before creating scripts."""
    monkeypatch.setattr("flepimop2.job.slurm.which", lambda _: None)
    with pytest.raises(Flepimop2ValidationError, match="sbatch"):
        provider.submit_plan(plan)
    assert not list(tmp_path.glob("flepimop-plan-*"))


@pytest.mark.parametrize("force", [0, 1, 2])
@pytest.mark.parametrize("dry_run", [False, True])
def test_core_cli_dispatches_slurm_plan(
    provider: SlurmJob,
    tmp_path: Path,
    fake_slurm: Path,
    force: int,
    *,
    dry_run: bool,
) -> None:
    """Core builds no-deps commands and caches each Slurm handle after dispatch."""
    provider.execution = "parallel"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({
            "jobs": {"cluster": provider.model_dump(mode="json")},
            "process": {
                "a": {"module": "shell"},
                "b": {"module": "shell"},
                "c": {"module": "shell", "depends": ["a", "b"]},
            },
        }),
        encoding="utf-8",
    )
    argv = ["process", str(config), "--target", "c", "--job-target", "cluster"]
    if force:
        argv.append("-" + "f" * force)
    if dry_run:
        argv.append("--dry-run")
    with patch("flepimop2.cli._job_command._cache.save_job") as save_job:
        result = CliRunner().invoke(job_group, argv)
    assert result.exit_code == 0, (result.output, result.exception)
    if dry_run:
        assert not fake_slurm.exists()
        save_job.assert_not_called()
        scripts = list(tmp_path.glob("flepimop-plan-*/dry-run.txt"))
        assert len(scripts) == 1
        assert "--dependency=afterok:" in scripts[0].read_text(encoding="utf-8")
        return
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    steps = ["a", "b", "c"]
    assert len(calls) == len(steps)
    assert "--dependency=afterok:101:102" in calls[-1]
    for step, call in zip(steps, calls, strict=True):
        body = Path(call[-1]).read_text(encoding="utf-8")
        command = shlex.split(body.splitlines()[2])
        assert command[:2] == ["flepimop2", "process"]
        assert command[command.index("--target") + 1] == step
        assert "--no-deps" in command
        assert "--dry-run" not in command
        should_force = force > 1 or (force == 1 and step == "c")
        assert ("-f" in command) == should_force
    handles = [call.args[0] for call in save_job.call_args_list]
    assert [handle.job_id for handle in handles] == ["101", "102", "103"]
    assert [handle.metadata["step"] for handle in handles] == steps


@pytest.mark.parametrize("explicit_output", [False, True])
def test_logs_do_not_use_submission_temp_directory(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    *,
    explicit_output: bool,
) -> None:
    """Compute-node output uses the working directory or the explicit setting."""
    provider.sbatch_directory = None
    expected = str(provider.chdir / "slurm-%x-%j.out")
    if explicit_output:
        expected = "custom-%j.out"
        provider.sbatch_options["output"] = expected
    provider.submit_plan(plan)
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    for call in calls:
        assert f"--output={expected}" in call


def test_journal_failure_stops_submission(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed append reports the accepted ID and prevents subsequent jobs."""
    monkeypatch.setenv("SBATCH_BREAK_JOURNAL", "1")
    with pytest.raises(PlanSubmissionError) as exc:
        provider.submit_plan(plan)
    assert len(json.loads(fake_slurm.read_text(encoding="utf-8"))) == 1
    assert exc.value.handles["A"].job_id == "101"
    assert isinstance(exc.value.__cause__, OSError)


def test_batch_preserves_exported_module_function(
    provider: SlurmJob,
    fake_slurm: Path,
    tmp_path: Path,
) -> None:
    """Direct Bash batch execution retains an exported environment-module function."""
    marker = tmp_path / "module-loaded"
    provider.pre_commands = ["module load example"]
    provider.submit_plan({"step": {"command": ["true"], "depends": []}})
    call = json.loads(fake_slurm.read_text(encoding="utf-8"))[0]
    assert "--wrap" not in call
    batch = Path(call[-1])
    assert batch.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash\n")
    launch = (
        'module() { printf "%s\\n" "$*" > "$MODULE_MARKER"; }; '
        'export -f module; exec bash "$1"'
    )
    subprocess.run(  # noqa: S603
        ["bash", "-c", launch, "test", str(batch)],  # noqa: S607
        check=True,
        env=os.environ | {"MODULE_MARKER": str(marker)},
    )
    assert marker.read_text(encoding="utf-8").strip() == "load example"


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        ("0", "0-00:00:00"),
        ("23:59:59", "0-23:59:59"),
        ("24:00:00", "1-00:00:00"),
        ("1-02:03:04", "1-02:03:04"),
        ("3-00:00:00", "3-00:00:00"),
    ],
)
def test_submission_serializes_time(
    provider: SlurmJob, plan: ProcessPlan, fake_slurm: Path, limit: str, expected: str
) -> None:
    """Submission uses Slurm duration syntax, including the one-day boundary."""
    provider = SlurmJob.model_validate(provider.model_dump() | {"time": limit})
    provider.submit_plan(plan)
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    assert all(f"--time={expected}" in call for call in calls)


def test_failed_fourth_submission_retains_journal(
    provider: SlurmJob,
    fake_slurm: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A late failure preserves all accepted IDs and allows a fresh later plan."""
    plan: ProcessPlan = {
        str(i): {"command": ["true"], "depends": [str(i - 1)] if i else []}
        for i in range(5)
    }
    monkeypatch.setenv("SBATCH_FAIL_AT", "4")
    with pytest.raises(PlanSubmissionError) as exc:
        provider.submit_plan(plan)
    assert [h.job_id for h in exc.value.handles.values()] == ["101", "102", "103"]
    rows = (
        (exc.value.directory / "submitted.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert [json.loads(row)["handle"]["job_id"] for row in rows] == [
        "101",
        "102",
        "103",
    ]
    assert len(json.loads(fake_slurm.read_text(encoding="utf-8"))) == len(plan) - 1
    monkeypatch.delenv("SBATCH_FAIL_AT")
    result = provider.submit_plan({"retry": {"command": ["true"], "depends": []}})
    assert isinstance(result, dict)
    assert list(result) == ["retry"]


def test_late_invalid_plan_submits_nothing(
    provider: SlurmJob, fake_slurm: Path
) -> None:
    """Whole-plan validation rejects a bad final step before submitting the first."""
    with pytest.raises(ValueError, match="unknown dependencies"):
        provider.submit_plan({
            "first": {"command": ["true"], "depends": []},
            "last": {"command": ["true"], "depends": ["missing"]},
        })
    assert not fake_slurm.exists()


def test_pre_command_failure_stops_batch(provider: SlurmJob, fake_slurm: Path) -> None:
    """Pre-command failure prevents both the process and post-commands from running."""
    provider.pre_commands = ["false"]
    provider.post_commands = ["echo post"]
    provider.submit_plan({"step": {"command": ["echo", "process"], "depends": []}})
    call = json.loads(fake_slurm.read_text(encoding="utf-8"))[0]
    result = subprocess.run(  # noqa: S603
        ["bash", call[-1]],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not result.stdout


def test_core_cli_serial_uses_one_job(
    provider: SlurmJob,
    tmp_path: Path,
    fake_slurm: Path,
) -> None:
    """Default serial dispatch submits the workflow once without no-deps."""
    config = tmp_path / "serial.json"
    config.write_text(
        json.dumps({
            "jobs": {"cluster": provider.model_dump(mode="json")},
            "process": {
                "a": {"module": "shell"},
                "b": {"module": "shell", "depends": ["a"]},
            },
        })
    )
    with patch("flepimop2.cli._job_command._cache.save_job") as save_job:
        result = CliRunner().invoke(
            job_group,
            [
                "process",
                str(config),
                "--target",
                "b",
                "--job-target",
                "cluster",
            ],
        )
    assert result.exit_code == 0, (result.output, result.exception)
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert "--no-deps" not in Path(calls[0][-1]).read_text(encoding="utf-8")
    save_job.assert_called_once()


def test_unusual_step_names(provider: SlurmJob, fake_slurm: Path) -> None:
    """Original names survive handles while filenames remain distinct and safe."""
    names = ["a b", "a$b", "../$(false)"]
    result = provider.submit_plan({
        name: {"command": ["true"], "depends": []} for name in names
    })
    assert isinstance(result, dict)
    assert list(result) == names
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    assert len({call[-1] for call in calls}) == len(names)
    assert all(
        Path(call[-1]).parent.name.startswith("flepimop-plan-") for call in calls
    )


@pytest.mark.parametrize(
    "variable",
    [
        "SBATCH_ARRAY_INX",
        "SBATCH_WAIT",
        "SBATCH_CLUSTER_CONSTRAINT",
        "SBATCH_CLUSTERS",
        "SLURM_CLUSTERS",
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_conflicting_environment_is_rejected(  # noqa: PLR0913
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    *,
    dry_run: bool,
) -> None:
    """Environment overrides are rejected before submission, including previews."""
    monkeypatch.setenv(variable, "1")
    with pytest.raises(ValueError, match=variable):
        provider.submit_plan(plan, dry_run=dry_run)
    assert not fake_slurm.exists()


def test_submission_preserves_caller_directory(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The submit directory stays distinct from artifact and compute directories."""
    launch = tmp_path / "launch"
    launch.mkdir()
    cwd_log = tmp_path / "submit-cwd.txt"
    monkeypatch.chdir(launch)
    monkeypatch.setenv("SBATCH_CWD_LOG", str(cwd_log))
    provider.submit_plan(plan)
    assert Path(cwd_log.read_text(encoding="utf-8")) == launch
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    assert all(f"--chdir={provider.chdir}" in call for call in calls)
    assert all(Path(call[-1]).is_absolute() for call in calls)


@pytest.mark.parametrize("phase", ["pre", "post"])
def test_pipeline_failure_propagates(
    provider: SlurmJob,
    fake_slurm: Path,
    phase: str,
) -> None:
    """A failed pipeline component makes the batch fail, including post-commands."""
    if phase == "pre":
        provider.pre_commands = ["false | cat"]
    else:
        provider.post_commands = ["false | cat"]
    provider.submit_plan({"step": {"command": ["echo", "process"], "depends": []}})
    call = json.loads(fake_slurm.read_text(encoding="utf-8"))[0]
    result = subprocess.run(  # noqa: S603
        ["bash", call[-1]],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    if phase == "pre":
        assert not result.stdout


def test_submission_error_includes_slurm_diagnostic(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The visible exception identifies the failed step and retains earlier IDs."""
    monkeypatch.setenv("SBATCH_FAIL_AT", "2")
    with pytest.raises(PlanSubmissionError, match="Invalid account") as exc:
        provider.submit_plan(plan)
    assert "step 'B'" in str(exc.value)
    assert exc.value.handles["A"].job_id == "101"
    assert len(json.loads(fake_slurm.read_text(encoding="utf-8"))) == len(plan) - 1


def test_long_step_names_remain_distinct(provider: SlurmJob, fake_slurm: Path) -> None:
    """Long names sharing a prefix retain unique bounded batch filenames."""
    prefix = "x" * 300
    names = [prefix + "a", prefix + "b"]
    result = provider.submit_plan({
        names[0]: {"command": ["true"], "depends": []},
        names[1]: {"command": ["true"], "depends": [names[0]]},
    })
    assert isinstance(result, dict)
    assert list(result) == names
    calls = json.loads(fake_slurm.read_text(encoding="utf-8"))
    assert calls[0][-1] != calls[1][-1]
    assert all(Path(call[-1]).is_file() for call in calls)
    assert "--dependency=afterok:101" in calls[1]
    assert [handle.metadata["step"] for handle in result.values()] == names


def test_disabled_wait_environment_is_allowed(
    provider: SlurmJob,
    plan: ProcessPlan,
    fake_slurm: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicitly disabled Slurm wait option does not block plan submission."""
    monkeypatch.setenv("SBATCH_WAIT", "0")
    result = provider.submit_plan(plan)
    assert isinstance(result, dict)
    assert result.keys() == plan.keys()
    assert len(json.loads(fake_slurm.read_text(encoding="utf-8"))) == len(plan)
