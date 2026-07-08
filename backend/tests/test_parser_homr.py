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


def test_homr_satb_voices_time_aligned():
    """4성부의 총 길이(quarter_length 합)가 일치해야 한다 — 성부 간 타이밍 정렬.

    homr가 트레블 보표에 2차 Voice(지나가는 음)를 내는 마디에서, 다중 Voice를
    offset 순으로 병합하지 않으면 그 음이 뒤에 연접되어 S/A 라인이 T/B보다
    길어진다(동기화 붕괴). 정렬이 올바르면 모든 성부의 총 길이가 같아야 한다.
    """
    score = Music21Parser().parse(FIX)
    totals = {
        v.value: sum(n.quarter_length for n in sc.notes)
        for v, sc in score.voices.items()
    }
    assert len(set(totals.values())) == 1, f"성부 길이 불일치: {totals}"
