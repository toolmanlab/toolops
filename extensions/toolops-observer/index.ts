import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LLMInputEvent {
  runId: string;
  sessionId: string;
  provider: string;
  model: string;
  systemPrompt: string;
  prompt: string;
  historyMessages: unknown[];
  imagesCount: number;
}

interface LLMOutputEvent {
  runId: string;
  sessionId: string;
  provider: string;
  model: string;
  assistantTexts: string[];
  lastAssistant: string;
  usage: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
    total: number;
  };
}

interface EventContext {
  agentId: string;
  sessionKey: string;
  sessionId: string;
  workspaceDir: string;
  messageProvider: string;
  trigger: string;
  channelId: string;
}

interface ObserverRecord {
  run_id: string;
  session_id: string;
  agent_id: string;
  session_key: string;
  provider: string;
  model: string;
  channel: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
  images_count: number;
  prompt_length: number;
  system_prompt_length: number;
  history_messages_count: number;
  trigger: string;
}

// ---------------------------------------------------------------------------
// Pricing (USD per million tokens)
// ---------------------------------------------------------------------------

interface ModelPricing {
  input: number;
  output: number;
  cacheWrite: number;
  cacheRead: number;
}

const PRICING_TABLE: Record<string, ModelPricing> = {
  "claude-opus-4-6": { input: 5.00, output: 25.00, cacheWrite: 10.00, cacheRead: 0.50 },
  "claude-sonnet-4-6": { input: 3.00, output: 15.00, cacheWrite: 6.00, cacheRead: 0.30 },
  "claude-haiku-4-5": { input: 1.00, output: 5.00, cacheWrite: 2.00, cacheRead: 0.10 },
  "kimi-k2.5": { input: 0.60, output: 3.00, cacheWrite: 0.60, cacheRead: 0.10 },
  "glm-4-flash": { input: 0, output: 0, cacheWrite: 0, cacheRead: 0 },
};

function calcCost(
  model: string,
  inputTokens: number,
  outputTokens: number,
  cacheReadTokens: number,
  cacheWriteTokens: number,
): number {
  const pricing = PRICING_TABLE[model];
  if (!pricing) return 0;
  const perM = 1_000_000;
  return (
    (inputTokens * pricing.input) / perM +
    (outputTokens * pricing.output) / perM +
    (cacheReadTokens * pricing.cacheRead) / perM +
    (cacheWriteTokens * pricing.cacheWrite) / perM
  );
}

// ---------------------------------------------------------------------------
// ClickHouse HTTP writer
// ---------------------------------------------------------------------------

const CLICKHOUSE_URL = "http://localhost:8123/?database=toolops";
const CLICKHOUSE_TABLE = "llm_openclaw";

async function flushToClickHouse(records: ObserverRecord[]): Promise<void> {
  if (records.length === 0) return;

  const lines = records
    .map((r) => JSON.stringify(r))
    .join("\n");

  const query = `INSERT INTO ${CLICKHOUSE_TABLE} FORMAT JSONEachRow`;

  const response = await fetch(
    `${CLICKHOUSE_URL}/?query=${encodeURIComponent(query)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-ndjson" },
      body: lines,
    },
  );

  if (!response.ok) {
    const text = await response.text().catch(() => "(no body)");
    throw new Error(`ClickHouse write failed: ${response.status} ${text}`);
  }
}

// ---------------------------------------------------------------------------
// Buffer
// ---------------------------------------------------------------------------

const FLUSH_BATCH_SIZE = 10;
const FLUSH_INTERVAL_MS = 5000;

const buffer: ObserverRecord[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleFlush(): void {
  if (flushTimer !== null) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    drainBuffer();
  }, FLUSH_INTERVAL_MS);
}

function drainBuffer(): void {
  if (buffer.length === 0) return;
  const batch = buffer.splice(0, buffer.length);
  flushToClickHouse(batch).catch((err: unknown) => {
    console.warn("[toolops-observer] ClickHouse flush error:", err);
  });
}

function pushRecord(record: ObserverRecord): void {
  buffer.push(record);
  if (buffer.length >= FLUSH_BATCH_SIZE) {
    if (flushTimer !== null) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    drainBuffer();
  } else {
    scheduleFlush();
  }
}

// ---------------------------------------------------------------------------
// Plugin entry
// ---------------------------------------------------------------------------

// In-flight metadata captured from llm_input
interface InputMeta {
  startTime: number;
  imagesCount: number;
  promptLength: number;
  systemPromptLength: number;
  historyMessagesCount: number;
}

const inputMeta = new Map<string, InputMeta>();

export default definePluginEntry({
  id: "toolops-observer",
  name: "ToolOps Observer",
  description: "LLM usage observer for ToolOps dashboard",
  register(api) {
    api.on("llm_input", (event: LLMInputEvent, _ctx: EventContext) => {
      try {
        inputMeta.set(event.runId, {
          startTime: Date.now(),
          imagesCount: event.imagesCount ?? 0,
          promptLength: event.prompt?.length ?? 0,
          systemPromptLength: event.systemPrompt?.length ?? 0,
          historyMessagesCount: event.historyMessages?.length ?? 0,
        });
      } catch (err: unknown) {
        console.warn("[toolops-observer] llm_input handler error:", err);
      }
    });

    api.on("llm_output", (event: LLMOutputEvent, ctx: EventContext) => {
      try {
        const now = Date.now();
        const meta = inputMeta.get(event.runId);
        const latencyMs = meta ? now - meta.startTime : 0;
        inputMeta.delete(event.runId);

        const usage = event.usage ?? { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 };
        const costUsd = calcCost(
          event.model,
          usage.input ?? 0,
          usage.output ?? 0,
          usage.cacheRead ?? 0,
          usage.cacheWrite ?? 0,
        );

        const record: ObserverRecord = {
          run_id: event.runId ?? "",
          session_id: event.sessionId ?? ctx.sessionId ?? "",
          agent_id: ctx.agentId ?? "",
          session_key: ctx.sessionKey ?? "",
          provider: event.provider ?? "",
          model: event.model ?? "",
          channel: ctx.channelId ?? "",
          input_tokens: usage.input ?? 0,
          output_tokens: usage.output ?? 0,
          cache_read_tokens: usage.cacheRead ?? 0,
          cache_write_tokens: usage.cacheWrite ?? 0,
          total_tokens: usage.total ?? 0,
          cost_usd: costUsd,
          latency_ms: latencyMs,
          images_count: meta?.imagesCount ?? 0,
          prompt_length: meta?.promptLength ?? 0,
          system_prompt_length: meta?.systemPromptLength ?? 0,
          history_messages_count: meta?.historyMessagesCount ?? 0,
          trigger: ctx.trigger ?? "",
        };

        pushRecord(record);
      } catch (err: unknown) {
        console.warn("[toolops-observer] llm_output handler error:", err);
      }
    });
  },
});
