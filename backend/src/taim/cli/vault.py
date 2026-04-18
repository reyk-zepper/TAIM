"""CLI commands for vault operations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

vault_app = typer.Typer(no_args_is_help=True)
console = Console()


@vault_app.command("init")
def init_vault(
    path: str = typer.Option("./taim-vault", help="Vault path"),
) -> None:
    """Initialize the tAIm vault directory structure."""
    from taim.brain.vault import VaultOps

    ops = VaultOps(Path(path))
    ops.ensure_vault()
    console.print(f"\n[green]✓[/green] Vault initialized at [cyan]{Path(path).resolve()}[/cyan]\n")


@vault_app.command("status")
def vault_status(
    path: str = typer.Option("./taim-vault", help="Vault path"),
) -> None:
    """Show vault status — path, disk usage, counts."""
    vault_path = Path(path).resolve()
    if not vault_path.exists():
        console.print(f"[red]Vault not found at {vault_path}[/red]")
        raise typer.Exit(1)

    agent_count = (
        len(list((vault_path / "agents").glob("*.yaml"))) if (vault_path / "agents").exists() else 0
    )
    prompt_count = (
        len(list((vault_path / "system" / "prompts").rglob("*.yaml")))
        if (vault_path / "system" / "prompts").exists()
        else 0
    )
    tool_count = (
        len(list((vault_path / "system" / "tools").glob("*.yaml")))
        if (vault_path / "system" / "tools").exists()
        else 0
    )
    skill_count = (
        len(list((vault_path / "system" / "skills").glob("*.yaml")))
        if (vault_path / "system" / "skills").exists()
        else 0
    )

    # Count memory entries
    memory_count = 0
    users_dir = vault_path / "users"
    if users_dir.exists():
        memory_count = len(list(users_dir.rglob("*.md")))

    console.print("\n[bold]Vault Status[/bold]\n")
    console.print(f"  Path:     [cyan]{vault_path}[/cyan]")
    console.print(f"  Agents:   [cyan]{agent_count}[/cyan]")
    console.print(f"  Prompts:  [cyan]{prompt_count}[/cyan]")
    console.print(f"  Tools:    [cyan]{tool_count}[/cyan]")
    console.print(f"  Skills:   [cyan]{skill_count}[/cyan]")
    console.print(f"  Memory:   [cyan]{memory_count} entries[/cyan]")
    console.print()
