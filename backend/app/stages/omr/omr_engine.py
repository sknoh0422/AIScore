"""Module 2b: YOLOv8 기반 음악 기호 검출 엔진."""
from __future__ import annotations
from pathlib import Path

from app.stages.omr.types import BBox, RawDetection

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover
    YOLO = None  # type: ignore


class OmrModelNotFoundError(FileNotFoundError):
    """YOLOv8 모델 파일을 찾을 수 없을 때."""


class OmrEngine:
    """YOLOv8 모델을 로드하고 음악 기호를 검출한다."""

    OMR_CLASSES = [
        "notehead_filled", "notehead_open",
        "rest_whole", "rest_half", "rest_quarter", "rest_eighth",
        "accidental_sharp", "accidental_flat", "accidental_natural",
        "key_sig_sharp", "key_sig_flat",
        "augmentation_dot",
        "clef_treble", "clef_bass",
        "time_sig_num",
    ]

    def __init__(self, model_path: Path, conf_threshold: float = 0.5) -> None:
        if not model_path.exists():
            raise OmrModelNotFoundError(
                f"YOLOv8 OMR 모델 파일 없음: {model_path}\n"
                "학습 후 models/omr/best.pt 에 위치시키거나 "
                "AISCORE_OMR_MODEL_PATH 환경변수를 설정하세요."
            )
        if YOLO is None:  # pragma: no cover
            raise ImportError("ultralytics 패키지가 설치되지 않았습니다: pip install ultralytics")
        self._model = YOLO(str(model_path))
        self._conf = conf_threshold

    def detect(self, image_path: Path) -> list[RawDetection]:
        """이미지에서 음악 기호를 검출해 RawDetection 목록을 반환한다."""
        results = self._model(str(image_path), conf=self._conf, verbose=False)
        detections: list[RawDetection] = []
        for result in results:
            boxes = result.boxes
            names = result.names
            for i in range(len(boxes.xyxy)):
                x1, y1, x2, y2 = (int(v) for v in boxes.xyxy[i])
                conf = float(boxes.conf[i])
                cls_idx = int(boxes.cls[i])
                detections.append(RawDetection(
                    bbox=BBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1),
                    class_name=names[cls_idx],
                    confidence=conf,
                ))
        return detections
