import soundfile as sf
from pathlib import Path
from app.domain.score import Score, Voice, Note, VoiceName
from app.stages.svs.vowel_synth_adapter import VowelSynthAdapter, SAMPLE_RATE, DEFAULT_BPM

def _score():
    v = Voice(name=VoiceName.SOPRANO, notes=[Note("A4", 1.0), Note(None, 1.0), Note("C5", 2.0)])
    return Score(voices={VoiceName.SOPRANO: v})

def test_synth_creates_wav_of_expected_length(tmp_path):
    out = tmp_path / "s.wav"
    VowelSynthAdapter().synthesize(_score(), VoiceName.SOPRANO, out)
    data, sr = sf.read(out)
    assert sr == SAMPLE_RATE
    expected_sec = (1.0 + 1.0 + 2.0) * (60.0 / DEFAULT_BPM)
    assert abs(len(data) / sr - expected_sec) < 0.05

def test_rest_is_silent(tmp_path):
    out = tmp_path / "s.wav"
    v = Voice(name=VoiceName.BASS, notes=[Note(None, 1.0)])
    VowelSynthAdapter().synthesize(Score(voices={VoiceName.BASS: v}), VoiceName.BASS, out)
    data, _ = sf.read(out)
    assert float(abs(data).max()) < 1e-6
