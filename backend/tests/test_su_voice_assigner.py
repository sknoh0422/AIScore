from app.stages.omr.types import BBox, RawDetection, StaffSystem
from app.stages.omr.voice_assigner import assign_voice

def _staff() -> StaffSystem:
    return StaffSystem(
        bbox=BBox(0, 90, 500, 60),
        line_ys=[100, 110, 120, 130, 140],
        clef="treble",
    )

def _det(y: int) -> RawDetection:
    return RawDetection(BBox(100, y, 15, 15), "notehead_filled", 0.9)

def test_upper_half_is_voice1():
    """보표 중간선(B4, y=120) 위는 Voice 1 (Soprano)."""
    assert assign_voice(_det(y=105), _staff()) == 1

def test_lower_half_is_voice2():
    """보표 중간선 아래는 Voice 2 (Alto)."""
    assert assign_voice(_det(y=135), _staff()) == 2
