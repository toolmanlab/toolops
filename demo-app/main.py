"""Demo RAG application simulating AI workload with full observability."""

from __future__ import annotations

import json
import logging
import os
import random
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
import uvicorn
from fastapi import FastAPI, Query
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

from otel_setup import init_telemetry
from scenarios import ScenarioParams, get_scenario

# -- Logging setup (structured JSON to stdout) --------------------------------
logger = logging.getLogger("demo-app")
logger.setLevel(logging.INFO)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "demo-app",
        }
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id  # type: ignore[attr-defined]
        return json.dumps(log_data)


# Stdout handler (keep for Docker logs)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(JsonFormatter())
logger.addHandler(stdout_handler)

# -- Prometheus metrics --------------------------------------------------------
QUERY_TOTAL = Counter("query_total", "Total queries", ["status"])
QUERY_LATENCY = Histogram(
    "query_latency_seconds",
    "Query latency",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
RETRIEVAL_LATENCY = Histogram(
    "retrieval_latency_seconds",
    "Retrieval step latency",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
LLM_INPUT_TOKENS = Counter("llm_token_input_total", "LLM input tokens")
LLM_OUTPUT_TOKENS = Counter("llm_token_output_total", "LLM output tokens")
CACHE_HIT_RATIO = Gauge("cache_hit_ratio", "Cache hit ratio (rolling)")

# Rolling cache stats
_cache_hits = 0
_cache_total = 0

# -- OTel tracer + logs --------------------------------------------------------
tracer, otel_log_handler = init_telemetry()
logger.addHandler(otel_log_handler)

# -- Scenario ------------------------------------------------------------------
SCENARIO_NAME = os.getenv("DEMO_SCENARIO", "normal")


# -- Simulated pipeline steps --------------------------------------------------

def _simulate_step(name: str, latency_range: tuple[float, float]) -> float:
    """Simulate a pipeline step with random latency. Returns elapsed time."""
    latency = random.uniform(*latency_range)
    time.sleep(latency)
    return latency


def _run_rag_pipeline(query: str, params: ScenarioParams) -> dict[str, Any]:
    """Execute the simulated RAG pipeline with full tracing."""
    global _cache_hits, _cache_total  # noqa: PLW0603

    # root_span wraps the entire pipeline so that logger.handle() in the
    # finally block is called while the span context is still active —
    # the OTel LoggingHandler can then inject TraceId / SpanId into ClickHouse.
    with tracer.start_as_current_span("rag_pipeline") as root_span:
        trace_id = uuid.uuid4().hex[:32]
        root_span.set_attribute("trace_id", trace_id)
        start = time.time()
        status = "success"
        result_text = f"Answer to: {query}"

        try:
            # 1. Embedding
            with tracer.start_as_current_span("embedding") as span:
                span.set_attribute("trace_id", trace_id)
                _simulate_step("embedding", params.embed_latency_range)

            # 2. Cache check
            _cache_total += 1
            cache_hit = random.random() < params.cache_hit_rate
            if cache_hit:
                _cache_hits += 1
                CACHE_HIT_RATIO.set(_cache_hits / _cache_total if _cache_total else 0)
                return {"query": query, "answer": result_text, "trace_id": trace_id, "cached": True}
            CACHE_HIT_RATIO.set(_cache_hits / _cache_total if _cache_total else 0)

            # 3. Vector search
            with tracer.start_as_current_span("vector_search") as span:
                span.set_attribute("trace_id", trace_id)
                retrieval_time = _simulate_step("vector_search", params.retrieval_latency_range)
                RETRIEVAL_LATENCY.observe(retrieval_time)
                if random.random() < params.retrieval_timeout_rate:
                    raise TimeoutError("Vector search timed out")

            # 4. LLM generation
            with tracer.start_as_current_span("llm_generate") as span:
                span.set_attribute("trace_id", trace_id)
                span.set_attribute("llm.model", params.llm_model)
                if random.random() < params.llm_rate_limit_rate:
                    status = "error"
                    raise RuntimeError("LLM rate limited (429)")
                _simulate_step("llm_generate", params.llm_latency_range)
                input_tokens = random.randint(*params.llm_input_tokens_range)
                output_tokens = random.randint(*params.llm_output_tokens_range)
                LLM_INPUT_TOKENS.inc(input_tokens)
                LLM_OUTPUT_TOKENS.inc(output_tokens)
                span.set_attribute("llm.input_tokens", input_tokens)
                span.set_attribute("llm.output_tokens", output_tokens)

        except Exception as e:
            status = "error"
            result_text = str(e)
        finally:
            # root_span is still the current span here — OTel LoggingHandler
            # will capture TraceId and SpanId from the active context.
            elapsed = time.time() - start
            QUERY_TOTAL.labels(status=status).inc()
            QUERY_LATENCY.observe(elapsed)
            log_record = logger.makeRecord(
                "demo-app", logging.INFO, "", 0, f"query={query} status={status} latency={elapsed:.3f}s", (), None
            )
            log_record.trace_id = trace_id  # type: ignore[attr-defined]
            logger.handle(log_record)

        return {"query": query, "answer": result_text, "trace_id": trace_id, "cached": False}


# -- Background traffic generator ---------------------------------------------

def _traffic_generator() -> None:
    """Background thread that generates 1-5 requests per second."""
    sample_queries = [
        "What is RAG?",
        "How does vector search work?",
        "Explain transformer attention",
        "Best practices for prompt engineering",
        "How to reduce LLM hallucination?",
        "What is RLHF?",
        "Compare GPT-4 vs Claude",
        "How to fine-tune a model?",
    ]
    port = int(os.getenv("PORT", "8080"))
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(3)  # Wait for server startup
    while True:
        try:
            q = random.choice(sample_queries)
            httpx.get(f"{base_url}/query", params={"q": q}, timeout=30)
        except Exception:
            pass
        time.sleep(random.uniform(0.2, 1.0))


# -- FastAPI app ---------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    t = threading.Thread(target=_traffic_generator, daemon=True)
    t.start()
    yield


app = FastAPI(title="Demo RAG App", lifespan=lifespan)


@app.get("/query")
def query_endpoint(q: str = Query("hello", description="Query string")) -> dict[str, Any]:
    """Simulate a RAG query."""
    params = get_scenario(SCENARIO_NAME)
    return _run_rag_pipeline(q, params)


@app.get("/metrics")
def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "scenario": SCENARIO_NAME}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
