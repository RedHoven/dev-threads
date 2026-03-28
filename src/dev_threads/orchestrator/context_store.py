"""Persistent context store for dev thread snapshots.

Snapshots are written as JSON files under ``CONTEXT_STORE_PATH``:

    <store_path>/<thread_id>.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from dev_threads.config import get_settings

logger = logging.getLogger(__name__)


class ContextStore:
    """Read/write thread context snapshots to/from the local file system."""

    def __init__(self, store_path: Path | None = None) -> None:
        settings = get_settings()
        self._root: Path = (
            store_path if store_path is not None
            else settings.expanded_context_store_path()
        )

    def _path(self, thread_id: str) -> Path:
        return self._root / f"{thread_id}.json"

    def _ensure_root(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self, thread_id: str, context: dict[str, Any]) -> None:
        """Persist *context* for *thread_id*."""
        self._ensure_root()
        path = self._path(thread_id)
        path.write_text(json.dumps(context, indent=2, default=str), encoding="utf-8")
        logger.debug("Saved context snapshot for thread %s → %s", thread_id, path)

    def load(self, thread_id: str) -> dict[str, Any]:
        """Load and return the stored context for *thread_id*.

        Returns an empty dict if no snapshot exists yet.
        """
        path = self._path(thread_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[return-value]

    def delete(self, thread_id: str) -> None:
        """Remove the stored context for *thread_id* (no-op if absent)."""
        path = self._path(thread_id)
        if path.exists():
            path.unlink()
            logger.debug("Deleted context snapshot for thread %s", thread_id)

    def list_thread_ids(self) -> list[str]:
        """Return the IDs of all threads that have a stored snapshot."""
        if not self._root.exists():
            return []
        return [p.stem for p in self._root.glob("*.json")]
