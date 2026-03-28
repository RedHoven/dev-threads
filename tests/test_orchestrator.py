"""Tests for the Orchestrator."""

from __future__ import annotations

import pytest

from dev_threads.orchestrator.orchestrator import Orchestrator
from dev_threads.threads.manager import ThreadNotFoundError
from dev_threads.threads.thread import ThreadStatus


@pytest.mark.anyio
async def test_new_thread_happy_path(orchestrator: Orchestrator):
    thread = await orchestrator.new_thread("auth", "Refactor auth module")
    assert thread.status == ThreadStatus.RUNNING
    assert thread.vm_id == "vm-abc"
    assert thread.session_id == "sess-123"
    assert thread.context.get("goal") == "Refactor auth module"


@pytest.mark.anyio
async def test_new_thread_persists_context(orchestrator: Orchestrator, tmp_path):
    thread = await orchestrator.new_thread("auth", "Refactor auth module")
    saved = orchestrator.store.load(thread.id)
    assert saved.get("goal") == "Refactor auth module"


@pytest.mark.anyio
async def test_pause_thread(orchestrator: Orchestrator):
    thread = await orchestrator.new_thread("auth", "Refactor auth module")
    paused = await orchestrator.pause_thread(thread.id)
    assert paused.status == ThreadStatus.PAUSED
    assert paused.context.get("openclaw_snapshot") is not None


@pytest.mark.anyio
async def test_resume_thread(orchestrator: Orchestrator):
    thread = await orchestrator.new_thread("auth", "Refactor auth module")
    await orchestrator.pause_thread(thread.id)
    resumed = await orchestrator.resume_thread(thread.id)
    assert resumed.status == ThreadStatus.RUNNING


@pytest.mark.anyio
async def test_kill_thread(orchestrator: Orchestrator):
    thread = await orchestrator.new_thread("auth", "Refactor auth module")
    killed = await orchestrator.kill_thread(thread.id)
    assert killed.id == thread.id
    with pytest.raises(ThreadNotFoundError):
        orchestrator.get_thread(thread.id)


@pytest.mark.anyio
async def test_share_context(orchestrator: Orchestrator):
    t1 = await orchestrator.new_thread("a", "goal a")
    t2 = await orchestrator.new_thread("b", "goal b")
    t1.update_context("shared_key", "hello")
    orchestrator.share_context(t1.id, t2.id, keys=["shared_key"])
    assert orchestrator.get_context(t2.id).get("shared_key") == "hello"


@pytest.mark.anyio
async def test_list_threads(orchestrator: Orchestrator):
    await orchestrator.new_thread("x", "goal x")
    await orchestrator.new_thread("y", "goal y")
    threads = orchestrator.list_threads()
    assert len(threads) == 2


@pytest.mark.anyio
async def test_list_threads_filtered(orchestrator: Orchestrator):
    t = await orchestrator.new_thread("x", "goal x")
    await orchestrator.pause_thread(t.id)
    await orchestrator.new_thread("y", "goal y")
    running = orchestrator.list_threads(status=ThreadStatus.RUNNING)
    assert len(running) == 1
    paused = orchestrator.list_threads(status=ThreadStatus.PAUSED)
    assert len(paused) == 1


@pytest.mark.anyio
async def test_new_thread_marks_failed_on_boxd_error(orchestrator: Orchestrator):
    orchestrator._boxd.create_vm.side_effect = RuntimeError("boxd unavailable")
    with pytest.raises(RuntimeError, match="boxd unavailable"):
        await orchestrator.new_thread("broken", "some goal")
    # Thread should be in FAILED state and still visible to the orchestrator
    threads = orchestrator.list_threads()
    assert threads[0].status == ThreadStatus.FAILED
