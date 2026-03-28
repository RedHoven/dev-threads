# dev-threads

Spin up ephemeral VMs with Claude Code inside via **boxd** and run user-defined tasks programmatically.

```python
from dev_threads import run_task

result = await run_task("Add docstrings to every public function in src/")
print(result.output)
```

---

## How it works

1. **Create** a fresh container on boxd (Docker-compatible API)
2. **Start** it — `claude --print "<your task>"` runs inside
3. **Wait** for Claude Code to finish
4. **Collect** the output
5. **Remove** the container

Every task gets its own isolated VM. No state leaks between runs.

---

## Install

```bash
pip install -e .
```

Requires Python ≥ 3.11 and a running [boxd](https://boxd.dev) endpoint.

---

## Quick start

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY and BOXD_ENDPOINT
```

### Single task

```python
from dev_threads import run_task

result = await run_task("Refactor the auth module to use async/await")
print(result.output)   # Claude Code's full output
print(result.success)  # True if exit code == 0
```

### Reuse a runner across multiple tasks

```python
from dev_threads import TaskRunner

async with TaskRunner() as runner:
    result = await runner.run("Write unit tests for utils.py")
    print(result.output)
```

### Run many tasks concurrently

```python
tasks = [
    "Add type hints to models.py",
    "Write a README for the billing module",
    "Refactor database.py to use connection pooling",
]

results = await runner.run_many(tasks, concurrency=3)
for r in results:
    print(r.task, "→", "✓" if r.success else "✗")
```

### Stream output live

```python
async for chunk in runner.stream("Explain this codebase"):
    print(chunk, end="", flush=True)
```

### Keep the VM on failure (for debugging)

```python
result = await runner.run("tricky task", keep_vm_on_error=True)
# VM is still alive — inspect it manually
```

---

## Configuration

Set via environment variables or a `.env` file:

| Variable | Description | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Forwarded into every Claude Code VM | – |
| `BOXD_ENDPOINT` | boxd API URL | `http://localhost:2375` |
| `BOXD_VM_IMAGE` | Container image with `claude` on PATH | `ghcr.io/anthropics/claude-code:latest` |
| `TASK_TIMEOUT` | Seconds before a task times out | `300` |

All settings can also be passed directly to `TaskRunner(...)` or `run_task(...)`.

---

## API reference

### `run_task(task, *, endpoint, image, anthropic_api_key, env, labels, timeout, keep_vm_on_error) → TaskResult`

One-shot convenience function. Creates a `TaskRunner`, runs one task, tears it down.

### `TaskRunner`

```python
runner = TaskRunner(endpoint=..., image=..., anthropic_api_key=..., timeout=...)

await runner.run(task, *, env, labels, image, keep_vm_on_error) → TaskResult
await runner.run_many(tasks, *, concurrency, **run_kwargs)       → list[TaskResult]
runner.stream(task, *, env, labels, image)                       → AsyncIterator[str]
```

### `TaskResult`

```python
result.task       # str  – original task description
result.output     # str  – combined stdout + stderr
result.exit_code  # int  – container exit code
result.vm_id      # str  – container ID
result.success    # bool – exit_code == 0
```

### `BoxdClient`

Lower-level async client for the boxd Docker-compatible API. Use this directly when you need fine-grained control over the VM lifecycle.

```python
async with BoxdClient(endpoint=..., image=...) as client:
    vm_id = await client.create_vm(command=[...], env={...})
    await client.start_vm(vm_id)
    exit_code = await client.wait_vm(vm_id)
    logs = await client.get_logs(vm_id)
    await client.remove_vm(vm_id)
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
mypy src
```

---

## License

MIT – see [LICENSE](LICENSE).
