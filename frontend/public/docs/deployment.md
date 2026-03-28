# 部署指南

> 3 步启动完整 ToolOps 栈

## Quick Start

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/toolops.git
cd toolops

# 2. 复制环境变量配置（可选，默认值开箱即用）
cp .env.example .env

# 3. 启动全栈
docker compose up -d
```

等待约 30 秒（ClickHouse healthcheck 通过后其他服务才启动），然后访问：

- **Dashboard**：`http://localhost:5173`（开发模式）或构建后静态文件
- **API**：`http://localhost:9003`
- **API 文档**：`http://localhost:9003/docs`

Demo App 启动后会自动产生流量，无需手动触发。

## docker-compose.yml 6 服务解读

```yaml
services:
  clickhouse:    # 统一存储
  otel-collector:# 遥测数据收集
  prometheus:    # 指标拉取
  loki:          # 日志收集（可选）
  demo-app:      # 模拟 RAG 应用
  toolops-api:   # Dashboard 后端
```

### 启动顺序（依赖链）

```
clickhouse (healthcheck: SELECT 1)
    ↓
otel-collector (depends_on: clickhouse healthy)
    ↓
demo-app (depends_on: otel-collector started)
    ↓
prometheus (depends_on: demo-app healthy)
toolops-api (depends_on: clickhouse healthy)
```

### ClickHouse

```yaml
clickhouse:
  image: clickhouse/clickhouse-server:24
  ports:
    - "8123:8123"   # HTTP API（API 服务使用）
    - "9002:9000"   # Native TCP（OTel Collector 使用）
  volumes:
    - clickhouse-data:/var/lib/clickhouse      # 数据持久化
    - ./toolops/storage/schema.sql:/docker-entrypoint-initdb.d/schema.sql:ro
  environment:
    CLICKHOUSE_DB: toolops
    CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT: 1
```

`schema.sql` 挂载到 `initdb.d/` 目录，ClickHouse 首次启动时自动执行。

### OTel Collector

```yaml
otel-collector:
  image: otel/opentelemetry-collector-contrib:latest
  command: ["--config=/etc/otel-collector-config.yaml"]
  ports:
    - "4317:4317"   # OTLP gRPC
    - "4318:4318"   # OTLP HTTP
```

使用 `contrib` 版本（包含 ClickHouse exporter），而非 `otel/opentelemetry-collector`（基础版无 ClickHouse 支持）。

### Demo App

```yaml
demo-app:
  build: ./demo-app
  ports:
    - "8081:8080"     # 宿主机 8081 映射容器内 8080
  environment:
    OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    DEMO_SCENARIO: ${DEMO_SCENARIO:-normal}
    PORT: 8080
```

默认使用 `normal` 场景，可通过 `.env` 文件的 `DEMO_SCENARIO` 变量切换。

### toolops-api

```yaml
toolops-api:
  build:
    context: .
    dockerfile: Dockerfile
  ports:
    - "9003:9000"    # 宿主机 9003 映射容器内 9000
  volumes:
    - ./toolops:/app/toolops:ro   # 开发模式：代码热更新
  environment:
    CLICKHOUSE_HOST: clickhouse
    CLICKHOUSE_PORT: 8123
    CLICKHOUSE_DATABASE: toolops
```

## 端口映射表

| 服务 | 容器内端口 | 宿主机端口 | 冲突说明 |
|------|-----------|-----------|---------|
| ClickHouse HTTP | 8123 | 8123 | 无冲突 |
| ClickHouse TCP | 9000 | **9002** | 避让 MinIO :9000 |
| OTel gRPC | 4317 | 4317 | 无冲突 |
| OTel HTTP | 4318 | 4318 | 无冲突 |
| Prometheus | 9090 | 9090 | 无冲突 |
| Loki | 3100 | 3100 | 无冲突 |
| demo-app | 8080 | **8081** | 避让 MCP/本地 :8080 |
| toolops-api | 9000 | **9003** | 避让 MinIO Console :9001 |
| frontend (dev) | 5173 | 5173 | 无冲突 |

> **端口冲突说明**：本机环境已有 :8080 (MCP Server)、:9000/:9001 (MinIO)，ToolOps 做了映射避让。如果你的环境没有这些冲突，可以在 `docker-compose.yml` 中恢复标准端口。

## 环境变量

完整配置见 `.env.example`：

```bash
# ClickHouse 连接（toolops-api 使用）
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=toolops

# API 服务地址
API_HOST=0.0.0.0
API_PORT=9000

# Demo App
DEMO_SCENARIO=normal            # 可选：normal/slow_retrieval/llm_rate_limit/...
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Docker Compose 内部容器间通信使用 Docker 网络（服务名作为 hostname），不受宿主机端口映射影响。

## Dev 模式（代码热更新）

`toolops-api` 服务挂载了 `./toolops:/app/toolops:ro`，修改 Python 代码后只需重启容器即可生效（无需重新 build）：

```bash
docker compose restart toolops-api
```

前端开发模式直接在宿主机运行 Vite dev server：

```bash
cd frontend
npm run dev   # http://localhost:5173
```

Vite 会将 `/api/*` 请求代理到 `http://localhost:9003`（需确认 `vite.config.ts` 中的 proxy 配置）。

## 常见问题

### Q: ClickHouse 启动失败，日志显示端口占用

检查 :8123 或 :9002 是否被其他进程占用：

```bash
lsof -i :8123
lsof -i :9002
```

### Q: Dashboard 没有数据

1. 确认所有服务健康：`docker compose ps`
2. 查看 demo-app 日志确认有请求在产生：`docker compose logs demo-app -f`
3. 查看 OTel Collector 日志确认数据写入：`docker compose logs otel-collector -f`
4. 直接查询 ClickHouse 验证数据：`curl "http://localhost:8123/?query=SELECT+count()+FROM+toolops.traces"`

### Q: Chain 页面日志与 Traces 无法关联

OTel LoggingHandler 只在 span context 活跃时才能注入 TraceId。确认 demo-app 的日志是在 `with tracer.start_as_current_span(...)` 块内发出的。

### Q: 切换 DEMO_SCENARIO 后没有效果

需要重建容器（不只是 restart）：

```bash
DEMO_SCENARIO=cascade_failure docker compose up -d --force-recreate demo-app
```

### Q: 前端无法连接 API（CORS 错误）

确认 `toolops/api/app.py` 的 `allow_origins` 包含你的前端地址。默认允许 `:3001` 和 `:5173`。

---

→ 环境变量详细说明，参见 [配置参考](configuration.md)  
→ 各组件功能介绍，参见 [架构总览](architecture.md)
