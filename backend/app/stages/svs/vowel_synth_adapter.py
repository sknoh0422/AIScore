"""L3 SVS(1단계): 성악가 특성 모델링 — 포먼트 필터 + 비브라토.

성부별 참조 성악가:
  소프라노: Renée Fleming  / 알토: Kathleen Ferrier
  테너:    Pavarotti       / 베이스: Samuel Ramey
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from scipy.signal import iirpeak, lfilter
import soundfile as sf
from app.domain.score import Score, VoiceName, to_midi

SAMPLE_RATE = 44_100
DEFAULT_BPM = 80

# 포먼트 정의: (주파수Hz, 대역폭Hz) 목록 — "우" 모음 성도 공명
_FORMANTS: dict[VoiceName, list[tuple[float, float]]] = {
    VoiceName.SOPRANO: [(350, 80), (900, 100), (2700, 120), (3200, 180)],
    VoiceName.ALTO:    [(350, 70), (700,  90), (2500, 110), (3000, 160)],
    VoiceName.TENOR:   [(350, 75), (800,  95), (2800, 100), (3300, 150)],  # squillo 2800Hz
    VoiceName.BASS:    [(300, 60), (600,  80), (2600, 110), (3100, 160)],
}

# 비브라토 (rate Hz, depth ±비율)
_VIBRATO: dict[VoiceName, tuple[float, float]] = {
    VoiceName.SOPRANO: (6.5, 0.007),
    VoiceName.ALTO:    (5.0, 0.006),
    VoiceName.TENOR:   (6.0, 0.006),
    VoiceName.BASS:    (4.5, 0.005),
}

# 배음 진폭 (기본 성문파)
_HARMONICS: dict[VoiceName, list[tuple[int, float]]] = {
    VoiceName.SOPRANO: [(1, 1.0), (2, 0.45), (3, 0.25), (4, 0.15), (5, 0.08), (6, 0.04)],
    VoiceName.ALTO:    [(1, 1.0), (2, 0.50), (3, 0.30), (4, 0.18), (5, 0.09), (6, 0.04)],
    VoiceName.TENOR:   [(1, 1.0), (2, 0.52), (3, 0.32), (4, 0.20), (5, 0.11), (6, 0.05)],
    VoiceName.BASS:    [(1, 1.0), (2, 0.55), (3, 0.35), (4, 0.20), (5, 0.09)],
}

_ATTACK_SEC  = 0.07
_RELEASE_SEC = 0.09


def _apply_formants(wave: np.ndarray, voice: VoiceName) -> np.ndarray:
    """IIR peak 필터로 포먼트(성도 공명) 적용."""
    out = wave.copy()
    for f0, bw in _FORMANTS[voice]:
        Q = f0 / bw
        b, a = iirpeak(f0, Q, fs=SAMPLE_RATE)
        out = lfilter(b, a, out)
    return out


def _freq(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _vocal_tone(freq: float, n: int, voice: VoiceName) -> np.ndarray:
    t = np.arange(n) / SAMPLE_RATE
    rate, depth = _VIBRATO[voice]
    vibrato = 1.0 + depth * np.sin(2 * np.pi * rate * t)
    phase = 2 * np.pi * freq * np.cumsum(vibrato) / SAMPLE_RATE

    wave = sum(amp * np.sin(h * phase) for h, amp in _HARMONICS[voice])
    wave = _apply_formants(wave.astype(np.float64), voice).astype(np.float32)

    # 숨소리(breathiness)
    wave += 0.015 * np.random.default_rng(seed=int(freq)).standard_normal(n).astype(np.float32)

    # 어택/릴리즈 엔벨로프
    env = np.ones(n, dtype=np.float32)
    atk = min(int(_ATTACK_SEC * SAMPLE_RATE), n // 3)
    rel = min(int(_RELEASE_SEC * SAMPLE_RATE), n // 3)
    if atk:
        env[:atk] = np.linspace(0.0, 1.0, atk)
    if rel:
        env[-rel:] = np.linspace(1.0, 0.0, rel)
    return wave * env


class VowelSynthAdapter:
    def __init__(self, bpm: int = DEFAULT_BPM) -> None:
        self.bpm = bpm

    def synthesize(self, score: Score, voice: VoiceName, out_path: Path) -> Path:
        notes = score.voices[voice].notes
        sec_per_quarter = 60.0 / self.bpm
        segments: list[np.ndarray] = []
        for note in notes:
            n = max(1, int(note.quarter_length * sec_per_quarter * SAMPLE_RATE))
            if note.pitch is None:
                segments.append(np.zeros(n, dtype=np.float32))
            else:
                segments.append(_vocal_tone(_freq(to_midi(note.pitch)), n, voice) * 0.25)
        audio = np.concatenate(segments) if segments else np.zeros(1, dtype=np.float32)
        sf.write(out_path, audio, SAMPLE_RATE)
        return out_path
