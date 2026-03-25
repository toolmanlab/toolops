# ToolOps

> AI app infrastructure, plug and play.

**ToolOps** is a composable DevOps toolkit for AI applications. Pick the components you need, generate a production-ready stack, and deploy — locally or to the cloud — in minutes.

🚧 **Status: Planning — Under design**

## The Problem

Building an AI application means wiring together 5-10 services: API server, vector database, cache, metadata store, LLM inference, monitoring, CI/CD. Every developer does this from scratch, copy-pasting Docker Compose files and stitching together configs.

The result: fragile setups that work on "my machine" but break everywhere else, with no observability, no migration path, and no documentation of why anything was chosen.

## The Solution

ToolOps provides **composable, pre-configured infrastructure components** for AI applications:

- **Pick your stack** — Choose from pluggable components (vector DB, cache, monitoring, CI/CD)
- **Generate configs** — Get a production-ready Docker Compose + environment configs
- **Deploy anywhere** — Same stack runs locally, on a VPS, or in the cloud
- **Migrate easily** — Scripts to move from local dev to cloud production

## Design Principles

1. **Plug and play.** Every component is optional and swappable. Need Qdrant instead of Milvus? Swap one directory.
2. **Local-first, cloud-ready.** Develop locally with `docker compose up`. Deploy to production with the same configs + env overrides.
3. **No vendor lock-in.** Standard Docker Compose, standard CI/CD, standard monitoring. No proprietary abstractions.
4. **Opinionated defaults, full escape hatches.** Sensible defaults for common AI app patterns, but everything is customizable.

## Components (Planned)

| Category | Options |
|---|---|
| Vector DB | Milvus, Qdrant, pgvector |
| Database | PostgreSQL, SQLite |
| Cache | Redis, None |
| LLM Serving | Ollama, vLLM, API-only |
| Monitoring | Langfuse, Grafana stack, None |
| CI/CD | GitHub Actions, GitLab CI |

## Usage (Planned)

```bash
# Initialize a new AI app stack
toolops init my-rag-app

# Start locally
toolops up

# Deploy to server
toolops deploy --target server --host my-vps.com
```

## Roadmap

- **Phase 1:** Core component templates + Docker Compose generation
- **Phase 2:** CLI tool (`toolops init/up/deploy`)
- **Phase 3:** Migration scripts (local → cloud)
- **Phase 4:** Monitoring dashboards + alert templates

## Related Projects

- [ToolRef](https://github.com/toolmanlab/toolref) — The reference engine for AI Agents (runs on ToolOps)

## License

MIT

---

*Built by [Toolman Lab](https://github.com/toolmanlab) — where tools get serious.*
