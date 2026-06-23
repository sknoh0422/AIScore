import pytest
from pathlib import Path

PNG_DIR = Path("score_images/png")
XML_DIR = Path("score_images/xml/분리")
SAMPLE_XML = XML_DIR / "새찬송가_001 만복의근원하나님.xml"


def test_parse_xml_returns_required_keys():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    assert "hymn_id" in result
    assert "measures" in result
    assert len(result["measures"]) > 0


def test_parse_xml_measure_has_four_voices():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    m = result["measures"][0]
    for voice in ("S", "A", "T", "B"):
        assert voice in m, f"voice {voice} missing"


def test_parse_xml_note_has_required_fields():
    from training.scripts.data_prep import parse_xml
    result = parse_xml(SAMPLE_XML)
    # measure 0은 전주(쉼표)일 수 있으니 첫 음표가 있는 마디 탐색
    note = None
    for m in result["measures"]:
        for v in ("S", "A", "T", "B"):
            if m[v]:
                note = m[v][0]
                break
        if note:
            break
    assert note is not None
    for field in ("pitch", "duration", "tie_start", "tie_end"):
        assert field in note, f"field {field} missing"


def test_split_dataset_ratios():
    from training.scripts.data_prep import split_dataset
    items = [{"hymn_id": str(i)} for i in range(100)]
    splits = split_dataset(items, seed=42)
    assert "train" in splits and "val" in splits and "test" in splits
    total = len(splits["train"]) + len(splits["val"]) + len(splits["test"])
    assert total == 100
    assert 75 <= len(splits["train"]) <= 82  # ~80%
