# ToolOps

> AI app infrastructure, plug and play.

Protocol-driven observability sidecar for AI applications. Unified traces, metrics, and logs — all correlated by `trace_id` in a single ClickHouse store.

## Why ToolOps?

Existing AI observability tools (LangFuse, Arize Phoenix, LangSmith) are SaaS-first or tightly coupled to specific frameworks. Generic PaaS platforms (Coolify, Dokploy) don't understand AI application topology.

**ToolOps fills the gap:** a self-hosted, protocol-driven platform that understands your AI stack — from embedding latency to LLM token spend to cache hit rates — with cross-signal correlation out of the box.

### Key Differentiators

- **Unified Storage** — ClickHouse stores traces, logs, and metrics in the same database. Cross-JOIN them by `trace_id` to answer "why was this query slow?"
- **AI-Native Dashboard** — Not another Grafana clone. Purpose-built views for RAG pipeline steps, LLM token economics, and retrieval quality.
- **Protocol-Driven** — `toolops.yaml` declares your app topology (api-gateway, vector-store, llm-provider). ToolOps understands what each service does.
- **~20 Lines to Integrate** — Add OTel SDK, set one env var, write a `toolops.yaml`. That's it.

## Architecture

```
┌───────────────────────────────────────────────────┐
│  Visualization — React Dashboard                   │
│  Overview │ Traces │ Metrics │ Logs │ Chain │ Infra │
├───────────────────────────────────────────────────┤
│  Storage — ClickHouse (unified)                    │
│  traces │ logs │ otel_metrics_*                    │
│  MergeTree + TTL 30d │ cross-JOIN correlation      │
├───────────────────────────────────────────────────┤
│  Collection                                        │
│  OTel Collector (push) │ Prometheus (pull) │ Loki   │
│  gRPC :4317 / HTTP :4318 │ :9090          │ :3100  │
├───────────────────────────────────────────────────┤
│  Deployment — Git webhook → build → rolling deploy │
│  (coming soon)                                     │
└───────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- Node.js 18+ (for frontend dev)
- Python 3.11+ (for backend dev)

### 1. Start Infrastructure

```bash
git clone https://github.com/toolmanlab/toolops.git
cd toolops
docker compose up -d
```

This starts 6 containers:

| Service | Port | Description |
|---------|------|-------------|
| ClickHouse | 8123 | Unified telemetry storage |
| OTel Collector | 4317, 4318 | Receives OTLP traces/logs/metrics |
| Prometheus | 9090 | Scrapes /metrics endpoints |
| Loki | 3100 | Docker log collection |
| demo-app | 8081 | Simulated RAG application |
| toolops-api | 9003 | Dashboard backend (FastAPI) |

### 2. Start Frontend (dev mode)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 3. Verify Data Flow

The demo-app generates background traffic (~1 req/s) simulating a RAG pipeline. Within seconds you should see:

- **Overview**: Request count, avg latency, error rate
- **Traces**: Individual spans (embedding → vector_search → llm_generate)
- **Metrics**: Latency and throughput charts
- **Logs**: Application logs with severity filtering
- **Infra**: All 6 services green

## Dashboard Pages

### Overview
Top-level KPIs: total requests, average latency, error rate, cache hit rate. Plus a quick-glance table of recent traces.

### Traces
Full span list ordered by time. Each RAG query produces spans for `embedding`, `vector_search`, and `llm_generate` — immediately visible which step is the bottleneck.

### Metrics
Time-series charts (recharts) showing avg latency per minute and request throughput. Data aggregated from ClickHouse traces.

### Logs
Filterable by severity (INFO/WARN/ERROR) with full-text body search. Logs flow through OTel Logs SDK → Collector → ClickHouse.

### Chain (Correlation)
Enter a `trace_id` → see the complete call chain (all spans + associated logs + metrics in the same time window). The core debugging workflow: user reports slow query → grab trace_id → pinpoint the bottleneck.

### Infra
Health status cards for all infrastructure components. Backend proxy checks (no browser CORS issues). Auto-refreshes every 15 seconds.

## Project Structure

```
toolops/
├── config/                     # Infrastructure configs
│   ├── otel-collector.yaml     # OTel Collector pipelines
│   ├── prometheus.yml          # Scrape targets
│   └── loki-config.yaml        # Loki storage config
├── demo-app/                   # Simulated RAG application
│   ├── main.py                 # FastAPI + background traffic gen
│   ├── otel_setup.py           # OTel SDK init (traces + logs)
│   └── scenarios.py            # Fault scenarios (normal/degraded/spike)
├── frontend/                   # React Dashboard (Vite + TS)
│   └── src/pages/              # 6 page components
├── toolops/                    # Backend Python package
│   ├── api/routes/             # FastAPI routes
│   ├── collector/              # Collector client wrappers
│   ├── config/                 # Settings management
│   └── storage/clickhouse.py   # Query helpers
├── tests/                      # Unit / Integration / E2E
├── docker-compose.yml          # Full stack orchestration
└── pyproject.toml              # Python package config
```

## Tech Stack

**Backend:** Python 3.13, FastAPI, clickhouse-connect, OpenTelemetry SDK

**Frontend:** React 18, TypeScript, Vite, recharts, TailwindCSS

**Infrastructure:** ClickHouse, OpenTelemetry Collector (contrib), Prometheus, Loki

**Dev Tools:** pytest, mypy, ruff

## Design Decisions

See [docs/architecture.md](docs/architecture.md) for detailed rationale on:
- Why ClickHouse as unified storage (not separate stores per signal)
- Why a custom dashboard (not Grafana)
- Why protocol-driven topology (`toolops.yaml`)

## Roadmap

- [x] OTel traces → ClickHouse → Dashboard
- [x] Prometheus metrics → Dashboard charts
- [x] OTel logs → ClickHouse → Dashboard
- [x] Cross-signal correlation (Chain page)
- [x] Infrastructure health monitoring
- [ ] `toolops.yaml` topology spec + auto-discovery
- [ ] Deployment management (Git webhook → rolling deploy)
- [ ] LLM-specific metrics (token cost, latency percentiles by model)
- [ ] Alert rules and notification channels
- [ ] Production Docker images + Helm chart

## License

MIT

---

*Built by [toolmanlab](https://github.com/toolmanlab) — the tool shop for AI builders.*
