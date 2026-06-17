import numpy as np, soundfile as sf
from app.stages.mixing.mixer import Mixer

def _wav(p, n, val=0.5):
    sf.write(p, np.full(n, val, dtype=np.float32), 44100)

def test_mix_pads_to_longest_and_normalizes(tmp_path):
    a, b, out = tmp_path/"a.wav", tmp_path/"b.wav", tmp_path/"mix.wav"
    _wav(a, 1000); _wav(b, 2000)
    Mixer().mix([a, b], out)
    data, sr = sf.read(out)
    assert sr == 44100
    assert len(data) == 2000
    assert float(abs(data).max()) <= 1.0
