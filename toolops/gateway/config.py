"""Gateway configuration: upstream URLs, listen port, and environment overrides."""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Upstream provider base URLs
# ---------------------------------------------------------------------------
# Can be overridden individually via environment variables:
#   TOOLOPS_UPSTREAM_ANTHROPIC, TOOLOPS_UPSTREAM_OPENAI, TOOLOPS_UPSTREAM_DEEPSEEK
# ---------------------------------------------------------------------------

UPSTREAM_URLS: dict[str, str] = {
    "anthropic": os.environ.get(
        "TOOLOPS_UPSTREAM_ANTHROPIC", "https://api.anthropic.com"
    ),
    "openai": os.environ.get(
        "TOOLOPS_UPSTREAM_OPENAI", "https://api.openai.com"
    ),
    "deepseek": os.environ.get(
        "TOOLOPS_UPSTREAM_DEEPSEEK", "https://api.deepseek.com"
    ),
    "moonshot": os.environ.get(
        "TOOLOPS_UPSTREAM_MOONSHOT", "https://api.moonshot.cn"
    ),
    "minimax": os.environ.get(
        "TOOLOPS_UPSTREAM_MINIMAX", "https://api.minimax.chat"
    ),
    "zhipu": os.environ.get(
        "TOOLOPS_UPSTREAM_ZHIPU", "https://open.bigmodel.cn/api/paas"
    ),
    "cliproxy": os.environ.get(
        "TOOLOPS_UPSTREAM_CLIPROXY", "http://localhost:8317"
    ),
    "ollama": os.environ.get(
        "TOOLOPS_UPSTREAM_OLLAMA", "http://localhost:11434"
    ),
}

# ---------------------------------------------------------------------------
# Proxy listen port
# ---------------------------------------------------------------------------

LISTEN_PORT: int = int(os.environ.get("TOOLOPS_GATEWAY_PORT", "9010"))

# ---------------------------------------------------------------------------
# Request / response size limits (bytes) for body buffering
# ---------------------------------------------------------------------------

MAX_BUFFER_BYTES: int = 10 * 1024 * 1024  # 10 MB

# ---------------------------------------------------------------------------
# OpenClaw request header names
# ---------------------------------------------------------------------------

HEADER_AGENT = "x-openclaw-agent"
HEADER_SESSION = "x-openclaw-session"
HEADER_SKILL = "x-openclaw-skill"
HEADER_CHANNEL = "x-openclaw-channel"
