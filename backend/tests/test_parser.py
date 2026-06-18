import pytest
from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser, _is_vocal_part
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


# ── 악기 필터 테스트 ──────────────────────────────────────────────

class _FakePart:
    def __init__(self, name):
        self.partName = name

def test_vocal_part_no_name():
    assert _is_vocal_part(_FakePart("")) is True
    assert _is_vocal_part(_FakePart(None)) is True

def test_vocal_part_keywords():
    assert _is_vocal_part(_FakePart("Soprano")) is True
    assert _is_vocal_part(_FakePart("Alto")) is True
    assert _is_vocal_part(_FakePart("Voice")) is True

def test_instrument_part_excluded():
    assert _is_vocal_part(_FakePart("Piano")) is False
    assert _is_vocal_part(_FakePart("Organ")) is False
    assert _is_vocal_part(_FakePart("피아노")) is False
    assert _is_vocal_part(_FakePart("Accompaniment")) is False

def test_parser_skips_piano_part(tmp_path):
    """Piano 파트명이 있는 파트는 제외되고 성악 파트만 추출된다."""
    mxl = tmp_path / "vocal_piano.musicxml"
    mxl.write_text("""<?xml version="1.0"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Soprano</part-name></score-part>
    <score-part id="P2"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><type>whole</type></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <note><pitch><step>G</step><octave>3</octave></pitch><duration>4</duration><type>whole</type></note>
    </measure>
  </part>
</score-partwise>""")
    score = Music21Parser().parse(mxl)
    # Piano 파트 제외 → 성부 1개(소프라노)만
    assert len(score.voices) == 1
    assert VoiceName.SOPRANO in score.voices
    assert score.voices[VoiceName.SOPRANO].notes[0].pitch == "C5"


def test_parser_single_vocal_part(tmp_path):
    """1성부 단선율 악보 → SOPRANO 1개만 추출."""
    mxl = tmp_path / "single.musicxml"
    mxl.write_text("""<?xml version="1.0"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Voice</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
    </measure>
  </part>
</score-partwise>""")
    score = Music21Parser().parse(mxl)
    assert len(score.voices) == 1
    assert VoiceName.SOPRANO in score.voices
