# Demo App

> 模拟 RAG pipeline 的可观测性靶场

## 概述

Demo App 是 ToolOps 的内置测试应用，模拟一个真实的 RAG（Retrieval-Augmented Generation）pipeline，用于演示可观测性数据的采集和展示。它不调用真实的 LLM API，而是通过参数化的 sleep + 随机数模拟各种延迟和故障场景。

代码位于 `demo-app/` 目录：

```
demo-app/
├── main.py          # FastAPI 应用 + 后台流量生成器 + RAG pipeline 模拟
├── otel_setup.py    # OTel SDK 初始化（traces + logs）
├── scenarios.py     # 7 种故障场景参数定义
└── requirements.txt # Python 依赖
```

## RAG Pipeline 结构

模拟的 pipeline 包含 4 个步骤，每个步骤对应一个 OTel span：

```
rag_pipeline (root span)
├── embedding          # 将查询文本转为向量表示
│   └── latency: 30-80ms（正常模式）
├── [cache check]      # 内存内缓存命中检查（无独立 span）
│   └── hit_rate: 40%（正常模式）
├── vector_search      # 向量数据库检索
│   └── latency: 50-200ms（正常模式）
└── llm_generate       # LLM 生成回答
    └── latency: 500ms-3s（正常模式）
```

完整实现见 `demo-app/main.py` 的 `_run_rag_pipeline()` 函数：

```python
with tracer.start_as_current_span("rag_pipeline") as root_span:
    # 1. Embedding
    with tracer.start_as_current_span("embedding") as span:
        _simulate_step("embedding", params.embed_latency_range)

    # 2. Cache check（命中则提前返回）
    cache_hit = random.random() < params.cache_hit_rate
    if cache_hit:
        return {"cached": True, ...}

    # 3. Vector search
    with tracer.start_as_current_span("vector_search") as span:
        retrieval_time = _simulate_step("vector_search", params.retrieval_latency_range)
        RETRIEVAL_LATENCY.observe(retrieval_time)
        if random.random() < params.retrieval_timeout_rate:
            raise TimeoutError("Vector search timed out")

    # 4. LLM generation
    with tracer.start_as_current_span("llm_generate") as span:
        span.set_attribute("llm.model", params.llm_model)
        span.set_attribute("llm.input_tokens", input_tokens)
        span.set_attribute("llm.output_tokens", output_tokens)
```

## 7 种故障场景

通过环境变量 `DEMO_SCENARIO` 控制，定义在 `demo-app/scenarios.py`：

| 场景名 | 故障类型 | 关键参数变化 |
|--------|---------|------------|
| `normal` | 正常运行 | retrieval: 50-200ms, llm: 0.5-3s, cache: 40% |
| `slow_retrieval` | 检索超时 | retrieval: 500ms-2s, timeout_rate: 15% |
| `llm_rate_limit` | LLM 限流 | rate_limit_rate: 30% |
| `cache_cold_start` | 缓存冷启动 | cache_hit_rate: 0% |
| `memory_pressure` | 内存压力 | memory_growth_mb: 0.5MB/req |
| `cascade_failure` | 级联故障 | retrieval: 1-5s, timeout: 30%, llm: 2-8s, rate_limit: 15% |
| `cost_spike` | 成本飙升 | model: gpt-4o, input_tokens: 500-2000, output: 200-1000 |

切换场景方式：

```bash
# 方式 1：修改 .env 后重启
DEMO_SCENARIO=cascade_failure docker compose up -d --force-recreate demo-app

# 方式 2：docker-compose.yml 环境变量
environment:
  DEMO_SCENARIO: ${DEMO_SCENARIO:-normal}
```

### 场景详解

**slow_retrieval**：检索延迟提升 10x，超时率 15%。Dashboard Traces 页面可以看到 `vector_search` span 的 DurationMs 异常高，部分请求出现 `TimeoutError`。

**llm_rate_limit**：30% 的请求在 `llm_generate` 阶段抛出 `RuntimeError("LLM rate limited (429)")`。Chain 页面可以看到失败 span 的 `StatusCode = STATUS_CODE_ERROR`。

**cascade_failure**：检索和 LLM 同时异常，模拟真实的"上游抖动导致全链路崩溃"场景。Overview 的错误率会显著上升。

**cost_spike**：使用更贵的模型（`gpt-4o` vs `gpt-4o-mini`），token 消耗量 3-4x。Metrics 页面的 `llm_token_input_total` 和 `llm_token_output_total` 趋势会明显上升。

## 后台流量生成器

Demo App 在启动时会开启一个后台线程，每 0.2-1 秒自动发起随机查询，持续产生遥测数据：

```python
def _traffic_generator() -> None:
    """Background thread that generates 1-5 requests per second."""
    sample_queries = [
        "What is RAG?",
        "How does vector search work?",
        "Explain transformer attention",
        # ... 8 个预设查询
    ]
    time.sleep(3)  # 等待服务器启动
    while True:
        q = random.choice(sample_queries)
        httpx.get(f"{base_url}/query", params={"q": q}, timeout=30)
        time.sleep(random.uniform(0.2, 1.0))
```

这意味着**无需手动触发请求**，启动后 Dashboard 就会自动有数据。

## Prometheus Metrics 端点

Demo App 暴露标准 Prometheus metrics 端点 `/metrics`，供 Prometheus scrape：

```python
QUERY_TOTAL        = Counter("query_total", "Total queries", ["status"])
QUERY_LATENCY      = Histogram("query_latency_seconds", "Query latency", buckets=[...])
RETRIEVAL_LATENCY  = Histogram("retrieval_latency_seconds", "Retrieval step latency")
LLM_INPUT_TOKENS   = Counter("llm_token_input_total", "LLM input tokens")
LLM_OUTPUT_TOKENS  = Counter("llm_token_output_total", "LLM output tokens")
CACHE_HIT_RATIO    = Gauge("cache_hit_ratio", "Cache hit ratio (rolling)")
```

## OTel 埋点设计

### Traces 埋点

手动创建 span，在每个 pipeline 步骤设置关键属性：

```python
span.set_attribute("llm.model", "gpt-4o-mini")
span.set_attribute("llm.input_tokens", 350)
span.set_attribute("llm.output_tokens", 120)
span.set_attribute("cache.hit", "true")   # 由 clickhouse.py 读取
```

### Logs 与 Traces 关联

关键设计：日志在 `root_span` 仍活跃时发出，OTel `LoggingHandler` 自动注入 `TraceId`：

```python
with tracer.start_as_current_span("rag_pipeline") as root_span:
    try:
        # ... pipeline 执行
    finally:
        # root_span 此时仍是 current span
        # OTel LoggingHandler 会把 TraceId/SpanId 写入 ClickHouse logs 表
        logger.handle(log_record)
```

这使得 Chain 页面可以通过 `trace_id` 同时展示 spans 和对应的日志。

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /query?q=...` | 触发一次 RAG pipeline 查询 |
| `GET /metrics` | Prometheus metrics（供 Prometheus scrape） |
| `GET /health` | 健康检查，返回当前 scenario 名称 |

---

→ OTel Collector 如何接收数据，参见 [数据采集层](collector.md)  
→ 启动 Demo App，参见 [部署指南](deployment.md)  
→ 切换场景的环境变量，参见 [配置参考](configuration.md)
