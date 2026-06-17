import UploadForm from "@/components/UploadForm";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-bold tracking-tight">AIScore</h1>
      <p className="text-slate-500 text-sm">SATB 찬송가 악보 → AI 합창 음원</p>
      <UploadForm />
    </main>
  );
}
