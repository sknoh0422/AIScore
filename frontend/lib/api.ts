const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type JobStatus = "queued"|"omr"|"parsing"|"synth"|"mixing"|"done"|"failed";

export interface JobState {
  id: string;
  status: JobStatus;
  failed_stage?: string;
  error?: string;
  result_path?: string;
  score_path?: string;
}

export async function createJob(file: File): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/jobs`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`업로드 실패 (${res.status})`);
  return res.json();
}

export async function getJob(id: string): Promise<JobState> {
  const res = await fetch(`${API}/jobs/${id}`);
  if (!res.ok) throw new Error(`조회 실패 (${res.status})`);
  return res.json();
}

export const audioUrl = (id: string) => `${API}/jobs/${id}/audio`;
export const scoreUrl = (id: string) => `${API}/jobs/${id}/score`;
