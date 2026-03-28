# API 接口

> FastAPI 后端：ClickHouse 查询的统一入口

## 概述

ToolOps API 是 Dashboard 与 ClickHouse 之间的薄封装层，无业务逻辑，仅做参数解析 → 查询转发 → 结果序列化。基于 FastAPI 0.115+，自动生成 OpenAPI 文档（`http://localhost:9003/docs`）。

## 服务信息

| 属性 | 值 |
|------|-----|
| 框架 | FastAPI 0.115 + Python 3.13 |
| 容器内端口 | 9000 |
| 宿主机端口 | 9003（避让 MinIO Console :9001）|
| OpenAPI 文档 | `http://localhost:9003/docs` |
| 数据源 | ClickHouse HTTP :8123 |

## CORS 配置

Dashboard（开发模式 :5173，生产模式 :3001）需要跨域访问 API。白名单仅允许本地开发地址：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

生产部署时需将前端地址加入 `allow_origins`，或通过 Nginx 反向代理统一域名。

## 依赖注入

所有路由通过 FastAPI `Depends` 获取 ClickHouse 客户端：

```python
# toolops/api/deps.py
def get_clickhouse() -> ClickHouseClient:
    return ClickHouseClient()
```

路由签名：

```python
@router.get("/")
def list_traces(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    ...
```

## 端点详解

### GET /health

健康检查，用于 Docker healthcheck 和负载均衡探针。

```
响应：{"status": "ok"}
```

### GET /api/overview/

返回最近 1 小时的总览统计，Dashboard Overview 页使用。

**响应格式**：
```json
{
  "total_requests": 1842,
  "avg_latency_ms": 523.4,
  "error_rate": 3.2,
  "cache_hit_rate": 41.5
}
```

- `total_requests`：1 小时内根 span（`ParentSpanId = ''`）数量
- `avg_latency_ms`：根 span 平均 Duration（纳秒 → 毫秒）
- `error_rate`：`StatusCode = 'STATUS_CODE_ERROR'` 占比（%）
- `cache_hit_rate`：`SpanAttributes['cache.hit'] = 'true'` 占比（%）

### GET /api/traces/

查询 traces 列表，支持多维度过滤。

**Query 参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `service` | string | 按服务名过滤 |
| `trace_id` | string | 按 TraceId 精确匹配 |
| `start` | datetime | 时间范围起始（ISO 8601） |
| `end` | datetime | 时间范围结束（ISO 8601） |
| `limit` | int | 最大返回条数，默认 100，上限 10000 |

**响应格式**（数组）：
```json
[
  {
    "TraceId": "abc123...",
    "SpanId": "def456...",
    "ParentSpanId": "",
    "SpanName": "rag_pipeline",
    "SpanKind": "SPAN_KIND_INTERNAL",
    "ServiceName": "demo-app",
    "DurationMs": 1234.5,
    "StatusCode": "STATUS_CODE_OK",
    "Timestamp": "2026-03-28T10:00:00"
  }
]
```

### GET /api/metrics/

查询 gauge 和 sum 类型的 metrics，合并返回。

**Query 参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `service` | string | 按服务名过滤 |
| `metric_name` | string | 按指标名过滤 |
| `start` | datetime | 时间范围起始 |
| `end` | datetime | 时间范围结束 |
| `limit` | int | 默认 1000，上限 10000 |

**响应格式**（数组）：
```json
[
  {
    "ServiceName": "demo-app",
    "MetricName": "cache_hit_ratio",
    "MetricDescription": "Cache hit ratio (rolling)",
    "Attributes": {},
    "TimeUnix": "2026-03-28T10:00:00",
    "Value": 0.42
  }
]
```

### GET /api/logs/

查询日志，支持全文搜索和多维度过滤。

**Query 参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `service` | string | 按服务名过滤 |
| `level` | string | 日志级别（INFO / WARN / ERROR） |
| `trace_id` | string | 按 TraceId 过滤（用于关联） |
| `search` | string | 全文搜索（`Body LIKE %search%`） |
| `start` | datetime | 时间范围起始 |
| `end` | datetime | 时间范围结束 |
| `limit` | int | 默认 1000，上限 10000 |

**响应格式**（数组）：
```json
[
  {
    "Timestamp": "2026-03-28T10:00:00",
    "TraceId": "abc123...",
    "SpanId": "def456...",
    "SeverityText": "INFO",
    "SeverityNumber": 9,
    "ServiceName": "demo-app",
    "Body": "query=hello status=success latency=0.523s"
  }
]
```

### GET /api/correlate/{trace_id}

核心关联接口：给定一个 `trace_id`，返回该请求的完整上下文（traces + logs + 时间范围内的 metrics）。

**路径参数**：`trace_id`（string）

**响应格式**：
```json
{
  "trace_id": "abc123...",
  "traces": [...],   // 该 trace_id 下所有 span
  "logs": [...],     // 携带该 trace_id 的所有日志
  "metrics": [...]   // 同服务、同时间范围内的 metrics
}
```

Dashboard Chain 页面使用此接口实现"输入 TraceId → 看完整调用链"。

### GET /api/infra/health

检查所有基础设施组件的健康状态，后端代理模式（避免浏览器直连 Docker 内网）。

**响应格式**（数组）：
```json
[
  {"name": "ClickHouse",    "port": 8123, "healthy": true},
  {"name": "OTel Collector","port": 4318, "healthy": true},
  {"name": "Prometheus",    "port": 9090, "healthy": true},
  {"name": "Loki",          "port": 3100, "healthy": false},
  {"name": "Demo App",      "port": 8080, "healthy": true}
]
```

每个组件的健康判断：`resp.status_code < 500`，超时时间 3 秒。

## 应用工厂

`toolops/api/app.py` 使用工厂函数模式，便于测试时注入不同配置：

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="ToolOps API",
        description="AI application observability platform",
        version="0.2.0",
    )
    app.add_middleware(CORSMiddleware, ...)
    app.include_router(overview.router)
    app.include_router(metrics.router)
    app.include_router(traces.router)
    app.include_router(logs.router)
    app.include_router(correlate.router)
    app.include_router(infra.router)
    # ... /health 端点
    return app
```

---

→ 前端如何调用这些接口，参见 [前端页面](frontend.md)  
→ ClickHouse 查询实现，参见 [数据存储层](storage.md)  
→ 启动 API 服务，参见 [部署指南](deployment.md)
