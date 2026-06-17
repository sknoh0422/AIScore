"""L3 OMR 어댑터: Audiveris 배치 CLI로 이미지→MusicXML(.mxl). OmrPort 구현."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from app.core import config
from app.core.errors import OmrError
from app.stages.omr.preprocess import ensure_resolution

class AudiverisAdapter:
    def __init__(self, work_dir: Path | None = None) -> None:
        self.work_dir = Path(work_dir) if work_dir else Path("data/omr")

    def recognize(self, image_path: Path) -> Path:
        image_path = Path(image_path)
        if not image_path.exists():
            raise OmrError(f"이미지 없음: {image_path}")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        pre = ensure_resolution(image_path, self.work_dir / "pre.png",
                                config.omr_min_long_edge())
        env = dict(os.environ)
        if config.java_home():
            env["JAVA_HOME"] = config.java_home()
            env["PATH"] = f"{config.java_home()}/bin:" + env.get("PATH", "")
        if config.tessdata_prefix():
            env["TESSDATA_PREFIX"] = config.tessdata_prefix()
        bin_path = config.audiveris_bin()
        if not Path(bin_path).exists():
            raise OmrError(f"Audiveris 미설치: {bin_path}")
        proc = subprocess.run(
            [bin_path, "-batch", "-transcribe", "-export",
             "-output", str(self.work_dir), str(pre)],
            capture_output=True, text=True, env=env,
        )
        mxl = self.work_dir / "pre.mxl"
        if proc.returncode != 0 or not mxl.exists():
            raise OmrError(
                f"Audiveris 실패(code={proc.returncode}, mxl_exists={mxl.exists()}): "
                f"{proc.stderr[-500:]}")
        return mxl
