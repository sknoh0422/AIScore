"""L3 OMR 어댑터: homr CLI(subprocess)로 이미지→MusicXML. OmrPort 구현.

homr는 별도 clone의 Python 3.11 venv + ONNX 모델로 실행되므로 프로세스로 격리한다.
homr는 입력 이미지 옆에 <stem>.musicxml 을 생성한다.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from app.core import config
from app.core.errors import OmrError


class HomrAdapter:
    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = Path(work_dir) if work_dir else Path("data/omr")

    def recognize(self, image_path: Path) -> Path:
        image_path = Path(image_path)
        if not image_path.exists():
            raise OmrError(f"이미지 없음: {image_path}")

        bin_path = config.homr_bin()
        if not Path(bin_path).exists():
            raise OmrError(f"homr 미설치: {bin_path}")

        omr_dir = self.work_dir / "omr"
        omr_dir.mkdir(parents=True, exist_ok=True)
        # 입력을 잡 전용 디렉터리로 복사 → homr 출력을 여기로 유도(격리·결정적 경로)
        local_img = omr_dir / f"input{image_path.suffix or '.png'}"
        shutil.copyfile(image_path, local_img)

        proc = subprocess.run(
            [bin_path, str(local_img)],
            capture_output=True, text=True,  # shell=False (리스트 인자)
        )
        out = local_img.with_suffix(".musicxml")
        if proc.returncode != 0 or not out.exists():
            raise OmrError(
                f"homr 실패(code={proc.returncode}, xml_exists={out.exists()}): "
                f"{proc.stderr[-500:]}")
        return out
