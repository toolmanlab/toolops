"""LLM Gateway Proxy — transparent HTTP reverse proxy with ClickHouse telemetry.

Start with::

    python -m toolops.gateway

or::

    uvicorn toolops.gateway.proxy:app --port 9010
"""

from __future__ import annotations

import os

# Clear system proxy environment variables so httpx connects directly to
# upstream providers.  The gateway itself is a proxy; it must not route
# outbound requests through another (SOCKS/HTTP) proxy.
for _var in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy",
             "HTTPS_PROXY", "https_proxy"):
    os.environ.pop(_var, None)

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from toolops.gateway.config import (
    HEADER_AGENT,
    HEADER_CHANNEL,
    HEADER_SESSION,
    HEADER_SKILL,
    UPSTREAM_URLS,
)
from toolops.gateway.parsers import ParsedUsage, get_parser
from toolops.pricing.models import calculate_cost
from toolops.storage.clickhouse import ClickHouseClient

logger = logging.getLogger(__name__)

app = FastAPI(title="ToolOps LLM Gateway", version="0.1.0")

# Shared async HTTP client (reuse connections)
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Return (or lazily create) the shared async HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),

        )
    return _http_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_api_key(auth_header: str | None) -> str:
    """Return the first 8 characters of the SHA-256 hash of the auth header.

    Args:
        auth_header: Raw ``Authorization`` header value (may be ``None``).

    Returns:
        8-character hex prefix, or empty string if no header present.
    """
    if not auth_header:
        return ""
    digest = hashlib.sha256(auth_header.encode()).hexdigest()
    return digest[:8]


def _build_record(
    *,
    request_id: str,
    method: str,
    path: str,
    upstream_url: str,
    model: str,
    provider: str,
    usage: ParsedUsage,
    latency_ms: float,
    ttfb_ms: float,
    status_code: int,
    request_bytes: int,
    response_bytes: int,
    is_streaming: bool,
    error_message: str,
    agent_name: str,
    session_key: str,
    skill_name: str,
    channel: str,
    api_key_hash: str,
    trace_id: str,
) -> dict[str, Any]:
    """Assemble a ClickHouse insert record for the ``llm_gateway`` table."""
    from datetime import datetime

    cost = calculate_cost(
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_tokens=usage.cache_creation_tokens,
        cache_read_tokens=usage.cache_read_tokens,
    )

    return {
        "timestamp": datetime.now(tz=UTC),
        "request_id": request_id,
        "method": method,
        "path": path,
        "upstream_url": upstream_url,
        "model": model,
        "provider": provider,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_tokens": usage.cache_creation_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": cost,
        "latency_ms": latency_ms,
        "ttfb_ms": ttfb_ms,
        "status_code": status_code,
        "request_bytes": request_bytes,
        "response_bytes": response_bytes,
        "is_streaming": 1 if is_streaming else 0,
        "error_message": error_message,
        "agent_name": agent_name,
        "session_key": session_key,
        "skill_name": skill_name,
        "channel": channel,
        "api_key_hash": api_key_hash,
        "trace_id": trace_id,
    }


async def _write_to_clickhouse(record: dict[str, Any]) -> None:
    """Insert a single gateway record into ClickHouse (fire-and-forget).

    Errors are logged but do not propagate to the caller.
    """
    try:
        ch = ClickHouseClient()
        ch.insert_llm_gateway([record])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write gateway record to ClickHouse: %s", exc)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "llm-gateway"}


# ---------------------------------------------------------------------------
# Proxy route
# ---------------------------------------------------------------------------


@app.api_route("/{provider}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(provider: str, path: str, request: Request) -> Response:
    """Transparent reverse proxy endpoint.

    URL pattern: ``/{provider}/{path}``

    The ``provider`` segment is used to select the upstream base URL and the
    appropriate response parser.  All request headers and body are forwarded
    verbatim to the upstream.

    Args:
        provider: Upstream provider name (``anthropic``, ``openai``, etc.).
        path: Remainder of the URL path to forward.
        request: Incoming FastAPI request.

    Returns:
        The upstream response, forwarded transparently to the client.
    """
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    # -- Resolve upstream URL ------------------------------------------------
    base_url = UPSTREAM_URLS.get(provider)
    if base_url is None:
        return JSONResponse(
            status_code=502,
            content={"error": f"Unknown provider: {provider!r}"},
        )
    upstream_url = f"{base_url}/{path}"

    # -- Read request body ---------------------------------------------------
    body_bytes = await request.body()
    request_bytes = len(body_bytes)

    # -- Extract metadata from request ---------------------------------------
    headers = dict(request.headers)
    auth_header = headers.get("authorization", "")
    api_key_hash = _hash_api_key(auth_header)
    agent_name = headers.get(HEADER_AGENT, "")
    session_key = headers.get(HEADER_SESSION, "")
    skill_name = headers.get(HEADER_SKILL, "")
    channel = headers.get(HEADER_CHANNEL, "")
    trace_id = headers.get("x-trace-id", headers.get("traceparent", ""))

    # -- Parse model from request body ---------------------------------------
    parser = get_parser(provider)
    model = ""
    request_body: dict[str, Any] = {}
    if body_bytes:
        try:
            request_body = json.loads(body_bytes)
            model = parser.parse_model(request_body)
        except (json.JSONDecodeError, Exception):
            pass

    is_streaming = bool(request_body.get("stream", False))

    # -- Build forwarded headers (remove host; keep everything else) ---------
    forward_headers: dict[str, str] = {
        k: v
        for k, v in headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    # -- Construct upstream query string -------------------------------------
    query_string = str(request.url.query)
    full_url = f"{upstream_url}?{query_string}" if query_string else upstream_url

    client = _get_http_client()

    # -- Handle streaming response -------------------------------------------
    if is_streaming:
        return await _handle_streaming(
            client=client,
            request_id=request_id,
            method=request.method,
            full_url=full_url,
            forward_headers=forward_headers,
            body_bytes=body_bytes,
            start_time=start_time,
            request_bytes=request_bytes,
            provider=provider,
            path=f"/{path}",
            upstream_url=upstream_url,
            model=model,
            parser=parser,
            api_key_hash=api_key_hash,
            agent_name=agent_name,
            session_key=session_key,
            skill_name=skill_name,
            channel=channel,
            trace_id=trace_id,
        )

    # -- Handle non-streaming response ---------------------------------------
    return await _handle_non_streaming(
        client=client,
        request_id=request_id,
        method=request.method,
        full_url=full_url,
        forward_headers=forward_headers,
        body_bytes=body_bytes,
        start_time=start_time,
        request_bytes=request_bytes,
        provider=provider,
        path=f"/{path}",
        upstream_url=upstream_url,
        model=model,
        parser=parser,
        api_key_hash=api_key_hash,
        agent_name=agent_name,
        session_key=session_key,
        skill_name=skill_name,
        channel=channel,
        trace_id=trace_id,
    )


# ---------------------------------------------------------------------------
# Non-streaming handler
# ---------------------------------------------------------------------------


async def _handle_non_streaming(
    *,
    client: httpx.AsyncClient,
    request_id: str,
    method: str,
    full_url: str,
    forward_headers: dict[str, str],
    body_bytes: bytes,
    start_time: float,
    request_bytes: int,
    provider: str,
    path: str,
    upstream_url: str,
    model: str,
    parser: Any,
    api_key_hash: str,
    agent_name: str,
    session_key: str,
    skill_name: str,
    channel: str,
    trace_id: str,
) -> Response:
    """Forward a non-streaming request and record usage.

    Args:
        client: Shared async HTTP client.
        request_id: Unique request identifier (UUID).
        method: HTTP method string.
        full_url: Full upstream URL including query string.
        forward_headers: Headers to forward verbatim.
        body_bytes: Raw request body.
        start_time: ``time.perf_counter()`` timestamp at request start.
        request_bytes: Size of request body in bytes.
        provider: Provider name.
        path: Request URL path (used in the telemetry record).
        upstream_url: Upstream base URL for the record.
        model: Model name extracted from request.
        parser: Provider-specific parser instance.
        api_key_hash: Hashed API key.
        agent_name: OpenClaw agent header value.
        session_key: OpenClaw session header value.
        skill_name: OpenClaw skill header value.
        channel: OpenClaw channel header value.
        trace_id: Trace ID header value.

    Returns:
        Response forwarded from upstream.
    """
    error_message = ""
    usage = ParsedUsage()
    status_code = 0
    response_bytes = 0
    response_body_bytes = b""

    try:
        upstream_resp = await client.request(
            method=method,
            url=full_url,
            headers=forward_headers,
            content=body_bytes,
        )
        status_code = upstream_resp.status_code
        response_body_bytes = upstream_resp.content
        response_bytes = len(response_body_bytes)

        # Attempt to parse usage from response body
        if status_code == 200:
            try:
                resp_json = json.loads(response_body_bytes)
                usage = parser.parse_response_usage(resp_json)
                if not model:
                    model = str(resp_json.get("model", ""))
            except (json.JSONDecodeError, Exception) as exc:
                logger.debug("Could not parse response body for usage: %s", exc)

        # Build response headers (exclude hop-by-hop)
        resp_headers: dict[str, str] = {
            k: v
            for k, v in upstream_resp.headers.items()
            if k.lower()
            not in (
                "transfer-encoding",
                "content-encoding",
                "content-length",
            )
        }

    except httpx.RequestError as exc:
        error_message = str(exc)
        status_code = 502
        resp_headers = {}
        logger.warning("Upstream request error for %s: %s", full_url, exc)

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    record = _build_record(
        request_id=request_id,
        method=method,
        path=path,
        upstream_url=upstream_url,
        model=model,
        provider=provider,
        usage=usage,
        latency_ms=latency_ms,
        ttfb_ms=0.0,
        status_code=status_code,
        request_bytes=request_bytes,
        response_bytes=response_bytes,
        is_streaming=False,
        error_message=error_message,
        agent_name=agent_name,
        session_key=session_key,
        skill_name=skill_name,
        channel=channel,
        api_key_hash=api_key_hash,
        trace_id=trace_id,
    )

    # Fire-and-forget ClickHouse write
    asyncio.create_task(_write_to_clickhouse(record))

    if error_message:
        return JSONResponse(status_code=502, content={"error": error_message})

    return Response(
        content=response_body_bytes,
        status_code=status_code,
        headers=resp_headers,
    )


# ---------------------------------------------------------------------------
# Streaming handler
# ---------------------------------------------------------------------------


async def _handle_streaming(
    *,
    client: httpx.AsyncClient,
    request_id: str,
    method: str,
    full_url: str,
    forward_headers: dict[str, str],
    body_bytes: bytes,
    start_time: float,
    request_bytes: int,
    provider: str,
    path: str,
    upstream_url: str,
    model: str,
    parser: Any,
    api_key_hash: str,
    agent_name: str,
    session_key: str,
    skill_name: str,
    channel: str,
    trace_id: str,
) -> StreamingResponse:
    """Forward a streaming (SSE) request, record TTFB and token usage.

    Chunks are forwarded to the client in real time.  Usage is accumulated
    across all chunks and written to ClickHouse after the stream ends.

    Args:
        client: Shared async HTTP client.
        request_id: Unique request identifier.
        method: HTTP method string.
        full_url: Full upstream URL including query string.
        forward_headers: Headers to forward verbatim.
        body_bytes: Raw request body.
        start_time: ``time.perf_counter()`` timestamp at request start.
        request_bytes: Size of request body in bytes.
        provider: Provider name.
        path: Request URL path (used in the telemetry record).
        upstream_url: Upstream base URL.
        model: Model name extracted from request.
        parser: Provider-specific parser instance.
        api_key_hash: Hashed API key.
        agent_name: OpenClaw agent header value.
        session_key: OpenClaw session header value.
        skill_name: OpenClaw skill header value.
        channel: OpenClaw channel header value.
        trace_id: Trace ID header value.

    Returns:
        :class:`StreamingResponse` that relays upstream chunks to the client.
    """
    # We need to capture state across the generator, so use a mutable container
    state: dict[str, Any] = {
        "ttfb_ms": 0.0,
        "first_content": False,
        "status_code": 0,
        "response_bytes": 0,
        "error_message": "",
        # Accumulated usage (merge chunks)
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }

    async def _stream_generator() -> AsyncIterator[bytes]:
        """Yield chunks from upstream and accumulate usage metadata."""
        try:
            async with client.stream(
                method=method,
                url=full_url,
                headers=forward_headers,
                content=body_bytes,
            ) as upstream_resp:
                state["status_code"] = upstream_resp.status_code

                async for raw_chunk in upstream_resp.aiter_raw():
                    if not raw_chunk:
                        continue

                    # Record TTFB on first content chunk
                    if not state["first_content"]:
                        state["first_content"] = True
                        state["ttfb_ms"] = (
                            time.perf_counter() - start_time
                        ) * 1000.0

                    state["response_bytes"] += len(raw_chunk)

                    # Parse SSE lines for usage extraction
                    for line in raw_chunk.decode("utf-8", errors="replace").splitlines():
                        if line.startswith("data:"):
                            data_payload = line[5:].strip()
                            chunk_usage = parser.parse_stream_chunk_usage(
                                data_payload
                            )
                            if chunk_usage is not None:
                                # Merge: accumulate non-zero values
                                if chunk_usage.input_tokens:
                                    state["input_tokens"] = chunk_usage.input_tokens
                                if chunk_usage.output_tokens:
                                    state["output_tokens"] = chunk_usage.output_tokens
                                if chunk_usage.cache_creation_tokens:
                                    state["cache_creation_tokens"] = (
                                        chunk_usage.cache_creation_tokens
                                    )
                                if chunk_usage.cache_read_tokens:
                                    state["cache_read_tokens"] = (
                                        chunk_usage.cache_read_tokens
                                    )

                    yield raw_chunk

        except httpx.RequestError as exc:
            state["error_message"] = str(exc)
            state["status_code"] = 502
            logger.warning("Streaming upstream error for %s: %s", full_url, exc)
            error_body = json.dumps({"error": str(exc)}).encode()
            yield error_body

        finally:
            # Write telemetry after stream completes
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            usage = ParsedUsage(
                input_tokens=state["input_tokens"],
                output_tokens=state["output_tokens"],
                cache_creation_tokens=state["cache_creation_tokens"],
                cache_read_tokens=state["cache_read_tokens"],
            )
            record = _build_record(
                request_id=request_id,
                method=method,
                path=path,
                upstream_url=upstream_url,
                model=model,
                provider=provider,
                usage=usage,
                latency_ms=latency_ms,
                ttfb_ms=state["ttfb_ms"],
                status_code=state["status_code"] or 200,
                request_bytes=request_bytes,
                response_bytes=state["response_bytes"],
                is_streaming=True,
                error_message=state["error_message"],
                agent_name=agent_name,
                session_key=session_key,
                skill_name=skill_name,
                channel=channel,
                api_key_hash=api_key_hash,
                trace_id=trace_id,
            )
            asyncio.create_task(_write_to_clickhouse(record))

    return StreamingResponse(
        _stream_generator(),
        media_type="text/event-stream",
    )
