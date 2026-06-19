"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { getJob, audioUrl, voiceAudioUrl, scoreUrl, metaUrl, imageUrl, JobState, ScoreMeta, NoteInfo } from "@/lib/api";

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

// 옥타브 번호 추출: 'G#5' → 5, 'B-4' → 4
function octave(pitch: string | null): string {
  if (!pitch) return "";
  const m = pitch.match(/\d+$/);
  return m ? m[0] : "";
}

// 옥타브별 색상 (소프라노 범위: C4~G5)
function noteColor(pitch: string | null): string {
  const o = parseInt(octave(pitch) || "4");
  if (o >= 5) return "bg-orange-100 text-orange-700 border-orange-300"; // 고음 주의
  if (o <= 3) return "bg-purple-100 text-purple-700 border-purple-300"; // 저음 주의
  return "bg-blue-50 text-blue-800 border-blue-200";
}

function SopranoNotes({ notes }: { notes: NoteInfo[] }) {
  // 마디별 그룹핑
  const byMeasure: Record<number, NoteInfo[]> = {};
  for (const n of notes) {
    const m = n.measure ?? 0;
    if (!byMeasure[m]) byMeasure[m] = [];
    byMeasure[m].push(n);
  }
  const measures = Object.keys(byMeasure).map(Number).sort((a, b) => a - b);

  // 4마디씩 한 줄 (마디0 = 불완전 마디, 첫 줄에 포함)
  const COLS = 4;
  const rows: number[][] = [];
  for (let i = 0; i < measures.length; i += COLS) {
    rows.push(measures.slice(i, i + COLS));
  }

  const renderNote = (n: NoteInfo, i: number) =>
    n.solfege === '쉼'
      ? <span key={i} className="text-[10px] text-slate-300 px-1 py-0.5 border border-dashed border-slate-200 rounded min-w-[22px] text-center">—</span>
      : <span key={i} className={`text-[11px] px-1.5 py-0.5 border rounded font-mono font-medium ${noteColor(n.pitch)}`}>
          {n.pitch ?? n.solfege}
        </span>;

  return (
    <div className="w-full overflow-x-auto">
      <div className="flex flex-col gap-2">
        {rows.map((row, ri) => (
          <div key={ri} className="flex items-stretch">
            {/* 첫 세로선 */}
            <div className="w-0.5 bg-slate-500 self-stretch" />
            {row.map((m, ci) => (
              <>
                {ci > 0 && <div key={`bar-${m}`} className="w-0.5 bg-slate-400 self-stretch" />}
                <div key={m} className={`flex flex-col flex-1 min-w-[60px] ${m === 0 ? 'bg-slate-50' : ''}`}>
                  <div className="px-1.5 pt-1 pb-0.5">
                    <span className="text-[9px] text-slate-400 font-mono">{m === 0 ? '불완전' : m}</span>
                  </div>
                  <div className="flex flex-wrap gap-1 px-1.5 pb-2">
                    {(byMeasure[m] ?? []).map(renderNote)}
                  </div>
                </div>
              </>
            ))}
            {/* 빈 셀 채우기 */}
            {row.length < COLS && Array.from({length: COLS - row.length}).map((_, i) => (
              <div key={`empty-${i}`} className="flex-1 border-l-2 border-slate-400" />
            ))}
            {/* 마지막 세로선 */}
            <div className={`self-stretch ${ri === rows.length - 1 ? 'w-1 bg-slate-500' : 'w-0.5 bg-slate-500'}`} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<JobState | null>(null);
  const [meta, setMeta] = useState<ScoreMeta | null>(null);

  useEffect(() => {
    if (!id) return;
    const poll = async () => {
      try {
        const j = await getJob(id);
        setJob(j);
        if (j.status === "done" && !meta) {
          fetch(metaUrl(id)).then(r => r.json()).then(setMeta).catch(() => {});
        }
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
          {/* 악보 메타정보 + 이미지 비교 */}
          {meta && (
            <div className="w-full border border-slate-200 rounded-lg overflow-hidden">
              {/* 메타 배지 */}
              <div className="flex flex-wrap gap-4 px-4 py-3 bg-slate-50 border-b border-slate-200 text-sm">
                <div><span className="text-slate-400">조성</span> <span className="font-semibold text-slate-800 ml-1">{meta.key}</span></div>
                <div><span className="text-slate-400">박자</span> <span className="font-semibold text-slate-800 ml-1">{meta.time}박자</span></div>
                <div><span className="text-slate-400">성부</span> <span className="font-semibold text-slate-800 ml-1">{meta.parts.length}성부</span></div>
                <div><span className="text-slate-400">소프라노</span> <span className="font-semibold text-slate-800 ml-1">{meta.soprano_notes.filter(n=>n.solfege!=='쉼').length}음</span></div>
              </div>

              {/* 좌: 원본 이미지 / 우: 계이름 */}
              <div className="flex flex-col md:flex-row">
                <div className="md:w-1/2 border-b md:border-b-0 md:border-r border-slate-200 overflow-auto max-h-[600px]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={imageUrl(id)} alt="원본 악보" className="w-full object-contain" />
                </div>
                <div className="md:w-1/2 p-4 overflow-auto max-h-[600px]">
                  <p className="text-xs font-semibold text-slate-500 mb-3">
                    소프라노 음표
                    <span className="ml-2 text-orange-400 font-normal">주황 = C5↑ 고음 주의</span>
                  </p>
                  <SopranoNotes notes={meta.soprano_notes} />
                </div>
              </div>
            </div>
          )}

          <div className="w-full">
            <p className="text-sm font-medium text-slate-600 mb-2">합창 음원</p>
            <audio controls src={audioUrl(id)} className="w-full" />
          </div>

          {job.voice_paths && Object.keys(job.voice_paths).length > 0 && (
            <div className="w-full">
              <p className="text-sm font-medium text-slate-600 mb-3">성부별 음원</p>
              <div className="grid grid-cols-1 gap-3">
                {(["soprano","alto","tenor","bass"] as const)
                  .filter(v => job.voice_paths![v])
                  .map(v => (
                    <div key={v} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
                      <span className="w-16 text-xs font-semibold text-slate-500 uppercase shrink-0">
                        {v === "soprano" ? "소프라노" : v === "alto" ? "알토" : v === "tenor" ? "테너" : "베이스"}
                      </span>
                      <audio controls src={voiceAudioUrl(id, v)} className="w-full h-8" />
                    </div>
                  ))}
              </div>
            </div>
          )}

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
