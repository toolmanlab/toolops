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


@app.command("recalculate-cost")
def recalculate_cost(
    clickhouse_host: str = typer.Option("localhost", help="ClickHouse host"),
    clickhouse_port: int = typer.Option(8123, help="ClickHouse HTTP port"),
    clickhouse_user: str = typer.Option("default", help="ClickHouse user"),
    clickhouse_password: str = typer.Option("", help="ClickHouse password"),
    clickhouse_database: str = typer.Option("toolops", help="ClickHouse database"),
    dry_run: bool = typer.Option(False, help="Print the SQL but do not execute it"),
) -> None:
    """Back-fill cost_usd for all existing llm_usage rows using the current pricing table.

    Uses a single ALTER TABLE UPDATE with CASE WHEN expressions grouped by model,
    so no rows need to be read into Python — the calculation happens entirely in
    ClickHouse SQL.
    """
    from toolops.config.settings import ClickHouseSettings
    from toolops.pricing.models import PRICING_TABLE, _lookup_pricing
    from toolops.storage.clickhouse import ClickHouseClient

    settings = ClickHouseSettings(
        host=clickhouse_host,
        port=clickhouse_port,
        user=clickhouse_user,
        password=clickhouse_password,
        database=clickhouse_database,
    )
    client = ClickHouseClient(settings)

    # Discover all distinct model names present in the table
    console.print("[bold]Fetching distinct models from llm_usage...[/bold]")
    try:
        result = client.client.query("SELECT DISTINCT model FROM llm_usage")
        models: list[str] = [row[0] for row in result.result_rows]
    except Exception as exc:
        console.print(f"[red]Failed to query llm_usage: {exc}[/red]")
        raise typer.Exit(1) from exc

    console.print(f"Found [bold]{len(models)}[/bold] distinct model(s): {models}")

    # Build CASE WHEN expression for cost_usd.
    # For each known model we emit one WHEN branch.  Unknown models keep their
    # existing value (the final ELSE clause uses the current column value).
    #
    # Formula (mirroring calculate_cost):
    #   non_cache_input = input_tokens - cache_creation_tokens - cache_read_tokens
    #   cost = (non_cache_input * input_per_m
    #           + output_tokens * output_per_m
    #           + cache_creation_tokens * cache_write_per_m
    #           + cache_read_tokens * cache_read_per_m) / 1_000_000
    #
    # We iterate over all distinct models actually present, match each to
    # PRICING_TABLE, and only include models we can price (skip unknowns).

    cases: list[str] = []
    priced: list[str] = []
    unpriced: list[str] = []

    for model in models:
        pricing = _lookup_pricing(model)
        if pricing is None:
            unpriced.append(model)
            continue

        priced.append(model)
        inp = pricing["input_per_m"]
        out = pricing["output_per_m"]
        cw = pricing["cache_write_per_m"]
        cr = pricing["cache_read_per_m"]

        # Escape single quotes in model name (just in case)
        safe_model = model.replace("'", "''")

        expr = (
            f"WHEN model = '{safe_model}' THEN "
            f"("
            f"  toFloat64(greatest(0, input_tokens - cache_creation_tokens - cache_read_tokens)) * {inp}"
            f"  + toFloat64(output_tokens) * {out}"
            f"  + toFloat64(cache_creation_tokens) * {cw}"
            f"  + toFloat64(cache_read_tokens) * {cr}"
            f") / 1000000"
        )
        cases.append(expr)

    if not cases:
        console.print("[yellow]No models matched the pricing table — nothing to update.[/yellow]")
        if unpriced:
            console.print(f"[dim]Unpriced models: {unpriced}[/dim]")
        return

    if unpriced:
        console.print(f"[yellow]Warning: no pricing for model(s): {unpriced} — those rows will be set to 0.0[/yellow]")

    case_sql = "CASE\n  " + "\n  ".join(cases) + "\n  ELSE 0.0\nEND"
    alter_sql = f"ALTER TABLE llm_usage UPDATE cost_usd = {case_sql} WHERE 1"

    if dry_run:
        console.print("[yellow]Dry-run — SQL that would be executed:[/yellow]")
        console.print(alter_sql)
        return

    console.print(f"[bold]Updating cost_usd for {len(priced)} model(s)...[/bold]")
    console.print(f"[dim]{alter_sql[:200]}...[/dim]")
    try:
        client.client.command(alter_sql)
        console.print("[bold green]Done. cost_usd recalculated for all matching rows.[/bold green]")
    except Exception as exc:
        console.print(f"[red]ALTER TABLE UPDATE failed: {exc}[/red]")
        raise typer.Exit(1) from exc


if __name__ == "__main__":
    app()
