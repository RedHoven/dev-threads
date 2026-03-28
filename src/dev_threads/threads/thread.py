"""DevThread – data model and state machine for a single Claude Code session."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ThreadStatus(str, Enum):
    """Lifecycle states for a dev thread."""

    PENDING = "pending"      # Created but VM not yet allocated
    RUNNING = "running"      # Active Claude Code session
    PAUSED = "paused"        # Snapshot taken; VM may be released
    COMPLETED = "completed"  # Goal reached; session closed cleanly
    FAILED = "failed"        # Unrecoverable error


class DevThread:
    """Represents a single Claude Code dev thread.

    Attributes:
        id:         Unique identifier (UUID).
        name:       Human-readable label.
        goal:       High-level task description sent to Claude Code on start.
        status:     Current lifecycle state.
        vm_id:      Identifier of the boxd VM backing this thread (if any).
        session_id: OpenClaw session identifier (if any).
        context:    Free-form dict of context snapshots / key facts.
        created_at: Creation timestamp (UTC).
        updated_at: Last-modified timestamp (UTC).
    """

    def __init__(
        self,
        name: str,
        goal: str,
        *,
        thread_id: str | None = None,
    ) -> None:
        self.id: str = thread_id or str(uuid.uuid4())
        self.name: str = name
        self.goal: str = goal
        self.status: ThreadStatus = ThreadStatus.PENDING
        self.vm_id: str | None = None
        self.session_id: str | None = None
        self.context: dict[str, Any] = {}
        self.created_at: datetime = datetime.now(tz=timezone.utc)
        self.updated_at: datetime = self.created_at

    # ── State transitions ────────────────────────────────────────────────────

    def mark_running(self, *, vm_id: str, session_id: str) -> None:
        self._require_status(ThreadStatus.PENDING, ThreadStatus.PAUSED)
        self.vm_id = vm_id
        self.session_id = session_id
        self._set_status(ThreadStatus.RUNNING)

    def pause(self) -> None:
        self._require_status(ThreadStatus.RUNNING)
        self._set_status(ThreadStatus.PAUSED)

    def complete(self) -> None:
        self._require_status(ThreadStatus.RUNNING)
        self._set_status(ThreadStatus.COMPLETED)

    def fail(self) -> None:
        self._set_status(ThreadStatus.FAILED)

    # ── Context helpers ──────────────────────────────────────────────────────

    def update_context(self, key: str, value: Any) -> None:  # noqa: ANN401
        self.context[key] = value
        self.updated_at = datetime.now(tz=timezone.utc)

    def snapshot_context(self) -> dict[str, Any]:
        """Return a copy of the current context dict."""
        return dict(self.context)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _require_status(self, *allowed: ThreadStatus) -> None:
        if self.status not in allowed:
            raise ValueError(
                f"Thread {self.id!r} is in status {self.status!r}; "
                f"expected one of {[s.value for s in allowed]}"
            )

    def _set_status(self, new_status: ThreadStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.now(tz=timezone.utc)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"DevThread(id={self.id!r}, name={self.name!r}, "
            f"status={self.status.value!r})"
        )
