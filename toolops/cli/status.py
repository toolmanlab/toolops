"""toolops status — check health of configured backend services."""

from __future__ import annotations

import socket
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from toolops.config.loader import load_config
from toolops.config.schema import ToolOpsConfig

console = Console()


def _tcp_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_vectorstore(config: ToolOpsConfig) -> tuple[str, str, str]:
    """Return (backend, address, status) for the active vector store."""
    backend = config.vectorstore
    if backend == "chroma":
        cfg = config.chroma
        addr = f"{cfg.host}:{cfg.port}"
        ok = _tcp_reachable(cfg.host, cfg.port)
    elif backend == "milvus":
        cfg = config.milvus
        addr = f"{cfg.host}:{cfg.port}"
        ok = _tcp_reachable(cfg.host, cfg.port)
    elif backend == "qdrant":
        cfg = config.qdrant
        addr = f"{cfg.host}:{cfg.port}"
        ok = _tcp_reachable(cfg.host, cfg.port)
    else:
        return backend, "N/A", "[yellow]unknown[/yellow]"
    status = "[green]● reachable[/green]" if ok else "[red]✗ unreachable[/red]"
    return backend, addr, status


def _check_cache(config: ToolOpsConfig) -> tuple[str, str, str]:
    """Return (backend, address, status) for the active cache."""
    backend = config.cache
    if backend == "memory":
        return backend, "in-process", "[green]● always up[/green]"
    elif backend == "redis":
        cfg = config.redis
        addr = f"{cfg.host}:{cfg.port}"
        ok = _tcp_reachable(cfg.host, cfg.port)
        status = "[green]● reachable[/green]" if ok else "[red]✗ unreachable[/red]"
        return backend, addr, status
    return backend, "N/A", "[yellow]unknown[/yellow]"


def _check_monitor(config: ToolOpsConfig) -> tuple[str, str, str]:
    """Return (backend, address, status) for the active monitor."""
    backend = config.monitor
    if backend == "null":
        return backend, "—", "[dim]disabled[/dim]"
    elif backend == "phoenix":
        cfg = config.phoenix
        addr = f"{cfg.host}:{cfg.port}"
        ok = _tcp_reachable(cfg.host, cfg.port)
        status = "[green]● reachable[/green]" if ok else "[red]✗ unreachable[/red]"
        return backend, addr, status
    return backend, "N/A", "[yellow]unknown[/yellow]"


def status_command(
    config_path: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Explicit path to toolops.yaml (auto-discovered if omitted).",
    ),
) -> None:
    """Check the health status of all configured backend services.

    Performs a TCP reachability probe for each enabled service
    and prints a summary table.
    """
    config = load_config(config_path)

    table = Table(
        title=f"ToolOps Status  [dim](env: {config.env})[/dim]",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Component", style="bold", min_width=12)
    table.add_column("Backend", min_width=10)
    table.add_column("Address", min_width=20)
    table.add_column("Status")

    vs_backend, vs_addr, vs_status = _check_vectorstore(config)
    table.add_row("Vector Store", vs_backend, vs_addr, vs_status)

    cache_backend, cache_addr, cache_status = _check_cache(config)
    table.add_row("Cache", cache_backend, cache_addr, cache_status)

    monitor_backend, monitor_addr, monitor_status = _check_monitor(config)
    table.add_row("Monitor", monitor_backend, monitor_addr, monitor_status)

    console.print(table)
