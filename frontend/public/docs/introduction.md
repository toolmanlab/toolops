# ToolOps 项目介绍

> Protocol-driven 的 AI 应用可观测性 sidecar 平台

## 是什么

ToolOps 是一个专为 AI 应用设计的可观测性平台，覆盖「代码部署完成 → 用户拿到响应」这段完整生命周期。它不是通用监控工具的堆砌，而是从 AI 应用的运行特征出发，重新定义了 Traces / Metrics / Logs 的采集、存储与展示方式。

核心技术栈：**OTel Collector + ClickHouse + FastAPI + React**。四层架构，每层职责清晰：

```
可视化层  →  数据存储层  →  数据采集层  →  部署管理层（开发中）
```

## 解决什么问题

AI 应用与传统 Web 应用有本质差异：

| 问题 | 传统 Web | AI 应用 |
|------|---------|---------|
| 延迟来源 | 数据库 / 网络 | LLM 推理 / 向量检索 / embedding |
| 成本指标 | RPS / 带宽 | token 消耗 / 模型调用次数 |
| 故障模式 | 500 错误 | 幻觉 / rate limit / 检索召回差 |
| 调用链结构 | 线性 HTTP | pipeline（embedding→cache→retrieval→LLM） |

现有工具（LangFuse / Phoenix / LangSmith）只做 LLM 可观测性，不管基础设施；Grafana / Datadog 是通用监控，不理解 AI 语义。ToolOps 试图填补这个中间地带。

## 目标用户

- **AI 应用开发者**：用 Python / TypeScript 构建 RAG pipeline、AI Agent、chatbot 的独立开发者
- **小团队**：5-20 人，没有专职 SRE，需要开箱即用的可观测性方案
- **接入要求**：~20 行代码 + 1 个环境变量（`OTEL_EXPORTER_OTLP_ENDPOINT`）

## 为什么不用现有工具

| 工具 | 擅长 | 缺少 |
|------|------|------|
| LangFuse | LLM 追踪、prompt 管理 | 基础设施监控、统一存储 |
| Arize Phoenix | AI 模型评估 | 部署管理、日志关联 |
| LangSmith | LangChain 生态 | 自托管、协议无关 |
| Coolify / Dokploy | 通用 PaaS 部署 | AI 应用语义、可观测性 |
| Grafana Stack | 通用可视化 | AI-specific 视图、简单接入 |

ToolOps 的目标是：**AI 应用开发者自托管的第一选择**。

## 三大设计原则

### 1. Protocol-Driven

使用行业标准协议（OpenTelemetry），而非私有 SDK。你的应用只需要标准的 OTLP exporter，不依赖 ToolOps 私有 API。未来可以无缝迁移到任何 OTel 兼容后端。

### 2. Unified Storage

Traces / Metrics / Logs 统一写入 ClickHouse，一张查询可以跨三种信号做关联。这是竞品分散存储无法做到的。

### 3. AI-Native

Dashboard 的每个页面都针对 AI 应用语义设计：RAG pipeline 分步延迟、LLM token 消耗趋势、缓存命中率、调用链关联。不是把 Grafana 改个皮。

---

→ 了解系统整体结构，参见 [架构总览](architecture.md)  
→ 3 分钟启动，参见 [部署指南](deployment.md)
