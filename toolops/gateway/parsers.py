"""Provider-specific request/response parsers for LLM Gateway.

Each parser implements the adapter pattern so that the proxy core remains
provider-agnostic.  Add a new class for each provider you want to support.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ParsedUsage:
    """Normalised token usage extracted from a provider response."""

    __slots__ = (
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
    )

    def __init__(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_tokens = cache_creation_tokens
        self.cache_read_tokens = cache_read_tokens

    @property
    def total_tokens(self) -> int:
        """Sum of all token counts."""
        return (
            self.input_tokens
            + self.output_tokens
        )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"ParsedUsage(in={self.input_tokens}, out={self.output_tokens}, "
            f"cache_create={self.cache_creation_tokens}, cache_read={self.cache_read_tokens})"
        )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class BaseParser(ABC):
    """Abstract base for provider-specific request/response parsers."""

    @abstractmethod
    def parse_model(self, body: dict[str, Any]) -> str:
        """Extract the model name from a decoded request body.

        Args:
            body: Decoded JSON request body.

        Returns:
            Model identifier string, or empty string if not found.
        """

    @abstractmethod
    def parse_response_usage(self, body: dict[str, Any]) -> ParsedUsage:
        """Extract token usage from a decoded (non-streaming) response body.

        Args:
            body: Decoded JSON response body.

        Returns:
            :class:`ParsedUsage` instance.
        """

    @abstractmethod
    def parse_stream_chunk_usage(self, chunk_data: str) -> ParsedUsage | None:
        """Try to extract token usage from a single SSE data payload.

        Called for every SSE chunk.  Returns ``None`` if this chunk carries no
        usage information; returns a :class:`ParsedUsage` for the chunk that
        does.

        Args:
            chunk_data: The raw SSE ``data:`` field string (not yet decoded).

        Returns:
            :class:`ParsedUsage` instance or ``None``.
        """


# ---------------------------------------------------------------------------
# Anthropic parser
# ---------------------------------------------------------------------------


class AnthropicParser(BaseParser):
    """Parser for Anthropic /v1/messages API (non-streaming and streaming)."""

    def parse_model(self, body: dict[str, Any]) -> str:
        """Extract ``model`` field from Anthropic request body."""
        return str(body.get("model", ""))

    def parse_response_usage(self, body: dict[str, Any]) -> ParsedUsage:
        """Extract usage from Anthropic non-streaming response.

        Anthropic response structure::

            {
              "usage": {
                "input_tokens": 123,
                "output_tokens": 45,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0
              }
            }
        """
        usage = body.get("usage") or {}
        return ParsedUsage(
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cache_creation_tokens=int(
                usage.get("cache_creation_input_tokens", 0)
            ),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0)),
        )

    def parse_stream_chunk_usage(self, chunk_data: str) -> ParsedUsage | None:
        """Extract usage from Anthropic streaming SSE chunks.

        Anthropic streaming emits a ``message_delta`` event with::

            {"type": "message_delta", "usage": {"output_tokens": N}}

        and a ``message_start`` event with full input usage::

            {"type": "message_start", "message": {"usage": {...}}}
        """
        if not chunk_data or chunk_data == "[DONE]":
            return None
        try:
            obj = json.loads(chunk_data)
        except json.JSONDecodeError:
            return None

        event_type = obj.get("type", "")

        # message_start carries input token counts
        if event_type == "message_start":
            message = obj.get("message") or {}
            usage = message.get("usage") or {}
            if usage:
                return ParsedUsage(
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                    cache_creation_tokens=int(
                        usage.get("cache_creation_input_tokens", 0)
                    ),
                    cache_read_tokens=int(
                        usage.get("cache_read_input_tokens", 0)
                    ),
                )

        # message_delta carries output token count at end of stream
        if event_type == "message_delta":
            usage = obj.get("usage") or {}
            if "output_tokens" in usage:
                return ParsedUsage(
                    output_tokens=int(usage.get("output_tokens", 0)),
                )

        return None


# ---------------------------------------------------------------------------
# OpenAI parser
# ---------------------------------------------------------------------------


class OpenAIParser(BaseParser):
    """Parser for OpenAI-compatible /v1/chat/completions API."""

    def parse_model(self, body: dict[str, Any]) -> str:
        """Extract ``model`` field from OpenAI request body."""
        return str(body.get("model", ""))

    def parse_response_usage(self, body: dict[str, Any]) -> ParsedUsage:
        """Extract usage from OpenAI non-streaming response.

        OpenAI response structure::

            {
              "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 45,
                "total_tokens": 168
              }
            }
        """
        usage = body.get("usage") or {}
        return ParsedUsage(
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )

    def parse_stream_chunk_usage(self, chunk_data: str) -> ParsedUsage | None:
        """Extract usage from OpenAI streaming SSE chunks.

        OpenAI optionally includes ``usage`` in the final chunk when
        ``stream_options: {include_usage: true}`` is set::

            {"choices": [], "usage": {"prompt_tokens": N, "completion_tokens": M}}
        """
        if not chunk_data or chunk_data == "[DONE]":
            return None
        try:
            obj = json.loads(chunk_data)
        except json.JSONDecodeError:
            return None

        usage = obj.get("usage")
        if usage and ("prompt_tokens" in usage or "completion_tokens" in usage):
            return ParsedUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            )

        return None


# ---------------------------------------------------------------------------
# Generic / fallback parser
# ---------------------------------------------------------------------------


class GenericParser(BaseParser):
    """Best-effort parser for unknown providers.

    Tries common field names for model and usage extraction.
    """

    def parse_model(self, body: dict[str, Any]) -> str:
        """Try common model field names."""
        for key in ("model", "model_id", "engine"):
            if key in body:
                return str(body[key])
        return ""

    def parse_response_usage(self, body: dict[str, Any]) -> ParsedUsage:
        """Try common usage field names."""
        usage = body.get("usage") or {}
        return ParsedUsage(
            input_tokens=int(
                usage.get("input_tokens", usage.get("prompt_tokens", 0))
            ),
            output_tokens=int(
                usage.get("output_tokens", usage.get("completion_tokens", 0))
            ),
        )

    def parse_stream_chunk_usage(self, chunk_data: str) -> ParsedUsage | None:
        """Try to find usage in any streaming chunk."""
        if not chunk_data or chunk_data == "[DONE]":
            return None
        try:
            obj = json.loads(chunk_data)
        except json.JSONDecodeError:
            return None

        usage = obj.get("usage")
        if usage:
            return ParsedUsage(
                input_tokens=int(
                    usage.get("input_tokens", usage.get("prompt_tokens", 0))
                ),
                output_tokens=int(
                    usage.get("output_tokens", usage.get("completion_tokens", 0))
                ),
            )
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_parser(provider: str) -> BaseParser:
    """Return the appropriate parser for *provider*.

    Args:
        provider: Lowercase provider name (e.g. ``"anthropic"``).

    Returns:
        A :class:`BaseParser` subclass instance.
    """
    mapping: dict[str, BaseParser] = {
        "anthropic": AnthropicParser(),
        "openai": OpenAIParser(),
        "deepseek": OpenAIParser(),   # DeepSeek is OpenAI-compatible
        "ollama": OpenAIParser(),     # Ollama uses OpenAI-compatible format
    }
    return mapping.get(provider, GenericParser())
