import { useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useCorrelate, type Trace } from "../lib/api";

function fmtTime(ts: string) {
  try {
    return new Date(ts).toLocaleString("sv-SE").replace("T", " ");
  } catch {
    return ts;
  }
}

const spanTypeColors: Record<string, string> = {
  embedding: "#3b82f6",
  vector_search: "#22c55e",
  llm_generate: "#f97316",
};

function getSpanColor(spanName: string): string {
  const lower = spanName.toLowerCase();
  for (const [key, color] of Object.entries(spanTypeColors)) {
    if (lower.includes(key)) return color;
  }
  return "#94a3b8";
}

function WaterfallChart({ spans }: { spans: Trace[] }) {
  const { tree, minTime, maxTime } = useMemo(() => {
    if (spans.length === 0) return { tree: [], minTime: 0, maxTime: 1 };

    const timestamps = spans.map((s) => new Date(s.Timestamp).getTime());
    const minTime = Math.min(...timestamps);
    const maxTime = Math.max(
      ...spans.map(
        (s) => new Date(s.Timestamp).getTime() + s.DurationMs
      )
    );

    // Build tree
    const spanIds = new Set(spans.map((s) => s.SpanId));
    const byParent = new Map<string, Trace[]>();
    for (const s of spans) {
      const pid = s.ParentSpanId || "";
      if (!byParent.has(pid)) byParent.set(pid, []);
      byParent.get(pid)!.push(s);
    }

    const roots = spans.filter(
      (s) => !s.ParentSpanId || !spanIds.has(s.ParentSpanId)
    );

    function flatten(span: Trace, depth: number): Array<Trace & { depth: number }> {
      const children = byParent.get(span.SpanId) || [];
      return [
        { ...span, depth },
        ...children.flatMap((c) => flatten(c, depth + 1)),
      ];
    }

    const tree = roots.flatMap((r) => flatten(r, 0));
    return { tree, minTime, maxTime };
  }, [spans]);

  const totalDuration = maxTime - minTime || 1;

  return (
    <div className="space-y-1">
      {tree.map((span, i) => {
        const startOffset = new Date(span.Timestamp).getTime() - minTime;
        const leftPct = (startOffset / totalDuration) * 100;
        const widthPct = Math.max((span.DurationMs / totalDuration) * 100, 1);
        const color = getSpanColor(span.SpanName);

        return (
          <div key={i} className="flex items-center gap-3 text-sm">
            <div
              className="shrink-0 text-right text-[#94a3b8] text-xs truncate"
              style={{ width: "180px", paddingLeft: `${span.depth * 16}px` }}
            >
              {span.SpanName}
            </div>
            <div className="flex-1 relative h-6 bg-[#0f172a] rounded overflow-hidden">
              <div
                className="absolute top-0 h-full rounded"
                style={{
                  left: `${leftPct}%`,
                  width: `${widthPct}%`,
                  backgroundColor: color,
                  opacity: 0.8,
                }}
                title={`${span.SpanName}: ${span.DurationMs}ms`}
              />
            </div>
            <div className="shrink-0 w-16 text-right text-xs font-mono text-[#94a3b8]">
              {span.DurationMs}ms
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Chain() {
  const [searchParams] = useSearchParams();
  const [inputValue, setInputValue] = useState(
    searchParams.get("trace_id") || ""
  );
  const [traceId, setTraceId] = useState<string | null>(
    searchParams.get("trace_id")
  );

  const { data, error, isLoading } = useCorrelate(traceId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTraceId(inputValue.trim() || null);
  }

  return (
    <div className="space-y-6">
      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          type="text"
          placeholder="Enter TraceId..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="bg-[#1e293b] border border-[#334155] rounded px-4 py-2 text-sm text-white flex-1 font-mono focus:outline-none focus:border-[#3b82f6]"
        />
        <button
          type="submit"
          className="bg-[#3b82f6] text-white px-6 py-2 rounded text-sm hover:bg-[#2563eb] transition-colors"
        >
          Correlate
        </button>
      </form>

      {!traceId && (
        <div className="text-[#94a3b8]">
          Enter a TraceId to view the full call chain.
        </div>
      )}

      {traceId && isLoading && (
        <div className="text-[#94a3b8]">Loading...</div>
      )}

      {traceId && error && (
        <div className="text-[#ef4444]">
          Failed to correlate: {error.message}
        </div>
      )}

      {traceId && data && (
        <>
          {/* Waterfall */}
          <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">
              Call Chain Waterfall
            </h2>
            {data.traces && data.traces.length > 0 ? (
              <>
                <div className="flex gap-4 mb-4 text-xs text-[#94a3b8]">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded" style={{ backgroundColor: "#3b82f6" }} />
                    embedding
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded" style={{ backgroundColor: "#22c55e" }} />
                    vector_search
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded" style={{ backgroundColor: "#f97316" }} />
                    llm_generate
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded" style={{ backgroundColor: "#94a3b8" }} />
                    other
                  </span>
                </div>
                <WaterfallChart spans={data.traces} />
              </>
            ) : (
              <div className="text-[#94a3b8]">No spans found</div>
            )}
          </div>

          {/* Related logs */}
          <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Related Logs</h2>
            {data.logs && data.logs.length > 0 ? (
              <div className="space-y-2">
                {data.logs.map((log, i) => (
                  <div
                    key={i}
                    className="flex gap-4 text-sm border-b border-[#334155]/50 pb-2"
                  >
                    <span className="text-[#94a3b8] shrink-0 text-xs">
                      {fmtTime(log.Timestamp)}
                    </span>
                    <span
                      className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium ${
                        log.SeverityText === "ERROR"
                          ? "bg-[#ef4444]/20 text-[#ef4444]"
                          : log.SeverityText === "WARN" ||
                              log.SeverityText === "WARNING"
                            ? "bg-[#f97316]/20 text-[#f97316]"
                            : "bg-[#3b82f6]/20 text-[#3b82f6]"
                      }`}
                    >
                      {log.SeverityText}
                    </span>
                    <span className="truncate">{log.Body}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[#94a3b8]">No related logs</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
