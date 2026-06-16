"""L3 SVS(1단계): 모음 '우' 합성. SvsPort 구현."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf
from app.domain.score import Score, VoiceName, to_midi

SAMPLE_RATE = 44_100
DEFAULT_BPM = 80
_HARMONICS = [(1, 1.0), (2, 0.25), (3, 0.12)]  # "우" 근사: 낮은 배음 위주

def _freq(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)

def _tone(freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SAMPLE_RATE
    wave = sum(amp * np.sin(2 * np.pi * freq * h * t) for h, amp in _HARMONICS)
    env = np.ones(n)
    fade = min(int(0.01 * SAMPLE_RATE), n // 2)  # 클릭 방지 페이드
    if fade:
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
    return (wave * env).astype(np.float32)

class VowelSynthAdapter:
    def __init__(self, bpm: int = DEFAULT_BPM) -> None:
        self.bpm = bpm

    def synthesize(self, score: Score, voice: VoiceName, out_path: Path) -> Path:
        notes = score.voices[voice].notes
        sec_per_quarter = 60.0 / self.bpm
        segments = []
        for note in notes:
            n = int(note.quarter_length * sec_per_quarter * SAMPLE_RATE)
            if note.pitch is None:
                segments.append(np.zeros(n, dtype=np.float32))
            else:
                segments.append(_tone(_freq(to_midi(note.pitch)), n) * 0.3)
        audio = np.concatenate(segments) if segments else np.zeros(1, dtype=np.float32)
        sf.write(out_path, audio, SAMPLE_RATE)
        return out_path
