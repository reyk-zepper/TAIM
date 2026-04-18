"""CLI commands for server management."""

from __future__ import annotations

import typer
from rich.console import Console

server_app = typer.Typer(no_args_is_help=True)
console = Console()


@server_app.command("start")
def start(
    host: str = typer.Option("localhost", help="Server bind address"),
    port: int = typer.Option(8000, help="Server port"),
    vault: str = typer.Option("./taim-vault", help="Vault path"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
) -> None:
    """Start the tAIm server."""
    import os

    os.environ["TAIM_VAULT_PATH"] = vault
    os.environ["TAIM_HOST"] = host
    os.environ["TAIM_PORT"] = str(port)

    console.print(f"\n  [bold]tAIm[/bold] starting on [cyan]http://{host}:{port}[/cyan]")
    console.print(f"  Vault: [dim]{vault}[/dim]")
    console.print(f"  Dashboard: [cyan]http://{host}:{port}[/cyan]\n")

    import uvicorn

    uvicorn.run(
        "taim.main:app",
        host=host,
        port=port,
        reload=reload,
    )
