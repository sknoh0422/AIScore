"""포트 계약 테스트: 각 어댑터가 ports.py 프로토콜을 구조적으로 충족하는지 검증."""
from pathlib import Path
from app.domain.ports import OmrPort, ScoreParserPort, SvsPort, MixerPort

def test_audiveris_adapter_satisfies_omr_port():
    from app.stages.omr.audiveris_adapter import AudiverisAdapter
    assert isinstance(AudiverisAdapter(work_dir=Path("/tmp")), OmrPort)

def test_oemer_adapter_satisfies_omr_port():
    from app.stages.omr.oemer_adapter import OemerAdapter
    assert isinstance(OemerAdapter(), OmrPort)

def test_music21_parser_satisfies_parser_port():
    from app.stages.parsing.music21_parser import Music21Parser
    assert isinstance(Music21Parser(), ScoreParserPort)

def test_vowel_synth_satisfies_svs_port():
    from app.stages.svs.vowel_synth_adapter import VowelSynthAdapter
    assert isinstance(VowelSynthAdapter(), SvsPort)

def test_mixer_satisfies_mixer_port():
    from app.stages.mixing.mixer import Mixer
    assert isinstance(Mixer(), MixerPort)
