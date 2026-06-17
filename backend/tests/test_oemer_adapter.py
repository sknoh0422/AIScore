import pytest
from pathlib import Path
from app.stages.omr.oemer_adapter import OemerAdapter
from app.core.errors import OmrError

def test_missing_image_raises(tmp_path):
    with pytest.raises(OmrError):
        OemerAdapter().recognize(tmp_path / "nope.png")

@pytest.mark.integration
def test_recognize_sample_produces_musicxml():
    img = Path(__file__).parents[2] / "score_images" / "온맘다해.png"
    out = OemerAdapter().recognize(img)
    assert out.exists() and out.suffix == ".musicxml"
