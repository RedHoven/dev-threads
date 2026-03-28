"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from dev_threads.threads.manager import ThreadManager
from dev_threads.orchestrator.context_store import ContextStore
from dev_threads.orchestrator.orchestrator import Orchestrator


@pytest.fixture
def thread_manager() -> ThreadManager:
    return ThreadManager()


@pytest.fixture
def context_store(tmp_path) -> ContextStore:
    return ContextStore(store_path=tmp_path / "contexts")


@pytest.fixture
def orchestrator(thread_manager, context_store, mocker) -> Orchestrator:
    openclaw = mocker.AsyncMock()
    openclaw.start_session.return_value = {"session_id": "sess-123", "status": "running"}
    openclaw.get_context.return_value = {"summary": "Refactoring auth module"}
    openclaw.stop_session.return_value = None
    openclaw.send_message.return_value = {"reply": "Done!"}

    boxd = mocker.AsyncMock()
    boxd.create_vm.return_value = {"id": "vm-abc", "status": "running"}
    boxd.destroy_vm.return_value = None

    return Orchestrator(
        thread_manager=thread_manager,
        context_store=context_store,
        openclaw_client=openclaw,
        boxd_client=boxd,
    )
