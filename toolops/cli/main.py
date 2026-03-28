"""ToolOps CLI — manage the observability stack."""

from __future__ import annotations

import subprocess

import typer
from rich.console import Console

app = typer.Typer(name="toolops", help="AI application observability platform CLI")
console = Console()


@app.command()
def up() -> None:
    """Start all services via docker compose."""
    console.print("[bold green]Starting ToolOps stack...[/bold green]")
    subprocess.run(["docker", "compose", "up", "-d"], check=True)


@app.command()
def down() -> None:
    """Stop all services."""
    console.print("[bold red]Stopping ToolOps stack...[/bold red]")
    subprocess.run(["docker", "compose", "down"], check=True)


@app.command()
def status() -> None:
    """Show service status."""
    subprocess.run(["docker", "compose", "ps"], check=True)


@app.command()
def demo(
    scenario: str = typer.Option("normal", help="Demo scenario name"),
) -> None:
    """Run the demo app with a specific scenario."""
    console.print(f"[bold]Running demo scenario: {scenario}[/bold]")
    subprocess.run(
        ["docker", "compose", "run", "-e", f"DEMO_SCENARIO={scenario}", "demo-app"],
        check=True,
    )


if __name__ == "__main__":
    app()
