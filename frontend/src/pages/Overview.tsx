import { useOverview, useTraces } from "../lib/api";

const statCards = [
  {
    key: "total_requests" as const,
    label: "Total Requests",
    icon: "# ",
    color: "text-[#3b82f6]",
    format: (v: number) => v.toLocaleString(),
  },
  {
    key: "avg_latency_ms" as const,
    label: "Avg Latency (ms)",
    icon: "~ ",
    color: "text-[#f97316]",
    format: (v: number) => v.toFixed(1),
  },
  {
    key: "error_rate" as const,
    label: "Error Rate (%)",
    icon: "! ",
    color: "text-[#ef4444]",
    format: (v: number) => v.toFixed(2),
  },
  {
    key: "cache_hit_rate" as const,
    label: "Cache Hit Rate (%)",
    icon: "$ ",
    color: "text-[#22c55e]",
    format: (v: number) => v.toFixed(2),
  },
];

function fmtTime(ts: string) {
  try {
    return new Date(ts).toLocaleString("sv-SE").replace("T", " ");
  } catch {
    return ts;
  }
}

export default function Overview() {
  const { data: overview, error: overviewErr, isLoading: overviewLoading } = useOverview();
  const { data: traces, error: tracesErr, isLoading: tracesLoading } = useTraces({ limit: 10 });

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div
            key={card.key}
            className="bg-[#1e293b] border border-[#334155] rounded-lg p-5"
          >
            <div className="text-[#94a3b8] text-sm mb-1">{card.label}</div>
            {overviewLoading ? (
              <div className="text-[#94a3b8] text-sm">Loading...</div>
            ) : overviewErr ? (
              <div className="text-[#ef4444] text-sm">Error</div>
            ) : (
              <div className={`text-2xl font-mono font-bold ${card.color}`}>
                <span className="text-lg opacity-60">{card.icon}</span>
                {overview ? card.format(overview[card.key]) : "--"}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Recent Traces */}
      <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
        <h2 className="text-lg font-semibold mb-4">Recent Traces</h2>
        {tracesLoading ? (
          <div className="text-[#94a3b8]">Loading...</div>
        ) : tracesErr ? (
          <div className="text-[#ef4444]">Failed to load traces: {tracesErr.message}</div>
        ) : !traces || traces.length === 0 ? (
          <div className="text-[#94a3b8]">No data</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-[#94a3b8] border-b border-[#334155]">
                <tr>
                  <th className="py-2 pr-4">TraceId</th>
                  <th className="py-2 pr-4">ServiceName</th>
                  <th className="py-2 pr-4">SpanName</th>
                  <th className="py-2 pr-4 text-right">DurationMs</th>
                  <th className="py-2 pr-4">StatusCode</th>
                  <th className="py-2">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {traces.map((t, i) => (
                  <tr key={i} className="border-b border-[#334155]/50 hover:bg-[#334155]/30">
                    <td className="py-2 pr-4 font-mono text-[#3b82f6]" title={t.TraceId}>
                      {t.TraceId.slice(0, 8)}
                    </td>
                    <td className="py-2 pr-4">{t.ServiceName}</td>
                    <td className="py-2 pr-4">{t.SpanName}</td>
                    <td className="py-2 pr-4 text-right font-mono">{t.DurationMs}</td>
                    <td className="py-2 pr-4">
                      <span
                        className={
                          t.StatusCode === "ERROR"
                            ? "text-[#ef4444]"
                            : "text-[#22c55e]"
                        }
                      >
                        {t.StatusCode}
                      </span>
                    </td>
                    <td className="py-2 text-[#94a3b8]">{fmtTime(t.Timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
