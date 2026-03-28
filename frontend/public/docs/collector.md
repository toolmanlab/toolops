# 数据采集层

> OTel Collector + Prometheus + Loki，三路采集，统一写入 ClickHouse

## 概述

数据采集层是 ToolOps 的神经末梢，负责将 AI 应用产生的三类遥测信号（Traces / Metrics / Logs）汇聚并持久化。当前实现采用三个独立组件协同工作：

```
┌─────────────────────────────────────────────────────┐
│               数据采集层                              │
│                                                     │
│  OTel Collector    Prometheus        Loki           │
│  :4317(gRPC)       :9090             :3100          │
│  :4318(HTTP)       └─ pull /metrics  └─ Docker logs │
│  └─ Traces                                          │
│  └─ Metrics (OTLP)                                  │
│  └─ Logs                                            │
│         │                │                │         │
│         └────────────────┘                │         │
│                  │                        │         │
│          ClickHouse :8123           (可选存储)        │
└─────────────────────────────────────────────────────┘
```

## OTel Collector Pipeline 配置

完整配置位于 `config/otel-collector.yaml`：

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1000

exporters:
  clickhouse:
    endpoint: tcp://clickhouse:9000?dial_timeout=10s&compress=lz4
    database: toolops
    logs_table_name: logs
    traces_table_name: traces
    metrics_table_name: metrics
    ttl: 720h
    create_schema: true   # 自动建表，无需手动 DDL

service:
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

**关键参数解释**：
- `batch.timeout: 5s`：最多缓冲 5 秒发送一批，权衡延迟和写入效率
- `batch.send_batch_size: 1000`：单批最大 1000 条，防止 ClickHouse 写入压力过大
- `compress=lz4`：TCP 连接启用 LZ4 压缩，减少网络传输量
- `ttl: 720h`：数据保留 30 天，OTel exporter 自动在建表 DDL 中添加 TTL 声明
- `create_schema: true`：首次启动自动创建表结构，无需手动执行 DDL

## 三种信号采集路径

### 路径 1：Traces（分布式追踪）

```
demo-app → OTel Python SDK → OTLP gRPC :4317 → OTel Collector → ClickHouse.traces
```

应用侧 SDK 初始化（`demo-app/otel_setup.py`）：

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

tracer_provider = TracerProvider(resource=resource)
span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
trace.set_tracer_provider(tracer_provider)
```

RAG pipeline 埋点示例（`demo-app/main.py`）：

```python
with tracer.start_as_current_span("rag_pipeline") as root_span:
    with tracer.start_as_current_span("embedding") as span:
        span.set_attribute("trace_id", trace_id)
        # ... 执行 embedding
    with tracer.start_as_current_span("vector_search") as span:
        # ... 执行向量检索
    with tracer.start_as_current_span("llm_generate") as span:
        span.set_attribute("llm.model", params.llm_model)
        span.set_attribute("llm.input_tokens", input_tokens)
```

### 路径 2：Metrics（指标）

**双路并行**：Prometheus pull + OTLP push

```
demo-app:/metrics ←── Prometheus (pull, 15s)  →  Prometheus DB
demo-app (OTel)   ──→ OTLP → OTel Collector  →  ClickHouse.otel_metrics_*
```

Dashboard Metrics 页目前从 ClickHouse traces 表聚合计算延迟和吞吐量，而非直接读 Prometheus，这样可以利用统一存储的 cross-JOIN 能力。

### 路径 3：Logs（日志）

```
demo-app (OTel LoggingHandler) → OTLP gRPC → OTel Collector → ClickHouse.logs
demo-app (stdout JSON)         → Docker → Loki :3100（可选）
```

日志与 Trace 关联的关键：**在 span context 内调用 logger**，OTel LoggingHandler 会自动注入 `TraceId` / `SpanId`：

```python
# root_span 仍是当前 span 时发出日志
with tracer.start_as_current_span("rag_pipeline") as root_span:
    # ... pipeline 执行
    finally:
        # 此时 root_span 仍活跃，OTel Handler 自动注入 TraceId
        logger.handle(log_record)
```

## 为什么选 OTel

1. **行业标准**：CNCF 毕业项目，AWS / GCP / Azure / Datadog 均原生支持 OTLP
2. **协议无关**：应用不依赖 ToolOps 私有 SDK，未来迁移成本为零
3. **三信号统一**：一个 Collector 处理 Traces + Metrics + Logs，简化部署
4. **生态丰富**：OTel Contrib 包含 100+ receiver / exporter，包括 ClickHouse exporter
5. **自动埋点**：Python SDK 支持 auto-instrumentation（HTTP、DB 等无需手写 span）

## 踩坑记录

### 坑 1：OTel Collector scratch 镜像无 Shell

使用 `otel/opentelemetry-collector` (scratch 基础镜像) 时，`docker exec -it ... sh` 会失败，因为镜像内没有任何 shell。

**解决方案**：改用 `otel/opentelemetry-collector-contrib:latest`，该镜像包含更多组件和调试工具，且 ClickHouse exporter 只在 contrib 版本中提供。

### 坑 2：TraceId 需要在 Span Context 内写日志

如果在 `with tracer.start_as_current_span(...)` 块**外部**调用 logger，OTel LoggingHandler 无法获取到当前 span context，`TraceId` 字段将为空字符串，导致 Chain 页面无法关联日志。

**解决方案**：确保关键日志在 span 内发出，或使用 `root_span` 包裹整个请求生命周期（见 `demo-app/main.py` 的 `finally` 块处理方式）。

### 坑 3：Batch Processor 导致数据延迟

默认 `timeout: 5s` 意味着最新数据会有 5 秒延迟才出现在 Dashboard。开发阶段可以将 `timeout` 调小，生产环境应保持 5-10s 以提升写入效率。

---

→ ClickHouse 表结构设计，参见 [数据存储层](storage.md)  
→ Demo App 埋点详解，参见 [Demo App](demo-app.md)  
→ 完整配置参数，参见 [配置参考](configuration.md)
