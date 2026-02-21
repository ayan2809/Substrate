"""Substrate CLI — First-Principles Reasoning Agent."""

from __future__ import annotations

import os
import sys

import typer
from dotenv import load_dotenv
from google import genai
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent import SubstrateAgent
from memory import SubstrateMemory

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


@app.command("models")
def models() -> None:
    """List all available Gemini models."""
    api_key = _load_api_key()
    client = genai.Client(api_key=api_key)

    with console.status("[bold cyan]Fetching available models...[/bold cyan]"):
        all_models = list(client.models.list())

    # Filter to generative models and sort by name
    gen_models = [
        m for m in all_models
        if "generateContent" in (m.supported_actions or [])
    ]
    gen_models.sort(key=lambda m: m.name or "")

    table = Table(
        title="\n⚛️  Available Gemini Models",
        title_style="bold cyan",
        border_style="dim",
        show_lines=True,
    )
    table.add_column("Model Name", style="bold green", no_wrap=True)
    table.add_column("Display Name", style="white")
    table.add_column("Description", style="dim", max_width=60)

    for m in gen_models:
        model_id = (m.name or "").replace("models/", "")
        table.add_row(
            model_id,
            m.display_name or "-",
            (m.description or "-")[:120],
        )

    console.print(table)
    console.print(
        f"\n[dim]{len(gen_models)} models available. "
        "Use with:[/dim] [bold]python main.py start --model [green]<model-name>[/green][/bold]\n"
    )


@app.command("start")
def start(
    model: str = typer.Option(
        "gemini-2.5-flash",
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
    memory = SubstrateMemory()
    agent = SubstrateAgent(api_key=api_key, memory=memory, model=model)

    console.print(
        f"[dim]Session [bold]{memory.session_uuid[:8]}[/bold] started  ·  "
        f"Model: [bold]{model}[/bold]  ·  "
        f"{memory.total_insights()} insight(s) in long-term memory[/dim]\n"
    )

    # — REPL —
    while True:
        try:
            user_input = console.input(PROMPT_MSG).strip()
        except (KeyboardInterrupt, EOFError):
            memory.close()
            console.print("\n[bold cyan]Session terminated. Think clearly.[/bold cyan]")
            raise typer.Exit()

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            memory.close()
            console.print("[bold cyan]Session terminated. Think clearly.[/bold cyan]")
            raise typer.Exit()

        # — Generator → Critic pipeline —
        try:
            # Phase 1: Generate
            status = console.status(SPINNER_MSG)
            status.start()

            def on_audit_start():
                status.update("[bold yellow]Substrate is auditing its own logic...[/bold yellow]")
                return status

            def on_audit_end():
                status.stop()

            response, audit_info = agent.run(
                user_input,
                on_audit_start=on_audit_start,
                on_audit_end=on_audit_end,
            )
            status.stop()

        except Exception as exc:
            try:
                status.stop()
            except Exception:
                pass
            console.print(f"[bold red]API Error:[/bold red] {exc}")
            continue

        # — Audit verdict —
        if audit_info["regenerated"]:
            console.print(
                f"[bold yellow]⚠ Critic flagged:[/bold yellow] [dim]{audit_info['reason']}[/dim]"
            )
            console.print("[bold green]✓ Re-generated with fix applied.[/bold green]")
        else:
            console.print("[bold green]✓ Audit passed.[/bold green]")

        # — Render Markdown —
        console.print()
        console.print(Markdown(response))
        console.print()


if __name__ == "__main__":
    app()
