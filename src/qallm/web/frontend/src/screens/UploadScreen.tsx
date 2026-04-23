import { useRef, useState } from "react";
import { Upload, GitBranch } from "lucide-react";
import type { SessionState } from "../hooks/useSession";
import * as api from "../api";

export default function UploadScreen({ state, patch }: { state: SessionState; patch: (p: Partial<SessionState>) => void }) {
  const [mode, setMode] = useState<"zip" | "repo">("zip");
  const [repoUrl, setRepoUrl] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    patch({ loading: true, error: null });
    try {
      const sid = await api.uploadZip(file);
      const files = await api.getFiles(sid);
      patch({ sessionId: sid, files, selectedFiles: files, loading: false, step: 2 });
    } catch (e: unknown) { patch({ loading: false, error: (e as Error).message }); }
  }

  async function handleClone() {
    if (!repoUrl.trim()) return;
    patch({ loading: true, error: null });
    try {
      const sid = await api.cloneRepo(repoUrl);
      const files = await api.getFiles(sid);
      patch({ sessionId: sid, files, selectedFiles: files, loading: false, step: 2 });
    } catch (e: unknown) { patch({ loading: false, error: (e as Error).message }); }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Here's code with problems</h2>
        <p className="mt-1 text-sm text-slate-500">Upload a ZIP or clone a repository to start the pipeline.</p>
        <div className="mt-5 flex gap-2">
          <button onClick={() => setMode("zip")} className={`flex-1 rounded-xl border px-3 py-2 text-sm font-medium transition ${mode === "zip" ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200"}`}>ZIP Upload</button>
          <button onClick={() => setMode("repo")} className={`flex-1 rounded-xl border px-3 py-2 text-sm font-medium transition ${mode === "repo" ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200"}`}>Git Repository</button>
        </div>
        {mode === "zip" ? (
          <label className="mt-5 flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center transition hover:border-slate-500">
            <Upload className="mb-3 h-8 w-8 text-slate-400" />
            <div className="font-medium">Drop source code here</div>
            <div className="mt-1 text-sm text-slate-500">ZIP with Python files or notebooks</div>
            <input ref={fileRef} type="file" accept=".zip" className="hidden" onChange={handleUpload} />
          </label>
        ) : (
          <div className="mt-5 space-y-3 rounded-2xl border bg-slate-50 p-5">
            <div className="flex items-center gap-2 text-sm font-medium"><GitBranch className="h-4 w-4" /> Repository URL</div>
            <input type="text" value={repoUrl} onChange={e => setRepoUrl(e.target.value)} placeholder="https://github.com/owner/repo" className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" />
            <button onClick={handleClone} disabled={state.loading} className="rounded-xl bg-slate-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50">{state.loading ? "Cloning..." : "Clone and continue"}</button>
          </div>
        )}
        {state.error && <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{state.error}</div>}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="font-semibold">What happens next</h3>
        <div className="mt-4 space-y-3 text-sm text-slate-600">
          {["QALLM extracts Python files and notebooks", "Static analysis scans for security, complexity, quality issues", "An LLM repairs critical issues; you can iterate", "RL-guided test generation finds bugs static analysis cannot"].map((t, i) => (
            <div key={i} className="flex items-start gap-3 rounded-xl bg-slate-50 p-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-bold">{i + 1}</span>
              <span>{t}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
