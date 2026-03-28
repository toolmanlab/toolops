import { useState, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:9003";

interface InfraStatus {
  name: string;
  port: number;
  healthy: boolean;
}

type HealthState = "checking" | "healthy" | "unreachable";

export default function Infra() {
  const [statuses, setStatuses] = useState<Record<string, HealthState>>({});
  const [components, setComponents] = useState<InfraStatus[]>([]);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const checkAll = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/infra/health`);
      const data: InfraStatus[] = await resp.json();
      setComponents(data);
      setStatuses(
        Object.fromEntries(
          data.map((c) => [c.name, c.healthy ? "healthy" : "unreachable"])
        )
      );
    } catch {
      // API itself is down
      setStatuses((prev) =>
        Object.fromEntries(
          Object.keys(prev).map((k) => [k, "unreachable" as const])
        )
      );
    } finally {
      const now = new Date();
      setLastChecked(
        `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`
      );
    }
  }, []);

  useEffect(() => {
    checkAll();
    const interval = setInterval(checkAll, 15000);
    return () => clearInterval(interval);
  }, [checkAll]);

  // Always show ToolOps API as a component
  const allComponents = [
    ...components,
    { name: "ToolOps API", port: 9003, healthy: true },
  ];

  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">Infrastructure Status</h2>
      {lastChecked && (
        <div className="text-xs text-[#94a3b8] mb-4">Last checked: {lastChecked}</div>
      )}
      <div className="grid grid-cols-3 gap-4">
        {allComponents.map((c) => {
          const status = statuses[c.name] || (c.healthy ? "healthy" : "checking");
          return (
            <div
              key={c.name}
              className="bg-[#1e293b] border border-[#334155] rounded-lg p-5 flex items-center gap-4"
            >
              <div
                className={`w-3 h-3 rounded-full shrink-0 ${
                  status === "healthy"
                    ? "bg-[#22c55e]"
                    : status === "unreachable"
                      ? "bg-[#ef4444]"
                      : "bg-[#94a3b8] animate-pulse"
                }`}
              />
              <div>
                <div className="font-medium">{c.name}</div>
                <div className="text-xs text-[#94a3b8]">port {c.port}</div>
              </div>
              <div className="ml-auto text-sm">
                {status === "healthy" ? (
                  <span className="text-[#22c55e]">Healthy</span>
                ) : status === "unreachable" ? (
                  <span className="text-[#ef4444]">Unreachable</span>
                ) : (
                  <span className="text-[#94a3b8]">Checking...</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
