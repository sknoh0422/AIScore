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


def test_tenor_squillo_present(tmp_path):
    """테너 2800Hz squillo 성분이 존재하는지 FFT로 확인"""
    out = tmp_path / "t.wav"
    VowelSynthAdapter().synthesize(_one_note_score(VoiceName.TENOR), VoiceName.TENOR, out)
    data, sr = sf.read(out)
    freqs = np.fft.rfftfreq(len(data), 1 / sr)
    mag = np.abs(np.fft.rfft(data))
    # 2500~3100Hz 대역 에너지가 존재해야 함
    band = mag[(freqs >= 2500) & (freqs <= 3100)]
    assert band.max() > 0.0


def test_all_voices_synthesize(tmp_path):
    for vn in VoiceName:
        out = tmp_path / f"{vn.value}.wav"
        VowelSynthAdapter().synthesize(_one_note_score(vn), vn, out)
        assert out.exists() and out.stat().st_size > 0
