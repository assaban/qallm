import { useState } from "react";
import { AlertTriangle, FileCode2, Search, Shield } from "lucide-react";
import { StatCard } from "../components/Shared";
import type { SessionState } from "../hooks/useSession";
import type { Finding } from "../types";
import * as api from "../api";

const SEV_CLS: Record<string, string> = { CRITICAL: "bg-red-100 text-red-800", HIGH: "bg-orange-100 text-orange-800", MEDIUM: "bg-yellow-100 text-yellow-800", LOW: "bg-blue-100 text-blue-800" };

export default function AnalyseScreen({ state, patch }: { state: SessionState; patch: (p: Partial<SessionState>) => void }) {
  const [filter, setFilter] = useState("");
  const [sevF, setSevF] = useState("");
  const has = state.findings.length > 0 || state.summary !== null;

  async function run() {
    if (!state.sessionId) return;
    patch({ loading: true, error: null });
    try {
      const r = await api.runAnalysis(state.sessionId, state.selectedFiles);
      const rounds = await api.getAnalysisHistory(state.sessionId).catch(() => []);
      patch({ summary: r.summary, findings: r.findings, analysisRounds: rounds, loading: false });
    } catch (e: unknown) { patch({ loading: false, error: (e as Error).message }); }
  }

  const shown = state.findings.filter((f: Finding) => {
    if (sevF && f.severity !== sevF) return false;
    if (filter && !`${f.message} ${f.file} ${f.tool}`.toLowerCase().includes(filter.toLowerCase())) return false;
    return true;
  });
  const sev = state.summary?.by_severity || {};

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <h2 className="text-xl font-semibold">Static analysis finds issues</h2>
          <p className="mt-1 text-sm text-slate-500">Bandit, Radon, Ruff, TruffleHog scan {state.selectedFiles.length} file(s).</p>
        </div>
        <button onClick={run} disabled={state.loading} className="flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">
          <Search className="h-4 w-4" />{state.loading ? "Analysing..." : has ? "Re-analyse" : "Run Analysis"}
        </button>
      </div>
      {state.error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{state.error}</div>}
      {has && <>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total" value={state.summary?.total || 0} icon={AlertTriangle} />
          <StatCard label="Critical + High" value={(sev.CRITICAL || 0) + (sev.HIGH || 0)} icon={Shield} />
          <StatCard label="Medium" value={sev.MEDIUM || 0} icon={FileCode2} />
          <StatCard label="Low" value={sev.LOW || 0} icon={FileCode2} />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-3 flex flex-wrap gap-2">
            <input type="text" placeholder="Search..." value={filter} onChange={e => setFilter(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none" />
            <select value={sevF} onChange={e => setSevF(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm"><option value="">All</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select>
            <span className="self-center text-xs text-slate-500">{shown.length} of {state.findings.length}</span>
          </div>
          <div className="max-h-[400px] overflow-auto rounded-xl border border-slate-200">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 border-b bg-slate-50"><tr><th className="px-3 py-2">Sev</th><th className="px-3 py-2">Tool</th><th className="px-3 py-2">File</th><th className="px-3 py-2">Line</th><th className="px-3 py-2">Message</th></tr></thead>
              <tbody>{shown.map((f: Finding, i: number) => (
                <tr key={f.id || i} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2"><span className={`rounded-md px-2 py-0.5 text-xs font-medium ${SEV_CLS[f.severity] || ""}`}>{f.severity}</span></td>
                  <td className="px-3 py-2 text-slate-600">{f.tool}</td>
                  <td className="px-3 py-2 font-mono text-xs">{f.file || "\u2014"}</td>
                  <td className="px-3 py-2">{f.line || "\u2014"}</td>
                  <td className="px-3 py-2">{f.message}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      </>}
    </div>
  );
}
