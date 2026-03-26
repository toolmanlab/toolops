# ToolOps — References

> 持续更新的参考文献库。论文、竞品、开源项目、技术博客。
> 每条标注：关联模块 + 对我们的启发/警示 + 状态（待读/已读/已应用）

---

## 📄 论文

### 可观测性 & MLOps

| 论文 | 关键发现 | 关联模块 | 对 ToolOps 的影响 | 状态 |
|------|---------|---------|------------------|------|
| [From Static Templates to Dynamic Runtime Graphs](https://arxiv.org/abs/2603.22386) (2026-03) | LLM Agent 工作流优化综述：静态模板→动态运行图 | Workflow 模板 | ToolOps 的 stacks/ 模板设计可参考"动态组合"思路 | ⏳ 待读 |
| [AI-Generated Code Is Not Reproducible (Yet)](https://arxiv.org/abs/2512.22387) (2025-12) | LLM 生成代码的依赖缺口实证 | CI/CD 模板 | ToolOps 的 CI 模板需考虑依赖锁定和可复现性 | ⏳ 待读 |

### Agent 安全

| 论文 | 关键发现 | 关联模块 | 对 ToolOps 的影响 | 状态 |
|------|---------|---------|------------------|------|
| [MCP Security Bench](https://arxiv.org/abs/2510.15994) (2025-10) | MCP 协议攻击面基准测试 | 安全配置 | ToolOps 管理的 MCP 服务需要安全默认配置 | ⏳ 待读 |
| [Agent Audit](https://arxiv.org/abs/2603.22853) (2026-03) | LLM Agent 应用安全分析系统 | 安全检查 | ToolOps 可考虑集成安全扫描模板 | ⏳ 待读 |
| [Mind Your HEARTBEAT!](https://arxiv.org/abs/2603.23064) (2026-03) | Agent 后台执行导致静默内存污染 | 运行时安全 | 部署 Agent 服务时的内存隔离配置参考 | ⏳ 待读 |

---

## 🔧 开源项目 — 竞品/参考

### 直接参考（AI 应用基础设施）

| 项目 | Stars | 定位 | 和 ToolOps 的关系 | 监控频率 |
|------|-------|------|------------------|---------|
| [Langfuse](https://github.com/langfuse/langfuse) | ~47K | MIT, LLM 可观测性 (tracing/evals/prompt mgmt) | 可作为 ToolOps 监控层的可选组件 | 月度 |
| [OpenLIT](https://github.com/openlit/openlit) | ~3K | Apache 2.0, OTel-native LLM 可观测性 | 轻量替代 Langfuse，44+ provider 支持 | 月度 |
| [LiteLLM](https://github.com/BerriAI/litellm) | ~20K | LLM 统一 API 代理 + 管理 | ToolOps 的 LLM 层可选组件 | 月度 |
| [Coolify](https://github.com/coollabsio/coolify) | ~40K | 自托管 PaaS (Heroku 替代) | 通用部署参考，但不是 AI-specific | 季度 |

### 部署平台参考

| 项目 | Stars | 参考价值 | 状态 |
|------|-------|---------|------|
| [Dify](https://github.com/langgenius/dify) | ~80K | Low-code AI 平台，Docker Compose 部署模式参考 | 已分析 |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | ~30K | 本地 RAG 平台，简洁部署流程参考 | 了解 |
| [Flowise](https://github.com/FlowiseAI/Flowise) | ~35K | 可视化 LLM 编排，Docker 部署参考 | 了解 |
| [Open WebUI](https://github.com/open-webui/open-webui) | ~70K | LLM 前端 + Ollama 管理 | UI 交互参考 |

### 上游依赖

| 项目 | 我们用的 | 监控重点 | 频率 |
|------|---------|---------|------|
| [Docker Compose](https://github.com/docker/compose) | 核心编排 | V2 新特性、profiles、include | 月度 |
| [Traefik](https://github.com/traefik/traefik) | 反向代理/负载均衡可选项 | 版本更新 | 季度 |
| [Grafana + Prometheus](https://github.com/grafana/grafana) | 监控可选组件 | LLM 相关 dashboard 模板 | 季度 |

---

## 📝 技术博客/文章

| 文章 | 来源 | 关键内容 | 对 ToolOps 的影响 |
|------|------|---------|------------------|
| ByteDance HiAgent 2.0 架构 (2026) | 内部分享 | 大规模 Agent 基础设施 | 组件编排思路参考（规模差距大但原则可借鉴） |
| Uber Michelangelo (2024) | Uber Blog | ML 平台架构 | 配置管理 + 环境切换设计参考 |
| Ramp CPO: AI 原生公司手册 (2026-03) | HN | L0-L3 AI 成熟度框架 | ToolOps 可按 L0-L3 提供不同 stack 模板 |

---

## ⚠️ 踩坑预警

| 风险 | 来源 | 预防措施 |
|------|------|---------|
| Docker Compose 组件版本冲突 | 常见运维坑 | 每个 stack 模板锁定组件版本，提供升级脚本 |
| Milvus etcd/MinIO 内存占用 | P1 实际经验 | 轻量模式默认 SQLite/本地存储，重型模式才启用 |
| LLM API key 泄露 | 常见安全问题 | .env.example + .gitignore + 启动时校验 |
| 模型下载慢/断点续传 | 国内网络 | 提供镜像源配置（HuggingFace mirror / ModelScope） |
| Langfuse 版本升级破坏 schema | 社区反馈 | pin 版本 + 数据库 migration 测试 |

---

## 📅 更新日志

- **2026-03-26**: 初始创建。纳入 3/25 竞品调研 + Pulse 论文推送
