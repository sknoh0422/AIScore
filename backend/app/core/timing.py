"""timing.json 생성: 악보 정보를 시간 기반 음표 이벤트로 변환.

core/ 횡단 유틸 — domain 객체만 의존, L2 오케스트레이터에서 직접 호출 가능.
"""
from __future__ import annotations
import json
from pathlib import Path
from app.domain.score import Score, VoiceName

DEFAULT_BPM = 80


def build_timing(score: Score, bpm: int = DEFAULT_BPM) -> dict:
    """Score를 timing 딕셔너리로 변환."""
    sec_per_quarter = 60.0 / bpm
    voices: dict[str, list[dict]] = {}
    for vname, voice in score.voices.items():
        events = []
        t = 0.0
        for i, note in enumerate(voice.notes):
            dur = note.quarter_length * sec_per_quarter
            events.append({
                "pitch": note.pitch,
                "start_sec": round(t, 4),
                "end_sec": round(t + dur, 4),
                "index": i,
            })
            t += dur
        voices[vname.value] = events
    return {"bpm": bpm, "voices": voices}


def write_timing(score: Score, out_path: Path, bpm: int = DEFAULT_BPM) -> Path:
    """timing 딕셔너리를 JSON 파일로 저장."""
    data = build_timing(score, bpm)
    out_path.write_text(json.dumps(data, ensure_ascii=False))
    return out_path
