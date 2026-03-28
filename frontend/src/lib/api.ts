import useSWR from "swr";

const API_BASE = "http://localhost:9003";

const fetcher = (url: string) =>
  fetch(`${API_BASE}${url}`).then((res) => {
    if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
    return res.json();
  });

const swrOptions = { refreshInterval: 10000 };

export function useOverview() {
  return useSWR<{
    total_requests: number;
    avg_latency_ms: number;
    error_rate: number;
    cache_hit_rate: number;
  }>("/api/overview/", fetcher, swrOptions);
}

export interface Trace {
  TraceId: string;
  SpanId: string;
  ParentSpanId: string;
  ServiceName: string;
  SpanName: string;
  DurationMs: number;
  StatusCode: string;
  Timestamp: string;
  SpanAttributes: Record<string, string>;
}

export function useTraces(params?: {
  limit?: number;
  trace_id?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.trace_id) searchParams.set("trace_id", params.trace_id);
  const qs = searchParams.toString();
  const key = `/api/traces/${qs ? `?${qs}` : ""}`;
  return useSWR<Trace[]>(key, fetcher, swrOptions);
}

export interface Metric {
  metric_name: string;
  value: number;
  timestamp: string;
  labels: Record<string, string>;
}

export function useMetrics(params?: { name?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.name) searchParams.set("name", params.name);
  const qs = searchParams.toString();
  const key = `/api/metrics/${qs ? `?${qs}` : ""}`;
  return useSWR<Metric[]>(key, fetcher, swrOptions);
}

export interface LogEntry {
  Timestamp: string;
  SeverityText: string;
  ServiceName: string;
  Body: string;
  TraceId: string;
}

export function useLogs(params?: { level?: string; search?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.level && params.level !== "ALL")
    searchParams.set("level", params.level);
  if (params?.search) searchParams.set("search", params.search);
  const qs = searchParams.toString();
  const key = `/api/logs/${qs ? `?${qs}` : ""}`;
  return useSWR<LogEntry[]>(key, fetcher, swrOptions);
}

export interface CorrelateResult {
  traces: Trace[];
  logs: LogEntry[];
}

export function useCorrelate(traceId: string | null) {
  return useSWR<CorrelateResult>(
    traceId ? `/api/correlate/${traceId}` : null,
    fetcher,
    swrOptions
  );
}

export async function checkHealth(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}
