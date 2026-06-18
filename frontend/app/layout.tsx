import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIScore — AI 찬양대 합창",
  description: "SATB 악보 이미지 → AI 합창 음원",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
