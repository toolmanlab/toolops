import { useState } from "react";
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
  useLLMGatewayOverview,
  useLLMGatewayRequests,
  useLLMGatewayAgents,
  useLLMGatewayLatency,
  useOpenClawOverview,
  useOpenClawAgents,
  useOpenClawTimeline,
  useOpenClawRequests,
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

// ── status code color helper ────────────────────────────────────────────────

function statusColor(code: number): string {
  if (code >= 500) return "text-[#ef4444]";
  if (code >= 400) return "text-[#f97316]";
  if (code >= 200) return "text-[#22c55e]";
  return "text-[#94a3b8]";
}

// ── main component ─────────────────────────────────────────────────────────

type Tab = "cc" | "gateway" | "openclaw";

export default function LLM() {
  const [tab, setTab] = useState<Tab>("cc");

  // CC Usage data
  const { data: overview, isLoading: ovLoading } = useLLMOverview();
  const { data: sessions, isLoading: sessLoading } = useLLMSessions(50);
  const { data: models } = useLLMModels();
  const { data: timeline } = useLLMTimeline("day");
  const { data: projects } = useLLMProjects();

  // Gateway data
  const { data: gwOverview, isLoading: gwOvLoading } = useLLMGatewayOverview();
  const { data: gwRequests, isLoading: gwReqLoading } = useLLMGatewayRequests(50);
  const { data: gwAgents } = useLLMGatewayAgents();
  const { data: gwLatency } = useLLMGatewayLatency("hour");

  // OpenClaw data
  const { data: ocOverview, isLoading: ocOvLoading } = useOpenClawOverview();
  const { data: ocAgents } = useOpenClawAgents();
  const { data: ocTimeline } = useOpenClawTimeline("hour");
  const { data: ocRequests, isLoading: ocReqLoading } = useOpenClawRequests(50);

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

  // CC stat cards
  const ccCards: StatCardProps[] = [
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

  // Gateway stat cards
  const gwCards: StatCardProps[] = [
    {
      label: "Total Requests",
      icon: "R",
      color: "text-[#3b82f6]",
      value: gwOvLoading ? "…" : fmtK(gwOverview?.total_requests ?? 0),
    },
    {
      label: "Total Tokens",
      icon: "T",
      color: "text-[#f97316]",
      value: gwOvLoading ? "…" : fmtK(gwOverview?.total_tokens ?? 0),
    },
    {
      label: "Est. Cost",
      icon: "$",
      color: "text-[#a855f7]",
      value: gwOvLoading ? "…" : fmtCost(gwOverview?.total_cost_usd ?? 0),
    },
    {
      label: "Avg Latency",
      icon: "L",
      color: "text-[#22c55e]",
      value: gwOvLoading
        ? "…"
        : `${Math.round(gwOverview?.avg_latency_ms ?? 0)} ms`,
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

  // Gateway latency: format bucket labels
  const latencyData = (gwLatency ?? []).map((b) => ({
    ...b,
    date: fmtDate(String(b.bucket)),
    p50_ms: Math.round(b.p50_ms),
    p95_ms: Math.round(b.p95_ms),
  }));

  // OpenClaw stat cards
  const ocCards: StatCardProps[] = [
    {
      label: "Total Requests",
      icon: "R",
      color: "text-[#3b82f6]",
      value: ocOvLoading ? "..." : fmtK(ocOverview?.total_requests ?? 0),
    },
    {
      label: "Total Tokens",
      icon: "T",
      color: "text-[#f97316]",
      value: ocOvLoading ? "..." : fmtK(ocOverview?.total_tokens ?? 0),
    },
    {
      label: "Est. Cost",
      icon: "$",
      color: "text-[#a855f7]",
      value: ocOvLoading ? "..." : fmtCost(ocOverview?.total_cost_usd ?? 0),
    },
    {
      label: "Avg Latency",
      icon: "L",
      color: "text-[#22c55e]",
      value: ocOvLoading
        ? "..."
        : `${Math.round(ocOverview?.avg_latency_ms ?? 0)} ms`,
    },
  ];

  // OpenClaw timeline data
  const ocTimelineData = (ocTimeline ?? []).map((b) => ({
    ...b,
    date: fmtDate(String(b.bucket)),
  }));

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold">LLM Usage</h1>
          {/* Tab switcher */}
          <div className="flex bg-[#0f172a] border border-[#334155] rounded-md overflow-hidden text-sm">
            <button
              onClick={() => setTab("cc")}
              className={`px-4 py-1.5 font-medium transition-colors ${
                tab === "cc"
                  ? "bg-[#3b82f6] text-white"
                  : "text-[#94a3b8] hover:text-white"
              }`}
            >
              CC Usage
            </button>
            <button
              onClick={() => setTab("gateway")}
              className={`px-4 py-1.5 font-medium transition-colors ${
                tab === "gateway"
                  ? "bg-[#3b82f6] text-white"
                  : "text-[#94a3b8] hover:text-white"
              }`}
            >
              Gateway
            </button>
            <button
              onClick={() => setTab("openclaw")}
              className={`px-4 py-1.5 font-medium transition-colors ${
                tab === "openclaw"
                  ? "bg-[#3b82f6] text-white"
                  : "text-[#94a3b8] hover:text-white"
              }`}
            >
              OpenClaw Agents
            </button>
          </div>
        </div>
        {tab === "cc" && (
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
        )}
      </div>

      {/* ── CC Usage tab ─────────────────────────────────────────────────── */}
      {tab === "cc" && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-4">
            {ccCards.map((c) => (
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
        </>
      )}

      {/* ── OpenClaw Agents tab ──────────────────────────────────────────── */}
      {tab === "openclaw" && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-4">
            {ocCards.map((c) => (
              <StatCard key={c.label} {...c} />
            ))}
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-2 gap-4">
            {/* Agent distribution pie */}
            <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Agent Distribution</h2>
              {!ocAgents || ocAgents.length === 0 ? (
                <div className="text-[#94a3b8]">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={ocAgents}
                      dataKey="total_tokens"
                      nameKey="agent_id"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                    >
                      {ocAgents.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Legend
                      formatter={(value, entry: any) => {
                        const total = (ocAgents ?? []).reduce((s, a) => s + a.total_tokens, 0);
                        const tokens = (entry?.payload as any)?.total_tokens ?? 0;
                        const pct = total > 0 ? ((tokens / total) * 100).toFixed(0) : "0";
                        return (
                          <span style={{ color: "#94a3b8", fontSize: 12 }}>
                            {value || "(unknown)"} ({pct}%)
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

            {/* Token timeline */}
            <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Token Timeline (hourly)</h2>
              {ocTimelineData.length === 0 ? (
                <div className="text-[#94a3b8]">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={ocTimelineData}>
                    <defs>
                      <linearGradient id="ocGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
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
                      stroke="#22c55e"
                      fill="url(#ocGrad)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Recent requests table */}
          <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Recent Requests</h2>
            {ocReqLoading ? (
              <div className="text-[#94a3b8]">Loading...</div>
            ) : !ocRequests || ocRequests.length === 0 ? (
              <div className="text-[#94a3b8]">No data</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-[#94a3b8] border-b border-[#334155]">
                    <tr>
                      <th className="py-2 pr-4">Time</th>
                      <th className="py-2 pr-4">Agent</th>
                      <th className="py-2 pr-4">Model</th>
                      <th className="py-2 pr-4">Provider</th>
                      <th className="py-2 pr-4 text-right">Tokens (In/Out)</th>
                      <th className="py-2 pr-4 text-right">Cost</th>
                      <th className="py-2 pr-4 text-right">Latency</th>
                      <th className="py-2">Trigger</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ocRequests.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-[#334155]/50 hover:bg-[#334155]/30"
                      >
                        <td className="py-2 pr-4 font-mono text-[#94a3b8] whitespace-nowrap">
                          {fmtDate(r.timestamp)}
                        </td>
                        <td className="py-2 pr-4">{r.agent_id || "—"}</td>
                        <td className="py-2 pr-4 text-[#94a3b8]">{r.model || "—"}</td>
                        <td className="py-2 pr-4 text-[#94a3b8]">{r.provider || "—"}</td>
                        <td className="py-2 pr-4 text-right font-mono text-[#94a3b8]">
                          {fmtK(r.input_tokens)} / {fmtK(r.output_tokens)}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-[#a855f7]">
                          {fmtCost(r.cost_usd ?? 0)}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono">
                          {r.latency_ms > 0 ? `${r.latency_ms} ms` : "—"}
                        </td>
                        <td className="py-2 text-[#94a3b8]">{r.trigger || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="text-xs text-[#94a3b8] mt-2">
                  Showing {ocRequests.length} requests
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Gateway tab ──────────────────────────────────────────────────── */}
      {tab === "gateway" && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-4">
            {gwCards.map((c) => (
              <StatCard key={c.label} {...c} />
            ))}
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-2 gap-4">
            {/* Latency timeline */}
            <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Latency Timeline (hourly)</h2>
              {latencyData.length === 0 ? (
                <div className="text-[#94a3b8]">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={latencyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <YAxis
                      unit=" ms"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155" }}
                      labelStyle={{ color: "#f1f5f9" }}
                      formatter={(v) => [`${v} ms`]}
                    />
                    <Legend formatter={(v) => <span style={{ color: "#94a3b8", fontSize: 12 }}>{v}</span>} />
                    <Line
                      type="monotone"
                      dataKey="p50_ms"
                      name="P50"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="p95_ms"
                      name="P95"
                      stroke="#f97316"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Agent distribution pie */}
            <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
              <h2 className="text-lg font-semibold mb-4">Agent Distribution</h2>
              {!gwAgents || gwAgents.length === 0 ? (
                <div className="text-[#94a3b8]">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={gwAgents}
                      dataKey="request_count"
                      nameKey="agent_name"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                    >
                      {gwAgents.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Legend
                      formatter={(value, entry: any) => {
                        const total = (gwAgents ?? []).reduce((s, a) => s + a.request_count, 0);
                        const cnt = (entry?.payload as any)?.request_count ?? 0;
                        const pct = total > 0 ? ((cnt / total) * 100).toFixed(0) : "0";
                        return (
                          <span style={{ color: "#94a3b8", fontSize: 12 }}>
                            {value || "(none)"} ({pct}%)
                          </span>
                        );
                      }}
                    />
                    <Tooltip
                      contentStyle={{ background: "#1e293b", border: "1px solid #334155" }}
                      formatter={(v) => [fmtK(Number(v)), "requests"]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Request table */}
          <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
            <h2 className="text-lg font-semibold mb-4">Recent Requests</h2>
            {gwReqLoading ? (
              <div className="text-[#94a3b8]">Loading…</div>
            ) : !gwRequests || gwRequests.length === 0 ? (
              <div className="text-[#94a3b8]">No data</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-[#94a3b8] border-b border-[#334155]">
                    <tr>
                      <th className="py-2 pr-4">Time</th>
                      <th className="py-2 pr-4">Agent</th>
                      <th className="py-2 pr-4">Model</th>
                      <th className="py-2 pr-4">Provider</th>
                      <th className="py-2 pr-4 text-right">Tokens (In/Out)</th>
                      <th className="py-2 pr-4 text-right">Cost</th>
                      <th className="py-2 pr-4 text-right">Latency</th>
                      <th className="py-2 pr-4 text-right">TTFB</th>
                      <th className="py-2 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gwRequests.map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-[#334155]/50 hover:bg-[#334155]/30"
                      >
                        <td className="py-2 pr-4 font-mono text-[#94a3b8] whitespace-nowrap">
                          {fmtDate(r.timestamp)}
                        </td>
                        <td className="py-2 pr-4">{r.agent_name || "—"}</td>
                        <td className="py-2 pr-4 text-[#94a3b8]">{r.model || "—"}</td>
                        <td className="py-2 pr-4 text-[#94a3b8]">{r.provider || "—"}</td>
                        <td className="py-2 pr-4 text-right font-mono text-[#94a3b8]">
                          {fmtK(r.input_tokens)} / {fmtK(r.output_tokens)}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-[#a855f7]">
                          {fmtCost(r.cost_usd ?? 0)}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono">
                          {Math.round(r.latency_ms)} ms
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-[#94a3b8]">
                          {r.ttfb_ms > 0 ? `${Math.round(r.ttfb_ms)} ms` : "—"}
                        </td>
                        <td className={`py-2 text-center font-mono font-semibold ${statusColor(r.status_code)}`}>
                          {r.status_code}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="text-xs text-[#94a3b8] mt-2">
                  Showing {gwRequests.length} requests
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
