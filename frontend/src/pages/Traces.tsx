import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTraces, type Trace } from "../lib/api";

function fmtTime(ts: string) {
  try {
    return new Date(ts).toLocaleString("sv-SE").replace("T", " ");
  } catch {
    return ts;
  }
}

function SpanTree({ spans }: { spans: Trace[] }) {
  const byParent = new Map<string, Trace[]>();
  for (const s of spans) {
    const pid = s.ParentSpanId || "";
    if (!byParent.has(pid)) byParent.set(pid, []);
    byParent.get(pid)!.push(s);
  }

  // find root spans (no parent or parent not in this set)
  const spanIds = new Set(spans.map((s) => s.SpanId));
  const roots = spans.filter(
    (s) => !s.ParentSpanId || !spanIds.has(s.ParentSpanId)
  );

  function renderSpan(span: Trace, depth: number): React.ReactNode {
    const children = byParent.get(span.SpanId) || [];
    return (
      <div key={span.SpanId}>
        <div
          className="flex items-center gap-3 py-1.5 hover:bg-[#334155]/30 px-2 rounded"
          style={{ paddingLeft: `${depth * 24 + 8}px` }}
        >
          {depth > 0 && (
            <span className="text-[#334155]">{"└─"}</span>
          )}
          <span
            className={
              span.StatusCode === "ERROR"
                ? "text-[#ef4444]"
                : span.StatusCode === "OK"
                  ? "text-[#22c55e]"
                  : "text-[#94a3b8]"
            }
          >
            {span.SpanName}
          </span>
          <span className="font-mono text-[#94a3b8] text-xs">
            {Math.round(span.DurationMs)}ms
          </span>
          {span.SpanAttributes &&
            Object.entries(span.SpanAttributes).map(([k, v]) => (
              <span
                key={k}
                className="text-xs bg-[#334155] px-1.5 py-0.5 rounded text-[#94a3b8]"
              >
                {k}={v}
              </span>
            ))}
        </div>
        {children.map((c) => renderSpan(c, depth + 1))}
      </div>
    );
  }

  return <div className="mt-2">{roots.map((r) => renderSpan(r, 0))}</div>;
}

export default function Traces() {
  const [searchParams] = useSearchParams();
  const paramTraceId = searchParams.get("trace_id");
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(
    paramTraceId
  );

  const { data: traces, error, isLoading } = useTraces({ limit: 50 });
  const { data: expandedSpans } = useTraces(
    expandedTraceId ? { trace_id: expandedTraceId } : undefined
  );

  // group traces to get unique trace IDs for the list
  const uniqueTraces = traces
    ? Array.from(
        new Map(traces.map((t) => [t.TraceId, t])).values()
      )
    : [];

  return (
    <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
      <h2 className="text-lg font-semibold mb-4">Traces</h2>
      {isLoading ? (
        <div className="text-[#94a3b8]">Loading...</div>
      ) : error ? (
        <div className="text-[#ef4444]">Failed to load traces: {error.message}</div>
      ) : uniqueTraces.length === 0 ? (
        <div className="text-[#94a3b8]">No data</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-[#94a3b8] border-b border-[#334155]">
              <tr>
                <th className="py-2 pr-4">Timestamp</th>
                <th className="py-2 pr-4">TraceId</th>
                <th className="py-2 pr-4">ServiceName</th>
                <th className="py-2 pr-4">SpanName</th>
                <th className="py-2 pr-4 text-right">DurationMs</th>
                <th className="py-2">StatusCode</th>
              </tr>
            </thead>
            <tbody>
              {uniqueTraces.map((t) => (
                <tr key={t.TraceId} className="group">
                  <td colSpan={6} className="p-0">
                    <div
                      className="flex cursor-pointer border-b border-[#334155]/50 hover:bg-[#334155]/30"
                      onClick={() =>
                        setExpandedTraceId(
                          expandedTraceId === t.TraceId ? null : t.TraceId
                        )
                      }
                    >
                      <div className="py-2 pr-4 pl-2 flex-none w-44 text-[#94a3b8]">
                        {fmtTime(t.Timestamp)}
                      </div>
                      <div
                        className="py-2 pr-4 flex-none w-28 font-mono text-[#3b82f6]"
                        title={t.TraceId}
                      >
                        {t.TraceId.slice(0, 8)}
                      </div>
                      <div className="py-2 pr-4 flex-1">{t.ServiceName}</div>
                      <div className="py-2 pr-4 flex-1">{t.SpanName}</div>
                      <div className="py-2 pr-4 flex-none w-24 text-right font-mono">
                        {Math.round(t.DurationMs)}ms
                      </div>
                      <div className="py-2 flex-none w-20">
                        <span
                          className={
                            t.StatusCode === "ERROR"
                              ? "text-[#ef4444]"
                              : t.StatusCode === "OK"
                                ? "text-[#22c55e]"
                                : "text-[#94a3b8]"
                          }
                        >
                          {t.StatusCode}
                        </span>
                      </div>
                    </div>
                    {expandedTraceId === t.TraceId && (
                      <div className="bg-[#0f172a] border-t border-[#334155] p-4">
                        {expandedSpans && expandedSpans.length > 0 ? (
                          <SpanTree spans={expandedSpans} />
                        ) : (
                          <div className="text-[#94a3b8] text-sm">
                            Loading spans...
                          </div>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-[#94a3b8] mt-2">Showing {uniqueTraces.length} rows</div>
        </div>
      )}
    </div>
  );
}
