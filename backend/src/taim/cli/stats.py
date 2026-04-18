"""CLI commands for statistics."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

stats_app = typer.Typer(invoke_without_command=True)
console = Console()


def _fetch(path: str) -> dict:
    import httpx

    try:
        r = httpx.get(f"http://localhost:8000{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        console.print(f"[red]Error:[/red] Could not reach tAIm server. ({e})")
        raise typer.Exit(1)


@stats_app.callback()
def stats_default(
    breakdown: bool = typer.Option(False, "--breakdown", help="Show per-provider breakdown"),
) -> None:
    """Show monthly usage stats."""
    data = _fetch("/api/stats/monthly")

    console.print("\n[bold]Monthly Statistics[/bold]\n")
    console.print(f"  Total cost:     [cyan]${data['total_cost_usd']:.4f}[/cyan]")
    console.print(f"  Total tokens:   [cyan]{data['total_tokens']:,}[/cyan]")
    console.print(f"  Tasks:          [cyan]{data['task_count']}[/cyan]")
    console.print(f"  Avg cost/task:  [cyan]${data['avg_cost_per_task']:.4f}[/cyan]")

    if breakdown and data.get("by_provider"):
        console.print()
        table = Table(title="By Provider")
        table.add_column("Provider", style="cyan")
        table.add_column("Calls", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right", style="bold")

        for p in data["by_provider"]:
            table.add_row(
                p["provider"],
                str(p["calls"]),
                f"{p['total_tokens']:,}",
                f"${p['cost_usd']:.4f}",
            )
        console.print(table)
    console.print()
