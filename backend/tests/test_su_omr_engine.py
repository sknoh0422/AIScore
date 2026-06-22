"""Test suite for YOLOv8 OMR Engine."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.stages.omr.omr_engine import OmrEngine, OmrModelNotFoundError
from app.stages.omr.types import RawDetection, BBox


def test_omr_engine_raises_if_no_model(tmp_path):
    """모델 파일 없으면 OmrModelNotFoundError."""
    with pytest.raises(OmrModelNotFoundError):
        OmrEngine(model_path=tmp_path / "nonexistent.pt")


def test_omr_engine_detect_returns_list(tmp_path):
    """detect()는 RawDetection 목록을 반환한다 (모델 mocking)."""
    fake_model_path = tmp_path / "fake.pt"
    fake_model_path.touch()

    mock_result = MagicMock()
    mock_box = MagicMock()
    mock_box.xyxy = [[10, 20, 60, 50]]
    mock_box.conf = [0.95]
    mock_box.cls = [0]
    mock_result.boxes = mock_box
    mock_result.names = {0: "notehead_filled"}

    with patch("app.stages.omr.omr_engine.YOLO") as MockYOLO:
        MockYOLO.return_value.return_value = [mock_result]
        engine = OmrEngine(model_path=fake_model_path)
        dummy_img = tmp_path / "img.png"
        dummy_img.touch()
        detections = engine.detect(dummy_img)

    assert isinstance(detections, list)
    assert all(isinstance(d, RawDetection) for d in detections)


def test_raw_detection_fields(tmp_path):
    """RawDetection 필드 검증."""
    fake_model_path = tmp_path / "fake.pt"
    fake_model_path.touch()

    mock_result = MagicMock()
    mock_box = MagicMock()
    mock_box.xyxy = [[10, 20, 60, 50]]
    mock_box.conf = [0.9]
    mock_box.cls = [0]
    mock_result.boxes = mock_box
    mock_result.names = {0: "notehead_filled"}

    with patch("app.stages.omr.omr_engine.YOLO") as MockYOLO:
        MockYOLO.return_value.return_value = [mock_result]
        engine = OmrEngine(model_path=fake_model_path)
        dummy_img = tmp_path / "img.png"
        dummy_img.touch()
        detections = engine.detect(dummy_img)

    d = detections[0]
    assert d.class_name == "notehead_filled"
    assert 0.0 <= d.confidence <= 1.0
    assert isinstance(d.bbox, BBox)
