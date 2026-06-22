# backend/tests/test_su_musicxml_assembler.py
import pytest
from pathlib import Path
from app.stages.omr.types import NoteEvent, ScoreMeta, LyricsResult
from app.stages.omr.musicxml_assembler import assemble

def _sample_notes() -> list[NoteEvent]:
    return [
        NoteEvent(pitch="G4", duration=1.0, voice=1, staff_idx=0, x=100),
        NoteEvent(pitch="A4", duration=1.0, voice=1, staff_idx=0, x=150),
        NoteEvent(pitch="B4", duration=2.0, voice=1, staff_idx=0, x=200),
        NoteEvent(pitch="E4", duration=1.0, voice=2, staff_idx=0, x=100),
        NoteEvent(pitch="F4", duration=1.0, voice=2, staff_idx=0, x=150),
        NoteEvent(pitch="G4", duration=2.0, voice=2, staff_idx=0, x=200),
    ]

def _sample_meta() -> ScoreMeta:
    return ScoreMeta(title="테스트 찬양", key="G major", time_num=4, time_den=4)

def test_assemble_creates_file(tmp_path):
    out = tmp_path / "score.mxl"
    result = assemble(_sample_meta(), _sample_notes(), LyricsResult(verses=[]), out)
    assert result == out
    assert out.exists()

def test_assemble_output_is_valid_musicxml(tmp_path):
    """출력 파일이 MusicXML로 파싱 가능해야 한다."""
    import music21
    out = tmp_path / "score.mxl"
    assemble(_sample_meta(), _sample_notes(), LyricsResult(verses=[]), out)
    score = music21.converter.parse(str(out))
    assert score is not None

def test_assemble_note_count(tmp_path):
    """음표 수가 일치해야 한다."""
    import music21
    notes = _sample_notes()
    out = tmp_path / "score.mxl"
    assemble(_sample_meta(), notes, LyricsResult(verses=[]), out)
    score = music21.converter.parse(str(out))
    all_notes = list(score.flatten().notes)
    assert len(all_notes) == len(notes)

def test_assemble_with_lyrics(tmp_path):
    """가사가 음표에 첨부되는지 확인한다."""
    import music21
    notes = [NoteEvent("G4", 1.0, 1, 0, 100), NoteEvent("A4", 1.0, 1, 0, 150)]
    lyrics = LyricsResult(verses=[["주", "님"]])
    out = tmp_path / "score.mxl"
    assemble(_sample_meta(), notes, lyrics, out)
    score = music21.converter.parse(str(out))
    note_list = [n for n in score.flatten().notes if isinstance(n, music21.note.Note)]
    assert note_list[0].lyric == "주"
