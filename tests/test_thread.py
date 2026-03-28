"""Tests for DevThread model and state machine."""

from __future__ import annotations

import pytest

from dev_threads.threads.thread import DevThread, ThreadStatus


def test_initial_state():
    t = DevThread(name="auth", goal="Refactor auth module")
    assert t.status == ThreadStatus.PENDING
    assert t.vm_id is None
    assert t.session_id is None
    assert t.context == {}


def test_mark_running():
    t = DevThread(name="auth", goal="Refactor auth module")
    t.mark_running(vm_id="vm-1", session_id="sess-1")
    assert t.status == ThreadStatus.RUNNING
    assert t.vm_id == "vm-1"
    assert t.session_id == "sess-1"


def test_pause():
    t = DevThread(name="auth", goal="Refactor auth module")
    t.mark_running(vm_id="vm-1", session_id="sess-1")
    t.pause()
    assert t.status == ThreadStatus.PAUSED


def test_complete():
    t = DevThread(name="auth", goal="Refactor auth module")
    t.mark_running(vm_id="vm-1", session_id="sess-1")
    t.complete()
    assert t.status == ThreadStatus.COMPLETED


def test_fail():
    t = DevThread(name="auth", goal="Refactor auth module")
    t.fail()
    assert t.status == ThreadStatus.FAILED


def test_invalid_transition_raises():
    t = DevThread(name="auth", goal="Refactor auth module")
    with pytest.raises(ValueError, match="PENDING"):
        t.pause()  # Can't pause a PENDING thread


def test_update_context():
    t = DevThread(name="auth", goal="Refactor auth module")
    t.update_context("files_changed", ["auth.py"])
    assert t.context["files_changed"] == ["auth.py"]


def test_snapshot_context_is_copy():
    t = DevThread(name="auth", goal="Refactor auth module")
    t.update_context("key", "value")
    snap = t.snapshot_context()
    snap["key"] = "mutated"
    assert t.context["key"] == "value"  # original unchanged


def test_resume_from_paused():
    t = DevThread(name="auth", goal="Refactor auth module")
    t.mark_running(vm_id="vm-1", session_id="sess-1")
    t.pause()
    t.mark_running(vm_id="vm-2", session_id="sess-2")
    assert t.status == ThreadStatus.RUNNING
    assert t.vm_id == "vm-2"
