# ToolOps 架构总览

> Protocol-driven AI 应用 ops sidecar — 统一应用可观测性 + LLM 成本智能平台

## 架构总览（五层）

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 5：LLM Intelligence（LLM 智能层）                        │
│  CC Log Collector  │  LLM Gateway Proxy (:9010)                 │
│  OpenClaw Observer Plugin（原生 llm_input/llm_output hooks）    │
├────────────────────────────────────────────────────────────────┤
│  Layer 4：Visualization（可视化层）                             │
│  React 19 Dashboard（nginx 生产部署，:3003）                    │
│  10 个页面：Overview / Traces / Metrics / Logs / Chain /        │
│            Infra / Docs + LLM(CC Usage / Gateway / OpenClaw)   │
│  FastAPI 后端（:9003）  /api/overview  /api/traces  /api/logs   │
│  /api/correlate  /api/infra/health  /api/llm/*                 │
├────────────────────────────────────────────────────────────────┤
│  Layer 3：Storage（数据存储层）— ClickHouse 24（统一存储）        │
│  traces / logs / otel_metrics_gauge / otel_metrics_sum         │
│  otel_metrics_histogram / llm_usage / llm_gateway / llm_openclaw│
│  MergeTree + TTL 30天 / 支持 cross-JOIN 关联查询                │
├────────────────────────────────────────────────────────────────┤
│  Layer 2：Collection（数据采集层）                              │
│  OTel Collector (OTLP push)  │  Prometheus (pull)  │  Loki     │
│  :4317 gRPC / :4318 HTTP     │  :9090              │  :3100    │
├────────────────────────────────────────────────────────────────┤
│  Layer 1：Deploy（部署管理层）— Git webhook → rolling deploy     │
│  (coming soon)                                                  │
└────────────────────────────────────────────────────────────────┘
```

## 各层职责

### 第五层：LLM Intelligence（LLM 智能层）

LLM 成本追踪与分析能力，通过三个独立通道采集 LLM 调用数据：

**通道 1 — CC Log Collector（Claude Code 日志采集）**
```
~/.claude/projects/**/*.jsonl（CC 对话日志）
  └─ CC Log Collector（Python 后台进程）
       └─ 解析 usage 字段（input_tokens / output_tokens / model）
            └─ 写入 ClickHouse: llm_usage 表
               (agent_id, session_id, model, input_tokens, output_tokens,
                cost_usd, timestamp)
```
已采集记录：52,000+ 条，覆盖多个 agent 和 session。

**通道 2 — LLM Gateway Proxy（透明反向代理）**
```
客户端请求
  └─ LLM Gateway (:9010)
       ├─ 记录请求开始时间（TTFB 计算起点）
       ├─ 转发至上游 LLM API（OpenAI / Anthropic / 国内厂商）
       ├─ 流式响应透传（SSE / streaming）
       ├─ 捕获响应 usage 字段
       └─ 写入 ClickHouse: llm_gateway 表
          (request_id, model, provider, ttfb_ms, duration_ms,
           input_tokens, output_tokens, cost_usd, status_code)
```
支持厂商：OpenAI、Anthropic、Moonshot、MiniMax、Zhipu、ClipProxy 等。

**通道 3 — OpenClaw Observer Plugin（原生 Agent 钩子）**
```
OpenClaw Agent 框架
  └─ toolops-observer（TypeScript 插件）
       ├─ llm_input hook：捕获请求参数（prompt, model, agent_id）
       ├─ llm_output hook：捕获响应结果（tokens, latency, tool_calls）
       └─ 写入 ClickHouse: llm_openclaw 表
          (agent_id, session_id, model, input_tokens, output_tokens,
           latency_ms, tool_calls_count, cost_usd, timestamp)
```
当前监控：12 个 agent，覆盖完整的 agent-session-call 调用链。

**成本计算逻辑**（`toolops/pricing/`）：
- 维护各模型的 input/output token 单价表（美元/百万 token）
- `calculate_cost(model, input_tokens, output_tokens) → cost_usd`
- 支持按 agent、session、时间段聚合汇总

### 第四层：可视化层（React Dashboard）
展示层，10 个页面分别对应不同可观测性维度。通过 SWR 每 10 秒自动轮询 API，无需手动刷新。暗色主题，针对 AI 应用语义定制视图。

**LLM Dashboard**（第 10 页，3 个 Tab）：
- **CC Usage Tab**：按 agent/session 维度展示 CC 日志采集的 token 消耗与费用趋势
- **Gateway Tab**：LLM Gateway 请求的延迟（TTFB / 总耗时）、token 消耗、按 provider 分组统计
- **OpenClaw Agents Tab**：12 个 agent 的调用频次、工具调用链、费用分布

所有 LLM 页面共享统一查询过滤器：时间范围、agent、session、model。

生产部署：nginx 静态文件服务 + 反向代理 API（`/api/` → toolops-api:9000），端口 3003。

### API 层（FastAPI）
薄封装层，无业务逻辑。接收 Dashboard 请求，转发至 ClickHouse 查询，格式化返回。CORS 白名单仅允许 `localhost:3003` 和 `localhost:5173`。

**完整 API 端点列表：**

| 端点 | 说明 |
|------|------|
| `GET /api/overview` | 总览指标（请求数、延迟、错误率、缓存命中率）|
| `GET /api/traces` | 分布式 Trace 列表，支持过滤 |
| `GET /api/traces/{trace_id}` | 单条 Trace 的所有 Span |
| `GET /api/metrics` | OTel 指标时序数据 |
| `GET /api/logs` | 结构化日志，支持全文搜索 |
| `GET /api/correlate/{trace_id}` | 跨信号关联：spans + logs + metrics |
| `GET /api/infra/health` | 基础设施组件健康检查 |
| `GET /api/llm/usage` | CC 日志采集的 token/费用数据 |
| `GET /api/llm/gateway` | LLM Gateway 请求记录 |
| `GET /api/llm/openclaw` | OpenClaw agent 调用记录 |
| `GET /api/llm/models` | 模型列表（用于过滤器下拉） |
| `GET /api/llm/agents` | Agent 列表（用于过滤器下拉） |
| `GET /api/llm/cost` | 费用汇总（按 agent/session/model 聚合） |

### 数据存储层（ClickHouse）
核心存储，承载五种信号的统一持久化。

| 表名 | 数据来源 | 主要字段 |
|------|----------|----------|
| `traces` | OTel Collector | TraceId, SpanId, SpanName, Duration |
| `logs` | OTel Collector | Timestamp, SeverityText, Body, TraceId |
| `otel_metrics_*` | OTel Collector | MetricName, Value, Timestamp |
| `llm_usage` | CC Log Collector | agent_id, session_id, model, tokens, cost_usd |
| `llm_gateway` | LLM Gateway Proxy | provider, model, ttfb_ms, tokens, cost_usd |
| `llm_openclaw` | OpenClaw Plugin | agent_id, tool_calls_count, latency_ms, cost_usd |

OTel Collector 的 `clickhouse` exporter 自动建表（`create_schema: true`）。TTL 720h（30 天），列式存储对时序聚合查询极为友好。

### 数据采集层（OTel Collector + Prometheus + Loki）
三路采集：
- **Traces / Logs**：OTLP push（gRPC :4317 / HTTP :4318）→ OTel Collector → ClickHouse
- **Metrics**：Prometheus 每 15 秒从 demo-app `/metrics` 拉取
- **容器日志**：Loki 收集 Docker stdout（开发期可选）

### 部署管理层（coming soon）
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

### LLM Intelligence（LLM 成本智能）
```
[CC Usage 通道]
~/.claude/projects/**/*.jsonl
  └─ CC Log Collector → ClickHouse: llm_usage

[Gateway 通道]
客户端 → LLM Gateway (:9010)
            ├─ 透传至 OpenAI / Anthropic / 国内厂商
            └─ ClickHouse: llm_gateway（含 TTFB、token、cost）

[OpenClaw 通道]
OpenClaw Agent
  └─ toolops-observer (TypeScript plugin)
       ├─ llm_input hook
       ├─ llm_output hook
       └─ ClickHouse: llm_openclaw（含 agent_id、tool_calls、latency）
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
| 前端服务 | nginx | 生产静态文件服务 + API 反向代理 |
| 配置 | pydantic-settings | 环境变量 → Pydantic model，类型安全 |
| LLM Gateway | Python (FastAPI) | 透明反向代理，支持 SSE 流式透传 |
| OpenClaw Plugin | TypeScript | 原生 hook 机制，零侵入 agent 代码 |

## 部署拓扑

```
宿主机（8 个容器）
├── :8123  → clickhouse (HTTP API)
├── :9002  → clickhouse (Native TCP，避让 MinIO :9000)
├── :4317  → otel-collector (OTLP gRPC)
├── :4318  → otel-collector (OTLP HTTP)
├── :9090  → prometheus
├── :3100  → loki
├── :8081  → demo-app (避让 MCP :8080)
├── :9003  → toolops-api (FastAPI backend)
├── :9010  → llm-gateway (透明反向代理)
└── :3003  → frontend (nginx，生产部署)
           :5173  → frontend (Vite dev server，开发模式)
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
├── extensions/
│   └── toolops-observer/      # OpenClaw Observer Plugin（TypeScript）
│       ├── src/index.ts       # llm_input / llm_output hooks
│       └── package.json
├── frontend/                  # React Dashboard
│   ├── public/docs/           # 文档 markdown 文件
│   ├── src/pages/             # 10 个页面组件
│   ├── Dockerfile             # 多阶段生产构建
│   └── nginx.conf             # nginx 反向代理配置
├── toolops/                   # 后端 Python 包
│   ├── api/                   # FastAPI 路由层
│   │   └── routes/            # overview, traces, metrics, logs, correlate, infra, llm
│   ├── collector/             # CC 日志采集器
│   ├── gateway/               # LLM 透明反向代理
│   ├── pricing/               # LLM 成本计算逻辑
│   ├── config/                # pydantic-settings 配置
│   └── storage/               # ClickHouse 查询封装
├── tests/                     # 单元测试（38 个，覆盖率 74%）
├── docker-compose.yml         # 全栈编排（8 个容器）
├── Dockerfile                 # toolops-api 镜像
└── pyproject.toml             # Python 包配置
```

---

→ 数据采集层详解，参见 [数据采集层](collector.md)  
→ ClickHouse 存储设计，参见 [数据存储层](storage.md)  
→ API 接口文档，参见 [API 接口](api.md)
