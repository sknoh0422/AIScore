"""횡단 설정: 경로·OMR 파라미터(pathlib 중립, env 오버라이드)."""
from __future__ import annotations
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]  # backend/app/core → repo root

def audiveris_home() -> Path:
    return Path(os.environ.get(
        "AISCORE_AUDIVERIS_HOME",
        str(_REPO / "vendor" / "audiveris" / "app-5.10.2")))

def audiveris_bin() -> str:
    return str(audiveris_home() / "bin" / "Audiveris")

def java_home() -> str | None:
    return os.environ.get(
        "AISCORE_JAVA_HOME",
        "/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home")

def tessdata_prefix() -> str | None:
    return os.environ.get("AISCORE_TESSDATA_PREFIX", "/opt/homebrew/share/tessdata")

def omr_min_long_edge() -> int:
    try:
        return int(os.environ.get("AISCORE_OMR_MIN_LONG_EDGE", "2000"))
    except ValueError:
        return 2000

def omr_model_path() -> Path | None:
    """YOLOv8 OMR 모델 경로. 환경변수 미설정 시 기본 경로 반환."""
    env = os.environ.get("AISCORE_OMR_MODEL_PATH")
    if env:
        return Path(env)
    default = _REPO / "models" / "omr" / "best.pt"
    return default if default.exists() else None

def dl_omr_model_path() -> Path | None:
    """DL-OMR CRNN 모델 경로. 환경변수 미설정 시 training/models/omr_crnn_best.pt 반환."""
    p = Path(os.getenv("DL_OMR_MODEL_PATH", str(_REPO / "training" / "models" / "omr_crnn_best.pt")))
    return p if p.exists() else None

def paddleocr_lang() -> str:
    """PaddleOCR 언어 설정. 기본값 'korean'."""
    return os.environ.get("AISCORE_PADDLEOCR_LANG", "korean")
