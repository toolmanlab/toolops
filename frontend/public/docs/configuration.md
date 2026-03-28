# 配置参考

> ToolOps 各组件配置文件完整说明

## 概览

| 配置文件 | 位置 | 作用 |
|---------|------|------|
| `.env` / `.env.example` | 根目录 | Python 后端环境变量 |
| `config/otel-collector.yaml` | 根目录 | OTel Collector pipeline |
| `config/prometheus.yml` | 根目录 | Prometheus scrape targets |
| `config/loki-config.yaml` | 根目录 | Loki 存储配置 |
| `toolops/storage/schema.sql` | 后端包 | ClickHouse 表结构 DDL |
| `toolops/config/settings.py` | 后端包 | pydantic-settings 模型 |

---

## 环境变量（.env）

完整的 `.env.example`：

```bash
# ────────── ClickHouse ──────────
CLICKHOUSE_HOST=localhost      # Docker 内部使用服务名 "clickhouse"
CLICKHOUSE_PORT=8123           # HTTP API 端口
CLICKHOUSE_USER=default        # 默认用户
CLICKHOUSE_PASSWORD=           # 默认无密码
CLICKHOUSE_DATABASE=toolops    # 数据库名

# ────────── API 服务 ──────────
API_HOST=0.0.0.0
API_PORT=9000                  # 容器内端口，宿主机映射到 9003

# ────────── Demo App ──────────
DEMO_SCENARIO=normal           # 故障场景：normal/slow_retrieval/llm_rate_limit/
                               # cache_cold_start/memory_pressure/cascade_failure/cost_spike
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317   # 本地直连
# Docker 内使用：http://otel-collector:4317
```

---

## pydantic-settings 配置模型

`toolops/config/settings.py` 使用 pydantic-settings 将环境变量自动解析为类型安全的 Python 对象：

```python
class ClickHouseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 8123
    user: str = "default"
    password: str = ""
    database: str = "toolops"

    model_config = {"env_prefix": "CLICKHOUSE_"}
    # 读取 CLICKHOUSE_HOST, CLICKHOUSE_PORT, ...

class APISettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 9000

    model_config = {"env_prefix": "API_"}
    # 读取 API_HOST, API_PORT
```

`env_prefix` 约定：
- `CLICKHOUSE_` 前缀 → `ClickHouseSettings`
- `API_` 前缀 → `APISettings`

---

## OTel Collector（config/otel-collector.yaml）

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317    # OTLP gRPC 接收端口
      http:
        endpoint: 0.0.0.0:4318    # OTLP HTTP 接收端口

processors:
  batch:
    timeout: 5s                   # 最多缓冲 5 秒
    send_batch_size: 1000         # 单批最大 1000 条

exporters:
  clickhouse:
    endpoint: tcp://clickhouse:9000?dial_timeout=10s&compress=lz4
    database: toolops
    logs_table_name: logs
    traces_table_name: traces
    metrics_table_name: metrics
    ttl: 720h                     # 数据保留 30 天（720 小时）
    create_schema: true           # 自动建表（首次启动）

extensions:
  health_check:
    endpoint: 0.0.0.0:13133      # Collector 自身健康检查

service:
  extensions: [health_check]
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse]
```

**关键参数调优**：

| 参数 | 默认值 | 建议（高流量） |
|------|-------|--------------|
| `batch.timeout` | 5s | 保持 5-10s |
| `batch.send_batch_size` | 1000 | 2000-5000 |
| `compress` | lz4 | 保持 lz4（速度快） |
| `ttl` | 720h | 根据存储容量调整 |

---

## Prometheus（config/prometheus.yml）

```yaml
global:
  scrape_interval: 15s       # 全局抓取间隔
  evaluation_interval: 15s   # 规则评估间隔

scrape_configs:
  - job_name: "demo-app"
    scrape_interval: 15s
    static_configs:
      - targets: ["demo-app:8080"]   # Docker 网络内服务名
    metrics_path: /metrics
```

**扩展 scrape target**：如果你有多个服务暴露 `/metrics`，在 `scrape_configs` 下追加：

```yaml
  - job_name: "my-service"
    static_configs:
      - targets: ["my-service:8080"]
```

---

## Loki（config/loki-config.yaml）

```yaml
auth_enabled: false            # 开发模式不启用认证

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1        # 单节点部署
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory           # 开发模式使用内存 KV

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb               # 使用 TSDB 索引格式（v13 最新）
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h             # 每天一个索引文件

limits_config:
  retention_period: 720h        # 日志保留 30 天
```

**注意**：当前架构中 Loki 主要作为 Docker stdout 的日志收集器（可选）。核心日志数据通过 OTel Logs SDK → OTel Collector → ClickHouse 流转。

---

## ClickHouse 表结构（toolops/storage/schema.sql）

初始化 DDL，ClickHouse 首次启动时执行（`/docker-entrypoint-initdb.d/`）：

```sql
-- Metrics 表（时序指标）
CREATE TABLE IF NOT EXISTS metrics (
    timestamp   DateTime64(3),
    service     String,
    metric_name String,
    metric_value Float64,
    labels      Map(String, String)
) ENGINE = MergeTree()
ORDER BY (service, metric_name, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY;

-- Traces 表（分布式追踪）
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

-- Logs 表（结构化日志）
CREATE TABLE IF NOT EXISTS logs (
    timestamp  DateTime64(3),
    service    String,
    level      String,
    message    String,
    trace_id   String,
    attributes Map(String, String)
) ENGINE = MergeTree()
ORDER BY (service, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY;
```

> **注意**：OTel Collector 的 `create_schema: true` 会自动创建结构更完整的 OTel 标准表（字段名为 PascalCase），`schema.sql` 的表是手动备用。实际查询以 OTel 自动创建的表为准。

---

→ 启动步骤，参见 [部署指南](deployment.md)  
→ ClickHouse 查询封装，参见 [数据存储层](storage.md)  
→ OTel Collector pipeline 深度解析，参见 [数据采集层](collector.md)
