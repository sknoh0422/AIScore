from pathlib import Path
from app.stages.parsing.music21_parser import Music21Parser
from app.domain.score import VoiceName

FIX = Path(__file__).parent / "fixtures" / "satb_audiveris.mxl"

def test_parses_grandstaff_voices_without_loss():
    score = Music21Parser().parse(FIX)
    assert 2 <= len(score.voices) <= 4
    assert VoiceName.SOPRANO in score.voices
    # 각 매핑된 성부에 음표가 실제로 있어야(보이스 외 음표 유실 방지)
    for v in score.voices.values():
        assert len(v.notes) > 0
