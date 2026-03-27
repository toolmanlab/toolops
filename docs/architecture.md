# ToolOps Architecture

> **ToolOps** — AI app infrastructure, plug and play.

## Overview

ToolOps is a **composable infrastructure suite** for AI applications.
It is not a standalone product—it is a reusable foundation that projects like
ToolRef (P1) and ToolArch (P3) build on top of.

Core philosophy: **pick the best wheels, don't reinvent them.**
Each infrastructure concern (vector storage, caching, observability) is
abstracted behind a clean Python ABC, and swappable via a single config line.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Downstream projects  (ToolRef · ToolArch · …)              │
└──────────────────────────┬──────────────────────────────────┘
                           │ import
┌──────────────────────────▼──────────────────────────────────┐
│                        ToolOps                              │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Plugin System                                         │ │
│  │                                                        │ │
│  │  VectorStorePlugin   CachePlugin   MonitorPlugin       │ │
│  │       ABC                ABC            ABC            │ │
│  │        │                  │              │             │ │
│  │   ┌────┴────┐        ┌────┴──┐     ┌────┴────┐        │ │
│  │   │ Chroma  │        │Memory │     │  Null   │        │ │
│  │   │ Milvus  │        │ Redis │     │ Phoenix │        │ │
│  │   │ Qdrant  │        └───────┘     └─────────┘        │ │
│  │   └─────────┘                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────────┐  │
│  │   CLI        │  │   Config    │  │     Utils         │  │
│  │  (Typer)     │  │ (Pydantic   │  │  docker.py        │  │
│  │  init        │  │  Settings)  │  │  (Jinja2 codegen) │  │
│  │  env         │  │  schema.py  │  └───────────────────┘  │
│  │  status      │  │  loader.py  │                         │
│  └──────────────┘  └─────────────┘                         │
└─────────────────────────────────────────────────────────────┘
         │                 │                   │
    Vector DB           Cache             Observability
  ┌──────────┐       ┌──────────┐        ┌──────────────┐
  │  Chroma  │       │  Redis   │        │Arize Phoenix │
  │  Milvus  │       │ (in-mem) │        │  (OTEL/OTLP) │
  │  Qdrant  │       └──────────┘        └──────────────┘
  └──────────┘
```

---

## Directory Layout

```
toolops/
├── toolops/               # Main package
│   ├── cli/               # Typer CLI commands
│   │   ├── main.py        # Entry point: toolops
│   │   ├── init.py        # toolops init
│   │   ├── env.py         # toolops env list|switch
│   │   └── status.py      # toolops status
│   ├── config/            # Configuration management
│   │   ├── schema.py      # Pydantic Settings v2 schema
│   │   ├── loader.py      # YAML + env var merge logic
│   │   └── templates/     # Jinja2 code-gen templates
│   ├── plugins/           # Pluggable adapters
│   │   ├── vectorstore/   # Chroma / Milvus / Qdrant
│   │   ├── cache/         # Memory / Redis
│   │   └── monitor/       # Null / Phoenix
│   └── utils/
│       └── docker.py      # Docker Compose + config file generation
└── tests/
    ├── test_config.py
    └── test_plugins.py
```

---

## Plugin System

### Implementing a new plugin

1. Subclass the relevant ABC (`VectorStorePlugin`, `CachePlugin`, or `MonitorPlugin`).
2. Implement all `@abstractmethod` methods.
3. Register the backend name in `ToolOpsConfig` (add it to the `Literal` union).
4. Wire it into the CLI `status` command's probe logic.

Example — adding a new cache backend:

```python
from toolops.plugins.cache.base import CachePlugin

class DragonflyCache(CachePlugin):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int | None = None) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
```

### Plugin interfaces at a glance

| Interface | Key methods |
|-----------|-------------|
| `VectorStorePlugin` | `connect`, `create_collection`, `insert`, `search`, `delete`, `delete_collection` |
| `CachePlugin` | `get`, `set`, `delete`, `exists`, `clear` |
| `MonitorPlugin` | `trace`, `log_metric`, `flush` |

---

## Configuration Resolution Order

```
1. Pydantic field defaults (lowest priority)
2. toolops.yaml  (auto-discovered by walking up the directory tree)
3. .env file
4. Shell environment variables  (highest priority)
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `toolops init` | Interactive setup wizard — generates `toolops.yaml` + `docker-compose.yaml` |
| `toolops env list` | Show all environments with active one highlighted |
| `toolops env switch <env>` | Change the active environment in `toolops.yaml` |
| `toolops status` | TCP health-check for all configured backends |

---

## Supported Backends

### Vector Stores

| Backend | Use Case | Extra dep |
|---------|----------|-----------|
| Chroma  | Local dev, lightweight | `pip install toolops[chroma]` |
| Milvus  | High-scale production | `pip install toolops[milvus]` |
| Qdrant  | Cloud-native, filtering | `pip install toolops[qdrant]` |

### Cache

| Backend | Use Case | Extra dep |
|---------|----------|-----------|
| memory  | Tests, single-process dev | (built-in) |
| Redis   | Production, multi-process | `pip install toolops[redis]` |

### Monitor

| Backend | Use Case | Extra dep |
|---------|----------|-----------|
| null    | Disabled (default) | (built-in) |
| Phoenix | LLM tracing & eval | `pip install toolops[phoenix]` |

---

## Design Decisions

### Why ABCs over Protocols?
ABCs enforce implementation at class definition time (not at call time) and
provide a clear `isinstance` check that downstream projects can rely on.

### Why Pydantic Settings v2?
Field-level validation, type coercion, environment variable binding, and
nested model merging are all handled declaratively with minimal boilerplate.

### Why Jinja2 for code generation?
Config templates need conditional blocks (e.g., only emit `redis:` section
when cache=redis). Jinja2's `{% if %}` blocks make this readable.

### Why synchronous plugin interfaces?
Most vector DB and cache clients provide both sync and async APIs.
Keeping the base interface synchronous avoids forcing an event loop on callers;
async consumers can wrap calls with `asyncio.to_thread`.
