"""Tests for integration clients (OpenClaw, boxd)."""

from __future__ import annotations

import json

import httpx
import pytest

from dev_threads.integrations.boxd import BoxdClient, BoxdError
from dev_threads.integrations.openclaw import OpenClawClient, OpenClawError


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_transport(status: int, body: dict) -> httpx.AsyncBaseTransport:
    """Return a mock HTTPX async transport that always returns *status* + *body*."""

    class _Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json=body)

    return _Transport()


# ── BoxdClient ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_boxd_create_vm_success():
    vm_resp = {"id": "vm-123", "status": "running"}
    transport = _mock_transport(201, vm_resp)
    client = BoxdClient.__new__(BoxdClient)
    client._endpoint = "http://localhost:2375"
    client._vm_image = "claude-code:latest"
    client._http = httpx.AsyncClient(
        base_url=client._endpoint, transport=transport
    )
    result = await client.create_vm("thread-1")
    assert result["id"] == "vm-123"
    await client.close()


@pytest.mark.anyio
async def test_boxd_create_vm_error():
    transport = _mock_transport(500, {"message": "internal error"})
    client = BoxdClient.__new__(BoxdClient)
    client._endpoint = "http://localhost:2375"
    client._vm_image = "claude-code:latest"
    client._http = httpx.AsyncClient(
        base_url=client._endpoint, transport=transport
    )
    with pytest.raises(BoxdError) as exc_info:
        await client.create_vm("thread-1")
    assert exc_info.value.status_code == 500
    await client.close()


# ── OpenClawClient ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_openclaw_start_session_success():
    sess_resp = {"session_id": "sess-abc", "status": "running"}
    transport = _mock_transport(200, sess_resp)
    client = OpenClawClient.__new__(OpenClawClient)
    client._base_url = "https://api.kiloclaw.io"
    client._api_key = "test-key"
    client._http = httpx.AsyncClient(
        base_url=client._base_url, transport=transport
    )
    result = await client.start_session("vm-1", "Build API")
    assert result["session_id"] == "sess-abc"
    await client.close()


@pytest.mark.anyio
async def test_openclaw_stop_session_error():
    transport = _mock_transport(404, {"detail": "not found"})
    client = OpenClawClient.__new__(OpenClawClient)
    client._base_url = "https://api.kiloclaw.io"
    client._api_key = "test-key"
    client._http = httpx.AsyncClient(
        base_url=client._base_url, transport=transport
    )
    with pytest.raises(OpenClawError) as exc_info:
        await client.stop_session("nonexistent")
    assert exc_info.value.status_code == 404
    await client.close()
