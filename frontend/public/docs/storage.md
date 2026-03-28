# 数据存储层

> ClickHouse 统一存储：Traces / Metrics / Logs 一库搞定

## 为什么选 ClickHouse

### 竞品对比

| 存储方案 | 使用工具 | 问题 |
|---------|---------|------|
| 分散存储 | LangFuse (PostgreSQL + Redis) | Traces 在 PG，无法和 Logs 做 JOIN |
| 时序专用 | Prometheus + InfluxDB | 只能存 Metrics，不支持 Traces |
| 搜索引擎 | Elasticsearch | 写入成本高，不适合时序聚合 |
| **统一存储** | **ClickHouse（ToolOps）** | Traces + Metrics + Logs 一张表可 JOIN |

### ClickHouse 的核心优势

1. **列式存储**：时序数据查询（按时间范围 + 聚合）天然友好，比行存快 10-100x
2. **MergeTree 引擎**：写入吞吐极高，后台自动 merge，无需手动维护索引
3. **TTL 原生支持**：建表时声明 `TTL toDateTime(timestamp) + INTERVAL 30 DAY`，数据自动过期
4. **OTel 原生 exporter**：`otelcol-contrib` 包含 `clickhouse` exporter，零代码接入
5. **cross-JOIN 关联**：同一个 `trace_id`，可以在一条 SQL 里关联 traces + logs + metrics

## 表结构

OTel Collector 的 `clickhouse` exporter 设置 `create_schema: true` 后会自动建表，同时 `toolops/storage/schema.sql` 提供了手动初始化的 DDL：

### traces 表

```sql
CREATE TABLE IF NOT EXISTS traces (
    trace_id       String,
    span_id        String,
    parent_span_id String,
    service        String,
    operation      String,
    start_time     DateTime64(3),
    duration_ms    Float64,
    status_code    UInt8,
    attributes     Map(String, String)
) ENGINE = MergeTree()
ORDER BY (service, start_time, trace_id)
TTL toDateTime(start_time) + INTERVAL 30 DAY;
```

OTel Collector 自动创建的表字段更完整，包含 `TraceId`、`SpanId`、`ParentSpanId`、`SpanName`、`SpanKind`、`ServiceName`、`ResourceAttributes`、`SpanAttributes`、`Duration`（纳秒）、`StatusCode`、`StatusMessage`。

### logs 表

```sql
CREATE TABLE IF NOT EXISTS logs (
    timestamp   DateTime64(3),
    service     String,
    level       String,
    message     String,
    trace_id    String,        -- 关联 traces 的核心字段
    attributes  Map(String, String)
) ENGINE = MergeTree()
ORDER BY (service, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY;
```

OTel exporter 自动建表字段：`Timestamp`、`TraceId`、`SpanId`、`TraceFlags`、`SeverityText`、`SeverityNumber`、`ServiceName`、`Body`、`ResourceAttributes`、`LogAttributes`。

### otel_metrics_* 表组

Metrics 分三张表，对应 OTel 的三种 metric 类型：

```sql
-- Gauge（瞬时值，如 cache_hit_ratio）
otel_metrics_gauge:     ServiceName, MetricName, Attributes, TimeUnix, Value

-- Sum（累计值，如 query_total）
otel_metrics_sum:       ServiceName, MetricName, Attributes, TimeUnix, Value, StartTimeUnix

-- Histogram（分布，如 query_latency_seconds）
otel_metrics_histogram: ServiceName, MetricName, Attributes, TimeUnix,
                        Count, Sum, BucketCounts, ExplicitBounds
```

## MergeTree + TTL 机制

```sql
ENGINE = MergeTree()
ORDER BY (service, start_time, trace_id)
TTL toDateTime(start_time) + INTERVAL 30 DAY
```

- **`ORDER BY`**：ClickHouse 按此键排序存储，决定查询性能。`(service, timestamp)` 的组合使得「按服务过滤 + 时间范围」的查询能命中索引
- **MergeTree**：后台持续合并小文件，维护排序顺序，读取时跳过不相关的 granule
- **TTL**：超过 30 天的数据由后台任务自动删除，无需 cron job

## cross-JOIN 关联查询

统一存储最大的价值：一个 `trace_id` 可以在 SQL 里关联三种信号。

`toolops/storage/clickhouse.py` 中的 `correlate()` 方法实现了这一逻辑：

```python
def correlate(self, trace_id: str) -> dict[str, Any]:
    """Correlate metrics, traces, and logs by trace_id."""
    traces = self.query_traces(trace_id=trace_id, limit=100)
    logs = self.query_logs(trace_id=trace_id, limit=100)

    # 从 traces 推导时间范围，查询同服务的 metrics
    services = {t["ServiceName"] for t in traces}
    metrics: list[dict[str, Any]] = []
    if traces:
        start = min(t["Timestamp"] for t in traces)
        end = max(t["Timestamp"] for t in traces)
        for svc in services:
            metrics.extend(self.query_metrics(service=svc, start=start, end=end))

    return {"trace_id": trace_id, "traces": traces, "logs": logs, "metrics": metrics}
```

## clickhouse.py 封装

`toolops/storage/clickhouse.py` 是 ClickHouse 客户端的薄封装层，提供以下查询方法：

| 方法 | 参数 | 说明 |
|------|------|------|
| `query_traces()` | service, trace_id, start, end, limit | 查询 traces 表，Duration 自动转毫秒 |
| `query_metrics()` | service, metric_name, start, end, limit | 合并 gauge + sum 两张表结果 |
| `query_metrics_histogram()` | service, metric_name, start, end, limit | 查询 histogram 表 |
| `query_logs()` | service, level, trace_id, search, start, end, limit | 支持全文搜索（LIKE） |
| `correlate()` | trace_id | 按 trace_id 关联三种信号 |
| `query_overview()` | 无 | 统计最近 1 小时总请求数 / 平均延迟 / 错误率 / 缓存命中率 |

所有查询使用参数化 SQL（`clickhouse-connect` 的 `{param:Type}` 语法），防止 SQL 注入：

```python
sql = (
    "SELECT ... FROM traces WHERE ServiceName = {service:String}"
    " AND Timestamp >= {start:DateTime64(9)}"
)
result = self.client.query(sql, parameters={"service": "demo-app", "start": dt})
```

## 运维注意事项

- **连接复用**：`ClickHouseClient` 使用懒初始化，`client` 属性在首次访问时创建连接，通过 FastAPI 依赖注入在请求间复用
- **异常隔离**：`query_metrics()` 对每张 metrics 表独立 try/except，防止某张表不存在时整个请求失败
- **Docker 网络**：容器内 OTel Collector 通过 `tcp://clickhouse:9000` 连接（Native TCP），API 服务通过 HTTP `:8123` 连接

---

→ API 如何查询 ClickHouse，参见 [API 接口](api.md)  
→ OTel Collector 如何写入 ClickHouse，参见 [数据采集层](collector.md)  
→ 配置 ClickHouse 连接，参见 [配置参考](configuration.md)
