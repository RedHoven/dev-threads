"""Tests for ThreadManager."""

from __future__ import annotations

import pytest

from dev_threads.threads.manager import ThreadManager, ThreadNotFoundError
from dev_threads.threads.thread import ThreadStatus


def test_create_and_get(thread_manager: ThreadManager):
    t = thread_manager.create(name="api", goal="Build REST API")
    fetched = thread_manager.get(t.id)
    assert fetched is t


def test_get_unknown_raises(thread_manager: ThreadManager):
    with pytest.raises(ThreadNotFoundError):
        thread_manager.get("nonexistent")


def test_list_all(thread_manager: ThreadManager):
    thread_manager.create("a", "goal a")
    thread_manager.create("b", "goal b")
    assert len(thread_manager.list()) == 2


def test_list_filtered_by_status(thread_manager: ThreadManager):
    t = thread_manager.create("a", "goal a")
    t.mark_running(vm_id="vm-1", session_id="s-1")
    thread_manager.create("b", "goal b")  # stays PENDING
    running = thread_manager.list(status=ThreadStatus.RUNNING)
    assert len(running) == 1
    assert running[0].id == t.id


def test_remove(thread_manager: ThreadManager):
    t = thread_manager.create("a", "goal a")
    removed = thread_manager.remove(t.id)
    assert removed is t
    assert len(thread_manager.list()) == 0


def test_remove_unknown_raises(thread_manager: ThreadManager):
    with pytest.raises(ThreadNotFoundError):
        thread_manager.remove("ghost")


def test_share_context(thread_manager: ThreadManager):
    src = thread_manager.create("src", "source goal")
    dst = thread_manager.create("dst", "dest goal")
    src.update_context("key", "value")
    thread_manager.share_context(src.id, dst.id)
    assert dst.context["key"] == "value"


def test_share_context_with_keys(thread_manager: ThreadManager):
    src = thread_manager.create("src", "source goal")
    dst = thread_manager.create("dst", "dest goal")
    src.update_context("a", 1)
    src.update_context("b", 2)
    thread_manager.share_context(src.id, dst.id, keys=["a"])
    assert dst.context.get("a") == 1
    assert "b" not in dst.context


def test_iter_and_len(thread_manager: ThreadManager):
    thread_manager.create("x", "x")
    thread_manager.create("y", "y")
    assert len(thread_manager) == 2
    ids = {t.id for t in thread_manager}
    assert len(ids) == 2
