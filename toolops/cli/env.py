"""toolops env — environment management sub-commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from toolops.config.loader import load_config, write_config

app = typer.Typer(help="Manage ToolOps deployment environments.")
console = Console()

_VALID_ENVS = ["local", "server", "cloud"]


@app.command("list")
def env_list() -> None:
    """List all available environments and highlight the active one."""
    config = load_config()
    active = config.env

    table = Table(title="ToolOps Environments", show_header=True, header_style="bold cyan")
    table.add_column("Environment", style="bold")
    table.add_column("Status")
    table.add_column("Description")

    descriptions = {
        "local": "Local Docker Compose — no cloud services",
        "server": "Self-hosted server — Kubernetes / bare-metal",
        "cloud": "Managed cloud services — Qdrant Cloud, Upstash, Phoenix Cloud",
    }

    for env_name in _VALID_ENVS:
        status = "[green]● active[/green]" if env_name == active else "○ available"
        table.add_row(env_name, status, descriptions[env_name])

    console.print(table)


@app.command("switch")
def env_switch(
    environment: str = typer.Argument(..., help="Target environment: local | server | cloud"),
    config_path: Path = typer.Option(
        Path("toolops.yaml"),
        "--config",
        "-c",
        help="Path to toolops.yaml",
    ),
) -> None:
    """Switch the active deployment environment.

    Updates the ``env`` field in toolops.yaml.
    """
    if environment not in _VALID_ENVS:
        console.print(
            f"[red]Unknown environment:[/red] {environment}\n"
            f"Valid options: {', '.join(_VALID_ENVS)}"
        )
        raise typer.Exit(code=1)

    config = load_config(config_path if config_path.exists() else None)
    old_env = config.env

    if old_env == environment:
        console.print(f"[yellow]Already on environment:[/yellow] {environment}")
        return

    updated = config.model_copy(update={"env": environment})  # type: ignore[arg-type]
    out = write_config(updated, config_path)
    console.print(
        f"[green]✓[/green] Switched from [yellow]{old_env}[/yellow] → "
        f"[cyan]{environment}[/cyan] (saved to {out})"
    )
