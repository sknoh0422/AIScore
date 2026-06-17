"use client";
import { useEffect, useRef } from "react";

export default function ScoreViewer({ url }: { url: string }) {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!divRef.current) return;
    import("opensheetmusicdisplay").then(({ OpenSheetMusicDisplay }) => {
      const osmd = new OpenSheetMusicDisplay(divRef.current!, { autoResize: true });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (osmd.load(url) as unknown as Promise<any>).then(() => osmd.render());
    });
  }, [url]);

  return <div ref={divRef} className="w-full overflow-x-auto bg-white rounded-lg p-4 border border-slate-200" />;
}
