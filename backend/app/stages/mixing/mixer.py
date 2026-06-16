"""L3 믹싱: 성부별 WAV → 합창 WAV. MixerPort 구현."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf

class Mixer:
    def mix(self, voice_wavs: list[Path], out_path: Path) -> Path:
        arrays = [sf.read(p)[0].astype(np.float32) for p in voice_wavs]
        if not arrays:
            raise ValueError("mix: 빈 입력")
        length = max(len(a) for a in arrays)
        acc = np.zeros(length, dtype=np.float32)
        for a in arrays:
            acc[:len(a)] += a
        peak = float(abs(acc).max())
        if peak > 1.0:
            acc /= peak
        sf.write(out_path, acc, 44_100)
        return out_path
