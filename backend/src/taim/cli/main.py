"""tAIm CLI — Power user interface."""

from __future__ import annotations

import typer

from taim.cli.agent import agent_app
from taim.cli.server import server_app
from taim.cli.stats import stats_app
from taim.cli.vault import vault_app

app = typer.Typer(
    name="taim",
    help="tAIm — Team AI Manager. AI team orchestration through natural language.",
    no_args_is_help=True,
)

app.add_typer(server_app, name="server", help="Start, stop, and manage the tAIm server.")
app.add_typer(agent_app, name="agent", help="List and inspect registered agents.")
app.add_typer(stats_app, name="stats", help="View token usage and cost statistics.")
app.add_typer(vault_app, name="vault", help="Vault operations — init, status, memory.")


@app.command()
def version() -> None:
    """Show tAIm version."""
    from rich.console import Console

    from taim import __version__

    Console().print(f"tAIm v{__version__}")
