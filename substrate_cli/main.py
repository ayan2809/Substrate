"""Substrate CLI — First-Principles Reasoning Agent."""

from __future__ import annotations

import os
import sys

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from agent import SubstrateAgent

# ── Typer & Rich setup ───────────────────────────────────────────────
app = typer.Typer(
    name="substrate",
    help="Substrate — a first-principles reasoning CLI.",
    add_completion=False,
)
console = Console()


@app.callback()
def callback() -> None:
    """Substrate — First-Principles Reasoning Agent."""
    pass

# ── Constants ─────────────────────────────────────────────────────────
BANNER = r"""
███████╗██╗   ██╗██████╗ ███████╗████████╗██████╗  █████╗ ████████╗███████╗
██╔════╝██║   ██║██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗╚══██╔══╝██╔════╝
███████╗██║   ██║██████╔╝███████╗   ██║   ██████╔╝███████║   ██║   █████╗  
╚════██║██║   ██║██╔══██╗╚════██║   ██║   ██╔══██╗██╔══██║   ██║   ██╔══╝  
███████║╚██████╔╝██████╔╝███████║   ██║   ██║  ██║██║  ██║   ██║   ███████╗
╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
"""

SPINNER_MSG = "[bold cyan]Deconstructing to atoms...[/bold cyan]"
PROMPT_MSG = "[bold green][Substrate][/bold green] Enter your idea or constraint (or type 'exit'): "


def _load_api_key() -> str:
    """Load the Gemini API key from .env or environment."""
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        console.print(
            "[bold red]Error:[/bold red] GEMINI_API_KEY not found. "
            "Add it to substrate_cli/.env or export it as an environment variable."
        )
        raise typer.Exit(code=1)
    return key


@app.command("start")
def start(
    model: str = typer.Option(
        "gemini-2.0-flash",
        "--model",
        "-m",
        help="Gemini model to use.",
    ),
) -> None:
    """Start an interactive Substrate reasoning session."""

    # — Banner —
    console.print(Text(BANNER, style="bold cyan"))
    console.print(
        Panel(
            "[bold white]First-Principles Reasoning Agent  ·  v1.0[/bold white]\n"
            "[dim]Recursive Deconstruction  ·  Highest Leverage  ·  Zero Jargon[/dim]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()

    # — Init —
    api_key = _load_api_key()
    agent = SubstrateAgent(api_key=api_key, model=model)
    console.print("[dim]Session started. Context is preserved until you exit.[/dim]\n")

    # — REPL —
    while True:
        try:
            user_input = console.input(PROMPT_MSG).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Session terminated. Think clearly.[/bold cyan]")
            raise typer.Exit()

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            console.print("[bold cyan]Session terminated. Think clearly.[/bold cyan]")
            raise typer.Exit()

        # — Call LLM with spinner —
        try:
            with console.status(SPINNER_MSG):
                response = agent.run(user_input)
        except Exception as exc:
            console.print(f"[bold red]API Error:[/bold red] {exc}")
            continue

        # — Render Markdown —
        console.print()
        console.print(Markdown(response))
        console.print()


if __name__ == "__main__":
    app()
