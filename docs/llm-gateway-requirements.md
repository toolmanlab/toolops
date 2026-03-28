# LLM Gateway 需求讨论（2026-03-29）

> P2 ToolOps 第五层能力：LLM 调用数据采集与分析

## 背景

Alex 日常使用多个 AI 入口：CC 终端（Claude Code）、OpenClaw 6 个 Agent（Dojo/Scout/Radar/Pulse/Cinema/Seven）、Claude Desktop、Claude Web、API key 项目（ToolRef）。所有 Claude 调用共用同一个订阅账号，Anthropic 不区分来源，导致：

- 不知道哪个 Agent / 哪个项目 / 哪个 session 消耗了多少
- 不知道哪个 Skill 的上下文注入是 token 黑洞
- 中转站（CPA）后台统计口径不透明，无法和本地实际消耗对账
- CC 命令行 `--usage` 只是快照，无法做趋势分析和维度拆解

## 核心定位

**不是 LLM Gateway（不做路由/负载/缓存），不是 LLM Observability 平台（不强制 SDK 埋点）。**

定位：**AI 开发者的 LLM 使用可视化 + 可审计平台。** 覆盖终端 Agent、API 调用两大高频场景，在 ClickHouse 中与现有应用层 trace/metrics/logs 关联分析。

一句话：「LiteLLM 只看模型调用，Langfuse 只看应用层，ToolOps JOINs both in the same ClickHouse。」

## Alex 的使用拓扑

```
入口                  链路                                          日常占比
─────────────────────────────────────────────────────────────────────────
CC 终端               CC → Anthropic（订阅直连）                    ~35%
OpenClaw 6 Agent      OpenClaw → CPA 反代 → Anthropic              ~45%
ToolRef (P1)          ToolRef → API key → Anthropic                ~10%
Claude Desktop        Desktop → Anthropic（直连）                   ~5%
Claude Web            浏览器 → claude.ai                            ~5%
```

## 数据采集方案（三通道）

### 通道 1：LLM Gateway Proxy（核心）

透明 HTTP 反向代理。用户仅需修改 `BASE_URL` 环境变量，零代码改动。

```
OpenClaw Agent → Gateway (localhost:9010) → CPA → Anthropic
ToolRef        → Gateway (localhost:9010) → Anthropic API
```

**采集方式：** 从 HTTP request/response 中解析。API key 透传（方案 A），Gateway 不接触密钥。

**可采集字段：**
- model
- input_tokens / output_tokens（从 response body 解析）
- request latency（TTFB + total）
- streaming chunk timing（SSE 逐 chunk 时间分布）
- HTTP status code / error
- request/response size (bytes)
- API key hash（脱敏）
- upstream provider（anthropic / openai / deepseek / ollama）
- OpenClaw 特有 header：agent name、session key、skill name、channel

**分析维度：**
- 按 Agent 拆分（Dojo vs Scout vs Radar…）
- 按 Skill 拆分（哪个 skill 上下文注入成本高）
- 按 Provider 拆分（Anthropic vs OpenAI vs 本地 Ollama）
- 延迟分布（P50 / P95 / P99）
- 错误率 + 重试率
- Streaming TTFT（首 token 延迟）
- 请求热力图（按时间段）

**用户侧配置：**
- OpenClaw：config.yaml 中 provider.baseUrl 指向 Gateway
- ToolRef / API 项目：环境变量 `ANTHROPIC_BASE_URL=http://localhost:9010/anthropic`

### 通道 2：CC Log Collector（补充）

定时读取 CC 本地 JSONL 文件，提取 usage 数据推入 ClickHouse。

**数据源：** `~/.claude/projects/{path-encoded}/{sessionId}.jsonl`

每条 assistant 消息包含：
```json
{
  "message": {
    "model": "claude-opus-4-6",
    "usage": {
      "input_tokens": 3,
      "cache_creation_input_tokens": 3957,
      "cache_read_input_tokens": 22965,
      "output_tokens": 17,
      "service_tier": "standard",
      "cache_creation": {
        "ephemeral_1h_input_tokens": 3957,
        "ephemeral_5m_input_tokens": 0
      }
    }
  },
  "sessionId": "xxx",
  "cwd": "/Users/xuelin/projects/toolref",
  "gitBranch": "main",
  "version": "2.1.63"
}
```

**可采集字段（CC 独有）：**
- model
- input_tokens / output_tokens
- cache_creation_input_tokens / cache_read_input_tokens
- cache 细分（ephemeral_1h / ephemeral_5m）
- service_tier（standard / priority）
- speed（standard / fast）
- server_tool_use（web_search / web_fetch 次数）
- sessionId
- project（工作目录路径）
- gitBranch
- CC version
- timestamp
- stop_reason（end_turn / tool_use）

**分析维度：**
- 按 session 拆分成本
- 按 project 拆分（哪个项目烧钱最多）
- 按 model 拆分（opus vs sonnet 成本比）
- 按时间段分析使用模式
- cache 命中率（cache_read / total_input）
- 每轮效率（output / input 比）
- Git branch 维度（哪个 feature branch 消耗大）

**稳定性评估：**
- CC JSONL 不是官方 public API，无向后兼容承诺
- 但半个 CC 生态的第三方工具（ccusage、CodexBar）都在读这些文件
- 短期 1-2 年内足够稳定
- 设计 adapter 抽象层，schema 变更只改 parser

**已验证不可采集的入口：**

| 入口 | 原因 |
|------|------|
| Claude Desktop Agent Mode | model 标为 `<synthetic>`，usage 全部为 0，Anthropic 有意隐藏 |
| Claude Desktop 普通对话 | 数据在 IndexedDB (LevelDB)，二进制格式，不稳定 |
| Claude Web (claude.ai) | 无本地文件 |

**覆盖率：** CC 终端 + OpenClaw + API 项目覆盖日常 ~90% 的 AI 消耗。Desktop 和 Web 偶尔聊天，token 消耗可忽略。

### 通道 3：OTel SDK（已有）

P1 ToolRef 应用层已埋 OTel trace/log/metrics，无需新增。

**可采集：**
- Trace spans（embedding / vector_search / reranking / llm_generate）
- Span duration + attributes
- 结构化 logs（带 TraceId 关联）
- Prometheus metrics（latency histogram / throughput counter）

### 对账参考（不纳入核心采集）

- **CPA 反代后台：** 有自己的统计面板，可手动对比。不接入 ToolOps，因为 Gateway 已截获同一批请求，数据更精确。
- **Anthropic 官方 usage：** 订阅用户无 API 级别的用量查询接口，仅 Dashboard 页面展示。

## 杀手级能力：跨通道 JOIN

三路数据统一存入 ClickHouse，通过 TraceId / timestamp 关联：

```sql
-- 一次 RAG 请求：应用层耗时 × LLM token/成本
SELECT
  t.TraceId,
  t.SpanName,
  t.Duration AS app_duration_ms,
  g.model,
  g.input_tokens,
  g.output_tokens,
  g.cost_usd,
  g.latency_ms AS llm_latency_ms
FROM otel_traces t
JOIN llm_gateway g ON t.TraceId = g.trace_id
WHERE t.SpanName = 'rag_pipeline'
```

**竞品无此能力：** LiteLLM / Portkey 只有模型调用数据，Langfuse / Phoenix 只有应用层数据。ToolOps 是唯一在同一 ClickHouse 中关联 LLM Gateway + 应用 OTel 的方案。

## 使用场景

### 场景 1：CC 开发 ToolRef — Session 级成本分析
看到一个 CC session 18 轮消耗 $1.24，其中 superpowers skill 每轮注入 2,300 tokens，总共贡献 22% 的成本。评估 skill 的性价比。

### 场景 2：OpenClaw 6 Agent — Agent 级日报
按 Agent 拆分日消耗，发现 Radar 每天 $1+ 但只推了 3 条有效信息，性价比存疑。优化后月省 $40。

### 场景 3：Skill 成本穿透
发现 cc-delegate skill 的 SKILL.md 占 1,200 tokens，github skill 占 900 tokens。4 轮对话里 skill 注入成本占 8.3%。

### 场景 4：RAG Pipeline 关联分析
一次 RAG query 端到端 3,847ms，其中 LLM 生成占 80.6% 时间和 100% 成本。检索结果 1,900 tokens 中有效信息约 40%，提示检索质量需优化。

### 场景 5：异常检测
Radar agent 某天 token 消耗 +220%，追踪发现 web_search 返回超长结果导致连锁放大。建议截断到 8K tokens 可节省 $1.8/天。

## 竞品差异

| 能力 | LiteLLM | Portkey | Langfuse | Helicone | **ToolOps** |
|------|---------|---------|----------|----------|-------------|
| LLM proxy | ✅ 重量级 | ✅ 轻量 | ❌ | ✅ | ✅ 薄层 |
| 应用层 trace | ❌ | ❌ | ✅ SDK | ❌ | ✅ OTel |
| 跨层 JOIN | ❌ | ❌ | ❌ | ❌ | **✅** |
| 本地终端采集 | ❌ | ❌ | ❌ | ❌ | **✅ CC Collector** |
| Agent/Skill 维度 | ❌ | ❌ | ❌ | ❌ | **✅** |
| 零侵入接入 | ❌ SDK | ✅ proxy | ❌ SDK | ✅ proxy | **✅ proxy + file** |
| ClickHouse 统一存储 | ❌ | ❌ | ✅（被收购后） | ✅ | **✅** |

## 架构设计约束

- **Gateway 必须保持薄层：** 只做数据采集 + 透明转发，不做路由/负载/缓存/guardrails。这些功能会被模型厂商吃掉。
- **核心价值在关联分析和可视化：** 模型厂商不知道你的 Redis 延迟和检索链路瓶颈。
- **Adapter 抽象层：** CC Collector 设计为可插拔 adapter，未来支持 Gemini CLI / Codex CLI / Aider 等。

```python
class BaseCollector(ABC):
    @abstractmethod
    def discover_sessions(self) -> List[Session]: ...
    @abstractmethod
    def parse_usage(self, raw) -> StandardUsage: ...

class ClaudeCodeCollector(BaseCollector): ...
class GeminiCLICollector(BaseCollector): ...
class CodexCollector(BaseCollector): ...
```

## 实现优先级

| 阶段 | 任务 | 预估 |
|------|------|------|
| P0 | Gateway proxy 核心（转发 + 记录 → ClickHouse） | 1-2 天 |
| P0 | Dashboard LLM 页面（token/cost/latency 时序图） | 1 天 |
| P1 | CC Collector（读 JSONL → ClickHouse） | 1 天 |
| P1 | Agent / Skill 维度拆分（header 标识方案） | 1 天 |
| P2 | 跨层关联查询 + 关联 Dashboard | 1 天 |
| P2 | 异常检测 + 告警规则 | 1 天 |

## 面试叙事

> "市场上 LLM Gateway 只看模型调用，LLM Observability 平台需要 SDK 埋点。ToolOps 做了两件别人没做的事：
>
> 第一，零侵入 Gateway 采集 LLM 数据，和应用层 OTel trace 在同一个 ClickHouse 关联分析——一条 SQL 看到 RAG pipeline 哪个环节耗时最长、LLM 花了多少 token。
>
> 第二，加了本地终端 Agent 的 usage 采集——因为我每天用 6 个 AI Agent + CC，skill 生态越来越大但成本完全不透明。我自己就是第一个用户，用真实数据优化后月省 $40。
>
> 本质上这是一个可审计性问题：本地独立计算 token，和 provider 账单交叉验证，差异超阈值告警。"

---

*讨论日期：2026-03-29 01:27-02:02 GMT+8*
*参与者：Alex + Dojo*
*状态：需求讨论完成，待进入实现阶段*
