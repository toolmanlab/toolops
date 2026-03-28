import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLogs } from "../lib/api";

function fmtTime(ts: string) {
  try {
    return new Date(ts).toLocaleString("sv-SE").replace("T", " ");
  } catch {
    return ts;
  }
}

const severityColors: Record<string, string> = {
  INFO: "bg-[#3b82f6]/20 text-[#3b82f6]",
  WARN: "bg-[#f97316]/20 text-[#f97316]",
  WARNING: "bg-[#f97316]/20 text-[#f97316]",
  ERROR: "bg-[#ef4444]/20 text-[#ef4444]",
  DEBUG: "bg-[#94a3b8]/20 text-[#94a3b8]",
};

export default function Logs() {
  const [level, setLevel] = useState("ALL");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const navigate = useNavigate();

  const { data: logs, error, isLoading } = useLogs({ level, search });

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex gap-4 items-center">
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="bg-[#1e293b] border border-[#334155] rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-[#3b82f6]"
        >
          <option value="ALL">ALL</option>
          <option value="INFO">INFO</option>
          <option value="WARN">WARN</option>
          <option value="ERROR">ERROR</option>
        </select>
        <form
          className="flex gap-2 flex-1"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(searchInput);
          }}
        >
          <input
            type="text"
            placeholder="Search body text..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="bg-[#1e293b] border border-[#334155] rounded px-3 py-2 text-sm text-white flex-1 focus:outline-none focus:border-[#3b82f6]"
          />
          <button
            type="submit"
            className="bg-[#3b82f6] text-white px-4 py-2 rounded text-sm hover:bg-[#2563eb] transition-colors"
          >
            Search
          </button>
        </form>
      </div>

      {/* Logs table */}
      <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-5">
        {isLoading ? (
          <div className="text-[#94a3b8]">Loading...</div>
        ) : error ? (
          <div className="text-[#ef4444]">Failed to load logs: {error.message}</div>
        ) : !logs || logs.length === 0 ? (
          <div className="text-[#94a3b8]">No data</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-[#94a3b8] border-b border-[#334155]">
                <tr>
                  <th className="py-2 pr-4">Timestamp</th>
                  <th className="py-2 pr-4">Severity</th>
                  <th className="py-2 pr-4">ServiceName</th>
                  <th className="py-2 pr-4">Body</th>
                  <th className="py-2">TraceId</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <tr
                    key={i}
                    className="border-b border-[#334155]/50 hover:bg-[#334155]/30"
                  >
                    <td className="py-2 pr-4 text-[#94a3b8] whitespace-nowrap">
                      {fmtTime(log.Timestamp)}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          severityColors[log.SeverityText] ||
                          "bg-[#334155] text-[#94a3b8]"
                        }`}
                      >
                        {log.SeverityText}
                      </span>
                    </td>
                    <td className="py-2 pr-4">{log.ServiceName}</td>
                    <td className="py-2 pr-4 max-w-md truncate" title={log.Body}>
                      {log.Body}
                    </td>
                    <td className="py-2">
                      {log.TraceId && (
                        <button
                          className="font-mono text-[#3b82f6] hover:underline text-xs"
                          title={log.TraceId}
                          onClick={() =>
                            navigate(`/chain?trace_id=${log.TraceId}`)
                          }
                        >
                          {log.TraceId.slice(0, 8)}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-xs text-[#94a3b8] mt-2">Showing {logs.length} rows</div>
          </div>
        )}
      </div>
    </div>
  );
}
