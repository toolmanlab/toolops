# toolops.yaml Specification (v1)

## Overview

`toolops.yaml` is the application topology descriptor for ToolOps. It declares what services your app consists of, what role each plays, and how they relate to each other.

ToolOps reads this file to:
1. **Tailor dashboards** — show relevant metrics per role (token cost for LLM providers, hit ratio for caches, query latency for vector stores)
2. **Auto-configure health checks** — know which port/path to probe for each service
3. **Build dependency graphs** — visualize service relationships
4. **Generate alerts** — role-aware thresholds (e.g., LLM rate limit > 5% → alert)

## Schema

### Top Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | yes | Schema version. Currently `"1"`. |
| `app` | object | yes | Application metadata. |
| `services` | map\<string, Service\> | yes | Service definitions. Key = service name (must match Docker Compose service name or OTel `service.name`). |

### `app`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Application name. |
| `description` | string | no | Human-readable description. |

### `Service`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role` | string | yes | Service role. See [Built-in Roles](#built-in-roles). |
| `port` | integer | no | Primary port. |
| `ports` | map\<string, integer\> | no | Named ports (e.g., `grpc: 4317`, `http: 4318`). |
| `healthcheck` | string | no | Health check path (relative to `port`). |
| `metrics` | Metrics | no | Metrics endpoint config. |
| `ai` | AIPipeline | no | AI pipeline declaration (for `ai-app` role). |
| `storage` | Storage | no | Storage details (for `*-store` roles). |
| `receivers` | list\<string\> | no | Telemetry receivers (for `collector` role). |
| `exporters` | list\<string\> | no | Telemetry exporters (for `collector` role). |
| `scrape_targets` | list\<string\> | no | Service names to scrape (for `metrics-scraper` role). |
| `depends_on` | list\<string\> | no | Service dependencies (references other service keys). |
| `labels` | map\<string, string\> | no | Custom key-value labels. |

### `Metrics`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | yes | Metrics endpoint path (e.g., `/metrics`). |
| `format` | string | yes | Format: `prometheus` or `otlp`. |

### `AIPipeline`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pipeline` | string | yes | Pipeline type: `rag`, `agent`, `chain`, `chat`. |
| `stages` | list\<string\> | no | Pipeline stage names (e.g., `embedding`, `vector_search`, `llm_generate`). Stages correspond to OTel span names. |
| `model` | string | no | Default model name (for cost tracking). |

### `Storage`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `engine` | string | yes | Storage engine: `clickhouse`, `postgresql`, `milvus`, `redis`, `neo4j`, etc. |
| `tables` | list\<string\> | no | Key tables/collections to monitor. |

## Built-in Roles

| Role | Dashboard Focus | Key Metrics |
|------|----------------|-------------|
| `api-gateway` | Request rate, latency, errors | p50/p95/p99 latency, error rate, throughput |
| `ai-app` | Pipeline stages, token usage | Stage duration breakdown, token count, cache hit ratio |
| `vector-store` | Query performance, recall | Query latency, result count, index size |
| `metadata-store` | Query performance, storage | Query latency, row count, disk usage |
| `cache` | Hit/miss ratio | Hit rate, miss rate, eviction rate, memory usage |
| `llm-provider` | Cost, rate limits | Token cost, rate limit errors, latency per model |
| `collector` | Pipeline throughput | Spans/s, logs/s, dropped events, queue depth |
| `metrics-scraper` | Scrape health | Scrape duration, targets up/down, sample count |
| `log-aggregator` | Ingestion throughput | Logs/s, storage size, query latency |
| `graph-store` | Query performance | Query latency, node/edge count, traversal depth |
| `custom` | User-defined | Based on labels and OTel attributes |

## Service Name Resolution

Service names in `toolops.yaml` are matched to telemetry data via:

1. **OTel `service.name` resource attribute** — Primary match
2. **Docker Compose service name** — Fallback for health checks and infra page
3. **Prometheus `job` label** — For scraped metrics

If a service name doesn't match any telemetry source, ToolOps shows it as "No Data" on the dashboard.

## Dependency Graph

`depends_on` fields are used to:
- Render a topology graph on the Overview page
- Order health checks (check dependencies first)
- Correlate cascading failures (if A depends on B and B is down, flag A's errors as "dependency failure")

## Validation Rules

1. `version` must be `"1"`
2. Every `depends_on` reference must exist as a service key
3. `role` must be a built-in role or `custom`
4. `port` and `ports` are mutually exclusive (use one or the other)
5. `ai` section is only valid for `ai-app` role
6. `scrape_targets` references must exist as service keys
7. Service keys must be valid DNS labels (lowercase, alphanumeric, hyphens)

## Example: ToolRef (RAG Application)

```yaml
version: "1"

app:
  name: toolref
  description: "RAG engine for professional domain knowledge"

services:
  toolref-backend:
    role: api-gateway
    port: 8000
    healthcheck: /health
    metrics:
      path: /metrics
      format: prometheus
    depends_on:
      - milvus
      - postgres
      - redis

  toolref-mcp-server:
    role: ai-app
    port: 8080
    ai:
      pipeline: rag
      stages:
        - query_parse
        - embedding
        - hybrid_search
        - reranking
        - llm_generate
      model: gpt-4o
    depends_on:
      - toolref-backend

  milvus:
    role: vector-store
    port: 19530
    storage:
      engine: milvus

  postgres:
    role: metadata-store
    port: 5432
    storage:
      engine: postgresql
      tables:
        - documents
        - chunks
        - namespaces

  redis:
    role: cache
    port: 6379
```

## File Location

ToolOps looks for `toolops.yaml` in (order of precedence):
1. Path specified by `TOOLOPS_CONFIG` environment variable
2. `./toolops.yaml` (project root)
3. `./config/toolops.yaml`
