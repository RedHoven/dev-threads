# dev-threads

> **Hackathon project** – Orchestrate multiple Claude Code dev threads from a single text or voice interface, eliminating the mental fatigue of context-switching between parallel coding sessions.

---

## Overview

`dev-threads` is an orchestration layer that lets you spin up, pause, resume, and communicate with multiple **Claude Code** instances at once. Each instance runs in an isolated VM managed by **boxd**, and the whole fleet is coordinated through **OpenClaw** running on **kiloclaw**.

```
┌─────────────────────────────────────────────────────────┐
│                     dev-threads UI                      │
│          (Text CLI / TUI  ·  Voice Commands)            │
└──────────────────────┬──────────────────────────────────┘
                       │
             ┌─────────▼──────────┐
             │    Orchestrator    │
             │  (thread manager,  │
             │   context store)   │
             └──┬──────────────┬──┘
                │              │
   ┌────────────▼──┐   ┌───────▼────────────┐
   │  OpenClaw /   │   │   boxd VM Pool     │
   │  kiloclaw API │   │  (spin up / tear   │
   │  (Claude Code │   │   down instances)  │
   │   sessions)   │   └────────────────────┘
   └───────────────┘
```

### Key problems solved

| Pain point | Solution |
|---|---|
| Losing context when switching threads | Orchestrator stores the full context snapshot of each thread |
| Spinning up a new Claude Code instance is slow | boxd pre-warms VMs; one command to attach a fresh session |
| No unified view of all ongoing tasks | TUI dashboard shows all threads, their status, and last output |
| Repeating task briefings across sessions | Shared project context is injected automatically on attach |

---

## Project structure

```
dev-threads/
├── src/
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── orchestrator.py   # Core orchestration logic
│   │   └── context_store.py  # Persists thread context to disk / SQLite
│   ├── threads/
│   │   ├── __init__.py
│   │   ├── thread.py         # DevThread model & state machine
│   │   └── manager.py        # ThreadManager – CRUD for threads
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── openclaw.py       # OpenClaw / kiloclaw API client
│   │   └── boxd.py           # boxd VM client (spin-up / teardown)
│   └── interfaces/
│       ├── __init__.py
│       ├── text_interface.py # Rich-based TUI / CLI
│       └── voice_interface.py# Voice command recognition & TTS
├── tests/
│   ├── test_thread.py
│   ├── test_manager.py
│   ├── test_orchestrator.py
│   └── test_integrations.py
├── .env.example
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Quick start

### Prerequisites

- Python ≥ 3.11
- A running **boxd** endpoint (local or remote)
- An **OpenClaw / kiloclaw** API key
- `uv` (recommended) or `pip`

### 1 – Clone & install

```bash
git clone https://github.com/RedHoven/dev-threads.git
cd dev-threads
uv sync          # or: pip install -e ".[dev]"
```

### 2 – Configure

```bash
cp .env.example .env
# Edit .env – fill in your API keys and endpoints
```

### 3 – Run the TUI

```bash
python -m dev_threads
```

### 4 – Run with Docker Compose (includes a mock boxd service)

```bash
docker compose up
```

---

## Usage

### Text interface commands

```
threads list                   – list all active dev threads
threads new  <name> <goal>     – spin up a new Claude Code thread
threads attach <id>            – attach to a running thread
threads pause  <id>            – pause and snapshot a thread
threads resume <id>            – resume a paused thread
threads kill   <id>            – stop and remove a thread
context show  <id>             – print the context snapshot for a thread
context share <src> <dst>      – copy relevant context from one thread to another
```

### Voice interface

Say **"Hey Threads"** (or the wake word you configure) then:

- *"New thread: refactor the auth module"*
- *"Switch to thread two"*
- *"What's the status of all threads?"*
- *"Pause thread three and summarise what it's doing"*

---

## Configuration reference (`.env`)

| Variable | Description | Default |
|---|---|---|
| `OPENCLAW_API_KEY` | API key for OpenClaw / kiloclaw | – |
| `OPENCLAW_BASE_URL` | Base URL of the kiloclaw endpoint | `https://api.kiloclaw.io` |
| `BOXD_ENDPOINT` | URL of the boxd API | `http://localhost:2375` |
| `BOXD_VM_IMAGE` | VM image tag to use for new instances | `claude-code:latest` |
| `CONTEXT_STORE_PATH` | Directory to persist thread context | `~/.dev-threads/contexts` |
| `VOICE_WAKE_WORD` | Wake word for the voice interface | `hey threads` |
| `VOICE_LANGUAGE` | BCP-47 language code for STT | `en-US` |
| `LOG_LEVEL` | Python logging level | `INFO` |

---

## Development

```bash
# Run tests
pytest

# Lint & format
ruff check src tests
ruff format src tests

# Type-check
mypy src
```

---

## Roadmap

- [ ] Real-time thread output streaming in TUI
- [ ] Shared context graph (threads can read each other's file trees)
- [ ] Automated thread-spawning from a high-level goal description
- [ ] Web dashboard (FastAPI + HTMX)
- [ ] Mobile voice client

---

## License

MIT – see [LICENSE](LICENSE).
