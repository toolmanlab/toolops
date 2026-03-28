import { NavLink, Outlet } from "react-router-dom";

const tabs = [
  { to: "/", label: "Overview" },
  { to: "/traces", label: "Traces" },
  { to: "/metrics", label: "Metrics" },
  { to: "/logs", label: "Logs" },
  { to: "/chain", label: "Chain" },
  { to: "/infra", label: "Infra" },
  { to: "/llm", label: "LLM" },
  { to: "/docs", label: "Docs" },
];

export default function App() {
  return (
    <div className="min-h-screen bg-[#0f172a] text-white">
      <nav className="border-b border-[#334155] bg-[#1e293b] px-6 py-3 flex items-center gap-8">
        <span className="text-lg font-bold tracking-wide text-[#3b82f6]">
          ToolOps
        </span>
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.to === "/"}
              className={({ isActive }) =>
                `px-4 py-2 rounded text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-[#3b82f6] text-white"
                    : "text-[#94a3b8] hover:text-white hover:bg-[#334155]"
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  );
}
