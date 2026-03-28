"""Tests for BoxdClient."""

from __future__ import annotations

import struct

import httpx
import pytest

from dev_threads.boxd import BoxdClient, BoxdError, _strip_docker_log_headers


# ── Transport helper ──────────────────────────────────────────────────────────

def _transport(status: int, body: object) -> httpx.AsyncBaseTransport:
    class _T(httpx.AsyncBaseTransport):
        async def handle_async_request(self, _: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json=body)
    return _T()


def _make_client(status: int, body: object) -> BoxdClient:
    c = BoxdClient.__new__(BoxdClient)
    c._endpoint = "http://localhost:2375"
    c._image = "claude-code:latest"
    c._http = httpx.AsyncClient(base_url=c._endpoint, transport=_transport(status, body))
    return c


# ── create_vm ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_create_vm_returns_id():
    client = _make_client(201, {"Id": "abc123", "Warnings": []})
    vm_id = await client.create_vm(command=["claude", "--print", "hello"])
    assert vm_id == "abc123"
    await client.close()


@pytest.mark.anyio
async def test_create_vm_error_raises():
    client = _make_client(500, {"message": "no such image"})
    with pytest.raises(BoxdError) as exc:
        await client.create_vm(command=["claude"])
    assert exc.value.status_code == 500
    assert "no such image" in exc.value.detail
    await client.close()


# ── start_vm ──────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_start_vm_success():
    client = _make_client(204, {})
    await client.start_vm("abc123")  # Should not raise
    await client.close()


@pytest.mark.anyio
async def test_start_vm_not_found_raises():
    client = _make_client(404, {"message": "no such container"})
    with pytest.raises(BoxdError) as exc:
        await client.start_vm("nope")
    assert exc.value.status_code == 404
    await client.close()


# ── wait_vm ───────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_wait_vm_returns_exit_code():
    client = _make_client(200, {"StatusCode": 0})
    code = await client.wait_vm("abc123")
    assert code == 0
    await client.close()


@pytest.mark.anyio
async def test_wait_vm_nonzero_exit():
    client = _make_client(200, {"StatusCode": 1})
    code = await client.wait_vm("abc123")
    assert code == 1
    await client.close()


# ── remove_vm ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_remove_vm_success():
    client = _make_client(204, {})
    await client.remove_vm("abc123")  # Should not raise
    await client.close()


# ── list_vms / inspect_vm ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_vms():
    client = _make_client(200, [{"Id": "a"}, {"Id": "b"}])
    vms = await client.list_vms()
    assert len(vms) == 2
    await client.close()


@pytest.mark.anyio
async def test_inspect_vm():
    client = _make_client(200, {"Id": "abc", "State": {"Status": "running"}})
    info = await client.inspect_vm("abc")
    assert info["Id"] == "abc"
    await client.close()


# ── log header stripping ──────────────────────────────────────────────────────

def _frame(payload: str, stream: int = 1) -> bytes:
    data = payload.encode()
    header = bytes([stream, 0, 0, 0]) + struct.pack(">I", len(data))
    return header + data


def test_strip_docker_log_headers_single_frame():
    raw = _frame("hello\n")
    assert _strip_docker_log_headers(raw) == "hello\n"


def test_strip_docker_log_headers_multiple_frames():
    raw = _frame("line1\n") + _frame("line2\n", stream=2)
    assert _strip_docker_log_headers(raw) == "line1\nline2\n"


def test_strip_docker_log_headers_raw_text():
    raw = b"plain text output"
    assert _strip_docker_log_headers(raw) == "plain text output"
