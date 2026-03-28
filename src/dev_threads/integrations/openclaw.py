"""OpenClaw / kiloclaw API client.

OpenClaw is the orchestration layer that manages Claude Code sessions running
inside kiloclaw-hosted VMs.  Each session corresponds to a single "dev thread"
that Claude Code is working on.

API contract (subject to change as the real API stabilises):

    POST   /sessions               → start_session()
    GET    /sessions/{id}/context  → get_context()
    DELETE /sessions/{id}          → stop_session()
    POST   /sessions/{id}/message  → send_message()
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from dev_threads.config import get_settings

logger = logging.getLogger(__name__)


class OpenClawError(Exception):
    """Raised on non-2xx responses from the OpenClaw API."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class OpenClawClient:
    """Async client for the OpenClaw / kiloclaw API.

    All methods are coroutines and must be awaited.
    """

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.openclaw_base_url).rstrip("/")
        self._api_key = api_key or settings.openclaw_api_key
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=30,
        )

    # ── Session lifecycle ─────────────────────────────────────────────────────

    async def start_session(
        self,
        vm_id: str,
        goal: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start a new Claude Code session on *vm_id*.

        Args:
            vm_id:   The boxd VM that will host the session.
            goal:    Task description given to Claude Code at startup.
            context: Optional context snapshot to inject (e.g. on resume).

        Returns:
            A dict with at least ``{"session_id": str, "status": str}``.
        """
        payload: dict[str, Any] = {"vm_id": vm_id, "goal": goal}
        if context:
            payload["context"] = context

        response = await self._http.post("/sessions", json=payload)
        self._raise_for_status(response)
        data: dict[str, Any] = response.json()
        logger.debug("Started OpenClaw session %s on VM %s", data.get("session_id"), vm_id)
        return data

    async def stop_session(self, session_id: str) -> None:
        """Terminate a running Claude Code session."""
        response = await self._http.delete(f"/sessions/{session_id}")
        self._raise_for_status(response)
        logger.debug("Stopped OpenClaw session %s", session_id)

    async def get_context(self, session_id: str) -> dict[str, Any]:
        """Retrieve the current context snapshot from a running session."""
        response = await self._http.get(f"/sessions/{session_id}/context")
        self._raise_for_status(response)
        data: dict[str, Any] = response.json()
        logger.debug("Fetched context for session %s", session_id)
        return data

    async def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        """Send a user message to a running Claude Code session.

        Returns:
            A dict with at least ``{"reply": str}``.
        """
        response = await self._http.post(
            f"/sessions/{session_id}/message",
            json={"message": message},
        )
        self._raise_for_status(response)
        data: dict[str, Any] = response.json()
        return data

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except (ValueError, KeyError):
                detail = response.text
            raise OpenClawError(status_code=response.status_code, detail=detail)

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> OpenClawClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
