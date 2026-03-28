"""Entry-point for ``python -m dev_threads``."""

from __future__ import annotations

import asyncio
import sys

from dev_threads.interfaces.text_interface import TextInterface
from dev_threads.orchestrator.orchestrator import Orchestrator


def main() -> None:
    orchestrator = Orchestrator()
    ui = TextInterface(orchestrator=orchestrator)
    try:
        asyncio.run(ui.run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
