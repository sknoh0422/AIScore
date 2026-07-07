"""조표 판정 로컬 서버 (표준 라이브러리만 사용).

homr 예측 조표 vs GT 조표가 다른 곡을 하나씩 보여주고, 사용자가 실제 악보
이미지를 보며 어느 쪽이 맞는지 클릭해 판정한다. 판정 결과는 JSON에 즉시 저장.

실행:
    PYTHONPATH=. /opt/miniconda3/envs/aiscore/bin/python \
        -m training.scripts.key_adjudicator.server [--port 8900]
결과 저장:
    training/baseline_eval/key_adjudication.json
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WEB = (Path(__file__).parent / "web").resolve()
IMG_DIRS = [Path("score_images/png"), Path("training/baseline_eval/homr_full")]
DECISIONS = Path("training/baseline_eval/key_adjudication.json")

CT = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
      ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
      ".png": "image/png"}


def load_decisions() -> dict:
    if DECISIONS.exists():
        return json.loads(DECISIONS.read_text(encoding="utf-8"))
    return {}


def save_decisions(d: dict) -> None:
    DECISIONS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body, ctype="text/plain; charset=utf-8") -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            path = "/index.html"
        if path == "/decisions.json":
            self._send(200, json.dumps(load_decisions(), ensure_ascii=False), CT[".json"])
            return
        if path.startswith("/img/"):
            name = path[len("/img/"):]
            for d in IMG_DIRS:
                f = d / name
                if f.exists():
                    self._send(200, f.read_bytes(), CT[".png"])
                    return
            self._send(404, "no image")
            return
        f = (WEB / path.lstrip("/")).resolve()
        if f.is_file() and str(f).startswith(str(WEB)):
            self._send(200, f.read_bytes(), CT.get(f.suffix, "application/octet-stream"))
            return
        self._send(404, "not found")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/save":
            self._send(404, "not found")
            return
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        hymn = str(data.get("hymn"))
        d = load_decisions()
        if data.get("verdict") is None:
            d.pop(hymn, None)
        else:
            d[hymn] = {"verdict": data["verdict"], "correct_fifths": data.get("correct_fifths")}
        save_decisions(d)
        self._send(200, json.dumps({"ok": True, "count": len(d)}), CT[".json"])

    def log_message(self, *a) -> None:  # 조용히
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8900)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"조표 판정 도구: http://127.0.0.1:{args.port}  (Ctrl+C 종료)")
    print(f"판정 저장: {DECISIONS}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
