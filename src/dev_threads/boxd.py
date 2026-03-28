"""boxd VM client.

boxd exposes a Docker-compatible HTTP API for spinning up ephemeral VMs.
This client covers the full container lifecycle needed to run a one-shot task:

    create → start → wait → logs → remove

References
----------
- POST   /containers/create          create_vm()
- POST   /containers/{id}/start      start_vm()
- POST   /containers/{id}/wait       wait_vm()
- GET    /containers/{id}/logs       get_logs()
- DELETE /containers/{id}            remove_vm()
- GET    /containers/json            list_vms()
- GET    /containers/{id}/json       inspect_vm()
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "http://localhost:2375"
_DEFAULT_IMAGE = "ghcr.io/anthropics/claude-code:latest"


class BoxdError(Exception):
    """Raised on non-2xx responses from the boxd / Docker API."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class BoxdClient:
    """Async client for the boxd VM API (Docker-compatible).

    Usage
    -----
    async with BoxdClient() as client:
        vm_id = await client.create_vm(command=["claude", "-p", "Write tests"])
        await client.start_vm(vm_id)
        exit_code = await client.wait_vm(vm_id)
        logs = await client.get_logs(vm_id)
        await client.remove_vm(vm_id)
    """

    def __init__(
        self,
        *,
        endpoint: str = _DEFAULT_ENDPOINT,
        image: str = _DEFAULT_IMAGE,
        timeout: float = 300.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._image = image
        self._http = httpx.AsyncClient(base_url=self._endpoint, timeout=timeout)

    # ── Container lifecycle ───────────────────────────────────────────────────

    async def create_vm(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        labels: dict[str, str] | None = None,
        image: str | None = None,
        working_dir: str = "/workspace",
    ) -> str:
        """Create a new container and return its ID.

        Args:
            command:     Command to run inside the container (e.g. ``["claude", "-p", "..."]``).
            env:         Optional environment variables injected into the container.
            labels:      Optional metadata labels attached to the container.
            image:       Override the default image for this VM only.
            working_dir: Working directory inside the container.

        Returns:
            The container ID string.
        """
        payload: dict[str, Any] = {
            "Image": image or self._image,
            "Cmd": command,
            "WorkingDir": working_dir,
            "AttachStdout": True,
            "AttachStderr": True,
        }
        if env:
            payload["Env"] = [f"{k}={v}" for k, v in env.items()]
        if labels:
            payload["Labels"] = labels

        resp = await self._http.post("/containers/create", json=payload)
        self._raise_for_status(resp)
        data: dict[str, Any] = resp.json()
        vm_id: str = data["Id"]
        logger.debug("Created VM %s", vm_id)
        return vm_id

    async def start_vm(self, vm_id: str) -> None:
        """Start a created container."""
        resp = await self._http.post(f"/containers/{vm_id}/start")
        self._raise_for_status(resp)
        logger.debug("Started VM %s", vm_id)

    async def wait_vm(self, vm_id: str) -> int:
        """Block until the container exits and return its exit code."""
        resp = await self._http.post(f"/containers/{vm_id}/wait")
        self._raise_for_status(resp)
        data: dict[str, Any] = resp.json()
        exit_code: int = data.get("StatusCode", -1)
        logger.debug("VM %s exited with code %d", vm_id, exit_code)
        return exit_code

    async def get_logs(self, vm_id: str, *, tail: int | str = "all") -> str:
        """Return the combined stdout + stderr of the container as a string.

        Args:
            vm_id: Container ID.
            tail:  Number of lines from the end to return, or ``"all"``.
        """
        resp = await self._http.get(
            f"/containers/{vm_id}/logs",
            params={"stdout": "true", "stderr": "true", "tail": str(tail)},
        )
        self._raise_for_status(resp)
        # Docker log responses use an 8-byte frame header per chunk; strip it.
        return _strip_docker_log_headers(resp.content)

    async def stream_logs(self, vm_id: str) -> AsyncIterator[str]:
        """Yield log lines as they arrive (uses HTTP streaming).

        The caller is responsible for awaiting container completion separately.
        """
        async with self._http.stream(
            "GET",
            f"/containers/{vm_id}/logs",
            params={"stdout": "true", "stderr": "true", "follow": "true"},
        ) as resp:
            self._raise_for_status(resp)
            async for chunk in resp.aiter_bytes():
                text = _strip_docker_log_headers(chunk)
                if text:
                    yield text

    async def remove_vm(self, vm_id: str, *, force: bool = True) -> None:
        """Remove a container (and optionally force-stop it first)."""
        resp = await self._http.delete(
            f"/containers/{vm_id}", params={"force": "true" if force else "false"}
        )
        self._raise_for_status(resp)
        logger.debug("Removed VM %s", vm_id)

    async def inspect_vm(self, vm_id: str) -> dict[str, Any]:
        """Return the full inspect payload for a container."""
        resp = await self._http.get(f"/containers/{vm_id}/json")
        self._raise_for_status(resp)
        data: dict[str, Any] = resp.json()
        return data

    async def list_vms(self, *, all: bool = True) -> list[dict[str, Any]]:
        """Return a list of containers managed by this boxd instance.

        Args:
            all: When *True* (default) also return stopped/exited containers.
        """
        resp = await self._http.get(
            "/containers/json", params={"all": "true" if all else "false"}
        )
        self._raise_for_status(resp)
        data: list[dict[str, Any]] = resp.json()
        return data

    # ── Error handling ────────────────────────────────────────────────────────

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.is_error:
            try:
                detail = resp.json().get("message", resp.text)
            except (ValueError, KeyError):
                detail = resp.text
            raise BoxdError(status_code=resp.status_code, detail=detail)

    # ── Context manager ───────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> BoxdClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_docker_log_headers(data: bytes) -> str:
    """Remove Docker's 8-byte multiplexed stream headers from log output.

    Each frame has the layout: [stream_type(1)] [0 0 0(3)] [size(4)] [payload...]
    If the data doesn't look framed (e.g. raw TTY), decode as-is.
    """
    output: list[str] = []
    offset = 0
    while offset < len(data):
        if offset + 8 > len(data):
            # Remaining bytes don't form a full header – treat as raw text.
            output.append(data[offset:].decode("utf-8", errors="replace"))
            break
        # Validate stream type byte (0=stdin, 1=stdout, 2=stderr)
        stream_type = data[offset]
        if stream_type not in (0, 1, 2):
            # Not a framed stream – decode everything as plain text.
            output.append(data.decode("utf-8", errors="replace"))
            break
        size = int.from_bytes(data[offset + 4 : offset + 8], "big")
        payload_start = offset + 8
        payload_end = payload_start + size
        output.append(data[payload_start:payload_end].decode("utf-8", errors="replace"))
        offset = payload_end
    return "".join(output)
