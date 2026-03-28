"""ThreadManager – in-memory CRUD registry for DevThread instances."""

from __future__ import annotations

from typing import Iterator

from dev_threads.threads.thread import DevThread, ThreadStatus


class ThreadNotFoundError(Exception):
    """Raised when a thread ID cannot be found in the registry."""


class ThreadManager:
    """Maintains an in-memory registry of all active dev threads.

    In production this could be backed by a SQLite/SQLModel store; for the
    hackathon prototype an in-memory dict is sufficient.
    """

    def __init__(self) -> None:
        self._threads: dict[str, DevThread] = {}

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(self, name: str, goal: str) -> DevThread:
        """Create a new thread in PENDING state and register it."""
        thread = DevThread(name=name, goal=goal)
        self._threads[thread.id] = thread
        return thread

    def get(self, thread_id: str) -> DevThread:
        """Return the thread with *thread_id*; raise if not found."""
        try:
            return self._threads[thread_id]
        except KeyError:
            raise ThreadNotFoundError(thread_id) from None

    def list(self, *, status: ThreadStatus | None = None) -> list[DevThread]:
        """Return all threads, optionally filtered by *status*."""
        threads = list(self._threads.values())
        if status is not None:
            threads = [t for t in threads if t.status == status]
        return threads

    def remove(self, thread_id: str) -> DevThread:
        """Remove and return the thread; raise if not found."""
        try:
            return self._threads.pop(thread_id)
        except KeyError:
            raise ThreadNotFoundError(thread_id) from None

    # ── Iteration ─────────────────────────────────────────────────────────────

    def __iter__(self) -> Iterator[DevThread]:
        return iter(self._threads.values())

    def __len__(self) -> int:
        return len(self._threads)

    # ── Context sharing ───────────────────────────────────────────────────────

    def share_context(
        self,
        source_id: str,
        dest_id: str,
        *,
        keys: list[str] | None = None,
    ) -> None:
        """Copy context keys from *source* thread to *dest* thread.

        Args:
            source_id: ID of the thread to copy context *from*.
            dest_id:   ID of the thread to copy context *to*.
            keys:      Specific context keys to copy.  If *None*, all keys
                       from the source are copied.
        """
        source = self.get(source_id)
        dest = self.get(dest_id)
        snapshot = source.snapshot_context()
        for key, value in snapshot.items():
            if keys is None or key in keys:
                dest.update_context(key, value)
