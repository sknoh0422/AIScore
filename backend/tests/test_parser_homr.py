from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser
from app.domain.score import VoiceName

FIX = Path(__file__).parent / "fixtures" / "satb_homr.musicxml"


def test_homr_piano_part_yields_satb():
    """homr는 파트명을 'Piano'로 내보내지만 성악 내용이다. 4성부가 나와야 한다."""
    score = Music21Parser().parse(FIX)
    # treble(S+A) + bass(T+B) 화음 분리 → 최소 소프라노·베이스는 존재
    assert VoiceName.SOPRANO in score.voices
    assert VoiceName.BASS in score.voices
    assert len(score.voices[VoiceName.SOPRANO].notes) > 0
