import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ── 文档列表（后续加文档只需：放文件到 public/docs/ + 这里加一行）──────────
const DOCS = [
  { name: "项目介绍", path: "/docs/introduction.md" },
  { name: "架构总览", path: "/docs/architecture.md" },
  { name: "数据采集层", path: "/docs/collector.md" },
  { name: "数据存储层", path: "/docs/storage.md" },
  { name: "API 接口", path: "/docs/api.md" },
  { name: "前端页面", path: "/docs/frontend.md" },
  { name: "Demo App", path: "/docs/demo-app.md" },
  { name: "部署指南", path: "/docs/deployment.md" },
  { name: "配置参考", path: "/docs/configuration.md" },
  { name: "toolops.yaml 规范", path: "/docs/topology.md" },
  { name: "LLM Intelligence", path: "/docs/llm-intelligence.md" },
];

// ─────────────────────────────────────────────────────────────────────────────

export default function Docs() {
  const [selectedDoc, setSelectedDoc] = useState(DOCS[0]);
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(selectedDoc.path)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.text();
      })
      .then((text) => {
        setContent(text);
        setLoading(false);
      })
      .catch((err) => {
        setError(String(err));
        setLoading(false);
      });
  }, [selectedDoc]);

  return (
    <div className="flex gap-6 h-full">
      {/* ── 左侧侧边栏 ───────────────────────────────────────────────────── */}
      <aside className="w-48 shrink-0">
        <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-3 sticky top-0">
          <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wider mb-3 px-1">
            Documents
          </div>
          <nav className="flex flex-col gap-1">
            {DOCS.map((doc) => (
              <button
                key={doc.path}
                onClick={() => setSelectedDoc(doc)}
                className={`text-left px-3 py-2 rounded-md text-sm transition-colors ${
                  selectedDoc.path === doc.path
                    ? "bg-[#1d3a5c] text-[#38bdf8] font-medium"
                    : "text-[#94a3b8] hover:bg-[#0f172a] hover:text-white"
                }`}
              >
                {doc.name}
              </button>
            ))}
          </nav>
        </div>
      </aside>

      {/* ── 右侧内容区 ───────────────────────────────────────────────────── */}
      <main className="flex-1 min-w-0">
        <div className="bg-[#1e293b] border border-[#334155] rounded-lg p-8">
          {loading && (
            <div className="flex items-center gap-3 text-[#64748b] text-sm">
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Loading…
            </div>
          )}
          {error && (
            <div className="text-red-400 text-sm">
              Failed to load document: {error}
            </div>
          )}
          {!loading && !error && (
            <div className="prose prose-invert prose-sm max-w-none prose-headings:text-slate-100 prose-a:text-sky-400 prose-code:text-sky-300 prose-pre:bg-slate-950 prose-pre:border prose-pre:border-slate-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
