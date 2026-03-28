"""Text (CLI/TUI) interface for dev-threads.

Commands
--------
threads list                      – list all active dev threads
threads new  <name> <goal>        – spin up a new Claude Code thread
threads attach <id>               – attach (interactively message) a thread
threads pause  <id>               – pause and snapshot a thread
threads resume <id>               – resume a paused thread
threads kill   <id>               – stop and remove a thread
context show  <id>                – print the context snapshot for a thread
context share <source> <dest>     – copy context from one thread to another
help                              – show this help
quit | exit                       – exit
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from typing import Any

from rich.console import Console
from rich.table import Table

from dev_threads.orchestrator.orchestrator import Orchestrator
from dev_threads.threads.manager import ThreadNotFoundError
from dev_threads.threads.thread import DevThread

logger = logging.getLogger(__name__)

HELP_TEXT = __doc__ or ""


class TextInterface:
    """Simple REPL-style text interface powered by Rich."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator
        self.console = Console()

    # ── Public entry-point ────────────────────────────────────────────────────

    async def run(self) -> None:
        """Start the interactive REPL loop."""
        self.console.print(
            "\n[bold green]dev-threads[/bold green] – Claude Code orchestrator  "
            "([dim]type 'help' for commands[/dim])\n"
        )
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("dev-threads> ")
                )
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Goodbye.[/dim]")
                break

            line = line.strip()
            if not line:
                continue
            await self._dispatch(line)

    # ── Dispatcher ────────────────────────────────────────────────────────────

    async def _dispatch(self, line: str) -> None:
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            self.console.print(f"[red]Parse error:[/red] {exc}")
            return

        if not parts:
            return

        cmd, *args = parts

        match cmd:
            case "threads":
                await self._cmd_threads(args)
            case "context":
                await self._cmd_context(args)
            case "help":
                self.console.print(HELP_TEXT)
            case "quit" | "exit":
                raise SystemExit(0)
            case _:
                self.console.print(f"[red]Unknown command:[/red] {cmd!r}  (type 'help')")

    # ── threads subcommands ───────────────────────────────────────────────────

    async def _cmd_threads(self, args: list[str]) -> None:
        if not args:
            self.console.print("[yellow]Usage:[/yellow] threads <list|new|attach|pause|resume|kill>")
            return

        sub, *rest = args

        match sub:
            case "list":
                self._print_thread_table(self.orchestrator.list_threads())
            case "new":
                if len(rest) < 2:
                    self.console.print("[yellow]Usage:[/yellow] threads new <name> <goal>")
                    return
                name, goal = rest[0], " ".join(rest[1:])
                with self.console.status(f"Spinning up thread [bold]{name}[/bold]…"):
                    thread = await self.orchestrator.new_thread(name, goal)
                self.console.print(
                    f"[green]✓[/green] Thread [bold]{thread.name}[/bold] started "
                    f"(id: {thread.id})"
                )
            case "attach":
                if not rest:
                    self.console.print("[yellow]Usage:[/yellow] threads attach <id>")
                    return
                await self._attach(rest[0])
            case "pause":
                if not rest:
                    self.console.print("[yellow]Usage:[/yellow] threads pause <id>")
                    return
                await self._run_and_report(
                    self.orchestrator.pause_thread(rest[0]),
                    "paused",
                )
            case "resume":
                if not rest:
                    self.console.print("[yellow]Usage:[/yellow] threads resume <id>")
                    return
                await self._run_and_report(
                    self.orchestrator.resume_thread(rest[0]),
                    "resumed",
                )
            case "kill":
                if not rest:
                    self.console.print("[yellow]Usage:[/yellow] threads kill <id>")
                    return
                await self._run_and_report(
                    self.orchestrator.kill_thread(rest[0]),
                    "killed",
                )
            case _:
                self.console.print(f"[red]Unknown sub-command:[/red] threads {sub!r}")

    # ── context subcommands ───────────────────────────────────────────────────

    async def _cmd_context(self, args: list[str]) -> None:
        if not args:
            self.console.print("[yellow]Usage:[/yellow] context <show|share>")
            return

        sub, *rest = args

        match sub:
            case "show":
                if not rest:
                    self.console.print("[yellow]Usage:[/yellow] context show <id>")
                    return
                try:
                    ctx = self.orchestrator.get_context(rest[0])
                except ThreadNotFoundError:
                    self.console.print(f"[red]Thread not found:[/red] {rest[0]}")
                    return
                self.console.print_json(data=ctx)
            case "share":
                if len(rest) < 2:
                    self.console.print("[yellow]Usage:[/yellow] context share <source_id> <dest_id>")
                    return
                try:
                    self.orchestrator.share_context(rest[0], rest[1])
                except ThreadNotFoundError as exc:
                    self.console.print(f"[red]Thread not found:[/red] {exc}")
                    return
                self.console.print(
                    f"[green]✓[/green] Context shared from {rest[0]!r} → {rest[1]!r}"
                )
            case _:
                self.console.print(f"[red]Unknown sub-command:[/red] context {sub!r}")

    # ── Attach / interactive messaging ────────────────────────────────────────

    async def _attach(self, thread_id: str) -> None:
        try:
            thread = self.orchestrator.get_thread(thread_id)
        except ThreadNotFoundError:
            self.console.print(f"[red]Thread not found:[/red] {thread_id}")
            return

        self.console.print(
            f"\nAttached to [bold]{thread.name}[/bold] ({thread.id})  "
            "[dim](type 'detach' to return)[/dim]\n"
        )
        loop = asyncio.get_event_loop()
        while True:
            try:
                msg = await loop.run_in_executor(None, lambda: input("  → "))
            except (EOFError, KeyboardInterrupt):
                break
            if msg.strip().lower() == "detach":
                self.console.print("[dim]Detached.[/dim]")
                break
            if not thread.session_id:
                self.console.print("[red]Thread has no active session.[/red]")
                break
            with self.console.status("Waiting for Claude…"):
                reply = await self.orchestrator.send_message(thread.id, msg)
            self.console.print(f"[cyan]Claude:[/cyan] {reply.get('reply', '')}\n")

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _run_and_report(
        self,
        coro: Any,  # noqa: ANN401
        action: str,
    ) -> None:
        try:
            thread: DevThread = await coro
            self.console.print(
                f"[green]✓[/green] Thread [bold]{thread.name}[/bold] {action}"
            )
        except ThreadNotFoundError as exc:
            self.console.print(f"[red]Thread not found:[/red] {exc}")
        except Exception as exc:  # noqa: BLE001
            self.console.print(f"[red]Error:[/red] {exc}")

    def _print_thread_table(self, threads: list[DevThread]) -> None:
        table = Table(title="Dev Threads", show_lines=True)
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Goal")
        table.add_column("VM", style="dim")

        status_colours = {
            "pending": "yellow",
            "running": "green",
            "paused": "blue",
            "completed": "dim",
            "failed": "red",
        }

        for t in threads:
            colour = status_colours.get(t.status.value, "white")
            table.add_row(
                t.id[:8],
                t.name,
                f"[{colour}]{t.status.value}[/{colour}]",
                t.goal[:60] + ("…" if len(t.goal) > 60 else ""),
                t.vm_id or "—",
            )

        if not threads:
            self.console.print("[dim]No active threads.[/dim]")
        else:
            self.console.print(table)
