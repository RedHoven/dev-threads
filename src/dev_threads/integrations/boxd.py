"""boxd VM client.

boxd (https://boxd.dev) is a lightweight API for spinning up ephemeral VMs.
Each dev thread gets its own VM so Claude Code instances are fully isolated.

API contract (Docker-compatible subset):

    POST   /containers/create   → create_vm()
    DELETE /containers/{id}     → destroy_vm()
    GET    /containers/{id}/json → get_vm_info()
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from dev_threads.config import get_settings

logger = logging.getLogger(__name__)


class BoxdError(Exception):
    """Raised on non-2xx responses from the boxd API."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class BoxdClient:
    """Async client for the boxd VM API.

    All methods are coroutines and must be awaited.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        vm_image: str | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = (endpoint or settings.boxd_endpoint).rstrip("/")
        self._vm_image = vm_image or settings.boxd_vm_image
        self._http = httpx.AsyncClient(base_url=self._endpoint, timeout=60)

    # ── VM lifecycle ──────────────────────────────────────────────────────────

    async def create_vm(self, thread_id: str) -> dict[str, Any]:
        """Provision a new VM for *thread_id*.

        Args:
            thread_id: Used as the container/VM name label for traceability.

        Returns:
            A dict with at least ``{"id": str, "status": str}``.
        """
        payload = {
            "Image": self._vm_image,
            "Labels": {"dev-threads.thread-id": thread_id},
        }
        response = await self._http.post("/containers/create", json=payload)
        self._raise_for_status(response)
        data: dict[str, Any] = response.json()
        logger.debug("Created VM %s for thread %s", data.get("id"), thread_id)
        return data

    async def destroy_vm(self, vm_id: str) -> None:
        """Stop and remove the VM with the given *vm_id*."""
        response = await self._http.delete(f"/containers/{vm_id}")
        self._raise_for_status(response)
        logger.debug("Destroyed VM %s", vm_id)

    async def get_vm_info(self, vm_id: str) -> dict[str, Any]:
        """Return metadata about a running VM."""
        response = await self._http.get(f"/containers/{vm_id}/json")
        self._raise_for_status(response)
        data: dict[str, Any] = response.json()
        return data

    async def list_vms(self) -> list[dict[str, Any]]:
        """Return a list of all VMs managed by this boxd instance."""
        response = await self._http.get("/containers/json")
        self._raise_for_status(response)
        data: list[dict[str, Any]] = response.json()
        return data

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_error:
            try:
                detail = response.json().get("message", response.text)
            except (ValueError, KeyError):
                detail = response.text
            raise BoxdError(status_code=response.status_code, detail=detail)

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> BoxdClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
