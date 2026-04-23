import type { AnalysisRound, AnalysisSummary, Finding, FunctionEntry, RepairResult, VerificationResult, VersionInfo } from "./types";

class ApiError extends Error {
  status: number;
  constructor(msg: string, status: number) { super(msg); this.status = status; }
}

async function req<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, opts);
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) throw new ApiError(`HTTP ${res.status}`, res.status);
  const d = await res.json();
  if (!res.ok) throw new ApiError(d.detail || `HTTP ${res.status}`, res.status);
  return d as T;
}

function post<T>(url: string, body: unknown): Promise<T> {
  return req<T>(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

/* Session */
export async function uploadZip(file: File): Promise<string> {
  const form = new FormData(); form.append("archive", file);
  return (await req<{ session_id: string }>("/api/session/upload", { method: "POST", body: form })).session_id;
}
export async function cloneRepo(url: string) { return (await post<{ session_id: string }>("/api/session/clone", { git_url: url })).session_id; }
export async function getFiles(sid: string) { return (await req<{ files: string[] }>(`/api/session/${sid}/files`)).files; }
export async function getVersions(sid: string) { return (await req<{ versions: VersionInfo[] }>(`/api/session/${sid}/versions`)).versions; }
export async function restoreVersion(sid: string, round: number) { await post(`/api/session/${sid}/restore/${round}`, {}); }
export async function getAnalysisHistory(sid: string) { return (await req<{ rounds: AnalysisRound[] }>(`/api/session/${sid}/analysis-history`)).rounds; }
export async function getFileDiff(sid: string, fp: string) { return (await req<{ diff: string }>(`/api/session/${sid}/diff/${fp}`)).diff; }
export async function downloadTestFiles(sid: string) { return (await req<{ files: { name: string; content: string }[] }>(`/api/session/${sid}/download/tests`)).files; }

/* Analysis */
export async function runAnalysis(sid: string, files: string[]): Promise<{ summary: AnalysisSummary; findings: Finding[] }> {
  return post("/api/analyse", { session_id: sid, selected_files: files });
}

/* Repair */
export async function getProviders() { return req<{ available: string[]; configured: string[] }>("/api/llm/providers"); }
export async function runRepair(sid: string, provider?: string): Promise<RepairResult> {
  return post(`/api/repair/${sid}`, { provider: provider || null });
}

/* Test generation */
export async function getModels() { return req<{ available: string[]; configured: string[] }>("/api/verification/models"); }
export async function getFunctions(sid: string) { return (await req<{ functions: FunctionEntry[] }>(`/api/verification/functions/${sid}`)).functions; }
export async function runTestGen(sid: string, model: string, oracle: string, rounds: number): Promise<VerificationResult> {
  return post("/api/verification/run", { session_id: sid, model, oracle, rounds });
}
