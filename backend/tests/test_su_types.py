"""Test suite for Score Understanding pipeline shared data types."""
from app.stages.omr.types import BBox, StaffSystem, NoteEvent, ScoreMeta, LyricsResult


def test_bbox_computed_properties():
    b = BBox(x=10, y=20, w=50, h=30)
    assert b.x2 == 60
    assert b.y2 == 50
    assert b.center_x == 35
    assert b.center_y == 35


def test_staff_system_space():
    ss = StaffSystem(
        bbox=BBox(0, 100, 500, 80),
        line_ys=[110, 120, 130, 140, 150],
        clef="treble",
    )
    assert ss.staff_space == 10.0


def test_note_event_defaults():
    n = NoteEvent(pitch="G4", duration=1.0, voice=1, staff_idx=0, x=100)
    assert n.measure is None
    assert n.is_dotted is False


def test_score_meta_defaults():
    m = ScoreMeta()
    assert m.key == "C major"
    assert m.time_num == 4


def test_lyrics_result_empty():
    lr = LyricsResult(verses=[])
    assert lr.verse_count == 0
