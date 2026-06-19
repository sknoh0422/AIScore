"""OmrPort 구현 — 5모듈 Score Understanding 파이프라인."""
from __future__ import annotations
from pathlib import Path

import cv2

from app.core.config import omr_model_path
from app.stages.omr.preprocessor import preprocess
from app.stages.omr.layout_analyzer import analyze_layout
from app.stages.omr.omr_engine import OmrEngine
from app.stages.omr.pitch_converter import y_to_pitch
from app.stages.omr.duration_classifier import classify_duration
from app.stages.omr.voice_assigner import assign_voice
from app.stages.omr.meta_extractor import extract_meta
from app.stages.omr.lyrics_ocr import extract_lyrics
from app.stages.omr.musicxml_assembler import assemble
from app.stages.omr.types import NoteEvent


class ScoreUnderstandingAdapter:
    """악보 이미지 → 완전한 MusicXML. OmrPort 구현체."""

    def __init__(self, work_dir: Path, conf_threshold: float = 0.5) -> None:
        self._work_dir = work_dir
        model = omr_model_path()
        self._engine = OmrEngine(model_path=model, conf_threshold=conf_threshold) if model else None

    def recognize(self, image_path: Path) -> Path:
        """이미지 경로를 받아 완전한 MusicXML 파일 경로를 반환한다."""
        job_dir = self._work_dir / image_path.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        # Module 0: 전처리
        pre_path = job_dir / "preprocessed.png"
        preprocess(image_path, pre_path)

        # 이미지 로드 (이후 모듈 공유)
        gray = cv2.imread(str(pre_path), cv2.IMREAD_GRAYSCALE)

        # Module 1: 레이아웃 분석
        layout = analyze_layout(gray)

        # Module 2: OMR
        detections = self._engine.detect(pre_path) if self._engine else []

        note_events: list[NoteEvent] = []
        for det in detections:
            if det.class_name not in ("notehead_filled", "notehead_open"):
                continue
            # 보표 시스템 찾기
            staff = next(
                (s for s in layout.staff_systems
                 if s.bbox.y <= det.bbox.center_y <= s.bbox.y2),
                None,
            )
            if staff is None:
                continue
            pitch = y_to_pitch(det.bbox.center_y, staff)
            ql, dotted = classify_duration(det, [d for d in detections if d is not det])
            voice = assign_voice(det, staff)
            staff_idx = layout.staff_systems.index(staff)
            note_events.append(NoteEvent(
                pitch=pitch, duration=ql, voice=voice,
                staff_idx=staff_idx, x=det.bbox.x, is_dotted=dotted,
            ))

        # Module 3: 메타 추출
        meta = extract_meta(layout, detections, gray)

        # Module 4: 가사 OCR
        lyrics = extract_lyrics(gray, layout.lyric_regions)

        # Module 5: MusicXML 조립
        out_path = job_dir / f"{image_path.stem}.mxl"
        return assemble(meta, note_events, lyrics, out_path)
