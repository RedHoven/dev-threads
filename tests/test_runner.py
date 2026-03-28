"""Tests for TaskRunner and run_task."""

from __future__ import annotations

import pytest

from dev_threads.boxd import BoxdError
from dev_threads.runner import TaskResult, TaskRunner, run_task


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def runner(mocker) -> TaskRunner:
    """A TaskRunner with a fully mocked BoxdClient."""
    r = TaskRunner(endpoint="http://mock:2375", anthropic_api_key="test-key")

    client = mocker.AsyncMock()
    client.create_vm.return_value = "vm-001"
    client.start_vm.return_value = None
    client.wait_vm.return_value = 0
    client.get_logs.return_value = "Task complete.\n"
    client.remove_vm.return_value = None

    r._client = client
    return r


# ── run() happy path ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_run_returns_task_result(runner: TaskRunner):
    result = await runner.run("Write unit tests for utils.py")
    assert isinstance(result, TaskResult)
    assert result.success
    assert result.exit_code == 0
    assert "Task complete." in result.output
    assert result.vm_id == "vm-001"
    assert result.task == "Write unit tests for utils.py"


@pytest.mark.anyio
async def test_run_lifecycle_order(runner: TaskRunner):
    """create → start → wait → logs → remove must happen in order."""
    calls: list[str] = []
    runner._client.create_vm.side_effect = lambda **_: (calls.append("create"), "vm-x")[1]  # type: ignore[attr-defined]
    runner._client.start_vm.side_effect = lambda *_: calls.append("start")  # type: ignore[attr-defined]
    runner._client.wait_vm.side_effect = lambda *_: (calls.append("wait"), 0)[1]  # type: ignore[attr-defined]
    runner._client.get_logs.side_effect = lambda *_: (calls.append("logs"), "")[1]  # type: ignore[attr-defined]
    runner._client.remove_vm.side_effect = lambda *_: calls.append("remove")  # type: ignore[attr-defined]

    await runner.run("do something")
    assert calls == ["create", "start", "wait", "logs", "remove"]


@pytest.mark.anyio
async def test_run_passes_api_key_in_env(runner: TaskRunner):
    await runner.run("task")
    call_kwargs = runner._client.create_vm.call_args.kwargs  # type: ignore[attr-defined]
    assert call_kwargs["env"]["ANTHROPIC_API_KEY"] == "test-key"


@pytest.mark.anyio
async def test_run_merges_extra_env(runner: TaskRunner):
    await runner.run("task", env={"MY_VAR": "hello"})
    env = runner._client.create_vm.call_args.kwargs["env"]  # type: ignore[attr-defined]
    assert env["MY_VAR"] == "hello"
    assert env["ANTHROPIC_API_KEY"] == "test-key"


@pytest.mark.anyio
async def test_run_nonzero_exit_still_returns_result(runner: TaskRunner):
    runner._client.wait_vm.return_value = 1  # type: ignore[attr-defined]
    result = await runner.run("task")
    assert result.exit_code == 1
    assert not result.success


# ── Error handling ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_run_removes_vm_on_error_by_default(runner: TaskRunner):
    runner._client.start_vm.side_effect = BoxdError(500, "oops")  # type: ignore[attr-defined]
    with pytest.raises(BoxdError):
        await runner.run("task")
    runner._client.remove_vm.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_run_keeps_vm_on_error_when_flag_set(runner: TaskRunner):
    runner._client.start_vm.side_effect = BoxdError(500, "oops")  # type: ignore[attr-defined]
    with pytest.raises(BoxdError):
        await runner.run("task", keep_vm_on_error=True)
    runner._client.remove_vm.assert_not_called()  # type: ignore[attr-defined]


# ── run_many() ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_run_many_returns_all_results(runner: TaskRunner):
    tasks = ["task A", "task B", "task C"]
    results = await runner.run_many(tasks)
    assert len(results) == 3
    assert all(isinstance(r, TaskResult) for r in results)


@pytest.mark.anyio
async def test_run_many_preserves_order(runner: TaskRunner):
    tasks = ["task 0", "task 1", "task 2"]
    results = await runner.run_many(tasks)
    for i, r in enumerate(results):
        assert r.task == f"task {i}"


# ── TaskResult helpers ────────────────────────────────────────────────────────

def test_task_result_success_property():
    r = TaskResult(task="t", output="out", exit_code=0, vm_id="vm")
    assert r.success is True


def test_task_result_failure_property():
    r = TaskResult(task="t", output="err", exit_code=1, vm_id="vm")
    assert r.success is False


def test_task_result_str_contains_task():
    r = TaskResult(task="my task", output="done", exit_code=0, vm_id="vm")
    assert "my task" in str(r)


# ── run_task() convenience function ──────────────────────────────────────────

@pytest.mark.anyio
async def test_run_task_function(mocker):
    mock_run = mocker.AsyncMock(
        return_value=TaskResult(task="t", output="ok", exit_code=0, vm_id="vm")
    )
    mocker.patch("dev_threads.runner.TaskRunner.run", mock_run)
    result = await run_task("t", anthropic_api_key="key")
    assert result.success
