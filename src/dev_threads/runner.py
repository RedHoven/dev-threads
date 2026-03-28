"""TaskRunner – spin up a VM and run a Claude Code task inside it.

Minimal public API
------------------
    from dev_threads import run_task, TaskRunner

    # One-shot helper (creates client, runs task, tears down):
    result = await run_task("Add docstrings to every public function in src/")
    print(result.output)

    # Reuse a single client across multiple tasks:
    async with TaskRunner() as runner:
        r1 = await runner.run("Refactor the auth module")
        r2 = await runner.run("Write unit tests for utils.py")

Task execution model
--------------------
1. Create a fresh ephemeral VM via boxd.
2. Start it with ``claude --print "<task>"`` (non-interactive, exits when done).
3. Wait for the process to exit.
4. Collect logs (the Claude Code output).
5. Remove the VM.

The VM is **always removed** after the task completes, even on error, unless
``keep_vm_on_error=True`` is passed to ``run()``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator

from dev_threads.boxd import BoxdClient, BoxdError
from dev_threads.config import get_settings

logger = logging.getLogger(__name__)


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    """The result of running a task inside a Claude Code VM.

    Attributes:
        task:      The original task string that was executed.
        output:    Full stdout + stderr captured from the container.
        exit_code: Process exit code (0 = success).
        vm_id:     The container ID that ran the task.
        success:   ``True`` when ``exit_code == 0``.
    """

    task: str
    output: str
    exit_code: int
    vm_id: str
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def __str__(self) -> str:
        status = "✓" if self.success else f"✗ (exit {self.exit_code})"
        return f"[{status}] {self.task!r}\n{self.output}"


# ── TaskRunner ────────────────────────────────────────────────────────────────

class TaskRunner:
    """High-level API for running Claude Code tasks in ephemeral boxd VMs.

    Parameters
    ----------
    endpoint:
        boxd API endpoint.  Defaults to ``BOXD_ENDPOINT`` env var or
        ``http://localhost:2375``.
    image:
        Container image that has ``claude`` on its PATH.  Defaults to
        ``BOXD_VM_IMAGE`` env var or ``ghcr.io/anthropics/claude-code:latest``.
    anthropic_api_key:
        API key forwarded to Claude Code inside the VM.  Defaults to
        ``ANTHROPIC_API_KEY`` env var.
    timeout:
        Seconds to wait for a task to complete before raising ``TimeoutError``.
        Default is 300 s (5 min).
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        image: str | None = None,
        anthropic_api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        cfg = get_settings()
        self._client = BoxdClient(
            endpoint=endpoint or cfg.boxd_endpoint,
            image=image or cfg.boxd_vm_image,
            timeout=timeout or cfg.task_timeout,
        )
        self._api_key = anthropic_api_key or cfg.anthropic_api_key
        self._timeout = timeout or cfg.task_timeout

    # ── Core run ──────────────────────────────────────────────────────────────

    async def run(
        self,
        task: str,
        *,
        env: dict[str, str] | None = None,
        labels: dict[str, str] | None = None,
        image: str | None = None,
        keep_vm_on_error: bool = False,
    ) -> TaskResult:
        """Run *task* inside a fresh Claude Code VM and return the result.

        Args:
            task:             Natural-language task description passed to
                              ``claude --print``.
            env:              Extra environment variables merged into the VM
                              (on top of ``ANTHROPIC_API_KEY``).
            labels:           Metadata labels attached to the container.
            image:            Override the default image for this task only.
            keep_vm_on_error: When ``True``, don't remove the VM if the task
                              fails – useful for debugging.

        Returns:
            :class:`TaskResult` with ``output``, ``exit_code``, and
            ``success``.

        Raises:
            BoxdError:    If the boxd API returns a non-2xx response.
            TimeoutError: If the task exceeds ``self._timeout`` seconds.
        """
        merged_env: dict[str, str] = {}
        if self._api_key:
            merged_env["ANTHROPIC_API_KEY"] = self._api_key
        if env:
            merged_env.update(env)

        vm_id = await self._client.create_vm(
            command=["claude", "--print", task],
            env=merged_env or None,
            labels=labels,
            image=image,
        )
        logger.info("VM %s created for task %r", vm_id, task[:80])

        exit_code = -1
        output = ""
        error: Exception | None = None
        try:
            await self._client.start_vm(vm_id)
            logger.debug("VM %s started", vm_id)

            exit_code = await asyncio.wait_for(
                self._client.wait_vm(vm_id),
                timeout=self._timeout,
            )
            output = await self._client.get_logs(vm_id)

        except Exception as exc:
            error = exc
            logger.error("Task failed on VM %s: %s", vm_id, exc)
        finally:
            should_remove = error is None or not keep_vm_on_error
            if should_remove:
                try:
                    await self._client.remove_vm(vm_id)
                    logger.debug("VM %s removed", vm_id)
                except BoxdError as rm_err:
                    logger.warning("Could not remove VM %s: %s", vm_id, rm_err)

        if error is not None:
            raise error

        result = TaskResult(
            task=task,
            output=output,
            exit_code=exit_code,
            vm_id=vm_id,
            labels=labels or {},
        )
        logger.info(
            "VM %s finished: exit=%d, output=%d chars",
            vm_id, exit_code, len(output),
        )
        return result

    async def run_many(
        self,
        tasks: list[str],
        *,
        concurrency: int = 4,
        **run_kwargs: object,
    ) -> list[TaskResult]:
        """Run multiple tasks concurrently.

        Args:
            tasks:       List of task strings.
            concurrency: Maximum number of VMs running simultaneously.
            **run_kwargs: Forwarded to :meth:`run` for every task.

        Returns:
            List of :class:`TaskResult` in the same order as *tasks*.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _bounded(task: str) -> TaskResult:
            async with semaphore:
                return await self.run(task, **run_kwargs)  # type: ignore[arg-type]

        return list(await asyncio.gather(*[_bounded(t) for t in tasks]))

    async def stream(
        self,
        task: str,
        *,
        env: dict[str, str] | None = None,
        labels: dict[str, str] | None = None,
        image: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield log chunks as the task runs, then clean up the VM.

        Usage::

            async for chunk in runner.stream("Explain this codebase"):
                print(chunk, end="", flush=True)
        """
        merged_env: dict[str, str] = {}
        if self._api_key:
            merged_env["ANTHROPIC_API_KEY"] = self._api_key
        if env:
            merged_env.update(env)

        vm_id = await self._client.create_vm(
            command=["claude", "--print", task],
            env=merged_env or None,
            labels=labels,
            image=image,
        )
        try:
            await self._client.start_vm(vm_id)
            async for chunk in self._client.stream_logs(vm_id):
                yield chunk
            await self._client.wait_vm(vm_id)
        finally:
            try:
                await self._client.remove_vm(vm_id)
            except BoxdError:
                pass

    # ── Context manager ───────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> TaskRunner:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


# ── Module-level convenience function ─────────────────────────────────────────

async def run_task(
    task: str,
    *,
    endpoint: str | None = None,
    image: str | None = None,
    anthropic_api_key: str | None = None,
    env: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
    timeout: float | None = None,
    keep_vm_on_error: bool = False,
) -> TaskResult:
    """One-shot helper: spin up a VM, run *task*, return the result.

    This is the fastest way to run a single task without managing a
    :class:`TaskRunner` instance yourself::

        result = await run_task("Add type hints to src/utils.py")
        print(result.output)

    All keyword arguments are forwarded to :class:`TaskRunner` and
    :meth:`TaskRunner.run` respectively.
    """
    async with TaskRunner(
        endpoint=endpoint,
        image=image,
        anthropic_api_key=anthropic_api_key,
        timeout=timeout,
    ) as runner:
        return await runner.run(
            task,
            env=env,
            labels=labels,
            keep_vm_on_error=keep_vm_on_error,
        )
