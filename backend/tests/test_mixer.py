import numpy as np, soundfile as sf
from app.stages.mixing.mixer import Mixer

def _wav(p, n, val=0.5, sr=44100):
    sf.write(p, np.full(n, val, dtype=np.float32), sr)

def test_mix_pads_to_longest_and_normalizes(tmp_path):
    a, b, out = tmp_path/"a.wav", tmp_path/"b.wav", tmp_path/"mix.wav"
    _wav(a, 1000); _wav(b, 2000)
    Mixer().mix([a, b], out)
    data, sr = sf.read(out)
    assert sr == 44100
    assert len(data) == 2000
    assert float(abs(data).max()) <= 1.0

def test_mix_stereo_input_produces_mono(tmp_path):
    """스테레오 입력 → 모노 출력, 길이 보존."""
    stereo = tmp_path / "stereo.wav"
    sf.write(stereo, np.full((1000, 2), 0.3, dtype=np.float32), 44100)
    out = tmp_path / "out.wav"
    Mixer().mix([stereo], out)
    data, sr = sf.read(out)
    assert data.ndim == 1
    assert len(data) == 1000

def test_mix_preserves_samplerate(tmp_path):
    """입력 samplerate를 출력에 그대로 사용."""
    a, out = tmp_path/"a.wav", tmp_path/"out.wav"
    _wav(a, 100, sr=22050)
    Mixer().mix([a], out)
    _, sr = sf.read(out)
    assert sr == 22050
