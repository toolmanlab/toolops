# LLM Intelligence 层

ToolOps 的第五层架构，专注 LLM 调用成本追踪、性能分析和 Agent 使用监控。

## 三个数据采集通道

### 1. CC Log Collector

从 Claude Code 本地 JSONL 日志文件增量采集使用数据。

**工作原理：**
- 扫描 `~/.claude/projects/` 下所有 `.jsonl` 文件
- 增量读取（基于字节偏移状态文件 `~/.toolops/cc_collector_state.json`）
- 过滤合成/零 token 记录
- 自动计算成本（基于内置定价表）
- 写入 ClickHouse `llm_usage` 表

**采集字段：** model, input/output/cache tokens, session_id, project/cwd, git branch, CC version, stop_reason 等。

**使用方式：**
```bash
# CLI 命令
toolops collect

# API 触发
POST /api/llm/collect
```

### 2. LLM Gateway Proxy

透明 HTTP 反向代理，部署在应用和 LLM Provider 之间。

**工作原理：**
- 接收 LLM API 请求，透明转发到上游 Provider
- 支持 streaming（aiter_raw 零延迟转发）和 non-streaming
- 记录 TTFB（首 token 时间）、总延迟、token 消耗
- Authorization header 存储为 SHA-256 hash 前缀（安全）
- ClickHouse 写入在 finally 块中（fire-and-forget，不影响请求）

**支持的 Provider：** anthropic, openai, deepseek, ollama, moonshot, minimax, zhipu, cliproxy

**URL 模式：** `http://localhost:9010/{provider}/{path}`

**OpenClaw 元数据提取：** 自动识别 OpenClaw 请求头中的 agent_name, session_key, skill_name, channel 字段。

**数据表：** `llm_gateway`

### 3. OpenClaw Observer Plugin

TypeScript 插件，利用 OpenClaw 原生 `llm_input` / `llm_output` 全局 hook。

**工作原理：**
- 注册 `llm_input` hook：记录请求开始时间、prompt 长度、图片数量
- 注册 `llm_output` hook：计算延迟、token 消耗、成本，写入 ClickHouse
- Batch 缓冲（10 条记录或 5 秒间隔）
- `runVoidHook` 机制：failure-safe，插件异常不影响推理

**采集字段：** agent_id, session_key, provider, model, input/output/cache tokens, cost_usd, latency_ms, prompt_length, history_messages_count, images_count, trigger, channel

**数据表：** `llm_openclaw`（TTL 90 天）

## 成本计算

内置定价表（USD per million tokens）：

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| claude-opus-4-6 | $5.00 | $25.00 | $10.00 | $0.50 |
| claude-sonnet-4-6 | $3.00 | $15.00 | $6.00 | $0.30 |
| claude-haiku-4-5 | $1.00 | $5.00 | $2.00 | $0.10 |
| kimi-k2 | $0.60 | $3.00 | $0.60 | $0.10 |

匹配逻辑：精确匹配 → 模糊 key-in-model 匹配（如 `claude-sonnet-4-6` 匹配 `cliproxy/claude-sonnet-4-6`）。

## Dashboard

LLM Dashboard 页面包含三个 Tab：

### CC Usage
- 统计卡片：总记录数、总 token、总成本、Session 数
- Token Timeline（每日时序图）
- Model Distribution（饼图）
- Top Projects by Tokens（水平柱图）
- Session Leaderboard（表格，含成本列）

### Gateway
- 统计卡片：请求数、Token、成本、平均延迟
- Latency Timeline（P50/P95 双线图）
- Agent Distribution（饼图）
- Recent Requests（表格，含状态码着色）

### OpenClaw Agents
- 统计卡片：请求数、Token、成本、Agent 数
- Agent Distribution（饼图）
- Token Timeline（每小时时序图）
- Session 列表（可点击过滤）
- Recent Requests（表格，支持按 agent/session/time 过滤）

## 查询过滤

所有 LLM 端点支持统一查询参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| agent_id | string | 按 Agent 过滤 |
| session_id | string | 按 Session 过滤 |
| model | string | 按模型过滤 |
| start | ISO 8601 | 起始时间 |
| end | ISO 8601 | 结束时间 |
| limit | int | 返回条数限制 |
| offset | int | 偏移量 |

后端使用参数化查询（`_build_filter_conditions`），防 SQL 注入。

## API 端点

### CC Usage
- `GET /api/llm/overview` — 总览统计
- `GET /api/llm/sessions` — Session 列表
- `GET /api/llm/sessions/{id}` — Session 详情
- `GET /api/llm/projects` — 按项目聚合
- `GET /api/llm/models` — 按模型聚合
- `GET /api/llm/timeline` — 时序数据
- `POST /api/llm/collect` — 触发 CC 日志采集

### Gateway
- `GET /api/llm/gateway/overview` — Gateway 总览
- `GET /api/llm/gateway/requests` — 请求列表
- `GET /api/llm/gateway/agents` — 按 Agent 聚合
- `GET /api/llm/gateway/latency` — 延迟时序

### OpenClaw
- `GET /api/llm/openclaw/overview` — OpenClaw 总览
- `GET /api/llm/openclaw/agents` — 按 Agent 聚合
- `GET /api/llm/openclaw/timeline` — 时序数据
- `GET /api/llm/openclaw/requests` — 请求列表
- `GET /api/llm/openclaw/sessions` — Session 列表
- `GET /api/llm/openclaw/sessions/{key}` — Session 详情
