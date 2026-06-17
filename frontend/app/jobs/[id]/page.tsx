"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { getJob, audioUrl, scoreUrl, JobState } from "@/lib/api";

const ScoreViewer = dynamic(() => import("@/components/ScoreViewer"), { ssr: false });

const STEPS = ["queued","omr","parsing","synth","mixing","done"] as const;
const STEP_LABEL: Record<string, string> = {
  queued:"대기", omr:"악보 인식", parsing:"성부 분리", synth:"가창 합성", mixing:"믹싱", done:"완료"
};

function ProgressBar({ status }: { status: string }) {
  const idx = STEPS.indexOf(status as typeof STEPS[number]);
  return (
    <div className="w-full max-w-md">
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        {STEPS.slice(0,-1).map((s) => <span key={s}>{STEP_LABEL[s]}</span>)}
      </div>
      <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 transition-all duration-500"
          style={{ width: `${Math.max(0, idx) / (STEPS.length - 1) * 100}%` }}
        />
      </div>
    </div>
  );
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<JobState | null>(null);

  useEffect(() => {
    if (!id) return;
    const poll = async () => {
      try {
        const j = await getJob(id);
        setJob(j);
        if (j.status !== "done" && j.status !== "failed") {
          setTimeout(poll, 2000);
        }
      } catch { setTimeout(poll, 3000); }
    };
    poll();
  }, [id]);

  if (!job) return <main className="flex items-center justify-center min-h-screen"><p className="text-slate-400">로딩 중…</p></main>;

  return (
    <main className="flex flex-col items-center gap-8 p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold">AIScore</h1>

      {job.status === "failed" ? (
        <div className="w-full p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <p className="font-semibold">처리 실패 — {job.failed_stage} 단계</p>
          <p className="mt-1 font-mono text-xs">{job.error}</p>
        </div>
      ) : (
        <ProgressBar status={job.status} />
      )}

      {job.status === "done" && (
        <>
          <div className="w-full">
            <p className="text-sm font-medium text-slate-600 mb-2">합창 음원</p>
            <audio controls src={audioUrl(id)} className="w-full" />
          </div>
          {job.score_path && (
            <div className="w-full">
              <p className="text-sm font-medium text-slate-600 mb-2">악보</p>
              <ScoreViewer url={scoreUrl(id)} />
            </div>
          )}
        </>
      )}

      <a href="/" className="text-sm text-blue-500 hover:underline">← 다른 악보 업로드</a>
    </main>
  );
}
