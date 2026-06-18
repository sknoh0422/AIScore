"use client";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { createJob } from "@/lib/api";

export default function UploadForm() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function upload(file: File) {
    setError(null);
    setUploading(true);
    try {
      const { id } = await createJob(file);
      router.push(`/jobs/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "업로드 실패");
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault(); setDragging(false);
          const f = e.dataTransfer.files[0];
          if (f) upload(f);
        }}
        className={`w-80 h-48 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-colors
          ${dragging ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white hover:border-blue-400"}`}
      >
        <span className="text-4xl mb-2">🎼</span>
        <p className="text-sm text-slate-500">
          {uploading ? "업로드 중…" : "악보 이미지를 드래그하거나 클릭"}
        </p>
        <p className="text-xs text-slate-400 mt-1">PNG · JPG · TIFF · 최대 20MB</p>
      </div>
      <input
        ref={inputRef} type="file" accept="image/*" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }}
      />
      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  );
}
