import { useMemo } from "react";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useTraces, useMetrics } from "../lib/api";

function fmtMinute(ts: string) {
  try {
    const d = new Date(ts);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch {
    return ts;
  }
}

export default function Metrics() {
  const { data: traces, error: tracesErr, isLoading: tracesLoading } = useTraces({ limit: 5000 });
  const { data: metrics, error: metricsErr } = useMetrics();

  const { latencyData, throughputData } = useMemo(() => {
    if (!traces || traces.length === 0)
      return { latencyData: [], throughputData: [] };

    // group by minute
    const byMinute = new Map<string, number[]>();
    for (const t of traces) {
      try {
        const d = new Date(t.Timestamp);
        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        if (!byMinute.has(key)) byMinute.set(key, []);
        byMinute.get(key)!.push(t.DurationMs);
      } catch {
        // skip invalid timestamps
      }
    }

    const sorted = [...byMinute.entries()].sort((a, b) =>
      a[0].localeCompare(b[0])
    );

    const latencyData = sorted.map(([ts, durations]) => ({
      time: fmtMinute(ts),
      avg: Math.round(durations.reduce((a, b) => a + b, 0) / durations.length),
    }));

    const throughputData = sorted.map(([ts, durations]) => ({
      time: fmtMinute(ts),
      rpm: durations.length,
    }));

    return { latencyData, throughputData };
  }, [traces]);

  const metricsData = useMemo(() => {
    if (!metrics || metrics.length === 0) return [];
    return metrics.map((m) => ({
      time: fmtMinute(m.timestamp),
      value: m.value,
      name: m.metric_name,
    }));
  }, [metrics]);

  if (tracesLoading) return <div className="text-[#94a3b8]">Loading...</div>;
  if (tracesErr)
    return (
      <div className="text-[#ef4444]">Failed to load data: {tracesErr.message}</div>
    );

  return (
    <div className="space-y-6">
      {/* Latency chart */}
      <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
        <h2 className="text-lg font-semibold mb-4">
          Request Latency (avg ms / min)
        </h2>
        {latencyData.length === 0 ? (
          <div className="text-[#94a3b8]">No data</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={latencyData}>
              <defs>
                <linearGradient id="latencyGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  color: "#fff",
                }}
                formatter={(value) => [`${value}ms`, "avg"]}
              />
              <Area
                type="monotone"
                dataKey="avg"
                stroke="#f97316"
                strokeWidth={2}
                fill="url(#latencyGradient)"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Throughput chart */}
      <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
        <h2 className="text-lg font-semibold mb-4">
          Throughput (requests / min)
        </h2>
        {throughputData.length === 0 ? (
          <div className="text-[#94a3b8]">No data</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={throughputData}>
              <defs>
                <linearGradient id="throughputGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  color: "#fff",
                }}
                formatter={(value) => [`${value} req/min`, "rpm"]}
              />
              <Area
                type="monotone"
                dataKey="rpm"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#throughputGradient)"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Metrics from API */}
      {!metricsErr && metricsData.length > 0 && (
        <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
          <h2 className="text-lg font-semibold mb-4">Metrics</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={metricsData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} />
              <Tooltip
                contentStyle={{
                  background: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  color: "#fff",
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
