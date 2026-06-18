import numpy as np
import soundfile as sf
from pathlib import Path
from app.domain.score import Score, Voice, Note, VoiceName
from app.stages.svs.vowel_synth_adapter import VowelSynthAdapter


def _one_note_score(voice: VoiceName, pitch="A4") -> Score:
    return Score(voices={voice: Voice(name=voice, notes=[Note(pitch=pitch, quarter_length=2.0)])})


def test_soprano_formant_produces_wav(tmp_path):
    out = tmp_path / "s.wav"
    VowelSynthAdapter().synthesize(_one_note_score(VoiceName.SOPRANO), VoiceName.SOPRANO, out)
    data, sr = sf.read(out)
    assert sr == 44100
    assert len(data) > 0


def test_tenor_squillo_formant_boost(tmp_path):
    """포먼트 필터가 테너 2800Hz squillo 대역을 실제로 증폭하는지 검증"""
    from app.stages.svs.vowel_synth_adapter import _apply_formants

    SAMPLE_RATE = 44_100
    rng = np.random.default_rng(42)
    white = rng.standard_normal(SAMPLE_RATE * 2).astype(np.float64)

    filtered = _apply_formants(white, VoiceName.TENOR)

    def band_energy(sig, lo, hi):
        mag = np.abs(np.fft.rfft(sig))
        freqs = np.fft.rfftfreq(len(sig), 1 / SAMPLE_RATE)
        return float(mag[(freqs >= lo) & (freqs <= hi)].sum())

    boost = band_energy(filtered, 2700, 2900) / (band_energy(white, 2700, 2900) + 1e-12)
    assert boost > 1.5, f"squillo 증폭 비율 {boost:.2f}x — 포먼트 필터 효과 미달"


def test_all_voices_synthesize(tmp_path):
    for vn in VoiceName:
        out = tmp_path / f"{vn.value}.wav"
        VowelSynthAdapter().synthesize(_one_note_score(vn), vn, out)
        assert out.exists() and out.stat().st_size > 0
