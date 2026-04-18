"""CLI commands for agent management."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

agent_app = typer.Typer(no_args_is_help=True)
console = Console()


def _fetch(path: str) -> dict:
    """Fetch from local API."""
    import httpx

    try:
        r = httpx.get(f"http://localhost:8000{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        console.print(f"[red]Error:[/red] Could not reach tAIm server. Is it running? ({e})")
        raise typer.Exit(1)


@agent_app.command("list")
def list_agents() -> None:
    """List all registered agents."""
    data = _fetch("/api/agents")
    table = Table(title="Registered Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Skills", style="dim")

    for agent in data.get("agents", []):
        table.add_row(
            agent["name"],
            agent["description"],
            ", ".join(agent.get("skills", [])),
        )
    console.print(table)


@agent_app.command("show")
def show_agent(name: str = typer.Argument(help="Agent name")) -> None:
    """Show full details of a specific agent."""
    data = _fetch(f"/api/agents/{name}")
    console.print(f"\n[bold cyan]{data['name']}[/bold cyan]")
    console.print(f"  {data['description']}\n")
    console.print(f"  [dim]Model preference:[/dim] {' → '.join(data.get('model_preference', []))}")
    console.print(f"  [dim]Skills:[/dim] {', '.join(data.get('skills', []))}")
    console.print(f"  [dim]Tools:[/dim] {', '.join(data.get('tools', []))}")
    console.print(f"  [dim]Max iterations:[/dim] {data.get('max_iterations', '?')}")
    if data.get("requires_approval_for"):
        console.print(f"  [dim]Approval gates:[/dim] {', '.join(data['requires_approval_for'])}")
    console.print()
