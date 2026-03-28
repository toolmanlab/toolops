# 前端页面

> React 19 + Vite 8 + TypeScript + Tailwind 4 + recharts + SWR

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| Vite | 8 | 构建工具 / Dev Server |
| TypeScript | 5 | 类型安全 |
| Tailwind CSS | 4 | 原子化样式 |
| recharts | 2 | 时序折线图 |
| SWR | 2 | 数据请求 + 自动轮询 |
| React Router | 6 | 客户端路由 |
| react-markdown | 9 | Markdown 渲染（Docs 页面） |
| remark-gfm | 4 | GitHub Flavored Markdown 支持 |

## 数据请求层

所有 API 调用封装在 `frontend/src/lib/api.ts`，通过 SWR 实现**每 10 秒自动轮询**，无需手动刷新页面：

```typescript
const API_BASE = "http://localhost:9003";

const swrOptions = { refreshInterval: 10000 };  // 10s 自动刷新

export function useTraces(params?: { limit?: number; trace_id?: string }) {
  const key = `/api/traces/${qs ? `?${qs}` : ""}`;
  return useSWR<Trace[]>(key, fetcher, swrOptions);
}
```

**类型定义**（`api.ts` 中）：
- `Trace`：TraceId / SpanId / ParentSpanId / ServiceName / SpanName / DurationMs / StatusCode / Timestamp / SpanAttributes
- `Metric`：metric_name / value / timestamp / labels
- `LogEntry`：Timestamp / SeverityText / ServiceName / Body / TraceId
- `CorrelateResult`：traces[] + logs[]

## 暗色主题

全局背景色 `#0f172a`（Slate 950），卡片背景 `#1e293b`（Slate 800），边框 `#334155`（Slate 700）。激活状态使用蓝色 `#3b82f6`。文字层级：

- 主文字：`white` / `#f1f5f9`
- 次要文字：`#94a3b8`（Slate 400）
- 禁用/标签：`#64748b`（Slate 500）
- 高亮链接：`#38bdf8`（Sky 400）

## 7 个页面职责

### Overview（总览）— `/`

**数据源**：`useOverview()` → `/api/overview/`

4 个 KPI 卡片：
- 总请求数（Total Requests）
- 平均延迟（Avg Latency ms）
- 错误率（Error Rate %）
- 缓存命中率（Cache Hit Rate %）

最近 10 条 trace 速览表格，点击 TraceId 跳转 Chain 页面。数据窗口：最近 1 小时。

### Traces（链路追踪）— `/traces`

**数据源**：`useTraces()` → `/api/traces/`

全量 trace 列表，字段：TraceId（可点击跳转）/ ServiceName / SpanName / DurationMs / StatusCode（色块：绿=OK，红=ERROR）/ Timestamp。

支持 `trace_id` query 参数过滤（从 Overview 点击 TraceId 跳转时自动填充）。

### Metrics（指标图表）— `/metrics`

**数据源**：`useMetrics()` → `/api/metrics/`

两张 recharts `LineChart`：
- **请求延迟趋势**：X 轴时间（分钟粒度），Y 轴平均 DurationMs
- **请求吞吐量**：X 轴时间，Y 轴 requests/min

图表配置：`CartesianGrid` + `XAxis` + `YAxis` + `Tooltip` + `Line`（蓝色，`type="monotone"`）。

### Logs（日志查看）— `/logs`

**数据源**：`useLogs()` → `/api/logs/`

功能：
- 日志级别筛选按钮：ALL / INFO / WARN / ERROR（不同色块）
- 全文搜索输入框（`search` 参数）
- 日志条目：时间戳 + 级别色块 + Body 文本 + TraceId（可点击跳转 Chain）

### Chain（调用链关联）— `/chain`

**数据源**：`useCorrelate(traceId)` → `/api/correlate/{trace_id}`

**核心排障场景**：输入一个 TraceId，查看该请求的完整上下文：

1. **Span 瀑布图**：所有 spans 按层级展示（root span → child spans），显示 SpanName + DurationMs
2. **关联日志**：该 TraceId 下的所有日志条目
3. **关联 Metrics**：同服务、同时间范围内的 metrics 数据

使用场景：用户反馈"某次查询很慢" → 找到对应 TraceId → 定位到 `llm_generate` span 耗时 8 秒 → 确认是 LLM rate limit 导致。

### Infra（基础设施状态）— `/infra`

**数据源**：`/api/infra/health`（直接 fetch，不走 SWR，每 15 秒手动 interval）

5 个组件健康检查卡片：
- ClickHouse :8123
- OTel Collector :4318
- Prometheus :9090
- Loki :3100
- Demo App :8080

健康=绿色徽标，不健康=红色，轮询刷新时显示最后检查时间。

### Docs（文档）— `/docs`

**数据源**：`fetch(/docs/*.md)`（浏览器直接请求 public/ 目录静态文件）

左侧导航栏列出 9 篇文档，右侧渲染 Markdown（`react-markdown` + `remark-gfm`）。支持表格、代码块语法高亮、链接跳转。当前文档即通过此页面访问。

## 路由配置

```typescript
// App.tsx 顶部导航
const tabs = [
  { to: "/",       label: "Overview" },
  { to: "/traces", label: "Traces" },
  { to: "/metrics",label: "Metrics" },
  { to: "/logs",   label: "Logs" },
  { to: "/chain",  label: "Chain" },
  { to: "/infra",  label: "Infra" },
  { to: "/docs",   label: "Docs" },
];
```

React Router 6 使用 `<NavLink>` 自动处理激活状态（蓝色高亮）。

## 开发模式启动

```bash
cd frontend
npm install
npm run dev   # Vite dev server: http://localhost:5173
```

Vite 会自动处理 HMR（Hot Module Replacement），修改 `.tsx` 文件后即时更新。

---

→ API 接口数据格式，参见 [API 接口](api.md)  
→ 本地完整启动，参见 [部署指南](deployment.md)
