import pytest
from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser
from app.core.errors import ParseError
from app.domain.score import VoiceName

FIX = Path(__file__).parent / "fixtures" / "satb_min.musicxml"

def test_parse_produces_four_voices():
    score = Music21Parser().parse(FIX)
    assert set(score.voices) == set(VoiceName)
    assert score.voices[VoiceName.SOPRANO].notes[0].pitch == "A4"
    assert score.voices[VoiceName.BASS].notes[0].pitch == "F3"

def test_parse_empty_score_raises(tmp_path):
    """음표가 없는 MusicXML → ParseError."""
    empty = tmp_path / "empty.musicxml"
    empty.write_text("""<?xml version="1.0"?>
<score-partwise version="4.0">
  <part-list/>
</score-partwise>""")
    with pytest.raises(ParseError):
        Music21Parser().parse(empty)
