from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser
from app.domain.score import VoiceName

FIX = Path(__file__).parent / "fixtures" / "satb_min.musicxml"

def test_parse_produces_four_voices():
    score = Music21Parser().parse(FIX)
    assert set(score.voices) == set(VoiceName)
    assert score.voices[VoiceName.SOPRANO].notes[0].pitch == "A4"
    assert score.voices[VoiceName.BASS].notes[0].pitch == "F3"
