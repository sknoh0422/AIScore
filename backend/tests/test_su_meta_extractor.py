import numpy as np
from app.stages.omr.types import BBox, LayoutResult, RawDetection, StaffSystem
from app.stages.omr.meta_extractor import extract_meta, accidentals_to_key


def _empty_layout(h=1200, w=900):
    return LayoutResult(
        image_h=h, image_w=w,
        title_region=BBox(0, 0, w, 100),
        tempo_region=BBox(0, 80, 200, 30),
        staff_systems=[StaffSystem(BBox(0,120,w,60), [130,140,150,160,170], "treble")],
        lyric_regions=[BBox(0, 800, w, 200)],
    )

def test_key_one_sharp():
    assert accidentals_to_key(1, "sharp") == "G major"

def test_key_two_sharps():
    assert accidentals_to_key(2, "sharp") == "D major"

def test_key_one_flat():
    assert accidentals_to_key(1, "flat") == "F major"

def test_key_zero():
    assert accidentals_to_key(0, "sharp") == "C major"

def test_extract_meta_returns_score_meta():
    layout = _empty_layout()
    detections = [
        RawDetection(BBox(50, 125, 20, 20), "key_sig_sharp", 0.9),
    ]
    gray = np.full((1200, 900), 230, dtype=np.uint8)
    meta = extract_meta(layout, detections, gray)
    assert meta.key == "G major"
    assert meta.time_num > 0

def test_extract_meta_time_signature():
    layout = _empty_layout()
    detections = [
        RawDetection(BBox(80, 125, 15, 15), "time_sig_num", 0.9),
        RawDetection(BBox(80, 142, 15, 15), "time_sig_num", 0.9),
    ]
    gray = np.full((1200, 900), 230, dtype=np.uint8)
    meta = extract_meta(layout, detections, gray)
    assert meta.time_num in (2, 3, 4, 6)
