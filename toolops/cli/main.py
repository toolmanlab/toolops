"""ToolOps CLI — main Typer application."""

from __future__ import annotations

import typer
from rich.console import Console

from toolops.cli.env import app as env_app
from toolops.cli.init import init_command
from toolops.cli.status import status_command

app = typer.Typer(
    name="toolops",
    help="ToolOps — AI app infrastructure, plug and play.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

# ── Sub-commands ──────────────────────────────────────────────
app.add_typer(env_app, name="env", help="Manage deployment environments.")
app.command("init")(init_command)
app.command("status")(status_command)


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context) -> None:
    """Show help when no sub-command is given."""
    if ctx.invoked_subcommand is None:
        console.print(
            "[bold cyan]ToolOps[/bold cyan] — AI app infrastructure, plug and play.\n"
            "Run [green]toolops --help[/green] to see available commands."
        )


if __name__ == "__main__":
    app()
