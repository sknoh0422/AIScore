import pytest
from pathlib import Path
from app.stages.omr.audiveris_adapter import AudiverisAdapter
from app.core.errors import OmrError

def test_missing_image_raises(tmp_path):
    with pytest.raises(OmrError):
        AudiverisAdapter(work_dir=tmp_path).recognize(tmp_path / "nope.png")

@pytest.mark.integration
def test_recognize_315_produces_mxl(tmp_path):
    img = Path(__file__).parents[2] / "score_images" / "315.JPG"
    out = AudiverisAdapter(work_dir=tmp_path).recognize(img)
    assert out.exists() and out.suffix == ".mxl"
