"""L3 OMR 어댑터(1차): oemer로 이미지→MusicXML. OmrPort 구현."""
from __future__ import annotations
import subprocess
from pathlib import Path
from app.core.errors import OmrError

class OemerAdapter:
    def recognize(self, image_path: Path) -> Path:
        image_path = Path(image_path)
        if not image_path.exists():
            raise OmrError(f"이미지 없음: {image_path}")
        out_dir = image_path.parent
        proc = subprocess.run(
            ["oemer", str(image_path), "-o", str(out_dir)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise OmrError(f"oemer 실패(code={proc.returncode}): {proc.stderr[-500:]}")
        result = out_dir / f"{image_path.stem}.musicxml"
        if not result.exists():
            raise OmrError(f"MusicXML 미생성: {result}")
        return result
