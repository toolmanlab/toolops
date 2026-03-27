"""Docker Compose file generator using Jinja2 templates."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "config" / "templates"


def _render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template from the templates directory.

    Args:
        template_name: Filename inside the templates/ directory.
        context:       Template variables.

    Returns:
        Rendered string.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, StrictUndefined

        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template(template_name)
        return template.render(**context)  # type: ignore[no-any-return]
    except ImportError as exc:
        raise RuntimeError("jinja2 is required. It should be installed with toolops.") from exc


def generate_docker_compose(
    vectorstore: str,
    cache: str,
    monitor: str,
    dest: Path | None = None,
) -> Path:
    """Generate a docker-compose.yaml for the chosen backend combination.

    Args:
        vectorstore: One of "chroma", "milvus", "qdrant".
        cache:       One of "memory", "redis".
        monitor:     One of "null", "phoenix".
        dest:        Output path.  Defaults to ./docker-compose.yaml.

    Returns:
        Path to the written file.
    """
    context: dict[str, Any] = {
        "vectorstore": vectorstore,
        "cache": cache,
        "monitor": monitor,
    }
    content = _render_template("docker-compose.yaml.j2", context)
    target = dest or (Path.cwd() / "docker-compose.yaml")
    target.write_text(content, encoding="utf-8")
    logger.info("docker-compose.yaml written to %s", target)
    return target


def generate_config_yaml(
    vectorstore: str,
    cache: str,
    monitor: str,
    env: str = "local",
    dest: Path | None = None,
) -> Path:
    """Generate a toolops.yaml from the interactive init template.

    Args:
        vectorstore: Active vector store backend.
        cache:       Active cache backend.
        monitor:     Active monitor backend.
        env:         Deployment environment (local/server/cloud).
        dest:        Output path.  Defaults to ./toolops.yaml.

    Returns:
        Path to the written file.
    """
    context: dict[str, Any] = {
        "vectorstore": vectorstore,
        "cache": cache,
        "monitor": monitor,
        "env": env,
    }
    content = _render_template("toolops.yaml.j2", context)
    target = dest or (Path.cwd() / "toolops.yaml")
    target.write_text(content, encoding="utf-8")
    logger.info("toolops.yaml written to %s", target)
    return target
