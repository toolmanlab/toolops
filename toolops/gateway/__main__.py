"""Entry point for running the LLM Gateway as a module.

Usage::

    python -m toolops.gateway [--port PORT] [--host HOST]
"""

from __future__ import annotations

import argparse
import logging

import uvicorn

from toolops.gateway.config import LISTEN_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Parse CLI args and start the gateway with uvicorn."""
    parser = argparse.ArgumentParser(
        prog="python -m toolops.gateway",
        description="ToolOps LLM Gateway Proxy",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=LISTEN_PORT,
        help=f"Port to listen on (default: {LISTEN_PORT})",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)",
    )
    args = parser.parse_args()

    logger.info("Starting ToolOps LLM Gateway on %s:%d", args.host, args.port)
    uvicorn.run(
        "toolops.gateway.proxy:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
