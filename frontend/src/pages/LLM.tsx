import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  BarChart,
  Bar,
} from "recharts";
import {
  useLLMOverview,
  useLLMSessions,
  useLLMModels,
  useLLMTimeline,
  useLLMProjects,
  triggerLLMCollect,
} from "../lib/api";

// ── helpers ────────────────────────────────────────────────────────────────

function fmtK(n: number): string {
  if (n >= 1_000_000_000) return parseFloat((n / 1_000_000_000).toFixed(1)) + "B";
  if (n >= 1_000_000) return parseFloat((n / 1_000_000).toFixed(1)) + "M";
  if (n >= 1_000) return parseFloat((n / 1_000).toFixed(1)) + "K";
  return String(n);
}

function fmtCost(usd: number): string {
  if (usd >= 1000) return "$" + Math.round(usd).toLocaleString();
  return "$" + usd.toFixed(2);
}

function shortProject(p: string): string {
  if (!p) return "—";
  let normalized = p.replace(/\\/g, "/");
  if (normalized === "/Users/xuelin" || normalized === "/Users/xuelin/") {
    return "~";
  }
  if (normalized.startsWith("/Users/xuelin/")) {
    normalized = normalized.replace("/Users/xuelin/", "~/");
  }
  const parts = normalized.split("/").filter(Boolean);
  return parts.slice(-2).join("/") || normalized;
}

function fmtDate(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString("sv-SE");
  } catch {
    return ts;
  }
}

const PIE_COLORS = ["#3b82f6", "#f97316", "#22c55e", "#a855f7", "#ec4899", "#14b8a6"];

// ── stat card ──────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string;
  icon: string;
  color: string;
}

function StatCard({ label, value, icon, color }: StatCardProps) {
  return (
    <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
      <div className="text-[#94a3b8] text-sm mb-1">{label}</div>
      <div className={`text-2xl font-mono font-bold ${color}`}>
        <span className="text-lg opacity-60">{icon} </span>
        {value}
      </div>
    </div>
  );
}

// ── main component ─────────────────────────────────────────────────────────

export default function LLM() {
  const { data: overview, isLoading: ovLoading } = useLLMOverview();
  const { data: sessions, isLoading: sessLoading } = useLLMSessions(50);
  const { data: models } = useLLMModels();
  const { data: timeline } = useLLMTimeline("day");
  const { data: projects } = useLLMProjects();

  const [collecting, setCollecting] = useState(false);
  const [collectMsg, setCollectMsg] = useState<string | null>(null);

  async function handleCollect() {
    setCollecting(true);
    setCollectMsg(null);
    try {
      const result = await triggerLLMCollect();
      setCollectMsg(
        result.status === "ok"
          ? `Collected ${result.collected}, inserted ${result.inserted} records`
          : `Error: ${result.status}`
      );
    } catch (e: unknown) {
      setCollectMsg(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setCollecting(false);
    }
  }

  // Stat cards data
  const cards: StatCardProps[] = [
    {
      label: "Total Tokens",
      icon: "T",
      color: "text-[#3b82f6]",
      value: ovLoading ? "…" : fmtK(overview?.total_tokens ?? 0),
    },
    {
      label: "Total Sessions",
      icon: "S",
      color: "text-[#f97316]",
      value: ovLoading ? "…" : String(overview?.total_sessions ?? 0),
    },
    {
      label: "Top Model",
      icon: "M",
      color: "text-[#22c55e]",
      value: ovLoading ? "…" : overview?.top_model || "—",
    },
    {
      label: "Est. Cost (USD)",
      icon: "$",
      color: "text-[#a855f7]",
      value: ovLoading ? "…" : fmtCost(overview?.total_cost_usd ?? 0),
    },
  ];

  // Timeline: format bucket labels for display
  const timelineData = (timeline ?? []).map((b) => ({
    ...b,
    date: fmtDate(String(b.bucket)),
  }));

  // Projects: shorten paths for display
  const projectData = (projects ?? []).map((p) => ({
    ...p,
    label: shortProject(p.project),
  }));

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">LLM Usage</h1>
        <div className="flex items-center gap-3">
          {collectMsg && <span className="text-sm text-[#94a3b8]">{collectMsg}</span>}
          <button
            onClick={handleCollect}
            disabled={collecting}
            className="px-4 py-2 bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-50 rounded text-sm font-medium transition-colors"
          >
            {collecting ? "Collecting…" : "Collect Now"}
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {cards.map((c) => (
          <StatCard key={c.label} {...c} />
        ))}
      </div>

      {/* Token timeline */}
      <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
        <h2 className="text-lg font-semibold mb-4">Token Timeline (daily)</h2>
        {timelineData.length === 0 ? (
          <div className="text-[#94a3b8]">No data</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timelineData}>
              <defs>
                <linearGradient id="llmGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis tickFormatter={fmtK} tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155" }}
                labelStyle={{ color: "#f1f5f9" }}
                formatter={(v) => [fmtK(Number(v)), "tokens"]}
              />
              <Area
                type="monotone"
                dataKey="total_tokens"
                stroke="#3b82f6"
                fill="url(#llmGrad)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Model pie + project bar */}
      <div className="grid grid-cols-2 gap-4">
        {/* Model distribution */}
        <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
          <h2 className="text-lg font-semibold mb-4">Model Distribution</h2>
          {!models || models.length === 0 ? (
            <div className="text-[#94a3b8]">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={models}
                  dataKey="total_tokens"
                  nameKey="model"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                >
                  {models.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Legend
                  formatter={(value, entry: any) => {
                    const total = (models ?? []).reduce((s, m) => s + m.total_tokens, 0);
                    const tokens = (entry?.payload as any)?.total_tokens ?? 0;
                    const pct = total > 0 ? ((tokens / total) * 100).toFixed(0) : "0";
                    return (
                      <span style={{ color: "#94a3b8", fontSize: 12 }}>
                        {value} ({pct}%)
                      </span>
                    );
                  }}
                />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155" }}
                  formatter={(v) => [fmtK(Number(v)), "tokens"]}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Project bar chart */}
        <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
          <h2 className="text-lg font-semibold mb-4">Top Projects by Tokens</h2>
          {!projectData || projectData.length === 0 ? (
            <div className="text-[#94a3b8]">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={projectData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  type="number"
                  tickFormatter={fmtK}
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={130}
                  tick={{ fill: "#94a3b8", fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155" }}
                  formatter={(v) => [fmtK(Number(v)), "tokens"]}
                />
                <Bar dataKey="total_tokens" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Session leaderboard */}
      <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
        <h2 className="text-lg font-semibold mb-4">Session Leaderboard</h2>
        {sessLoading ? (
          <div className="text-[#94a3b8]">Loading…</div>
        ) : !sessions || sessions.length === 0 ? (
          <div className="text-[#94a3b8]">No data</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-[#94a3b8] border-b border-[#334155]">
                <tr>
                  <th className="py-2 pr-4">Session</th>
                  <th className="py-2 pr-4">Project</th>
                  <th className="py-2 pr-4">Model</th>
                  <th className="py-2 pr-4 text-right">Total Tokens</th>
                  <th className="py-2 pr-4 text-right">Cost (USD)</th>
                  <th className="py-2 pr-4 text-right">In / Out</th>
                  <th className="py-2 pr-4 text-right">Msgs</th>
                  <th className="py-2">Last Active</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s, i) => (
                  <tr
                    key={i}
                    className="border-b border-[#334155]/50 hover:bg-[#334155]/30"
                  >
                    <td
                      className="py-2 pr-4 font-mono text-[#3b82f6]"
                      title={s.session_id}
                    >
                      {s.session_id.slice(0, 8)}
                    </td>
                    <td className="py-2 pr-4 text-[#94a3b8]" title={s.project}>
                      {shortProject(s.project)}
                    </td>
                    <td className="py-2 pr-4">{s.model}</td>
                    <td className="py-2 pr-4 text-right font-mono">
                      {fmtK(s.total_tokens)}
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-[#a855f7]">
                      {fmtCost(s.cost_usd ?? 0)}
                    </td>
                    <td className="py-2 pr-4 text-right font-mono text-[#94a3b8]">
                      {fmtK(s.input_tokens)} / {fmtK(s.output_tokens)}
                    </td>
                    <td className="py-2 pr-4 text-right">{s.message_count}</td>
                    <td className="py-2 text-[#94a3b8]">{fmtDate(s.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-xs text-[#94a3b8] mt-2">
              Showing {sessions.length} sessions
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
