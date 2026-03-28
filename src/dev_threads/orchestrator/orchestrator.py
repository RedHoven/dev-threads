"""Core Orchestrator – coordinates thread lifecycle, OpenClaw, and boxd."""

from __future__ import annotations

import logging
from typing import Any

from dev_threads.integrations.boxd import BoxdClient
from dev_threads.integrations.openclaw import OpenClawClient
from dev_threads.orchestrator.context_store import ContextStore
from dev_threads.threads.manager import ThreadManager, ThreadNotFoundError
from dev_threads.threads.thread import DevThread, ThreadStatus

logger = logging.getLogger(__name__)


class Orchestrator:
    """High-level API consumed by the UI layer.

    Responsibilities:
    - Manage the lifecycle of DevThread objects.
    - Delegate VM operations to BoxdClient.
    - Delegate Claude Code session operations to OpenClawClient.
    - Persist / restore thread context via ContextStore.
    """

    def __init__(
        self,
        *,
        thread_manager: ThreadManager | None = None,
        context_store: ContextStore | None = None,
        openclaw_client: OpenClawClient | None = None,
        boxd_client: BoxdClient | None = None,
    ) -> None:
        self.threads = thread_manager or ThreadManager()
        self.store = context_store or ContextStore()
        self._openclaw = openclaw_client or OpenClawClient()
        self._boxd = boxd_client or BoxdClient()

    # ── Thread lifecycle ──────────────────────────────────────────────────────

    async def new_thread(self, name: str, goal: str) -> DevThread:
        """Spin up a new boxd VM and start a Claude Code session.

        Returns the DevThread in RUNNING state.
        """
        thread = self.threads.create(name=name, goal=goal)
        logger.info("Created thread %s (%s)", thread.id, name)

        try:
            vm = await self._boxd.create_vm(thread_id=thread.id)
            session = await self._openclaw.start_session(
                vm_id=vm["id"],
                goal=goal,
            )
            thread.mark_running(vm_id=vm["id"], session_id=session["session_id"])
            thread.update_context("goal", goal)
            self.store.save(thread.id, thread.snapshot_context())
            logger.info(
                "Thread %s running on VM %s (session %s)",
                thread.id,
                vm["id"],
                session["session_id"],
            )
        except Exception:
            thread.fail()
            logger.exception("Failed to start thread %s", thread.id)
            raise

        return thread

    async def pause_thread(self, thread_id: str) -> DevThread:
        """Snapshot context and pause the given thread."""
        thread = self.threads.get(thread_id)
        context = await self._openclaw.get_context(thread.session_id or "")
        thread.update_context("openclaw_snapshot", context)
        self.store.save(thread.id, thread.snapshot_context())
        thread.pause()
        logger.info("Thread %s paused", thread_id)
        return thread

    async def resume_thread(self, thread_id: str) -> DevThread:
        """Resume a paused thread: spin up a new VM and restore context."""
        thread = self.threads.get(thread_id)
        saved_context = self.store.load(thread.id)
        thread.context.update(saved_context)

        vm = await self._boxd.create_vm(thread_id=thread.id)
        session = await self._openclaw.start_session(
            vm_id=vm["id"],
            goal=thread.goal,
            context=thread.context,
        )
        thread.mark_running(vm_id=vm["id"], session_id=session["session_id"])
        logger.info("Thread %s resumed on VM %s", thread_id, vm["id"])
        return thread

    async def kill_thread(self, thread_id: str) -> DevThread:
        """Stop and remove a thread and its VM."""
        thread = self.threads.get(thread_id)
        if thread.session_id:
            await self._openclaw.stop_session(thread.session_id)
        if thread.vm_id:
            await self._boxd.destroy_vm(thread.vm_id)
        self.store.delete(thread.id)
        return self.threads.remove(thread_id)

    # ── Context ───────────────────────────────────────────────────────────────

    def get_context(self, thread_id: str) -> dict[str, Any]:
        thread = self.threads.get(thread_id)
        return thread.snapshot_context()

    def share_context(
        self,
        source_id: str,
        dest_id: str,
        *,
        keys: list[str] | None = None,
    ) -> None:
        self.threads.share_context(source_id, dest_id, keys=keys)
        dest = self.threads.get(dest_id)
        self.store.save(dest_id, dest.snapshot_context())

    # ── Query ─────────────────────────────────────────────────────────────────

    def list_threads(self, *, status: ThreadStatus | None = None) -> list[DevThread]:
        return self.threads.list(status=status)

    def get_thread(self, thread_id: str) -> DevThread:
        return self.threads.get(thread_id)

    # ── Messaging ─────────────────────────────────────────────────────────────

    async def send_message(self, thread_id: str, message: str) -> dict[str, Any]:
        """Send a message to a running thread's Claude Code session."""
        thread = self.threads.get(thread_id)
        if not thread.session_id:
            raise ValueError(f"Thread {thread_id!r} has no active session.")
        return await self._openclaw.send_message(thread.session_id, message)

    # ── Re-export error type so callers don't need to import separately ───────
    ThreadNotFoundError = ThreadNotFoundError
