# ToolOps 架构总览

> Protocol-driven 的 AI 应用可观测性 sidecar 平台

## 四层架构

```
┌────────────────────────────────────────────────────────────┐
│  可视化层 — React 19 Dashboard                              │
│  Overview / Traces / Metrics / Logs / Chain / Infra / Docs  │
│  技术栈：Vite 8 + TypeScript + Tailwind 4 + recharts + SWR  │
├────────────────────────────────────────────────────────────┤
│  API 层 — FastAPI (Python 3.13)                             │
│  /api/overview  /api/traces  /api/metrics  /api/logs        │
│  /api/correlate/{trace_id}   /api/infra/health              │
├────────────────────────────────────────────────────────────┤
│  数据存储层 — ClickHouse 24（统一存储）                       │
│  traces / logs / otel_metrics_gauge / otel_metrics_sum      │
│  otel_metrics_histogram                                     │
│  MergeTree + TTL 30天 / 支持 cross-JOIN 关联查询             │
├────────────────────────────────────────────────────────────┤
│  数据采集层                                                  │
│  OTel Collector (OTLP push)  │  Prometheus (pull)  │  Loki  │
│  :4317 gRPC / :4318 HTTP     │  :9090              │  :3100  │
├────────────────────────────────────────────────────────────┤
│  部署管理层 — Git webhook → build → rolling deploy（待实现）  │
└────────────────────────────────────────────────────────────┘
```

## 各层职责

### 可视化层（React Dashboard）
展示层，7 个页面分别对应不同可观测性维度。通过 SWR 每 10 秒自动轮询 API，无需手动刷新。暗色主题，针对 AI 应用语义定制视图（如 RAG pipeline 分步延迟、LLM token 消耗）。

### API 层（FastAPI）
薄封装层，无业务逻辑。接收 Dashboard 请求，转发至 ClickHouse 查询，格式化返回。CORS 白名单仅允许 `localhost:3001` 和 `localhost:5173`。

### 数据存储层（ClickHouse）
核心存储，承载三种信号的统一持久化。OTel Collector 的 `clickhouse` exporter 自动建表（`create_schema: true`）。TTL 720h（30 天），列式存储对时序聚合查询极为友好。

### 数据采集层（OTel Collector + Prometheus + Loki）
三路采集：
- **Traces / Logs**：OTLP push（gRPC :4317 / HTTP :4318）→ OTel Collector → ClickHouse
- **Metrics**：Prometheus 每 15 秒从 demo-app `/metrics` 拉取
- **容器日志**：Loki 收集 Docker stdout（开发期可选）

### 部署管理层（规划中）
目标：Git webhook 触发 → Docker build → Rolling deploy → 健康检查。这是与 Coolify/Dokploy 的差异点：理解 AI 应用拓扑（`toolops.yaml` 声明服务角色）。

## 数据流全景

### Traces（分布式追踪）
```
demo-app
  └─ OTel Python SDK
       └─ tracer.start_as_current_span("rag_pipeline")
            ├─ span: embedding
            ├─ span: vector_search
            └─ span: llm_generate
                  │
                  ▼  OTLP gRPC :4317
            OTel Collector
                  │  batch processor (5s / 1000条)
                  ▼
            ClickHouse: traces 表
            (Duration 单位：纳秒，查询时 /1000000 转毫秒)
```

### Metrics（指标）
```
demo-app (prometheus_client)
  ├─ query_total{status}            Counter
  ├─ query_latency_seconds          Histogram
  ├─ retrieval_latency_seconds      Histogram
  ├─ llm_token_input_total          Counter
  ├─ llm_token_output_total         Counter
  └─ cache_hit_ratio                Gauge
        │
        ▼  HTTP pull :8080/metrics (每15s)
  Prometheus :9090
        │
        ▼  (Dashboard Metrics 页直接从 ClickHouse traces 聚合)
  ClickHouse: otel_metrics_gauge / otel_metrics_sum / otel_metrics_histogram
```

### Logs（日志）
```
demo-app (Python logging)
  ├─ OTel LoggingHandler → OTLP gRPC → OTel Collector → ClickHouse: logs 表
  │   └─ 在 span context 内发出时，自动注入 TraceId / SpanId
  └─ stdout JSON → Docker json-file → Loki :3100（可选）
```

## 技术选型表

| 组件 | 选型 | 理由 |
|------|------|------|
| 存储 | ClickHouse 24 | 列式时序、MergeTree、cross-JOIN、OTel 原生 exporter |
| 采集 | OTel Collector Contrib | 行业标准、协议无关、三信号统一入口 |
| 指标拉取 | Prometheus | 与 prometheus_client 无缝对接 |
| 日志收集 | Loki 3.0 | 轻量、与 Docker 日志驱动集成简单 |
| API | FastAPI + Python 3.13 | 异步、类型安全、OpenAPI 自动文档 |
| 前端 | React 19 + Vite 8 + SWR | 现代技术栈、SWR 自动轮询 |
| 配置 | pydantic-settings | 环境变量 → Pydantic model，类型安全 |

## 部署拓扑

```
宿主机
├── :8123  → clickhouse (HTTP API)
├── :9002  → clickhouse (Native TCP，避让 MinIO :9000)
├── :4317  → otel-collector (OTLP gRPC)
├── :4318  → otel-collector (OTLP HTTP)
├── :9090  → prometheus
├── :3100  → loki
├── :8081  → demo-app (避让 MCP :8080)
├── :9003  → toolops-api (避让 MinIO Console :9001)
└── :5173  → frontend (Vite dev server)
```

> 端口冲突说明：本机已有 :8080 (MCP)、:9000/:9001 (MinIO) 占用，ToolOps 做了映射避让。

## 目录结构

```
toolops/
├── config/                    # 基础设施配置
│   ├── otel-collector.yaml    # OTel Collector pipeline
│   ├── prometheus.yml         # Prometheus scrape targets
│   └── loki-config.yaml       # Loki 存储配置
├── demo-app/                  # 模拟 RAG 应用
│   ├── main.py                # FastAPI + 后台流量生成器
│   ├── otel_setup.py          # OTel SDK 初始化
│   └── scenarios.py           # 7 种故障场景参数
├── frontend/                  # React Dashboard
│   ├── public/docs/           # 文档 markdown 文件
│   └── src/pages/             # 7 个页面组件
├── toolops/                   # 后端 Python 包
│   ├── api/                   # FastAPI 路由层
│   ├── collector/             # 采集器客户端封装
│   ├── config/                # pydantic-settings 配置
│   └── storage/               # ClickHouse 查询封装
├── tests/                     # 单元 / 集成 / e2e 测试
├── docker-compose.yml         # 全栈编排（6 服务）
├── Dockerfile                 # toolops-api 镜像
└── pyproject.toml             # Python 包配置
```

---

→ 数据采集层详解，参见 [数据采集层](collector.md)  
→ ClickHouse 存储设计，参见 [数据存储层](storage.md)  
→ API 接口文档，参见 [API 接口](api.md)
