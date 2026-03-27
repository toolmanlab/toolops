"""toolops init — interactive project initialization command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

_VECTORSTORE_CHOICES = ["chroma", "milvus", "qdrant"]
_CACHE_CHOICES = ["memory", "redis"]
_MONITOR_CHOICES = ["null", "phoenix"]
_ENV_CHOICES = ["local", "server", "cloud"]


def init_command(
    output_dir: Annotated[Path, typer.Option(
        "--output-dir",
        "-o",
        help="Directory to write generated files.",
        show_default=True,
    )] = Path("."),
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Accept all defaults without prompting."),
    ] = False,
) -> None:
    """Interactively initialize a ToolOps project.

    Generates:
    - toolops.yaml  — project configuration
    - docker-compose.yaml — ready-to-run service stack
    - .env.example  — environment variable template
    """
    console.print(
        Panel.fit(
            "[bold cyan]ToolOps Init[/bold cyan]\n"
            "Configure your AI infrastructure stack.",
            border_style="cyan",
        )
    )

    # ── Backend selection ─────────────────────────────────────
    if yes:
        vectorstore = "chroma"
        cache = "memory"
        monitor = "null"
        env = "local"
    else:
        console.print("\n[bold]Vector Store[/bold] (where embeddings live)")
        for i, name in enumerate(_VECTORSTORE_CHOICES, 1):
            console.print(f"  {i}. {name}")
        vs_raw = Prompt.ask(
            "Choose vector store",
            choices=_VECTORSTORE_CHOICES,
            default="chroma",
        )
        vectorstore = vs_raw

        console.print("\n[bold]Cache[/bold] (key-value store for fast lookups)")
        cache = Prompt.ask(
            "Choose cache backend",
            choices=_CACHE_CHOICES,
            default="memory",
        )

        console.print("\n[bold]Monitor[/bold] (LLM tracing & observability)")
        monitor = Prompt.ask(
            "Choose monitor backend",
            choices=_MONITOR_CHOICES,
            default="null",
        )

        console.print("\n[bold]Environment[/bold]")
        env = Prompt.ask(
            "Deployment environment",
            choices=_ENV_CHOICES,
            default="local",
        )

    # ── Summary ───────────────────────────────────────────────
    console.print(
        f"\n[bold]Selected stack:[/bold]\n"
        f"  Vector store : [green]{vectorstore}[/green]\n"
        f"  Cache        : [green]{cache}[/green]\n"
        f"  Monitor      : [green]{monitor}[/green]\n"
        f"  Environment  : [green]{env}[/green]\n"
    )

    if not yes and not Confirm.ask("Generate configuration files?", default=True):
        console.print("[yellow]Aborted.[/yellow]")
        raise typer.Exit()

    # ── File generation ───────────────────────────────────────
    dest = output_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    from toolops.utils.docker import generate_config_yaml, generate_docker_compose

    cfg_path = generate_config_yaml(vectorstore, cache, monitor, env, dest=dest / "toolops.yaml")
    console.print(f"[green]✓[/green] {cfg_path}")

    dc_path = generate_docker_compose(
        vectorstore, cache, monitor, dest=dest / "docker-compose.yaml",
    )
    console.print(f"[green]✓[/green] {dc_path}")

    # Copy .env.example if it doesn't exist
    env_example_src = Path(__file__).parent.parent.parent / ".env.example"
    env_example_dst = dest / ".env.example"
    if env_example_src.exists() and not env_example_dst.exists():
        env_example_dst.write_text(env_example_src.read_text())
        console.print(f"[green]✓[/green] {env_example_dst}")

    console.print(
        "\n[bold cyan]Done![/bold cyan] "
        "Start your stack with: [green]docker compose up -d[/green]"
    )
