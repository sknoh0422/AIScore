"""L3 믹싱: 성부별 WAV → 합창 WAV. MixerPort 구현."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf

def _to_mono(a: np.ndarray) -> np.ndarray:
    return a.mean(axis=1) if a.ndim == 2 else a

class Mixer:
    def mix(self, voice_wavs: list[Path], out_path: Path) -> Path:
        reads = [sf.read(p) for p in voice_wavs]
        if not reads:
            raise ValueError("mix: 빈 입력")
        arrays = [_to_mono(data.astype(np.float32)) for data, _ in reads]
        sr = reads[0][1]
        length = max(len(a) for a in arrays)
        acc = np.zeros(length, dtype=np.float32)
        for a in arrays:
            acc[:len(a)] += a
        peak = float(abs(acc).max())
        if peak > 1.0:
            acc /= peak
        sf.write(out_path, acc, sr)
        return out_path
