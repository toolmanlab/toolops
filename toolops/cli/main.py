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


collect_app = typer.Typer(help="Data collector commands.")
app.add_typer(collect_app, name="collect")


@collect_app.command("cc")
def collect_cc(
    clickhouse_host: str = typer.Option("localhost", help="ClickHouse host"),
    clickhouse_port: int = typer.Option(8123, help="ClickHouse HTTP port"),
    clickhouse_user: str = typer.Option("default", help="ClickHouse user"),
    clickhouse_password: str = typer.Option("", help="ClickHouse password"),
    clickhouse_database: str = typer.Option("toolops", help="ClickHouse database"),
    dry_run: bool = typer.Option(False, help="Parse but do not insert into ClickHouse"),
) -> None:
    """Scan Claude Code local session files and write usage to ClickHouse."""
    from toolops.collector.cc_collector import ClaudeCodeCollector
    from toolops.config.settings import ClickHouseSettings
    from toolops.storage.clickhouse import ClickHouseClient

    console.print("[bold]Scanning Claude Code sessions...[/bold]")
    collector = ClaudeCodeCollector()
    usages = collector.collect()
    console.print(f"Found [bold green]{len(usages)}[/bold green] usage records.")

    if dry_run:
        console.print("[yellow]Dry-run mode — skipping ClickHouse insert.[/yellow]")
        return

    settings = ClickHouseSettings(
        host=clickhouse_host,
        port=clickhouse_port,
        user=clickhouse_user,
        password=clickhouse_password,
        database=clickhouse_database,
    )
    client = ClickHouseClient(settings)
    inserted = collector.ingest_to_clickhouse(client, usages)
    console.print(f"Inserted [bold green]{inserted}[/bold green] records into ClickHouse.")


if __name__ == "__main__":
    app()
