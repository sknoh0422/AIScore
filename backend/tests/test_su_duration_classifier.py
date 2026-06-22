from app.stages.omr.types import BBox, RawDetection
from app.stages.omr.duration_classifier import classify_duration

def _det(cls: str, x=100, y=100, w=20, h=20) -> RawDetection:
    return RawDetection(bbox=BBox(x, y, w, h), class_name=cls, confidence=0.9)

def test_open_notehead_no_nearby_is_whole():
    ql, dotted = classify_duration(_det("notehead_open"), [])
    assert ql == 4.0
    assert dotted is False

def test_filled_notehead_no_flag_is_quarter():
    ql, dotted = classify_duration(_det("notehead_filled"), [])
    assert ql == 1.0

def test_filled_notehead_with_flag_is_eighth():
    flag = _det("flag_eighth", x=110, y=80, w=10, h=20)
    ql, _ = classify_duration(_det("notehead_filled"), [flag])
    assert ql == 0.5

def test_dotted_note():
    dot = _det("augmentation_dot", x=125, y=100, w=5, h=5)
    ql, dotted = classify_duration(_det("notehead_filled"), [dot])
    assert dotted is True

def test_rest_quarter_duration():
    ql, _ = classify_duration(_det("rest_quarter"), [])
    assert ql == 1.0

def test_rest_half_duration():
    ql, _ = classify_duration(_det("rest_half"), [])
    assert ql == 2.0
