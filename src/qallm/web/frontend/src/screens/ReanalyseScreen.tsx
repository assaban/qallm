import { RotateCw, TrendingUp, AlertTriangle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { StatCard } from "../components/Shared";
import type { SessionState } from "../hooks/useSession";
import * as api from "../api";

export default function ReanalyseScreen({ state, patch }: { state: SessionState; patch: (p: Partial<SessionState>) => void }) {
  async function run() {
    if (!state.sessionId) return;
    patch({ loading: true, error: null });
    try {
      const r = await api.runAnalysis(state.sessionId, state.selectedFiles);
      const rounds = await api.getAnalysisHistory(state.sessionId).catch(() => []);
      patch({ summary: r.summary, findings: r.findings, analysisRounds: rounds, loading: false });
    } catch (e: unknown) { patch({ loading: false, error: (e as Error).message }); }
  }

  const rounds = state.analysisRounds;
  const first = rounds[0];
  const last = rounds[rounds.length - 1];
  const improved = first && last ? first.total - last.total : 0;
  const pct = first && first.total > 0 ? Math.round((improved / first.total) * 100) : 0;

  const chartData = rounds.map(r => ({
    name: `Round ${r.round}`,
    "Critical+High": (r.by_severity.CRITICAL || 0) + (r.by_severity.HIGH || 0),
    Medium: r.by_severity.MEDIUM || 0,
    Low: r.by_severity.LOW || 0,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <h2 className="text-xl font-semibold">Re-analyse shows improvement</h2>
          <p className="mt-1 text-sm text-slate-500">Compare findings before and after repair.</p>
        </div>
        <button onClick={run} disabled={state.loading} className="flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">
          <RotateCw className="h-4 w-4" />{state.loading ? "Analysing..." : "Re-analyse"}
        </button>
      </div>
      {state.error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{state.error}</div>}
      {rounds.length >= 2 ? <>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Initial" value={first?.total || 0} icon={AlertTriangle} />
          <StatCard label="Current" value={last?.total || 0} icon={AlertTriangle} />
          <StatCard label="Improvement" value={`${pct}%`} hint={`${improved} resolved`} icon={TrendingUp} />
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 font-semibold">Findings across rounds</h3>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip />
                <Bar dataKey="Critical+High" stackId="a" fill="#ef4444" />
                <Bar dataKey="Medium" stackId="a" fill="#f59e0b" />
                <Bar dataKey="Low" stackId="a" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </> : !state.loading && (
        <div className="rounded-2xl border bg-slate-50 p-8 text-center text-sm text-slate-500">
          Run analysis at least twice (before and after repair) to see comparison.
        </div>
      )}
    </div>
  );
}
